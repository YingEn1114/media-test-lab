"""邮件发件箱：默认把邮件渲染成 .eml 落地 outbox/ 并写入 mails 表（模拟发送）。

本产品版本始终只落地，不因 SMTP 环境存在而外发。
"""
import json
import os
import re
import sqlite3
import time
import uuid
from email.message import EmailMessage
from email.utils import formatdate

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTBOX = os.path.join(ROOT, "outbox")
DB_PATH = os.getenv("ZG_DB", os.path.join(ROOT, "platform.db"))
os.makedirs(OUTBOX, exist_ok=True)

_CFG = None


def config():
    global _CFG
    if _CFG is None:
        path = os.path.join(ROOT, "pipeline_config.json")
        with open(path, encoding="utf-8") as f:
            _CFG = json.load(f)
    return _CFG


def init_mail_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS mails (
            id TEXT PRIMARY KEY,
            created REAL NOT NULL,
            to_addr TEXT NOT NULL,
            cc TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            pipeline_id TEXT,
            bug_id TEXT,
            eml TEXT,
            transport TEXT
        )"""
    )
    conn.commit()
    conn.close()


def _slug(s):
    return re.sub(r"[^a-zA-Z0-9]+", "-", s or "")[:40].strip("-") or "mail"


def _smtp_send(msg):
    import smtplib

    host = os.getenv("ZG_SMTP_HOST")
    port = int(os.getenv("ZG_SMTP_PORT", "465"))
    user = os.getenv("ZG_SMTP_USER", "")
    pwd = os.getenv("ZG_SMTP_PASS", "")
    use_tls = os.getenv("ZG_SMTP_TLS", "1").lower() in ("1", "true", "yes")
    if use_tls and port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as s:
            if user:
                s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            if use_tls:
                s.starttls()
            if user:
                s.login(user, pwd)
            s.send_message(msg)


def send(to, subject, body, cc=None, pipeline_id=None, bug_id=None):
    """发送（或落地）一封邮件，返回记录 dict。to/cc 可为字符串或列表。"""
    cfg = config()
    to_list = [to] if isinstance(to, str) else list(to or [])
    cc_list = [cc] if isinstance(cc, str) else list(cc or [])
    sender = cfg.get("from", "zg-qa-platform@local")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body)

    transport = "outbox"
    mid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    eml_name = f"{mid}-{_slug(subject)}.eml"
    eml_path = os.path.join(OUTBOX, eml_name)
    with open(eml_path, "w", encoding="utf-8") as f:
        f.write(msg.as_string())

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO mails(id,created,to_addr,cc,subject,body,pipeline_id,bug_id,eml,transport)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        (mid, time.time(), ", ".join(to_list), ", ".join(cc_list), subject, body,
         pipeline_id, bug_id, eml_name, transport),
    )
    conn.commit()
    conn.close()
    print(f"[mail/{transport}] -> {msg['To']} | {subject}", flush=True)
    return {"id": mid, "to": to_list, "cc": cc_list, "subject": subject,
            "eml": eml_name, "transport": transport}


def list_mails(limit=100, pipeline_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if pipeline_id:
        rows = conn.execute(
            "SELECT * FROM mails WHERE pipeline_id=? ORDER BY created DESC LIMIT ?",
            (pipeline_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM mails ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
