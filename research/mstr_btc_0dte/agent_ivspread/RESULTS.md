# MSTR-vs-IBIT IV-spread long/cash rule — result (registered): FAILED all gates

Spec + gates: `PREREGISTRATION.md` (registered 2026-10-17T00:23:10, before any IV
was computed). Runner: `ivspread_study.py` once; book mechanics imported from
`../agent_mnav/mnav_core.py`. Outputs: `ivspread_results.json`,
`ivspread_series.csv`, `ivspread_table.txt`.

## Numbers

- Window: sessions 2024-11-19..2026-09-16 (456); IV available both sides on
  456/456 sessions (no gaps). Rule z-warm-up → evaluation window
  **2025-02-18..2026-09-16 (397 sessions)**; rule and benchmark evaluated on the
  same window.
- Spread S = IV30_mstr − IV30_ibit (vol points, decimal): mean **+0.305**
  (30.5 pts), median +0.280, min +0.05, max +1.48. (Level trend: ~+80..+145 pts
  at the Nov-2024 start decaying to ~+30 pts by Sep-2026 — MSTR's vol premium
  over IBIT compressed steadily.)
- Rule: stance long only **56/397 sessions (14.1%)**, 7 round trips,
  **net total −16.2%**, SR −0.636, maxDD −19.6%.
- Benchmark B&H same window: net total −61.5%, SR −0.451, maxDD −81.6%.
- Bootstrap base: P(SR diff > 0) = **0.419**, point diff −0.185
  [q05 −1.91, q95 +1.71]; stress P = 0.412.
- Gates: **G1 ✗** (SR below bench and P < 0.95), **G2 ✗** (P < 0.90),
  **G3 ✗** (net total < 0). **PASS = False.**

The rule did avoid the 2025H2–2026H1 MSTR crashes (halves: rule {−9.5%, +3.4%,
−10.4%, 0.0%} vs bench {+15.5%, −59.9%, −44.8%, +50.8%}), preserving capital
relative to holding (−16% vs −61%), but with negative absolute return and a
Sharpe below the benchmark's, it fails the family gates as registered.

## Validity checks (post-run, reported for the record)

- Measurement hand-verified on 2026-09-16: MSTR S=126.18, expiry 2026-10-16
  (dte 30), K=125; call print 10.30 → IV 67.6%, put 9.05 → 67.1% (session IV
  67.4%); IBIT S=43.04, K=43 → 38.2%. No unit or inversion error; IV levels
  are plausible ATM vols.
- Bootstrap anomaly: the stress (and possibly base) quantile rows can be NaN
  because a drawn 21-session block of rule returns can be exactly constant
  (cash), giving zero variance → NaN Sharpe per the family's `sharpe_ann`
  convention and `np.quantile` doing no NaN skipping. This affects reported
  quantiles only; P is computed from non-NaN diffs and the verdict does not
  depend on it.
- Descriptive z-quintile → next-session MSTR close return: q1 −0.16%, q2
  +0.12%, q3 +0.22%, q4 −0.31%, q5 −0.40% (n≈79–80 per bucket). The raw
  "cheap vol → positive drift" ordering does not appear; no monotonicity.

## Reading

The registered hypothesis (froth/capitulation asymmetry in MSTR's idiosyncratic
vol premium) is **not supported**. The biggest structural feature — a strongly
decaying spread level — means a fixed trailing z-lookback maps almost
everything into "normal or rich" territory as the premium compresses; long
exposure ended up sparse and poorly timed (chopped in the H1 periods, absent
for the H2 2026 rebound). Recorded as FAIL; no re-runs or variants on this
window (a detrended/ratio variant would be a post-viewing change and is
therefore closed with it). The IV measurement machinery (`iv_core.py`) is
validated and reusable by a *future* registration on data that does not exist
yet.
