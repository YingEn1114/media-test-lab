#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# 默认只允许本机访问；LAN 共享时用 ZG_HOST=0.0.0.0
HOST="${ZG_HOST:-127.0.0.1}"
PORT="${ZG_PORT:-8090}"

# 可选访问控制：ZG_AUTH=user:password
exec .venv/bin/uvicorn app:app --host "$HOST" --port "$PORT"
