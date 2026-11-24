#!/usr/bin/env bash
# One-command local start.
#   ./scripts/start.sh          -> http://<laptop-ip>:8000
#   ./scripts/start.sh --ssl    -> https://<laptop-ip>:8443 (phone camera)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  echo "Creating Python virtual environment…"
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r backend/requirements.txt
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "Building the frontend…"
  if [ ! -d frontend/node_modules ]; then
    (cd frontend && npm install --no-audit --no-fund)
  fi
  (cd frontend && npm run build)
fi

ARGS=(--host 0.0.0.0 --port "${PORT:-8000}")
if [ "${1:-}" = "--ssl" ]; then
  if [ ! -f certs/server.crt ] || [ ! -f certs/server.key ]; then
    ./scripts/generate_cert.sh
  fi
  ARGS=(--host 0.0.0.0 --port "${PORT:-8443}" --ssl)
fi

exec .venv/bin/python backend/run.py "${ARGS[@]}"
