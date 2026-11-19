# BTC overnight volatility -> MSTR option straddle / iron-fly (vol_straddle)

Question: does overnight BTC volatility predict whether MSTR's 09:31 ATM option prices are under- or over-priced
versus the realized move after the open? Rule: signal true -> buy ATM straddle; signal false -> sell iron fly.

## What was tested
- Sample: engine.prepare('dev') Mon/Fri sessions, kept to <= 2023-12-31. 273 sessions have option data (from 2020-11-16).
  DEV = 128 sessions <= 2022-06-30; CHECK = 145 sessions 2022-07-01..2023-12-31.
- Entry: first minute 09:31-09:35 where ATM call and put (and iron-fly wings) print in the same minute. ATM = nearest strike to parity spot.
- Exits: time only, 10:30, 12:00, 15:55. No targets or stops.
- Iron fly: short ATM straddle, long wings at spot x (1 +/- 5%), max risk = wider wing - net credit.
- Costs: half-spread max($0.03, 2.5%) per leg per side; $0.65/contract/side.
- Overnight features use BTC 1m bars stamped <= 09:28 ET, window 16:00 prior weekday -> 09:29 ET. Corr with daily_panel btc_off = 0.98.
- Signals (pre-registered before any result): S1 range/|net| >= dev median (2.36); S2 RV z vs prior 20 nights >= 1;
  S3 RV / median of prior 20 nights >= 1.5; S4 late share (|08:00->09:29| / total |move|) > 0.5; S5 Monday (weekend night).

**Variant count: 15 primary rules (5 signals x 3 exits) plus their 15 exact flips = 30.** Fills: base only (worst-fill not run; see limits).

## Results (pooled trades; return on premium for straddle, on max risk for fly)
Pooled dev mean, all 30 dev cells:
| | dev mean | dev t | check mean | check t |
|---|---|---|---|---|
| Best primary S5 Mon, exit 15:55 | -0.027 | -0.5 | -0.161 | -4.2 |
| Best primary S5 Mon, exit 12:00 | -0.028 | -0.7 | -0.121 | -4.0 |
| Best primary S2 RVz, exit 12:00 | -0.057 | -1.2 | -0.170 | -4.3 |
| Best flip (S3 RV ratio, 12:00) | -0.132 | -2.9 | -0.018 | -0.5 |
| Unconditional long straddle 10:30 (control) | -0.042 | -1.2 | -0.067 | -3.2 |
| Unconditional short iron fly 10:30 (control) | -0.239 | -4.2 | -0.141 | -5.1 |

Pooled dev mean > 0 in **0 of 30** dev cells. Pooled check mean > 0 in **0 of 30** check cells.
Win rates 25-53%; avg loss usually 2-3x avg win for the straddle legs.

Zero-cost diagnostic (dev+check, gross, no spread or commission; not used for selection):
long straddle gross means -0.07 to +0.05 with |t| < 1.6; fly gross dev mean up to +0.59 (t 1.0) but check mean -0.08 to +0.05.
So even before costs there is no stable signal in either direction.

## Best rules, written precisely
- Best primary by dev mean: IF Monday (S5) THEN buy ATM straddle at first same-minute print in 09:31-09:35, sell at 15:55 (ffill last print);
  ELSE sell iron fly (wings +/-5%) at the same entry, buy back at 15:55.
  Dev: n 68, mean -0.027, t -0.5. Check: n 117, mean -0.161, t -4.2. FAIL.
- Best primary with S2 (RV z >= 1): exit 12:00. Dev mean -0.057 (n 66), check mean -0.170 (n 116). FAIL.
- Flip control: for S3 at 12:00 the flip (sell straddle on high-RV nights) has dev mean -0.132, check -0.018. Flips are also negative, so the signal is not a sign-flip edge either.

## Gate and verdict
Pre-registered gate: dev pooled mean > 0, t >= 2.0, flip mean < 0; check pooled mean > 0 and t >= 1.0.
No cell passes the dev gate, so **no rule was taken to the 2024+ validation.** val_days_full.pkl was not opened, and no 2024+ result was computed.

**Verdict: NONE.** Overnight BTC volatility does not separate under- from over-priced MSTR ATM straddles at the open.
Costs make unconditional straddles and flies lose (-4% to -24% per trade), and the signal adds nothing on top.

## Limits and honesty notes
- Small sample (about 130 dev and 145 check sessions). Power to detect a 5-10% per-trade edge is low, so "NONE" means no evidence for an edge, not proof of none.
- Worst-fill (bar high/low) stress was not run because nothing passed the base gate.
- Exit prices use the last print at or before the exit minute (stale prints possible on thin strikes).
- Data handling: engine.prepare('dev') reads the option chunk that also holds some 2024 rows, then filters to < 2024 inside the engine. Only dev-period rows were used. BTC loaded < 2024-01-01 only. Nothing after 2026-08-10 was loaded.
- Files: features.py, trades.py, run_dev.py, gross_diag.py, dev_check_results.csv, night_features_dev.parquet, dev_days_vol.pkl (in research/btc_ah/vol_straddle/).
