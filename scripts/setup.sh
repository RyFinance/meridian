#!/usr/bin/env bash
# One-time setup: Python env + dependencies + .env. Safe to re-run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
[[ -d .venv ]] || "$PYTHON" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; }
mkdir -p bot/state
echo "ready. start the desk:   scripts/desk.sh   (http://127.0.0.1:${MERIDIAN_PORT:-8420})"
echo "run one cycle now:       scripts/cycle.sh   (the first run downloads price history; a few minutes)"
echo "schedule it (macOS):     scripts/install_launchd.sh"
