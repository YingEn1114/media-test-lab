import contextlib
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path


def uid():
    return str(uuid.uuid4())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Problem(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status
        super().__init__(message)


def require(condition, message, status=409):
    if not condition:
        raise Problem(message, status)


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.migrate()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextlib.contextmanager
    def tx(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self):
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            existing = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            has_schema = any(r[0] == "qa_schema_migrations" for r in existing)
            if existing and not has_schema:
                backup = self.path + ".pre-qa-v1.bak"
                if not os.path.exists(backup):
                    with sqlite3.connect(backup) as dest:
                        conn.backup(dest)
        with self.tx() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS qa_schema_migrations(version INTEGER PRIMARY KEY, applied REAL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS qa_objects(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS qa_kind ON qa_objects(kind,created)")
            conn.execute("""CREATE TABLE IF NOT EXISTS qa_users(
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1)""")
            if "email" not in {r[1] for r in conn.execute("PRAGMA table_info(qa_users)")}:
                conn.execute("ALTER TABLE qa_users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
            conn.execute("""CREATE TABLE IF NOT EXISTS qa_audit(
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
                object_id TEXT, created REAL NOT NULL, details TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS qa_runner_slot(
                slot INTEGER PRIMARY KEY CHECK(slot=1), run_id TEXT NOT NULL)""")
            slot_columns = {r[1] for r in conn.execute("PRAGMA table_info(qa_runner_slot)")}
            for column, declaration in (("pid", "INTEGER"), ("owner", "TEXT"), ("host", "TEXT")):
                if column not in slot_columns:
                    conn.execute(f"ALTER TABLE qa_runner_slot ADD COLUMN {column} {declaration}")
            conn.execute("INSERT OR IGNORE INTO qa_schema_migrations VALUES(1,?)", (time.time(),))
            conn.execute("INSERT OR IGNORE INTO qa_schema_migrations VALUES(2,?)", (time.time(),))
            conn.execute("INSERT OR IGNORE INTO qa_schema_migrations VALUES(3,?)", (time.time(),))

    def bootstrap(self):
        """Credentials are server-issued, never accepted as roles from the browser."""
        with self.tx() as conn:
            if conn.execute("SELECT 1 FROM qa_users").fetchone():
                return
            token = os.getenv("ZG_ADMIN_TOKEN") or secrets.token_urlsafe(32)
            if not os.getenv("ZG_ADMIN_TOKEN"):
                path = Path(self.path + ".admin-token")
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as output:
                    output.write(token)
                print(f"[qa] 本机管理员令牌文件：{path}", flush=True)
            conn.execute("INSERT INTO qa_users(id,name,role,token_hash,active) VALUES(?,?,?,?,1)",
                         (uid(), "本机管理员", "admin", digest(token)))

    def actor(self, token):
        with self.connect() as conn:
            row = conn.execute("SELECT id,name,role,email FROM qa_users WHERE token_hash=? AND active=1",
                               (digest(token),)).fetchone()
        require(row is not None, "需要有效的服务端签发令牌", 401)
        return dict(row)

    def get(self, conn, object_id, kind=None):
        row = conn.execute("SELECT kind,data FROM qa_objects WHERE id=?", (object_id,)).fetchone()
        require(row is not None and (not kind or row["kind"] == kind), "对象不存在", 404)
        return json.loads(row["data"])

    def list(self, conn, kind):
        return [json.loads(r[0]) for r in conn.execute(
            "SELECT data FROM qa_objects WHERE kind=? ORDER BY created DESC", (kind,))]

    def put(self, conn, kind, data):
        data.setdefault("id", uid())
        data.setdefault("created", time.time())
        data["updated"] = time.time()
        conn.execute("""INSERT INTO qa_objects VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated=excluded.updated""",
                     (data["id"], kind, json.dumps(data, ensure_ascii=False), data["created"], data["updated"]))
        return data

    def audit(self, conn, actor, action, object_id=None, details=None):
        conn.execute("INSERT INTO qa_audit VALUES(?,?,?,?,?,?)",
                     (uid(), actor["id"], action, object_id, time.time(),
                      json.dumps(details or {}, ensure_ascii=False)))
