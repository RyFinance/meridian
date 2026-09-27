# Forward evidence actions, research cycle 4 (2026-09-24, director session)

Research logging only. No order, trade or broker action. Nothing backfilled.

## Checks before recording (2026-09-24 21:57 PDT = 2026-09-25 00:57 ET)

- **Chain:** `research.forward.verify` → OK, 3 records, head seq 2 `0f2c2c1d…`. No anchors have been recorded yet; anchoring is the user's action.
- **Frozen spec:** `research/forward_audit/tsy_month_end_v1_spec.json`.
  - Recomputed `registry.spec_hash` = `90924b12…`, equal to the registered seq-2 spec hash.
  - The registered payload equals the file.
- **Frozen code:** `research/tsy_month_end/core.py` `481cb112…` and `evaluate.py` `397a81e0…`, both equal to the spec.
- **Calendar (`research.forward.nyse`):**
  - September 2026: 4th-to-last session 2026-09-25, last 2026-09-30.
  - October: 10-27 and 10-30.
  - First session of October: 10-01.
- **Official close availability:**
  - TLT 2026-09-24 close 79.42 from the LSE 30-minute regular-session rebuild; the yfinance official close is 79.42 (difference 0.0002 bp).
  - No data flags.

## Recorded

| seq | strategy | decision_key | targets | market_asof | intended execution | recorded_at_utc |
|---|---|---|---|---|---|---|
| 3 | tsy_month_end_v1 | 2026-09-25 | {"TLT": 1.0} | 2026-09-24 (final) | 2026-09-25 20:00Z (close) | 2026-09-25T04:58:19Z |

After recording, `verify` → OK, 4 records. **New head: seq 3 `04dff2c7b64c5705392fc664de612b78fb8c331310cc96e2a1d7dc42f7d7cc9d`.**

## Prepared, not recorded

- **tsy_month_end_v1 exit.**
  - Command:
    `PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy tsy_month_end_v1 --date 2026-09-30 --targets '{"TLT": 0.0}'`
  - A dry run is valid (market_asof 2026-09-29; execution 2026-09-30 20:00Z).
  - **Operating rule:** record only after the 2026-09-29 close is final (after 20:15Z on 9-29) and before 20:00Z on 9-30.
  - **Adapter gap:** the adapter does not refuse an early exit record for `execution: close` specs. The evaluator would exclude a decision whose market_asof was not final when it was recorded, so early recording must be avoided by the operator.
- **momentum_gold_v1.**
  - Command:
    `PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy momentum_gold_v1 --date 2026-10-01`
  - A dry run now is correctly REFUSED: "too early: this decision uses data final at 2026-10-01T20:15:00Z".
  - Record in the window from 2026-10-01 20:15Z to 2026-10-02 13:30Z (next open).
- **Anchoring (user):** anchor head seq 3 `04dff2c7…` externally now (git push or email), and again after each record.
