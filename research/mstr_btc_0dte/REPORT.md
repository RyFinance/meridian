# MSTR near-the-money options, direction from BTC's off-hours move (2026-10-16)

Exploratory study (not pre-registered; whole 2020-08..2026-08 sample viewed). Scripts: `signal_study.py`, `backtest.py`, `extra.py`, `montecarlo.py`.
Data: BTC 1m (BTC-Acum/data, ends 2026-08-11), MSTR official daily (yfinance), MSTR OPRA daily per-contract prints from the LSE vault (`data/lse/options_mstr/MSTR.parquet`).

## Findings
1. MSTR has **Friday expiries only** (plus a few Thursdays before holidays). There is no Monday 0DTE; Monday trades use that week's Friday option (4DTE).
2. MSTR's opening print already prices the BTC off-hours move: gap beta ≈ 1.0 (Mon 1.01, Fri 0.91). BTC off-hours direction barely predicts MSTR's open→close move (corr Mon +0.00, Fri +0.04; sign flips by year).
3. Options backtest, buy the first OTM strike at the open (513 trades): signal gross +6.9%/trade on premium vs anti-signal −4.2% and random −5.0%. Paired t = 1.17, so not significant. **Net of costs −1.5%/trade (t −0.27); with doubled costs −9.3%.** Win rate 34%; the median trade loses 31%. ITM1 is no better.
4. "Under-reaction" variant (MSTR opened away from what BTC implies): worked before 2023-07 and reversed afterwards, in both options and shares, so it is dead.
5. Shares, RAW Monday open→close: +42 bp/trade, t 1.35, Sharpe 0.55. It is the only lead, and it is weak.
6. 1-year Monte Carlo (104 trades, block bootstrap): 2% of equity per trade → median −6%, P(loss) 61%. 5% → median −24%, P(−30%) 44%. 10% → median −58%. Fri-only 0DTE at 2% → median −1.5%, 5th..95th percentile −42%..+78%: a lottery ticket with a negative edge.

## Verdict
Not tradable as specified. If pursued, only as a forward paper test of RAW-Monday in **shares**, registered from today.

## Intraday follow-up (2026-10-16): take-profit-ASAP, arbitrage, premium selling. Verdict: no edge.
Protocol: `INTRADAY_PROTOCOL.md`; dev = 1-minute OPRA prints 2020-08..2023-12; validation = 2024-01..2026-05-21, run once on 3 frozen candidates (`CANDIDATES.md`).
- **Take-profit-ASAP option buying** (the user's rule): 72% wins, but the average win is +13% against an average loss of −46%, so net −3.5% per trade. Across ~12k buy variants in dev, none passed (best t 0.75). Variants tried: strike depth, entry delay, confirmation, take-profit, stop-loss, time stop, BTC filter.
- **BTC→MSTR minute lead-lag arbitrage**: none on real MSTR stock minutes (2026-04..08). corr(BTC past 5m, MSTR next 5m) = 0.001; MSTR reprices within the same minute (corr 0.66). The apparent lag in option-implied prices is stale prints.
- **Credit spreads** (adjacent wing): negative in dev; two sets of spreads eat the premium.
- **Friday 0DTE naked premium selling**: looked excellent in dev (94–100% wins, t 4–7), and **failed validation**.
  - V1, BTC-safe side 6% OTM: +0.07% per Friday, t 0.15, worst −28% of margin, max drawdown −40%.
  - V2, 4% strangle: −0.8% per Friday, −75% compounded.
  - V3: about 0%, max drawdown −48%.
  - The dev window had no Friday tail; 2024–26 did.
- Conclusion: BTC's off-hours move is priced into MSTR's open. What is left after 9:30 is noise plus a short-volatility premium that is fully repaid in tail events. No options rule tested here is tradable. The Monday-shares forward test (`FORWARD_PLAN.md`) keeps running as a cheap forward check.
- Second holdout 2026-05-22..08-10 (worst fills): V1 n=9, +0.73%; V2 n=10, +2.31%; V3 n=5, +1.61%. All positive, but 5-10 trades in a calm stretch. This is the same win-small pattern that 2024-26 punished, so it does not change the verdict.
- **C1/C2 one-shot validation (2024-01-05..2026-08-10): BOTH FAILED** (`VALIDATION_RESULTS_C1C2.md`). C1 IC-v1 iron condor: −3.7% of risk/trade base (t −1.62), −14.0% worst fills (t −5.78); C2 NNV-v1 naked side: −14.1% of premium base (t −0.83), worst trade −19.9x premium. Dev-window edge (+24.6%/+24.7%) did not persist; same win-small/pay-big flip. Closes the whole intraday short-premium family on 2024+.

## mNAV trend sealed validation (2026-10-17): FAILED as registered

`agent_mnav/HOLDOUT_PLAN.md` (registered 00:09:50) → `HOLDOUT_RESULTS.md` / `.json`. Window 2023-01-03..2026-08-10, 903 sessions, 43 BTC-16:00 gap sessions under the frozen stance-carry policy.
- M1 (10d mom + 50d SMA, long/cash): SR **1.148**, +534.2%, CAGR +67.0%, maxDD **−47.0%**, time long 0.36, 37 entries. B&H: SR 1.046, +582.3%, maxDD −84.5%.
- M1 per-year: {2023 +67.6%, 2024 +103.0%, 2025 **+59.2%**, 2026 +17.1%} vs B&H {+363.3%, +369.7%, **−50.7%**, **−36.4%**}.
- Bootstrap (stationary 21-session blocks, 2,000 draws, seed 20260817): SR diff +0.102, P(D>0) = **0.592**, 5–95% [−0.602, +0.871].
- Gates: G1 (SR > B&H **and** P ≥ 0.95) **✗**; G2 stress (P ≥ 0.90) ✗; G3 net > 0 ✓. **Verdict: FAIL — power failure, not sign.** M2 SR 0.938 (P 0.389), M3 SR 1.078 (P 0.514).
- Costs immaterial (stress ≈ base). No promotion; no re-runs on this window. Cheap prospective monitoring only: `FORWARD_PLAN_M1.md` (registered separately; cannot convert this FAIL).

## Purchase-announcement rules P1/P5 sealed validation (2026-10-17): FAILED as registered

`agent_events/GATES_ADDENDUM.md` (registered 00:11:42) → `event_study.py` run once → `RESULTS.md`. EDGAR acceptance-time entry (first MSTR session close at/after acceptance), 106 validated positive-purchase 8-K events (dev 21 / holdout 85), 0 fetch failures, costs 3 bp/side + $0.005/share.
- Primary P5 holdout: n=85, net mean **+1.23%**/5-session window vs unconditional same-length control **+1.88%** (946 sessions) → excess **−0.66%**; bootstrap 2.5% quantile of excess **−3.28%** (10k, seed 20261017). **FAIL** (required q025 > 0). Robust to the control reading: under the daily control the q025 is still −1.79%.
- P1 secondary: excess −0.96%, q025 −1.96%. Dev flip again: P5 dev excess +2.94% (n=21) → holdout −0.66%.
- Reported-only: event means survive 20 bp/side; every BTC-regime and funding bucket sits at/below the control; 27 episodes +61.9% net with −78.8% maxDD. Event windows after 2024 add nothing beyond ordinary long MSTR exposure.
- Closes the purchase-announcement family on 2023+; no re-runs on this window.

## Parallel screens reviewed 2026-10-17 (dispatched-agent folders)

**Disclosure:** none of these three had a central `preregistrations.jsonl` entry before its run; each self-froze locally (protocol/freeze files + hashes recorded by its own runner). Late `late_registration_record` entries added 2026-10-17. Their evidentiary status is weaker than centrally registered unlocks; recorded as-is, nothing promoted.

### BTC-proxy open→close drift (`agent_proxy/`) — failed its precommitted bar (2023+ window consumed)

- Signal known 09:29 ET (BTC off-hours ≥ threshold, ≤5-min stale check); buy opening auction, sell same-day close; 3 bp/side + $0.005/share.
- **P1 MSTR 2%**: dev Sharpe 0.81 / +83% → validation 2023-01-03..2026-08-10: 148 trades, **+46.97% net, Sharpe 0.48** (gate ≥ 0.50 → **failed by 0.02**), maxDD −44.8%, win 53.4%, 2025 −24%. Cost-robust (6 bp/side: +34.5%) and adjacent 1.5%/2.5% thresholds positive (+153%/+103%) — a clean near-miss.
- **P2 CLSK**: −74.4% (Sharpe −0.68). **P3 COIN**: −7.9% (0.05), sign flips across adjacent thresholds.
- Verdict: no rule passes; the P1 near-miss does **not** justify relaxing the precommitted bar post hoc. Re-runs on 2023+ closed; any future use of P1 must be a separately registered forward paper test.

### BTC SMA / two-factor MSTR gates (`agent_regime/`) — dev rejection, holdout untouched

Isolated positive cells (BTC SMA40 +87.6% Sharpe 0.74; TF-50-50 +29.8% 0.48) surrounded by negative neighbors and bad 2022s; rejected in development per protocol, no validation run.

### Friday BTC-trend → Monday-open MSTR gap (`agent_weekend/`) — dev rejection, holdout untouched

Best dev cells (5d/10d lookback) t ≤ 1.11 with unstable 2022; adjacent 20-day negative. No validation run, none queued.

### MSTR-vs-IBIT IV spread timing (`agent_ivspread/`) — FAILED all gates (one-shot, no clean dev window)

Signal: z-score (120-session) of IV30_mstr − IV30_ibit ≤ −1 → long MSTR next open, else cash. Window: 456 sessions 2024-11-19..2026-09-16 (entire IBIT options history); eval 397 sessions from 2025-02-18 (z warm-up).
- Spread mean +30.5 vol pts (MSTR ~76% vs IBIT ~45%), but steadily compressing from ~+100 pts to ~+30 pts — non-stationary level.
- Rule: 14.1% time long, 7 round trips, **−16.2% net** (SR −0.636, maxDD −19.6%) vs B&H −61.5% (SR −0.451, maxDD −81.6%). Bootstrap P(SR diff>0) = 0.42 base / 0.41 stress. G1/G2/G3 all ✗.
- The rule dodged the 2025H2–2026H1 crashes (−59.9%/−44.8% B&H halves) but had negative absolute return; z-quintile bucket table shows no monotone "cheap vol" signal. Measurement hand-verified; no promotion; re-runs on this window closed (including any detrended variant), `report`ed in `agent_ivspread/RESULTS.md`.
- **Queued next (not started): convertible/ATM issuance-flow effects (2024+ only; needs its own registration before any statistics).** Superseded same day by the study below.

## Issuance / convertible-announcement study (`agent_issuance/verified/`, 2026-10-17): development screen negative — CLOSED, no holdout run

**Registration disclosure:** the development return run used the 2019–2023 price window (viewed by earlier registered studies) and had **no central `preregistrations.jsonl` entry before it ran**, although the study's protocol (`PROTOCOL.md`) was written first and no 2024+ issuance-event return was ever computed. Recorded post hoc as a `late_registration_record` (2026-10-17, review-completion pass); weaker evidentiary status than a centrally registered unlock; nothing promoted.

- Question: does the earliest SEC-documented announcement of a new MSTR convertible offering (long) or a new Class A common-stock ATM program (short) drift afterwards? 290 EDGAR primary documents (2019-12..2026-10) hand-reviewed into a 17-event ledger (7 development / 10 future-source), each with acceptance timestamp and document SHA-256. Development extended through 2023-12-29 per the sanctioned ≤2023 exploration split to reach the minimum five ATM episodes.
- Development results (prices ≤2023-12-29): convertible family n=2 → structurally un-freezable (closed without a holdout). ATM-short family n=5: 1-session −1.98% net, −1.63% matched excess; 3-session +1.02% / +2.30% (one event = 51.5% of positive profit); **5-session +4.66% / +6.71%, but bootstrap mean CI −6.03%..+14.28%, t 0.82, and the Sep-2022 episode = 55.95% of positive profit.** All candidates fail the pre-written screens; **no rule frozen, no 2024–26 issuance return computed.** The apparent five-session effect is one losing week (−14.1%) away from zero, and short-side borrow availability is unverifiable.
- Review-completion amendments (same day, disclosed in-tree and in the registry entry): future-source ledger extended with the 2026-03-23 additional $21bn common-annex addendum; 2025-11-04 omnibus consolidation / joinders / preferred IPOs documented as exclusions; excess-column transcription aligned to the committed final outputs (decision unchanged); dev outputs re-verified byte-identical after both changes.
- Panel artifact (`agent_issuance/` weekly ATM/BTC/repurchase tables, 2024Q4+): descriptive only, no return statistic. 5 cross-era anchors re-verified against cached filings (`panel_qa_results.md`); BTC-quantity cross-check vs the events-agent purchase series (`panel_btc_crosscheck.md`, 2026-10-17): six event-level deltas fully enumerated (incl. three panel misses under the Aug–Sep 2026 "BTC Purchased" dialect and two exhibit-only events missed by the events series), identity closes at exactly −2,975 BTC, no impact on the closed study. Current era (Oct 2026): small dribble common sales + preferred buybacks + USD reserve — no new programs (2026-10-13 press release; note BTC sales ran 2026-05-26..08-09, 6,948 BTC total, outside both datasets' purchase-only scope).
