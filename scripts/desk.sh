#!/usr/bin/env bash
# Start the desk in the foreground: http://127.0.0.1:${MERIDIAN_PORT:-8420}
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT_FROM_SHELL="${MERIDIAN_PORT:-}"
set -a; [[ -f .env ]] && . ./.env; set +a
MERIDIAN_PORT="${PORT_FROM_SHELL:-${MERIDIAN_PORT:-8420}}"
exec env PYTHONPATH="$ROOT" .venv/bin/python -m uvicorn live_backtest.dashboard.backend:app \
  --host 127.0.0.1 --port "${MERIDIAN_PORT:-8420}"
