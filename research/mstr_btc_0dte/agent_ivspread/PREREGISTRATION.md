# Pre-registration: MSTR vs IBIT implied-volatility spread timing (agent_ivspread)

Registered BEFORE the first IV, spread, or return value was computed (only
data-availability recon was done; see Disclosure). One-shot study; research
only; never submits orders.

## Hypothesis (fixed before data)

`S_t = IV30_mstr(t) − IV30_ibit(t)` (vol points) measures MSTR's *idiosyncratic*
volatility premium over plain spot-BTC vol. The directional prior: the low tail
of `S_t` (MSTR options unusually cheap relative to IBIT options — capitulation /
despair in the MSTR complex) is followed by positive MSTR drift, while ordinary
and high levels carry no such information. Rule (long-only, cash otherwise):

**Long MSTR when `z_t ≤ −1.0`; cash otherwise**, where `z_t` is the z-score of
`S_t` over a trailing 120-session window (min 60 valid observations, ddof=1).

Single threshold; no shorts (no borrow modeling); no leverage.

## Measurement spec (fixed)

- Window: sessions **2024-11-19 .. 2026-09-16** (entire IBIT options print
  history; both option files end 2026-09-16). There is no pre-2024 IBIT options
  history, so this study has **no clean development window**; it is one
  fully-precommitted shot on the only window that exists. Disclosed as weaker
  than a study with untouched holdout.
- IV30 per instrument per session:
  - eligible expiries: dte ∈ [20, 45] calendar days; chosen = min |dte − 30|,
    ties → earlier expiry;
  - chosen strike: among that expiry's printed contracts, strike nearest the
    session close `S`; require |K/S − 1| ≤ 0.10;
  - per-contract IV: Black–Scholes European (r = 0, q = 0) inverted from the
    session's **close** print, σ ∈ [0.05, 5], require print > $0.005 and
    volume ≥ 1;
  - session IV = mean of the call and put IVs at the chosen strike; single side
    if only one is available (recon: rare); NaN if neither. If the chosen
    expiry/strike fails the filters there is NO fallback (deliberate: no hidden
    selection); NaN sessions carry the prior stance.
- Spots: MSTR close from `research/mstr_btc_0dte/mstr_daily_yf.parquet`; IBIT
  close from `data/ibit_daily_yf.parquet` (yfinance, fetched 2026-10-17).
- American early-exercise is ignored; with r = 0 and no dividends the
  European–American ATM gap is negligible. Close prints (not quotes) are used;
  both legs are measured identically so the spread inherits only differential
  print noise. Both limitations disclosed.

## Execution, costs, evaluation window

- Signal after close `t` → position at MSTR official open `t+1`; 100% MSTR or
  100% cash. NAV marked at each session's open, execution and forced final
  liquidation identical to `agent_mnav/mnav_core.py` (`simulate_long_only`),
  which this study imports so the book mechanics are the family's frozen ones.
- Costs: base 3 bp/side + $0.005/share; stress 6 bp/side + $0.010/share.
- Effective window: from the first z-valid session to 2026-09-16 (≈60-session
  warm-up; ≈396 sessions ≈ 19 months). Rule and benchmark are evaluated on
  this SAME effective window. B&H = long MSTR over it, same costs.

## Gates (mirror of the mNAV family gates; registered before any statistic)

- **G1**: base rule Sharpe > B&H Sharpe **and** stationary-block bootstrap
  P(SR_rule − SR_B&H > 0) ≥ **0.95** (21-session blocks, 2,000 draws, seed
  20260817, mNAV comparability).
- **G2**: same at stress costs with P ≥ 0.90.
- **G3**: rule net total return > 0.
- **PASS iff G1 ∧ G2 ∧ G3** → forward paper-test registration only, no capital.
- Power disclosure: at ≈400 sessions this bar needs an unusually large true
  Sharpe difference; a power failure (sign right, P low) will be recorded as
  FAIL exactly like the mNAV run. Near-misses do NOT authorize re-runs on this
  window; proactive-only monitoring needs its own separate registration.

## Reported-only (never substitutes)

Half-year splits, cost table, IV/spread descriptive stats, stance counts, z
bucket → next-session MSTR return table, and BTC context over the window.

## Disclosure of prior viewing

- The 2024-11+ window has been used by other hypotheses (mNAV, events);
  MSTR returns in it are broadly known. The IBIT IV series and the spread do
  not exist anywhere yet.
- Data-availability recon only (counts, tenors, moneyness coverage) was run on
  the option files before this registration; no IV was computed.
- Multiple-testing note: one other candidate (convertible/ATM issuance flow)
  remains queued and, if run, needs its own registration.

## Inputs and code (hashes recorded in preregistrations.jsonl)

- `data/lse/options_ibit_1d/IBIT.parquet` (pull manifest sha256), pulled
  2026-10-17 from the LSE vault, 593,325 rows.
- `data/lse/options_mstr/MSTR.parquet` (existing frozen panel).
- `data/ibit_daily_yf.parquet` (new daily closes; hash recorded).
- Code: `iv_core.py` (measurement), `ivspread_study.py` (runner), mechanism
  import from `../agent_mnav/mnav_core.py` (hash already registered).
