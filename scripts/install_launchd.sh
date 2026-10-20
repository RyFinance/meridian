#!/usr/bin/env bash
# macOS: schedule the trading cycle, the watchdog and the desk with launchd.
#   scripts/install_launchd.sh            install + load
#   scripts/install_launchd.sh --remove   unload + delete
# Cycle runs Mon-Fri at 16:20 New York time (after the close), converted to
# this Mac's local clock. The desk stays up at http://127.0.0.1:${MERIDIAN_PORT:-8420}.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${MERIDIAN_LAUNCHD_PREFIX:-com.meridian}"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/meridian"
PY="$ROOT/.venv/bin/python"
PORT="${MERIDIAN_PORT:-8420}"
JOBS=(pead_bot pead_watchdog desk)

if [[ "${1:-}" == "--remove" ]]; then
  for job in "${JOBS[@]}"; do
    launchctl bootout "gui/$(id -u)/$PREFIX.$job" 2>/dev/null || true
    rm -f "$AGENTS/$PREFIX.$job.plist"
  done
  echo "removed ${JOBS[*]}"; exit 0
fi

[[ -x "$PY" ]] || { echo "run scripts/setup.sh first"; exit 1; }
mkdir -p "$AGENTS" "$LOGS"
read -r HOUR MINUTE < <("$PY" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
ny = datetime.now(ZoneInfo("America/New_York")).replace(hour=16, minute=20, second=0, microsecond=0)
local = ny.astimezone()
print(local.hour, local.minute)
PY
)

calendar() {
  for day in 1 2 3 4 5; do
    printf '<dict><key>Weekday</key><integer>%s</integer><key>Hour</key><integer>%s</integer><key>Minute</key><integer>%s</integer></dict>' "$day" "$HOUR" "$MINUTE"
  done
}

plist() { # label, program args xml, extra xml
  cat > "$AGENTS/$1.plist" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key><array>$2</array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>$ROOT</string><key>MERIDIAN_LAUNCHD_PREFIX</key><string>$PREFIX</string></dict>
  <key>StandardOutPath</key><string>$LOGS/${1##*.}.log</string>
  <key>StandardErrorPath</key><string>$LOGS/${1##*.}.log</string>
  $3
</dict></plist>
XML
}

plist "$PREFIX.pead_bot" "<string>$PY</string><string>-m</string><string>bot.run_cycle</string>" \
  "<key>RunAtLoad</key><true/><key>StartCalendarInterval</key><array>$(calendar)</array>"
plist "$PREFIX.pead_watchdog" "<string>$PY</string><string>-m</string><string>bot.watchdog</string>" \
  "<key>StartInterval</key><integer>14400</integer>"
plist "$PREFIX.desk" "<string>$PY</string><string>-m</string><string>uvicorn</string><string>live_backtest.dashboard.backend:app</string><string>--host</string><string>127.0.0.1</string><string>--port</string><string>$PORT</string>" \
  "<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>"

for job in "${JOBS[@]}"; do
  launchctl bootout "gui/$(id -u)/$PREFIX.$job" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/$PREFIX.$job.plist"
done
echo "installed: cycle Mon-Fri $(printf '%02d:%02d' "$HOUR" "$MINUTE") local (16:20 New York), watchdog every 4h, desk on :$PORT"
echo "logs: $LOGS"
