"""Dead-man's-switch: the "one layer up" check bot/PLAN.md flagged as
"not built -- no running process exists to watch yet." Now that
run_cycle.py is scheduled to run unattended (launchd, independent of any
chat session), THIS is what watches it: if no cycle has completed
successfully within `max_age_hours` on a trading weekday, something is
wrong (crash, machine asleep/off, the scheduler itself broken) and nobody
would otherwise notice -- the exact class of silent failure the stale
`get_earnings_dates()` endpoint bug was, one level down the stack.

Deliberately its own separate, more-frequently-scheduled job (see
bot/PLAN.md's launchd notes) rather than a check run_cycle.py performs on
itself -- a process that has crashed cannot be relied on to notice its own
absence.

SESSION-AWARE STALENESS (2026-10-19): the threshold used to be compared with
raw wall-clock age, so every Monday's pre-cycle checks saw Friday's heartbeat
as 53-71h old and fired (bot_alerts.jsonl, every week since August). The age
compared with `max_age_hours` now excludes NYSE non-session days (weekends
and full holidays, from research/forward/nyse.py) on the ET calendar, so a
Fri->Mon or Fri->Tue-after-holiday-Monday gap is ~1 trading day old, while a
genuinely missed session still pushes the age past 26h.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from bot.alerting import ALERT_DEAD_MANS_SWITCH, BotAlerter, build_alerter
from bot.heartbeat import HEARTBEAT_FILE, read_heartbeat_timestamp
from research.forward.nyse import ET, is_session

DEFAULT_MAX_AGE_HOURS = 26.0


def _is_trading_day(now: datetime) -> bool:
    return is_session(now.astimezone(ET).date())


def _session_age_seconds(last: datetime, now: datetime) -> float:
    """Seconds between `last` and `now` (both tz-aware), not counting time
    that falls on ET calendar days that are not NYSE sessions."""
    total = 0.0
    cursor = last.astimezone(ET)
    end = now.astimezone(ET)
    while cursor < end:
        next_midnight = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), tzinfo=ET)
        segment_end = min(next_midnight, end)
        if is_session(cursor.date()):
            total += (segment_end - cursor).total_seconds()
        cursor = segment_end
    return total


def check_dead_mans_switch(
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    now: datetime | None = None,
    heartbeat_path=HEARTBEAT_FILE,
    alerter: BotAlerter | None = None,
) -> bool:
    """Returns True iff the switch fired (alert was written). Only
    evaluates on NYSE session days -- the cycle only trades on those, so a
    stale heartbeat on a weekend or holiday is expected, not a failure.

    `max_age_hours` is measured in session-day hours (see module docstring),
    not wall-clock hours. A naive `now` is local time."""
    now = (now or datetime.now()).astimezone()
    if not _is_trading_day(now):
        return False

    alerter = alerter or build_alerter()
    try:
        last_beat = datetime.fromtimestamp(heartbeat_path.stat().st_mtime).astimezone()
        age_hours = _session_age_seconds(last_beat, now) / 3600.0
    except OSError:
        age_hours = float("inf")
    if age_hours <= max_age_hours:
        return False

    last_ts = read_heartbeat_timestamp(heartbeat_path)
    last_seen = datetime.fromtimestamp(last_ts).isoformat() if last_ts is not None else "never"
    alerter.alert(
        ALERT_DEAD_MANS_SWITCH,
        f"no successful paper-trading cycle in {age_hours:.1f} session-hours (threshold {max_age_hours}h) -- "
        f"last heartbeat: {last_seen}",
        age_hours=round(age_hours, 2), last_heartbeat=last_seen,
    )
    return True


if __name__ == "__main__":
    fired = check_dead_mans_switch()
    print("ALERT FIRED" if fired else "heartbeat OK")
