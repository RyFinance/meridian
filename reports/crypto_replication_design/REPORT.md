# Funding-XS external replication protocol (cycle 5, C2): design only

*Written by the cycle-5 C2 agent (design only, not registered). Saved by the director session.*

**Status:** design document, not registered. **Claim replicated:** the frozen Binance USD-M rule in `research/crypto_funding_xs/PLAN.md`:
- long the bottom quintile and short the top quintile of the 7-day daily-equivalent funding signal;
- universe is the top 100 by 30-day median quote volume;
- daily 00:00 UTC rebalance, ±0.5 gross per leg, net of funding and costs.

**Standing:** this is second-stage evidence. It is not a new first test.

## 0. Preconditions and ordering

1. **The corrected-data decision on Binance dev comes first** (the 69 missing symbols, 29 of them live in dev).
   - No other venue's 2020–2022 funding-sorted returns may be computed before the corrected Binance re-run has been registered and executed, and its outcome filed.
   - Otherwise a Bybit result could influence whether, or how, the director corrects Binance. That would contaminate a corrected-data audit (Amendment 1 §C).
2. **Reference effect.** Once §0.1 is final, the "Binance dev effect" is frozen in the replication registration. It is the corrected-data estimate if a corrected run exists, otherwise 1.65. It is never updated afterwards.
3. **Completeness audit, as the lesson from the Binance defect.** Before any return is computed on any venue, the registration attaches a metadata-only completeness check:
   - the symbol list from two independent sources (for example, Bybit static-archive folders and v5 instrument history or announcements);
   - expected and received file counts per symbol and month;
   - zero failed downloads;
   - a daily count of eligible symbols, from listing and delisting dates only.
   - These counts use no prices and no funding values.

## 1. Independence

**1a. Bybit 2020–2022 against Binance 2020–2022 is nearly the same draw.** The reasons are mechanical, not empirical:
- **Same prices.** Same-coin perp prices on major venues are held within a few bp by cross-venue arbitrage, so daily same-coin returns across venues correlate at about 1. The price leg (≈58% of Binance dev gross P&L) is effectively identical for common coins.
- **Same funding mechanics.** Binance and Bybit (and OKX) use the same funding template: premium index plus clamp(interest − premium, ±0.05%), with an interest component of 0.01% per 8 h. Funding on both venues is driven by the same leveraged-long demand.
- **Arbitrage bound, computed without data (`arbitrage_bound.csv`).** A persistent same-coin funding gap across venues can be traded: long the perp on one venue and short it on the other. So the venue-specific part of the 7-day signal is capped at roughly the arbitrage cost.
  - The same-coin signal correlation satisfies r ≥ s_c² / (s_c² + b²), where s_c is the cross-coin spread of the signal and b is the venue-specific part.
  - With a cross-coin sd of 3–10 bp/day and a venue-specific sd of 1–2 bp/day, r is at least 0.69–0.99. The central case is r ≈ 0.9.
- **From r to strategy-return correlation (`dependence_weight_cosine.csv`).** The two books' weight vectors have cosine 0.56, 0.64, 0.75 and 0.82 at r = 0.7, 0.8, 0.9 and 0.95. Scaled by a universe overlap of φ ≈ 0.85, the strategy returns correlate at about **0.47–0.70**.
- **Literature.** To my reading, the sources agree:
  - He, Manela, Ross & von Wachter (2022) find perp–spot deviations co-move across exchanges.
  - Schmeling, Schrimpf & Todorov's carry is a market-wide factor.
  - Cross-venue funding arbitrage is the practitioner trade, precisely because the gaps are small.
  - I could not open the papers in this session. The director should check the exact figures before citing them.
- **Consequence (`conditional_false_pass.csv`).** Given the Binance dev Sharpe of 1.65 (implied SE 0.93), a Bybit 2020–2022 test at the nominal p < 0.05 gate has these pass rates when the true Sharpe is 0:

  | ρ | P(pass given Binance dev) |
  |---|---|
  | 0.5 | 0.19 |
  | 0.7 | 0.29 |
  | 0.8 | 0.35 |
  | 0.9 | 0.46 |

  That is against a nominal 0.05. At ρ = 0.7, Bybit adds only about 1 − ρ² ≈ 0.5 of a sample of new information. Most of what it adds is venue noise, not new months or new coins.
  - **It re-draws 2021 again.** The Binance dev result is one year (2021 = +90% of P&L, and 2022 negative). Bybit covers the same 2021.
  - **No p-threshold fixes this.** Even at p < 0.01, a zero-edge Bybit run would still pass at several times its nominal rate given the Binance result. The test's null distribution is shifted by the shared sample path. A stricter α does not remove that shift.

**1b. Bybit 2023–2026 would contaminate the locked Binance validation.** Its Sharpe would correlate with the unviewed Binance validation Sharpe at about 0.5–0.9.
- At ρ = 0.8, seeing it would reveal about 64% of the validation statistic's variance.
- That would decide in advance whether the director opens validation under the corrected-data rule.

**Locked-window rule (proposed for registration):** while `crypto_funding_xs` validation is locked, or unrun after being opened, nobody may compute, view or report any cross-sectional funding-sorted return or funding→return statistic, on any venue or data source, for any day in 2023-01-01 → 2026-08-31.
- This covers Bybit, OKX, BitMEX, Hyperliquid, dYdX v4, Kraken, Deribit, aggregators and third-party dashboards.
- Metadata-only work (listing and delisting dates, file counts) is allowed.
- The lock lifts only when either:
  - the Binance validation result is filed; or
  - the director registers that the validation is permanently forfeited, in which case the window is recorded as contaminated for this claim for good.
- A breach is logged in the ledger, and the Binance validation, if later run, is labelled "contaminated".

## 2. Comparability: translation rules fixed before any outcome

- **Same code path.** `core.py` logic is unchanged. Only venue adapters change: file readers, and mapping each venue's columns to open, close, quote volume, calc_time and funding.
- **Funding normalisation.**
  - Signal: the sum of all settlements with calc_time in [t − 7d, t), divided by 7 (a daily equivalent). This works for any interval: 8 h, 4 h, 2 h or 1 h.
  - Minimum settlements: at least 10/21 ≈ 47.6% of the expected count, given each symbol's interval in force (10 at 8 h, 20 at 4 h, 80 at 1 h).
  - Funding paid on day t: all settlements with calc_time in (t, t + 1d].
- **Caps and formulas.** No adjustment: caps are part of the mechanism. The venue's cap and formula regime by date is recorded, not used.
- **Universe.** Identical rule:
  - top 100 by trailing 30-day median quote volume (USDT turnover);
  - all eligible symbols when fewer than 100 qualify;
  - days with fewer than 25 eligible perps are dropped;
  - 60 days of history required before eligibility.
  - N is not scaled to venue size. A scaled N is a forking path.
  - Venue-specific index products (the analogues of BTCDOM, DEFI and so on) are excluded by a list fixed before registration. The tokenized-stock exclusion carries over as written.
- **Settlement currency.** Linear USDT perps only. USDC-margined, inverse and quanto contracts are excluded.
- **Fees.**
  - Base cost per side = max(7 bp, the venue's published base-tier taker fee in force + 2 bp). For Bybit 2020–2022 the historical taker fee was about 0.075%, so base ≈ 10 bp; the fee must be verified from Bybit's fee announcements, not from data.
  - Stress = max(20 bp, 2 × base) plus the adverse 20% move on delisting days.
- **Delisting.** Identical: a held perp with no kline on day t returns 0 in base and suffers an adverse 20% move in stress. A venue's final settlement price is not used, so the treatment matches Binance.
- **BitMEX.** Excluded from the exact claim:
  - Its 2020–2022 perps are mostly inverse (XBT-settled) or quanto (for example ETHUSD), with fewer than about 20 names. The frozen MIN_UNIVERSE of 25 therefore drops every day.
  - Translating it to linear would need a quanto/convexity adjustment. That would change the tested claim.
  - Pre-2020, BitMEX has at most about 5 perps, so there is no cross-section.
- **Hyperliquid and dYdX v4.** They start in 2023, so they fall entirely inside the lock until it lifts. They are usable only as forward venues.

## 3. Evidence standard

**Recommended gate for any admissible (non-overlapping) replication:** the Amendment 3 P2 form.
- One-sided p < 0.05/k_rep from a mean-centred 21-day block bootstrap on the replication window alone;
- stress mean > 0;
- net Sharpe ≥ 0.30;
- fixed horizon, frozen code hash, no pooling with dev;
- G1–G7 reported. CONFIRM is not promotion.

**Reported but not gating:**
- the Verhagen–Wagenmakers replication Bayes factor BF_r0, with the prior centred on the frozen reference effect;
- the sceptical-prior posterior under N(0, 0.5²);
- the winner's-curse-corrected dev estimate.

**Why this gate, and why not the stricter options** (`power_summary.csv`, `bayes_criteria_oc.csv`):
- **Selection biases the dev estimate, not the replication's null.** On a fully independent sample, p < 0.05 keeps Type I error at 5% whatever the selection. The strictness that matters is structural: zero coin × month overlap with dev, a fixed horizon, and frozen code. §1a shows that tightening α cannot rescue an overlapping sample.
- **p < 0.01 costs a lot of power.** At 3 years forward (base error model), power at a true Sharpe of 0.7 falls from 0.31 to 0.12, and the design goes from MARGINAL to INCAPABLE.
- **The "≥ 50% of dev (0.825) with the CI excluding 0" rule is either redundant or harmful.**
  - Its 0.825 floor does not bind until SE < 0.42, which means at least about 6 years forward.
  - Before that, it is just p < 0.025.
  - Once it binds, it becomes the effect-size filter that Amendment 3 retired. It also anchors on a winner's-cursed and possibly mis-measured 1.65.
- **The replication BF with a prior at 1.65 tests "as large as dev".** At 3 years forward:
  - P(BF ≥ 3 | S = 0.7) = 0.23;
  - P(BF ≥ 10 | S = 0.7) = 0.10;
  - both below the p < 0.05 gate's 0.31.
  - It penalises the realistic, smaller true effect.
- **The sceptical N(0, 0.5²) posterior (P > 0.975) is nearly powerless before about 5 years:**
  - 3 years: P(meet | S = 0.7) = 0.03;
  - 5 years: 0.11.
- **If the director wants extra strictness anyway:** use one-sided p < 0.025 (95% CI excludes 0). At 5 years it keeps the design MARGINAL in the base model (0.32) but makes it INCAPABLE in the heavy model (0.21).

## 4. Power (plan_check, single-stage, gate p < 0.05 + stress + floor 0.30, k = 1)

Two error models:
- **base:** the c4a series model;
- **heavy:** spread AR 0.30, which matches the SE implied by the reported Binance dev bootstrap, 1.36/√year.

| Design | Years | SE (base / heavy) | Power at S = 0.7 | Power at S = 1.0 | Power at S = 1.65 | Verdict |
|---|---|---|---|---|---|---|
| R1 Bybit 2020–22 (≈1.5 eff. yrs, N≈50) | 1.5 | 0.86 / 1.11 | 0.21 / 0.16 | 0.32 / 0.23 | 0.61 / 0.44 | INCAPABLE, and not independent (§1a) |
| R2 Bybit 2023–26 | 3.67 | 0.55 / 0.71 | 0.36 / 0.26 | 0.57 / 0.41 | 0.91 / 0.75 | MARGINAL, **FORBIDDEN** (§1b) |
| R3 BitMEX perps 2020–22 (N≈15, re-specified) | 2 | 0.74 / 0.96 | 0.24 / 0.18 | 0.38 / 0.27 | 0.71 / 0.53 | INCAPABLE, and **infeasible** for the exact rule |
| F1 forward | 1 | 1.05 / 1.36 | 0.17 / 0.13 | 0.25 / 0.18 | 0.47 / 0.33 | INCAPABLE |
| F2 forward | 2 | 0.74 / 0.96 | 0.24 / 0.18 | 0.38 / 0.27 | 0.71 / 0.53 | INCAPABLE |
| F3 forward | 3 | 0.61 / 0.79 | 0.31 / 0.23 | 0.50 / 0.36 | 0.85 / 0.67 | MARGINAL / INCAPABLE |
| F5 forward | 5 | 0.47 / 0.61 | 0.44 / 0.31 | 0.68 / 0.50 | 0.97 / 0.85 | MARGINAL |
| Forward, group-sequential (looks at 3 and 5 yrs, O'Brien–Fleming z 2.19 then 1.70; kill if z < −1 at 1 or 2 yrs) | ≤5 | — | 0.42 / 0.30 | 0.67 / 0.48 | 0.96 / 0.84 | MARGINAL (false pass 0.049) |

- **Years needed at S = 0.7:**
  - 50% power (the DECISIVE bar): about 6.1 years (base) or 10.2 years (heavy);
  - 80% power: 14.0 years (base) or 23.5 years (heavy).
- **No design is DECISIVE.** Every historical option is INCAPABLE, forbidden or infeasible.
- **The only way anything short of 5 years confirms the claim is if the effect is LARGE.** At S ≈ 1.65, a 3-year forward test has 0.85 / 0.67 power.

## 5. Which samples are untouched, and stay untouched

1. **The Binance validation, 2023-01 → 2026-08.** It is untouched, and it is the strongest remaining test (3.67 years). It stays untouched only under the §1b lock. It opens only through the director's corrected-data route (Amendment 1 §C.8), not through this replication.
2. **Forward data from the first 00:00 UTC after registration and external anchoring.** This is on any venue, and belongs to Binance for the exact claim. It is untouched by construction.
   - The gap from 2026-09-01 to the forward start is left unused, because the forward-evidence rules forbid backfill.
3. **Nothing else.**
   - Bybit, OKX and Kraken 2020–2022 are the same draw as Binance dev.
   - All venues in 2023–2026 fall under the lock.
   - Pre-2020 no venue has a cross-section of 25 or more perps.

## 6. Recommendation: a forward-only route, and no Bybit 2020–2022 replication

- **Primary route.** Register a new forward trial of the frozen rule on Binance USD-M. It is observation only; Binance is not available to US persons, which is already an implementation flag.
  - Use the group-sequential design above, or a successor to `reports/future_lab/monitoring_rule_spec.json` registered before the start.
  - Kill-only looks at 12 and 24 months; efficacy looks at 3 and 5 years.
  - Gate as in §3.
  - Record it in `reports/forward/registry.jsonl`, with the head anchored externally before each execution.
  - Pre-state the design as MARGINAL. A FAIL is recorded as "FAIL, not certified (low power)".
  - A Bybit forward shadow may run in parallel for non-gating reporting only. Given cross-venue ρ ≈ 0.5–0.8, pooling the two adds little.
- **In parallel, and independent of this protocol:** the director's corrected-data re-run of Binance dev. If it passes the original gate, the Binance validation is the real second stage. Forward data then becomes a third stage, and it is disjoint from the validation window.
- **Bybit 2020–2022:** not a replication.
  - It may be run only after §0.1 is final, and it must be labelled a non-confirmatory venue-robustness diagnostic, with zero evidential weight toward the validation unlock or promotion.
  - Even as a diagnostic, it is INCAPABLE (0.21 / 0.16 at S = 0.7), and it will tend to "pass" if Binance dev did: 0.29–0.46 conditional false pass.
- **Rejected:** BitMEX, which is infeasible or a different claim, and any 2023–2026 venue, which is forbidden by the lock.

**Assumptions to confirm by metadata only before registration:**
- Bybit's effective years with 25 or more eligible perps in 2020–2022 (1.5 assumed) and its mean N (50 assumed);
- Bybit's historical taker fee;
- the per-venue funding-interval history.