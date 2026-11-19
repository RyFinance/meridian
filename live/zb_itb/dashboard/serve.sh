#!/usr/bin/env bash
# ZB -> ITB canvas desk launcher.
#   Usage:  live/zb_itb/dashboard/serve.sh          -> http://localhost:8502
#           PORT=8503 live/zb_itb/dashboard/serve.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."
exec env PYTHONPATH=. .venv/bin/python -m live.zb_itb.dashboard.server
