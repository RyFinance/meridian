# BTC off-hours move -> BTC-linked stock swing trades (agent: swing)

Question: after large BTC moves while US equities are closed (16:00 ET -> 09:25 ET), do BTC-linked stocks over- or under-shoot over the next 1-10 sessions?
Sealed holdout respected: all data filtered to <= 2026-08-10. Dev = signal dates <= 2023-06-30; check = 2023-07-01..2026-08-10.

## Setup
- Signal m_t = BTC close 09:25 ET on day t / BTC close 16:00 ET on prior session - 1 (1m UTC bars, last bar before target).
- Residual gap r_t = gap_t - beta_t * m_t, gap_t = adj open_t / adj close_{t-1} - 1, beta_t = OLS of past 250 sessions (min 120), lagged one day.
- Families: BTC (|m| > 3/5/8%), GAP (|r| > 3/5/8%). Entry at 09:30 open or 16:00 close; hold N = 1,2,3,5,10 sessions, exit at close.
- Directions: continuation (sign of signal) or reversal. Long-short per trade, shorts with no borrow cost.
- Costs: 3 bp per side; 10 bp per side if raw entry price < $5. Round trip charged.
- Non-overlap per ticker (next entry >= N sessions after last). t-stat uses date-clustered averages (mean of per-date means / SE).
- Universe "POOLED12" = MSTR MARA RIOT CLSK HUT CIFR WULF IREN COIN BTBT IBIT BITO. "MINER_BASKET" = equal weight of the 8 miners.
- Drift control: buy-and-hold (or short-and-hold) over ALL sessions in the same period and window, weighted by the rule's long/short mix. Excess = net mean - drift base.

## Variants tested
- Rule specs: 2 families x 3 thresholds x 2 entries x 5 holds x 2 directions = 120.
- Units: POOLED12, MINER_BASKET, and each of 12 tickers = 14 units -> 1,680 variants (diagnostics only for tickers).
- Dev selection pool: 240 (POOLED12 + MINER_BASKET). 82 passed n >= 30, mean > 0, excess > 0 on dev. Top 3 by dev t taken, nothing else.
- Multiple testing: 1,680 variants, so |t| > 2 is expected by chance in ~5% of them.

## Dev top 3 -> check (all selected by dev only)
| # | Rule (signal on day t, trade from t) | Dev n / mean / t / excess | Check n / mean / t / excess | Flip (opposite) check mean | Check win |
|---|---|---|---|---|---|
| A | gap \|r\| > 3%, open entry, hold 1, REVERSAL, POOLED12 | 822 / +1.12% / 2.62 / +1.22% | 861 / +0.06% / 0.94 / +0.14% | -0.26% (cont) | 52.7% |
| B | gap \|r\| > 8%, open entry, hold 1, REVERSAL, POOLED12 | 74 / +3.96% / 2.35 / +4.06% | 71 / -0.45% / 0.45* / -0.40% | +0.26% (cont) | 50.7% |
| C | gap \|r\| > 3%, close entry, hold 10, CONTINUATION, POOLED12 | 294 / +2.51% / 2.06 / +1.97% | 342 / -0.48% / 0.16* / -0.80% | +0.28% (rev) | 48.2% |

*Check t has a different sign from the check mean. That happens because t uses date-clustered averages and the mean is per trade.

Rule A check averages: win/loss +5.4% / -5.9%. Rule A per year, net mean: 2021 +1.04%, 2022 +1.23%, 2023 +1.21%, 2024 -0.29%, 2025 +0.19%, 2026 -0.53%.

Secondary (BTC-move signal, not among the 3 picks since the gap rules ranked higher on dev):
- MINER_BASKET, \|m\| > 3%, close entry, hold 3, CONTINUATION: dev n 114 / +1.98% / t 2.01 -> check n 77 / -1.74% / t -1.47, flip (reversal) check +1.53%.
- POOLED12 BTC-move dev rules overall: continuation dev mean +0.83%, check -2.97%; reversal dev -0.99%, check +2.79%.

## Key findings
- Direction is unstable across periods. Across the 60 BTC-family rules per unit, excess in dev vs check has correlation -0.63 (POOLED12) and -0.63 (MINER_BASKET). The sign flipped: continuation paid in 2020-23 and reversal paid in 2023-26. Dev and check excess signs agree for only 42% of pooled rules and 38% of basket rules.
- No dev pick held up. All three top picks lose most of their dev excess in check. Check excess is +0.14%, -0.40% and -0.80%, and none has a check t above 1.
- Flip controls: Rule A's continuation flip is -0.26% in check and Rule C's reversal flip is +0.28%. Both flips are about as small as the rules themselves, so neither direction is a clean edge.
- Check-period |t| > 2 appears in 16 of 60 BTC-family POOLED12 rules and 14 of 60 basket rules. These are overlapping variants of the same events, so that is not independent evidence.
- Long side in check: for continuation BTC rules, the long-trade excess over long buy-and-hold was positive in only 10% of rule-units (median -2.2% basket, -1.8% pooled). Longs after BTC up-moves lagged drift.

## Caveats
- Gap rules (Rule A, B) measure the gap with the 09:30 open print and then fill at that same print. The signal therefore uses the fill price. Treat open-entry gap rules as optimistic and not tradable as specified. Close-entry Rule C is clean on that point but still fails on check.
- Daily bars only (no intraday fill). Adjusted opens from yfinance. Sample starts 2020-08.
- Shorts ignore borrow fees, which matter for miners. That makes reversal results optimistic.
- IBIT (from 2024) and BITO (from 2021) are missing from part of dev, so POOLED12 dev is a smaller name set. Per-name NaNs are skipped, not zero-filled.

## Verdict: NONE
No pre-selected rule has a positive, stable net excess over drift in check. BTC-move overshoot or undershoot is not established. The only check-period pattern is a sign reversal (fading the off-hours BTC move), found after the fact. It would need a new pre-registration, not a dev-selected rule.

Files: swing.py (full run), run_log.txt (stdout), all_rules.csv (every variant x period), dev_top3.csv, top3_dev_check.csv, top3_per_year.csv.
