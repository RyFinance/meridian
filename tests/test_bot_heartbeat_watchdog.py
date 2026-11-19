"""Tests for bot/heartbeat.py and bot/watchdog.py (the dead-man's-switch).
Time manipulation uses real file mtimes (os.utime) rather than mocking
time.time() globally -- exercises the actual staleness-detection code path.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from bot.alerting import ALERT_DEAD_MANS_SWITCH, BotAlerter
from bot.heartbeat import read_heartbeat_age_seconds, read_heartbeat_timestamp, touch_heartbeat
from bot.watchdog import check_dead_mans_switch


def test_module_global_reassignment_redirects_bare_calls(tmp_path, monkeypatch):
    """Regression test for a real bug found 2026-08-19: touch_heartbeat's
    signature used to be `path: Path = HEARTBEAT_FILE` -- a def-time-bound
    default that a later `bot.heartbeat.HEARTBEAT_FILE = other_path`
    reassignment would NOT actually redirect. Confirms a caller that
    reassigns the module global and then calls touch_heartbeat() with NO
    arguments (exactly how bot/run_cycle.py calls it) is correctly
    redirected."""
    import bot.heartbeat as hb_module
    redirected = tmp_path / "redirected_heartbeat.txt"
    monkeypatch.setattr(hb_module, "HEARTBEAT_FILE", redirected)

    hb_module.touch_heartbeat()  # bare call, no path argument -- must use the reassigned global
    assert redirected.exists()
    assert hb_module.read_heartbeat_age_seconds() < 2.0
    assert hb_module.read_heartbeat_timestamp() is not None


def test_touch_heartbeat_creates_fresh_file(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    touch_heartbeat(hb)
    assert hb.exists()
    assert read_heartbeat_age_seconds(hb) < 2.0


def test_missing_heartbeat_is_infinitely_stale(tmp_path):
    assert read_heartbeat_age_seconds(tmp_path / "nope.txt") == float("inf")


def test_read_heartbeat_timestamp_roundtrip(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    before = time.time()
    touch_heartbeat(hb)
    ts = read_heartbeat_timestamp(hb)
    assert ts is not None
    assert abs(ts - before) < 2.0


def _beat_at(hb, when: datetime):
    """Write the heartbeat and back-date its mtime to `when` (naive = local)."""
    touch_heartbeat(hb)
    ts = when.timestamp()
    os.utime(hb, (ts, ts))


def _check(hb, now, tmp_path, **kw):
    alerts_path = tmp_path / "alerts.jsonl"
    fired = check_dead_mans_switch(max_age_hours=kw.pop("max_age_hours", 26), now=now, heartbeat_path=hb,
                                   alerter=BotAlerter(alerts_path=alerts_path))
    return fired, alerts_path


def test_watchdog_silent_when_heartbeat_fresh(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    monday = datetime(2026, 8, 17, 12, 0, 0)  # a real Monday
    _beat_at(hb, monday - timedelta(minutes=5))
    fired, _ = _check(hb, monday, tmp_path)
    assert fired is False


def test_watchdog_fires_on_stale_heartbeat_on_weekday(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    wednesday = datetime(2026, 8, 19, 12, 0, 0)
    _beat_at(hb, wednesday - timedelta(hours=30))  # simulates a real crash gap, all on session days
    fired, alerts_path = _check(hb, wednesday, tmp_path)

    assert fired is True
    lines = alerts_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["kind"] == ALERT_DEAD_MANS_SWITCH
    assert record["age_hours"] > 26


def test_watchdog_fires_on_missing_heartbeat_on_weekday(tmp_path):
    hb = tmp_path / "never_written.txt"
    monday = datetime(2026, 8, 17, 12, 0, 0)
    fired, _ = _check(hb, monday, tmp_path)
    assert fired is True


def test_watchdog_silent_on_weekend_even_if_stale(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    saturday = datetime(2026, 8, 15, 12, 0, 0)  # a real Saturday
    _beat_at(hb, saturday - timedelta(hours=100))  # very stale
    fired, _ = _check(hb, saturday, tmp_path)
    assert fired is False


def test_watchdog_respects_custom_threshold(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    monday = datetime(2026, 8, 17, 12, 0, 0)
    _beat_at(hb, monday - timedelta(seconds=10))
    fired, _ = _check(hb, monday, tmp_path, max_age_hours=0.001)  # ~3.6s threshold
    assert fired is True


# --- session-aware staleness: weekends / NYSE holidays don't count -----------
# Cycle times below mirror the real schedule (launchd 15:42 local; the Fri
# Oct 16 2026 heartbeat landed 19:12) and the watchdog's 4-hourly checks.

def test_fri_to_mon_gap_does_not_alert(tmp_path):
    """The exact false alarm in bot_alerts.jsonl: Fri Oct 16 heartbeat, Monday
    Oct 19 checks before that day's cycle (53.4h .. 67.7h wall clock)."""
    hb = tmp_path / "heartbeat.txt"
    _beat_at(hb, datetime(2026, 10, 16, 19, 12, 48))
    for hour, minute in [(0, 37), (4, 37), (8, 37), (14, 52)]:
        fired, alerts_path = _check(hb, datetime(2026, 10, 19, hour, minute), tmp_path)
        assert fired is False, (hour, minute)
    assert not alerts_path.exists()


def test_missed_tuesday_cycle_alerts(tmp_path):
    """Mon cycle ran, Tue's never did: the first Wednesday check alerts."""
    hb = tmp_path / "heartbeat.txt"
    _beat_at(hb, datetime(2026, 10, 19, 15, 44))  # Monday's cycle
    fired, _ = _check(hb, datetime(2026, 10, 20, 14, 0), tmp_path)  # Tue, before its cycle
    assert fired is False
    fired, alerts_path = _check(hb, datetime(2026, 10, 21, 0, 37), tmp_path)  # Wed, Tue's cycle missed
    assert fired is True
    assert json.loads(alerts_path.read_text().strip().splitlines()[-1])["age_hours"] > 26


def test_holiday_monday_is_not_counted(tmp_path):
    """Labor Day (Mon Sep 7 2026, NYSE closed): Fri heartbeat is still fine
    through Tue's pre-cycle check; a missed Tue cycle then alerts on Wed."""
    hb = tmp_path / "heartbeat.txt"
    _beat_at(hb, datetime(2026, 9, 4, 15, 44))  # Friday's cycle
    fired, _ = _check(hb, datetime(2026, 9, 7, 12, 0), tmp_path)  # the holiday itself
    assert fired is False
    fired, _ = _check(hb, datetime(2026, 9, 8, 14, 0), tmp_path)  # Tue, before its cycle (~94h wall clock)
    assert fired is False
    fired, _ = _check(hb, datetime(2026, 9, 9, 4, 0), tmp_path)  # Wed, Tue's cycle missed
    assert fired is True
