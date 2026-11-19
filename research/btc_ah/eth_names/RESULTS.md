# ETH overnight move -> ETH-linked US stocks (agent: eth_names)

**Verdict: WEAK.** A small, same-direction ETH follow tilt in open→close returns. It does not clear a multiple-testing or decay bar, and the cleanest ETFs show nothing significant.

## What was tested
- Signal (decided 09:25 ET): m = ETH(09:25 bar open) / ETH(16:00 prev trading day bar open) − 1. Weekends included (Fri 16:00 → Mon 09:25).
- Entry = next bar after decision (09:30 open). Exits: 16:00 close (set1), 10:30 open (set2, first hour), 16:00 close after a 10:30 entry (set3).
- Rules: follow sign(m) or fade sign(m) with |m| ≥ k (k ∈ {0, 0.5%, 1%, 2%}); residual-gap follow/fade with beta from the past N 60m-days only (N ∈ {60, 120}).
- Costs: 3 bp per side; 10 bp per side when entry price < $5 (per the question's rule).
- Dev = first 60% of each name's calendar for that family; check = remainder.
- **Variant count: 184 name-level rule variants**: set1 daily 72 (9 names × 4 k × 2 sides), set2 60m first-hour 80 (10 × 4 × 2), set3 residual 32 (N=60: 10×2 = 20 variants; N=120: 6×2 = 12 variants). Pooled-across-names rows are diagnostic only, not in the search.

## Data and hygiene
- ETH: Coinbase ETH-USD 5m candles, 2017-01-01 to 16:00 ET 2026-08-10 (sealed; nothing requested or kept after that).
- Stocks: yfinance daily (full history) and 60m (2024-10-21 to 2026-08-07). Holdout filter applied at load.
- ETHZ is not on yfinance, so it is dropped (10 names left).
- yfinance daily and 60m series disagree in scale for some names (GAME 60m ≈ 0.13× daily; ETHA 60m ≈ 0.33× daily). Each rule therefore uses a single series.
- BTCS daily is corrupt (142 open→close moves > 30%, closes up to 2.1m) and is excluded from set1. Its first draft gave a spurious +1.6%/trade "edge".
- Other daily glitch days (any leg > 30%) dropped: SBET 58, GAME 48, BTBT 16, ETHE 8, other names < 5.
- Residual N=120 is nearly untestable: the 60m window leaves 7 calendar days for the beta warm-up, so per-name dev n ≤ 4 and check n ≤ 3. Those variants are in the universe count but never qualify for selection.

## Top 3 by dev t (dev n ≥ 30, dev mean > 0). All ETHE set1 follow; they are nested in k, so not independent
| rule (ETHE, daily open→close) | dev n | dev mean | dev t | check n | check mean | check t | check win | avg win / loss | flip (check) |
|---|---|---|---|---|---|---|---|---|---|
| follow, k=0.5% | 889 | +0.88% | 4.36 | 605 | +0.27% | 2.37 | 55.0% | +2.14% / −2.02% | −0.39% (t −3.4) |
| follow, k=1.0% | 757 | +0.93% | 4.35 | 483 | +0.33% | 2.53 | 55.1% | +2.24% / −2.01% | −0.45% (t −3.4) |
| follow, k=0 | 1071 | +0.75% | 4.16 | 716 | +0.20% | 1.81 | 55.0% | +2.08% / −2.10% | −0.32% (t −2.9) |

- Dev-to-check decay is about 70% (+0.88% → +0.27% for k=0.5%).
- Unconditional long open→close on ETHE: dev −0.46%, check −0.17%. The follow edge is not just drift.
- Flip control: the fade side loses money in check (−0.32% to −0.45%, t −2.9 to −3.4), so the signal is not drift.
- Per-year, ETHE follow k=0.5% (mean net): 2019 +0.74%, 2020 +2.11%, 2021 −0.13%, 2022 +0.39%, 2023 +1.17%, 2024 +0.38%, 2025 +0.14%, 2026 +0.24%. Flip per year is negative in 7 of 8 years. Dev is dominated by 2019–2020, when ETHE was a non-ETF trust; that regime may not be comparable to today.

## Other families (k=0, follow / fade; check-window means)
- **set1 daily open→close, follow:** positive check means for 8 of 9 names (BMNR +0.90% t 2.9; ETHU +0.34%; GAME +0.30%; ETHE +0.20%; ETHA +0.19%; SBET +0.19%; FETH +0.17%; COIN +0.18%; BTBT +0.03%). Fade is negative for nearly all names. Pooled ALL follow (diagnostic, overlapping names on the same days): dev +0.26% t 3.7, check +0.20% t 2.8. The t-stats overstate significance because names share the same ETH shock on the same days.
- **set2 first-hour exit (09:30→10:30):** dev means near zero for every name (|t| < 1 for most). Pooled check follow rises with k (k=2%: +0.64%, t 6.4) while dev falls (−0.05%). A check-window-only effect that dev did not show is not usable.
- **set3 residual gap (60-day beta, 10:30→close):** pooled follow/fade near zero (dev t −2.0 to +0.4; check t −2.2 to +0.7). Single names have |t| < 2.9 with no consistent sign. ETHU fade and FETH fade reach dev t 2.4 but do not hold in the check window; they are not top-3 candidates.
- **ETH ETFs (ETHA, FETH, ETHU) are the cleanest test of ETH→stock lag and show nothing significant:** ETHA follow dev t 1.36 / check t 1.05; FETH 1.44 / 0.96; ETHU 1.60 / 0.94.

## Read
- Real but weak: follow beats fade and the flip loses money, so this is not drift. Net per trade is about +0.2–0.3% in check for the k=0 variant, against 6 bp round-trip costs.
- Not robust: dev-to-check decay of about 70%, one name carries the top ranks, the ETFs do not confirm it, and set2 and set3 show nothing.
- Multiple testing: 184 variants, and only 8 pass the dev filter. 23 variants show check t > 2, but follow/fade come in mirror pairs and the k thresholds are nested, so these are not independent hits. About 4 of 184 would clear |t| > 2 by chance on a two-sided test.
- Suggested next step, not done here: a forward test on ETHE, sized small, with a 2026-08-10 → later holdout the lead controls.

Files: `analysis.py` (final), `fetch_eth.py`, `fetch_stocks.py`, `variants.csv` (all 184 + pooled + baselines), `trades.parquet`, `data/` (ETH 5m, stock 1d/60m, all ≤ 2026-08-10).
