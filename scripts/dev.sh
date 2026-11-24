#!/usr/bin/env bash
# Development mode: FastAPI with reload + Vite dev server.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  echo "Run ./scripts/start.sh once to create the environment." >&2
  exit 1
fi

PYTHONPATH=backend .venv/bin/python backend/run.py --reload --port 8000 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

cd frontend
if [ ! -d node_modules ]; then npm install --no-audit --no-fund; fi
npm run dev
