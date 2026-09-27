# quant_v7 research ledger — consolidated 2026-09-23

Built from the files, not from memory. Sources:
- `research/preregistrations.jsonl`: 43 entries after this session's two;
- every `reports/*/REPORT.md` and `results.json` cited below;
- git HEAD `bc2c529` plus the uncommitted Codex work of 2026-09-19..21.

Check this list before proposing any experiment. Classifications:
- **SPENT**: tested; do not re-specify.
- **PARTIALLY USED**: some of the information is untested.
- **GENUINELY NEW**: never touched.
- **FORWARD ONLY**: evidence can come only from data after registration.

Approximate project trial count: ~111. The momentum verification counted 85–109 before the
Codex follow-ups; this session adds 2.

## 1. The result Manav remembers (~20% / ~1 Sharpe, 2019–2026)

It is **the 50% SPMO / 50% GLD portfolio**, `reports/momentum_gold_20260919/`. Monthly rebalance,
next-open fills, 5 bps a side.

| Window | Net CAGR | Excess Sharpe | Max DD |
|---|---:|---:|---:|
| 2020 – 2026-09-17 (as reported) | 19.91% | 1.03 | −18.74% |
| 2017 – 2026-09-17 | 17.98% | 1.06 | −18.74% |
| **pre-2024 (2017–2023)** | **12.13%** | **0.82** | −18.74% |
| 2020–2023 | 10.91% | 0.64 | −18.74% |
| 2022–2023 | 4.93% | 0.17 | −17.55% |
| 2024 – 2026-09 | 34.69% | 1.55 | −13.63% |
| Control 50% SPY / 50% GLD, pre-2024 | 11.28% | 0.80 | — |
| SPY/GLD control, 2005–2016 (SPMO did not exist) | 8.54% | 0.57 | −33.04% |

- **Active return over 50/50 SPY/GLD:** +3.13%/yr, HAC t 1.58, 95% CI [−0.75%, 7.01%].
- **Development status:** none. It is a post-hoc follow-up on already-viewed years, chosen after
  three other fund designs.
- **What weakens it:**
  - gold's 2024–25 run (GLD +63.7% in 2025);
  - asset choice made with hindsight;
  - it is the known stock/gold diversification effect, not a distinct edge.
- **Status:** research benchmark. Forward paper spec frozen 2026-09-20; zero fills. Next scheduled
  decision is the 2026-10-01 close.

The other near-match is the **stock-momentum book** from `return_search`:
- Original: 36.22% / 1.00 over 2019–2026, which is survivor-biased.
- Restricted to point-in-time S&P members: 20.32% / 0.66 (Claude verification) or 21.27% / 0.69
  (Codex diagnostic).
- FF5 + UMD alpha: 0.57%/yr, t 0.13.
- SPMO, which you can simply buy, did 22.38% / 0.89 over the same window.
- **Status:** dead as an edge.

## 2. Ledger by family

| # | Family (dir) | Information | Dev window → dev result | Validation | Forward | Main caveat | Class |
|---|---|---|---|---|---|---|---|
| 1 | PEAD production model (`bot/`, `pead_audit`, `pead_attack`) | earnings surprise (SUE) + ML filter | 2021-08 → 2025-06 recorded: 0.70 marked excess Sharpe (2×). **Pre-registered portfolio placebo (2026-09-23):** random selection under identical rules = 0.46 [0.06, 0.85]; real vs random **p = 0.113**. SUE sign contributes −0.58%/yr. The filter ranks on the stock's own 20-day pre-event return (ρ −0.63), i.e. dip-buying, not PEAD. Edge over the control is concentrated in 2021-10 → 2023-10 (removed: IR 0.30 → −1.29, p 0.02); active vs control was −6.4% in 2024 and −0.8% in 2025 | 2004–2014 pre-reg: **0.52, FAIL** (alpha t 1.12) | paper bot since 2026-08-18. **89 of 92 ledger events are backfill**. Live decisions are logged about 3.5 h after the close they fill at, so none counts as clean forward evidence (reports/forward). The 2026-09-21 'stale feed' alerts were a network outage misreported | static 2026 dollar-volume-rank feature (small impact); train/live pre-earnings return mismatch (ρ 0.22); replay ≠ live (31% of events unscorable in replay); sizing and universe chosen on the same window | **SPENT as an edge. It is an event-exposure product.** Any future claim must beat random selection (P1 0.46), not SPY |
| 2 | PEAD portfolio B1–B5 (`pead_portfolio`) | PEAD + hedges/sleeves | best B3 0.74, p = 0.47 | — | — | ceiling about 0.77 even with hindsight weights | SPENT |
| 3 | PEAD streak S1–S2 (`pead_streak`) | SUE sequences | S1 0.13; S2 0.79 but below the all-events control | locked | — | short leg thin | SPENT |
| 4 | Multi-asset book, 17 sleeves (`multiasset`) | ETF / futures prices, carry, VIX basis, overnight | dev 0.57 | hold-out 2018–26 **−0.02, FAIL** | — | — | SPENT |
| 5 | Crypto trend (`multiasset/crypto`) | BTC/ETH prices | registered hold-out candidate crypto_trend_long_only 1.24 dev (= BTC buy-and-hold's Sharpe); crypto_tsmom_multi 1.11 | hold-out 2022–26: long_only **0.40, FAIL**; tsmom_multi 0.17 | — | the earlier '1.11 → 0.40' mixed two candidates (corrected by null_lab) | SPENT |
| 6 | Options H1–H4 (`options_signals`) | OPRA prints, 100 stocks: O/S, IV spread, skew, composite | net −0.37 / −0.91 / −0.94 / −1.08 | locked | — | trade prints, no bid/ask; H3 skew failed gross even though skew (SmileSlope) is the top OSAP survivor | SPENT |
| 7 | IV changes V1–V3 (`iv_changes`) | OPRA 30-day ATM IV changes | −0.28 / −1.01 / −1.69 | locked | — | same data limits | SPENT |
| 8 | Put-writing P1–P3 (`putwrite`) | SPY/QQQ/IWM 1-day puts | 0.21 / 0.15 / 0.04 | locked | quote recorder only | premium about 1.5 bps/trade gross | PARTIALLY USED (index options beyond 1-day puts untested) |
| 9 | COT C1–C3 (`cot`) | CFTC positioning, 11 commodity ETFs | 0.25 / 0.33 / 0.05 (C1 gross 0.94) | locked | — | futures-cost version would be post-hoc | SPENT |
| 10 | Crowding unwind (`edge_search_20260919`) | COT extremes, 14 markets | corrected 3.47% CAGR, 0.09 excess Sharpe (2021–25); negative under stress | — | — | — | SPENT |
| 11 | Intraday I1–I4 (`intraday`) | ES/NQ 30m bars; event dates | I1 −0.12, I2 0.38, I3 −0.96, I4 0.55 | I4 **−0.09, FAIL** | — | — | SPENT |
| 12 | LETF close flow L1–L2 (`letf_rebalancing`) | ProShares AUM × leverage | 0.39 / 0.48 (gate 0.5); monotone dose-response | locked | suggested: L2 NQ-only, data after 2026-09-19 only | Direxion missing | FORWARD ONLY |
| 13 | Month-end rebalancing R1–R3 (`rebalancing`) | 60/40 drift | R2 0.74, R3 0.82 | **0.63 / 0.45, FAIL** | — | 2008/2020-driven; one-day lag kills it | SPENT |
| 14 | Treasury auction A1–A3 (`auction_cycle`) | auction calendar | −0.23 / 0.03 / −0.18 | locked | — | — | SPENT |
| 15 | FX carry/IV F1–F3 (`fx_carry_vol`) | forward points, 1-month IV | −0.03 / −0.22 / −0.33 | locked | — | — | SPENT |
| 16 | FX session rules (`fx_session_20260918`) | hourly FX | bounded null | — | — | — | SPENT |
| 17 | ETF convergence, share class, liquidity pressure (`edge_search_20260918`) | ETF pairs, share classes | bounded nulls; share class −1.41 | — | — | — | SPENT |
| 18 | Insider N1–N4 (`insider`) | SEC Form 4, 2006–2026 | N3 0.77, N4 0.51 | **0.49 / 0.51, FAIL** (gate 0.75); CAPM alpha ≈ 0 | — | survivor-biased price universe | SPENT |
| 19 | Fundamentals F1–F3 (`fundamentals`) | SEC financial reports with acceptance times: issuance, EPS consistency | all negative | locked (2015+ unviewed for these signals) | — | current-member universe | PARTIALLY USED |
| 20 | OSAP survivor hybrids (`survivor_hybrid`) | academic anomaly portfolios | H1 0.72, H4 0.70 (gate 0.75) | — | — | half of it is GameStop, Jan 2021 | SPENT |
| 21 | ETF hybrids E1–E5 (`etf_hybrids`) | sector/country ETF prices | E1 0.66, E2 0.57 | **0.38 / 0.44, FAIL** | — | — | SPENT |
| 22 | Return search, 20 candidates (`return_search_20260919`) | stock/ETF/crypto prices, ML | stock momentum 30.7% / 0.93 (survivor-biased) | eval 14.6 months | paper candidates frozen, not run | survivorship (measured about +16 pts CAGR) | SPENT |
| 23 | Momentum verification (`momentum_verification_20260919`) | point-in-time membership | de-biased 20.3% / 0.66, alpha t 0.13 | — | — | cache lacks removed names (23% in 2019, 50% in 2008) | infrastructure |
| 24 | Residual momentum R1–R4 | FF residuals | no variant beats SPMO in both halves | — | — | — | SPENT |
| 25 | Momentum construction, 10 variants | lookback/slots/skip/sector | 0 / 10 pass | — | — | median correlation 0.94 | SPENT |
| 26 | Vol-managed momentum V1–V5 | exposure overlays | 0 / 30 cells beat baseline | — | — | long-only book has no crash leg | SPENT |
| 27 | Overlay control | trend/vol overlays on buyable ETFs | overlays do not help | — | — | — | SPENT |
| 28 | Momentum fund designs (Codex) | vol-scaled, trend, defensive rotation | 0.73 / 0.64 / 0.53 vs SPMO 0.84 (2020–26) | — | — | — | SPENT |
| 29 | **SPMO/GLD 50/50** (Codex) | fund prices | see section 1 | — | frozen spec, 0 fills | regime and hindsight | FORWARD ONLY (benchmark) |
| 30 | Reversal research (Codex, `reversal_research_20260921`) | 5-day sector/stock reversal | **run crashed** (sector ETFs not in panel); registration only in its own folder, not in `preregistrations.jsonl` | — | — | stock leg survivor-biased | INCOMPLETE (not a trial) |
| 31 | higher_sharpe, sleeve_blend, strategy_research | assorted sleeves 2021–25 | 2024–25 eval: none qualifies; blend 0.27 | — | — | 1.5-year windows | SPENT |
| 32 | **Macro surprise M1–M2 (`macro_surprise`, this session)** | **calendar actual vs consensus** | **M1 −0.50 net** (gross −0.20), CI [−1.26, 0.22]; M2 not eligible | locked | — | contemporaneous IC +0.12 but forward IC −0.02: priced on release | SPENT (country-equity continuation) |
| — | Edge graveyard (`reports/edge_graveyard`) | OSAP meta-study | meta only | — | — | its 2015+ tables have already shown every OSAP predictor's recent performance | meta |

## 3. Information sources on disk, by status

| Source | Status | What is left |
|---|---|---|
| US stock prices/volume (503 current S&P names) | SPENT, and survivor-biased | Nothing credible until a delisted-inclusive universe exists |
| ETF prices (sectors, countries, asset classes) | SPENT | — |
| Crypto prices | SPENT | — |
| Earnings surprises (SUE, 2015–2025) | heavily mined | Forward paper only; the feed is stale |
| OPRA stock options (100 names, 2014–2026, prints only) | SPENT (7 signals) | Needs bid/ask and open interest to be worth revisiting |
| OPRA index options (SPY/QQQ/IWM) | PARTIALLY USED | Only 1-day put writing tested. Index-level timing is a single series: low power |
| ES/NQ 30-minute futures | SPENT | — |
| GC/SI 30-minute futures | unused | Price-only; low prior |
| COT | SPENT | — |
| FX forwards/IV/hourly | SPENT | — |
| Economic calendar, dates | SPENT | — |
| Economic calendar, surprises | PARTIALLY USED | FX and rates untested; low prior after this session's contemporaneous-pricing finding |
| SEC Form 4 | SPENT | — |
| SEC financial reports (acceptance times) | PARTIALLY USED | Profitability, accruals and asset growth untested. Their 2015+ performance is already known from OSAP, and the universe is survivor-biased |
| LETF AUM | FORWARD ONLY | — |
| Dividends/splits (LSE) | unused as signals | Survivor-biased universe; the related anomalies have decayed |
| OSAP portfolios | SPENT | — |

## 4. Standing conclusions

1. No historical result in the project clears a Sharpe of 1 after correction, with a control and
   outside the 2024–26 regime.
2. **Best measured numbers**, with no development-plus-validation pass behind any of them:
   - PEAD 2×: 0.70 marked excess Sharpe (pre-registered 2004–2014 replication: 0.52; stock
     selection alone: 0.30);
   - SPMO/GLD: 0.82 pre-2024, which is SPY/GLD's 0.80 plus noise.
3. The locally available historical information is close to exhausted for honest testing.
   What remains either:
   - is a single time series with no power; or
   - is contaminated by OSAP's already-published 2015+ performance; or
   - needs data the project does not have: delisted-inclusive equities, option quotes with
     bid/ask and open interest, or institutional holdings.
4. Genuinely forward evidence in the project today is small:
   - PEAD: 3 events;
   - SPMO/GLD: 0 fills;
   - LETF: not started.


## 5. Update, later on 2026-09-23 (director cycle 2; see RESEARCH_DIRECTION_2026-09-23.md)

- **Null-world calibration** (`reports/null_lab`).
  - The record is indistinguishable from an all-null world: 9 dev passes against 7.8 expected
    (p 0.35); 0 of 9 validation passes against 4.0 expected if the dev numbers were true (p 0.002).
  - The combined validation edge has p 0.22.
  - The 0.5 dev gate false-passes 10–19% of zero-mean nulls.
  - The absolute-Sharpe gate passes 87–89% of null long-only timing books.
- **New gates for future registrations:**
  - dev net Sharpe ≥ 1.8/√T per candidate;
  - ≥ 2.4/√T per member of a family of four;
  - long-biased books gated on active return against an exposure-matched control;
  - `research.null_lab.api.run_null` reports P(pass | null) with every new result.
- **PEAD** is reclassified: SPENT as an edge (row 1 above; `reports/pead_attack`).
- **Forward machinery** (`research/forward`, `reports/forward`).
  - A hash-chained registry; head seq=1 `4e50ac94…`, which needs an external anchor.
  - momentum_gold_v1 is registered. Its first decision is due in the 2026-10-01 post-close window.
  - PEAD decisions are excluded until an entry-convention fix is registered as pead_bot_v2.
- **Forward monitoring rule** (`reports/future_lab/monitoring_rule_spec.json`) was registered in
  the ledger before any forward data.
- **Data** (`reports/data_scout`).
  - The cheapest credible unlock is Sharadar ($499/yr) plus ORATS ($599 one-off). This is the
    user's decision.
  - The LSE vault/MCP has no delisted names, no index membership and no option bid/ask or OI.

## 6. Additional independent LSE information trials, 2026-09-23

Both plans were hashed into `research/preregistrations.jsonl` before any strategy return was
calculated. Both used the stricter exposure-matched development gate and 5,000 shift-null worlds.
Neither qualified to unlock validation; do not reverse or tune either signal.

| Family | Frozen development result | Control/null conclusion | Status |
|---|---|---|---|
| LSE USD liquid HY/IG credit-index ratio, 20 common sessions, monthly SPY/IEF rotation (`research/credit_lead/PLAN.md`) | 2012–2020 active net Sharpe **−0.21** vs +0.60 gate; stress active mean −2.75%/yr | Matched static mix 9.62%/yr vs strategy 7.65%; 75.8% of 5,000 shifts matched/exceeded active Sharpe (`reports/credit_lead/REPORT.md`) | **FAIL; 2021+ locked** |
| LSE OPRA SPY/QQQ/IWM 7–30DTE put/call volume breadth, weekly SPY/IEF rotation (`research/index_option_breadth/PLAN.md`) | 2015–2019 active net Sharpe **−1.21** vs +0.85 gate; stress active mean −11.84%/yr | Matched static mix 8.08%/yr vs strategy −1.70%; 99.16% of 5,000 shifts matched/exceeded active Sharpe (`reports/index_option_breadth/REPORT.md`) | **FAIL; 2020+ locked** |

The options reverse-allocation placebo has high raw historical Sharpe but was preregistered only
as a placebo. Promoting it would be a new, post-result trial on viewed development data.

## 6. Update, 2026-09-23 (cycle 3)

| # | Family | Information | Dev result | Validation | Class |
|---|---|---|---|---|---|
| 33 | Bond-market policy trend → equity-index selection (`policy_trend`, P1) | vol-scaled 6-month change in short government yields, 10 economies; futures-equivalent local-index returns | net Sharpe **0.03** (gross 0.07); gate 0.657; permutation p 0.39; shift-null p 0.42; alpha on momentum and rate-level controls −0.2%/yr | locked | **SPENT** |
| 34 | FX continuation after scheduled macro/policy news (`fx_news`, F1/F2) | 1-minute FX, 6 majors; calendar actual vs consensus (growth, inflation, policy); timestamps realigned from release schedules | plan drafted; 1-minute pull in progress; not yet registered | — | IN PROGRESS |

Frontier map: `research/LSE_FRONTIER_MAP_2026-09-23.md`.

Data finding: bulk-loaded calendar rows are stamped Europe/Berlin wall time for 2015 and a fixed
UTC+1 from 2016. Live rows (created from 2025-12-31) are UTC.
- This was verified against release schedules. EUR/USD volatility peaks at exactly minute 0 after
  correction.
- The earlier note in `macro_surprise/PLAN.md` ("other regions look like UTC") described live-feed
  rows only.
- That study used date-level signals with a one-day lag, so its result is unaffected.

**Row 34 result.**
- F1: gross −0.41 bp/event, net Sharpe −4.7. F2: gross −0.29 bp, net Sharpe −1.6. Permutation p is
  0.94 and 0.69 respectively.
- **SPENT**, as a bounded null over about 7,900 events.
- Scheduled news is priced within minutes, with no continuation after +15 minutes
  (`reports/fx_news/REPORT.md`).

| 35 | Credit-conditions gate (`credit_gate`, G) | iBoxx USD Liquid HY / USD corp 1–3y total-return ratio, 63-obs change, LSE vault 2010+ | active vs exposure-matched Sharpe **−0.04**; vs own-trend gate +2.3%/yr (p 0.20); shift-null p 0.45 | locked | **SPENT** |

## 7. Structural-return batch (Codex, 2026-09-23)

The [ex-ante ranking](structural_frontier/RANKING_2026-09-23.md) and one [registered plan](structural_frontier/PLAN.md) preceded all three returns. The three-test batch used `1.8/√T` active-Sharpe thresholds, stress costs and a one-sided centered block-null threshold of 0.05/3. All validation remains locked; see [report](../reports/structural_frontier/REPORT.md).

| # | Return source | Development result against investable control | Decision |
|---|---|---|---|
| 36 | Intermediate Treasury duration premium: IEF minus SHY, 2003–2014 | +3.31%/yr, active Sharpe **0.57**, stress mean positive; p=**0.023** misses registered 0.0167 batch threshold; best 24 months removed Sharpe 0.35 | **FAIL gate; suggestive only, no validation** |
| 37 | High-yield default/liquidity premium: HYG minus 1/3 LQD + 2/3 SHY, 2008–2016 | +3.43%/yr, active Sharpe **0.30**, gate 0.60, p=0.186; best post-crisis year removed flips mean negative; equity-beta correlation +0.60 | **FAIL** |
| 38 | Monthly cash-secured TLT put insurance premium vs 50% TLT + bills, 2014–2022 | +0.30%/yr, active Sharpe **0.07**, gate 0.62, p=0.427; stress active mean −1.15%/yr; option prints have no historical bid/ask | **FAIL** |

This batch is economically distinct from credit/option-volume directional timing and short-dated equity put writing. The missing LSE historical contract-by-expiry futures curve prevents an honest commodity roll/convenience-yield trial now.
| 36 | Monthly ATM SPY put writing (`vrp_putwrite`, PW) | OPRA prints, 67 dev cycles | Sharpe 0.72, β 0.50, α −0.2%/yr (t −0.11); active vs 0.5×SPY −0.05 (p 0.56) | locked | **SPENT** (volatility premium = equity beta here) |
| 37 | Bond-ETF liquidity provision (`etf_basis`, B) | HYG/LQD vs own iBoxx index basis | book 0.71; active vs exposure-matched 0.34 (gate 0.74); stress active < 0; shift p 0.10; HYG-only, 2014/2016 | locked | **SPENT** (HY-only forward idea at most) |
| 38 | Treasury month-end index extension (`tsy_month_end`, M) | calendar forced flow; TLT last 3 sessions | dev active Sharpe **0.66** (gate 0.52, shift p 0.006): PASS | validation **0.69** vs gate 0.75: **FAIL** (shift p 0.005, bootstrap p 0.004, 10/12 years positive); combined p 0.00034, ×120 = 0.041 | **FORWARD OBSERVATION** (strongest evidence to date; not validated) |

**Erratum (2026-09-23 22:55 PDT).** `research/{vrp_putwrite,etf_basis,tsy_month_end}/PLAN.md` say
"Written 2026-09-24". Their ledger `registered_at` timestamps (2026-09-23T22:27–22:32 −0700) are
correct, and the plans were written minutes earlier on 2026-09-23. The registered files are not
edited: that would break their hashes.

Parallel-session results, also recorded:
- `research/structural_frontier` (A IEF−SHY duration premium: Sharpe gate passed but batch p 0.023
  failed; B HYG credit carry: FAIL; C monthly TLT put writing: FAIL);
- `research/japan_us_flow`: FAIL;
- `research/index_option_breadth`: FAIL;
- `research/credit_lead`: FAIL.
All are SPENT.

## 8. Research-organization cycle (director session, 2026-09-23 23:16–23:59 PDT)

Three workstreams:
- **A:** structural premia;
- **B:** market structure;
- **C:** the certification lab.

Candidates were ranked from scout outputs before any return was seen; see
[RESEARCH_DIRECTION](RESEARCH_DIRECTION_2026-09-23.md) §Cycle 3. Four plans were registered at 23:16:05 PDT under the
protocol-amendment gates. Row numbers continue from 38; rows 36–38 appear twice above because of parallel sessions.

| # | Family | Information | Development | Validation | Status |
|---|---|---|---|---|---|
| 39 | Commodity roll premium via same-commodity ETF pairs (`commodity_roll`, A1): long USL/UNL/DBC, short USO/UNG/GSG | ETF curve-point pairs (no contract curves available) | **PASS**: 0.596 vs 0.557, p 0.0064. Independent audit **WEAKENED**: spot-hedged alpha 7.2%/yr (t 3.09), tradable pure-roll t 1.6 | **FAIL**: 0.21 vs 0.75, p 0.24. Stricter pre-registered V1/V4/V5 also fail. 2020 super-contango +34%; ex-2020 Sharpe −0.10; 2026 −19.5% | **SPENT** (natgas-only strength is post hoc, not a candidate) |
| 40 | MBS negative-convexity premium (`mbs_convexity`, A2): MBB minus PIT IEF/SHY hedge | agency MBS pass-through ETF | **FAIL**: 0.40 vs 0.61, p 0.043; 2009 QE year dominates | locked | **SPENT** |
| 41 | Month-end index extension in LQD/MBB/TIP, rate-hedged (`sector_month_end`, B1) | TLT mechanism applied to other bond indices | **FAIL**: active −0.43 vs 0.55; stress −3.1%/yr. Shift p 0.038 only because the null mean was −0.96 (null not mean-zero) | locked | **SPENT** (does not corroborate tsy_month_end) |
| 42 | Month-end FX hedge-rebalancing flow (`fx_hedge_rebal`, B2; Melvin–Prins) | 1-min FX majors, equity MTD returns | **FAIL**: 0.09 vs 0.72, permutation p 0.18; gross 2.6 bp/event; quarter-ends weaker (wrong sign for the mechanism) | locked | **SPENT** |

**Row 38 (tsy_month_end) is downgraded by an independent audit** ([report](../reports/audit_tsy/REPORT.md);
[addendum](../reports/tsy_month_end/ADDENDUM_AUDIT_2026-09-23.md)):
- **WEAKENED.** The rule was published in 2019. Post-publication active Sharpe is 0.56 (p 0.059); the last 36 months
  0.25.
- The combined p of 0.00034 was not pre-registered. "Strongest evidence" is withdrawn. Status stays FORWARD
  OBSERVATION.

**Validation record: 0 of 11 development passes have validated.**

**Workstream C infrastructure** (not trials):
- `research/certify/` promotion guards G1–G7 plus a trust scorecard (tests pass);
- `research/null_lab2/` gate consistency;
- `research/future_lab2/` alternate futures for forward candidates;
- `research/forward_audit/` forward readiness (tsy_month_end_v1 registered at registry seq 2).

## 9. Cycle 4: power first (director session, 2026-09-24/25)

**Protocol changes.**
- Registered: protocol amendment 3 (binding power check; calibrated validation gate: p < 0.05/k_val, stress > 0,
  Sharpe ≥ 0.30) and `PLAN_TEMPLATE_v2.md`.
- Trial accounting (`reports/trial_accounting/`): about 240 total shots (222–258); M_eff (Li–Ji) ≈ 25; every
  information family currently on disk is exhausted.

**Batch cycle4_E1_E2 (k = 2).**

| # | Family | Information | Power (pre-registered) | Development | Status |
|---|---|---|---|---|---|
| 43 | Treasury auction demand (`tsy_auction_demand`, E2): w = −z(bid-to-cover surprise) → 5-day tenor-yield reversal | Auction results, 2000–2026 (new information; calendar/flow sibling) | **DECISIVE** (joint 0.59 at S 0.7) | **FAIL**: −0.42 vs 0.50, p 0.92, placebo p 0.42 | **SPENT** (informative null) |
| 44 | Crypto perp funding cross-section (`crypto_funding_xs`, E1): long low / short high 7-day funding, Binance USD-M, delisted included | Binance public archive (new) | INCAPABLE for S 0.7; registered as a large-effect test | **FAIL on p only**: Sharpe 1.65 vs 1.22, stress +27%/yr, bootstrap p 0.038 vs 0.025; 2021 = +90% of the P&L | **FAIL, not certified (low power)**; validation 2023–26 still locked and unviewed |

**Examined and not registered** (power or cleanliness failed before any return was seen):
- EIA energy carry 1986–2005: INCAPABLE, 0.22 joint; the data stay quarantined and it cannot replicate the frozen
  commodity_roll claim.
- FINRA short volume: INCAPABLE, and negative net at realistic turnover.
- 8-K item events: price-side survivorship.
- 13F, insider, dividends and issuance: knowledge-contaminated by the OSAP graveyard, or spent.

## 10. Cycle 5: evidence quality (2026-09-25)

| # | Family | Result | Status |
|---|---|---|---|
| 45 | Primary-dealer >6y Treasury inventory → 10-year duration (`pd_inventory`, k = 1, DECISIVE at 0.7) | Development FAIL: active Sharpe 0.01, p 0.47 | **SPENT** |
| 44 (audit) | `crypto_funding_xs`, corrected-data re-measurement (amendment 1 §C.8; an audit, not a trial) | The as-run result used an incomplete archive. Corrected development: Sharpe 2.44, p 0.0026, a **PASS**. Two hostile audits: implementation SURVIVES; statistics and economics WEAKENED (the effect is regime-concentrated; bootstrap under-covers; calibrated Šidák p ≈ 0.3; G3/G5 fail; capacity about $1–5M) | **Development PASS, WEAKENED; validation LOCKED** (unlock is the user's decision; not a survivor) |

**Infrastructure and protocol.**
- Registered:
  - `LOCK_2023_2026.md`: no funding-sorted 2023–26 analysis on any venue;
  - the corrected-data re-measurement.
- Proposed, not registered: amendment 4 (`research/PROTOCOL_AMENDMENT_4_PROPOSAL_2026-09-25.md`).
