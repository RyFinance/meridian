#!/usr/bin/env bash
# Run one trading cycle now (it only trades after a completed NYSE session).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; [[ -f .env ]] && . ./.env; set +a
exec env PYTHONPATH="$ROOT" .venv/bin/python -m bot.run_cycle
