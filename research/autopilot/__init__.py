"""Rebalancing autopilot (cycle 9, item 3): deterministic, offline, research-only.

Turns (a menu portfolio config, a hand-edited holdings file, a snapshot-verified price file) into a
human-readable rebalancing report, a JSON summary and one hash-chained paper-log line.  See ``SPEC.md``.

Nothing here talks to a broker or the network, and nothing it prints is a recommendation to trade.
"""
from __future__ import annotations

SCHEMA_VERSION = "autopilot_v1"
