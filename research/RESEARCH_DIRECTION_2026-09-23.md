# Research direction — work cycle 2026-09-23 (director's record)

## Decision

This cycle does **not** search for a new historical edge. It spends effort on categories C, D and E
(verify, forward evidence, falsification), with B (better data) scouted in parallel.

## Why

1. **The record gives no evidence of any edge yet.**
   - About 111 trials have been run. No candidate has passed both a development gate and a locked
     validation.
   - Every candidate that reached validation lost most of its Sharpe there: I4, R2, R3, E1, E2,
     N3, N4, the multi-asset book, crypto trend.
   - Before looking further, we need to know the base rate: how often our own gates pass when no
     edge exists. Without it we cannot read any future result. (Null-world lab.)
2. **The "best surviving strategy" may not be an edge.**
   - PEAD's 0.70 marked Sharpe has three weak spots: stock selection alone is 0.30 [−0.61, 1.25];
     the pre-registered 2004–2014 replication failed at 0.52; and an earlier event-level placebo
     put the SUE ranking at p = 0.29.
   - If PEAD is an event-exposure product rather than a selection edge, its forward paper test is
     testing the wrong thing. (PEAD attack.)
3. **Forward evidence is the only evidence left that is not contaminated, and it is barely being
   collected.** 89 of 92 PEAD paper events are backfill. The bot reports a stale earnings feed.
   The SPMO/GLD benchmark spec has 0 fills. (Forward integrity and tamper-evident registry.)
4. **Path risk and the size of a forward test are unquantified.**
   - Before anything reaches capital we need drawdown, ruin and underperformance distributions
     under plausible alternate paths.
   - We also need a pre-registered sequential rule that says when forward data promotes or kills a
     candidate. (Simulated-futures lab.)
5. **The local historical surface is nearly exhausted** (see RESEARCH_LEDGER_2026-09-23.md).
   - The single biggest unlock is survivorship-free equity data and option quotes with open
     interest.
   - This is a purchase decision for the user, so it is scouted, not bought. (Data scout.)

## Work streams, run as parallel agents with separate directories

| Stream | Category | Directory | Question |
|---|---|---|---|
| Null-world lab | E | research/null_lab, reports/null_lab | P(pass gates \| no edge); is the project record distinguishable from all-null? |
| Simulated futures | E / C | research/future_lab, reports/future_lab | Path risk, sequence dependence, forward-test length and kill rules |
| PEAD attack | C | research/pead_attack, reports/pead_attack | Is PEAD selection skill or exposure? Any leakage? |
| Forward integrity | D | research/forward, reports/forward | Is the PEAD forward record clean? Build a hash-chained forward registry |
| Data scout | B | reports/data_scout | Cheapest credible survivorship-free / option-quote data |

## Rules for all streams

- No trades.
- No changes to bot/ or launchd.
- No commits.
- No validation unlocks.
- Pre-register any test whose outcome changes belief about a specific strategy.

Results and the synthesis are appended below when the streams finish.

---

## Results of cycle 2 (all five streams complete; 100 new tests pass)

### What the evidence now says

1. **The research machine has found nothing real so far, and the record says so statistically.**
   - At development: 9 passes from 46 gated candidates, against 7.8 expected if every candidate
     were null (p 0.35).
   - At validation: 0 of 9 passed. If the development Sharpes had been true, 4.0 passes were
     expected (p 0.002). Combined validation edge p = 0.22.
   - The best market-neutral development Sharpe (R3, 0.82) is what the best of about 111 null
     trials typically looks like.
   - Source: `reports/null_lab`.
2. **PEAD is not an edge.**
   - Under its own portfolio rules, random selection gets 0.46 Sharpe against the real 0.70
     (p 0.113, pre-registered).
   - The SUE sign contributes −0.58%/yr.
   - The "PEAD" filter is really a dip-buying filter (ρ −0.63 with the stock's own 20-day
     pre-event return).
   - Its edge over the control comes from one 2021–23 episode (removing it gives IR −1.29,
     p 0.02). Active return against the control was negative in 2024 and 2025.
   - Sources: `reports/pead_attack`, `reports/future_lab`, and an independent recomputation by the
     director.
3. **There is no clean forward evidence for any strategy yet.**
   - PEAD's paper decisions are logged about 3.5 hours after the close they fill at, and 89 of 92
     events are backfill.
   - The 2026-09-21 "stale feed" alerts were a network outage that the code misreports.
   - A tamper-evident registry now exists; its first clean decision can be momentum_gold_v1 on
     2026-10-01.
   - Source: `reports/forward`.
4. **The best buyable allocation is SPMO/GLD, and it is a benchmark, not an edge.**
   - Its edge over SPY/GLD depends on 2023–25: removing that stretch takes IR from 0.48 to 0.10.
   - Beating the control with forward data would need 20–29 years.
   - Its absolute Sharpe is plausible, but it is the stock/gold diversification premium.
5. **Data.**
   - Survivorship can be fixed for about $1,100 (Sharadar plus ORATS). The LSE vault and MCP
     cannot fix it.
   - New data re-opens audits and a few genuinely unviewed windows: stocks 1998–2003, options
     2007–2014. It does not re-open viewed history for tested ideas.

### Trust-stack scorecard (layers: 1 implementation, 2 pre-registered dev, 3 locked validation, 4 robustness to alternate paths, 5 beats a null/placebo, 6 clean forward, 7 live)

| Candidate | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Standing |
|---|---|---|---|---|---|---|---|---|
| PEAD (production bot) | partial: minor leakage; replay ≠ live | ✗: config chosen on the window; 2004–14 pre-reg failed | ✗ | ✗: one episode, p 0.02 | ✗: p 0.113 vs random | ✗: no clean record | ✗ | Event-exposure product; not an edge |
| SPMO/GLD 50/50 | ✓: independent ledger | ✗: post-hoc | — | edge over control ✗ (2023–25) | vs SPY/GLD ✗ | registered; first decision 2026-10-01 | ✗ | Benchmark allocation |
| Month-end rebalancing R2/R3 | ✓ | ✓ | ✗: 0.63 / 0.45 | 2008/2020-dependent; dies with a 1-day lag | gross effect real, net ✗ | — | ✗ | The only persistent *gross* effect in the record |
| LETF close flow | ✓ | ✓ (failed gate) | locked | monotone dose-response | — | forward-only spec not yet registered | ✗ | Forward-only idea |
| Macro-surprise rotation | ✓ | ✓ (−0.50) | locked | — | bounded null | — | — | Dead |

No candidate clears layers 2 through 5 together. Nothing is close to layer 7.

### Methodology changes registered this cycle

- `research/PROTOCOL_AMENDMENT_2026-09-23.md`:
  - 1.8/√T and 2.4/√T dev gates;
  - active-return gating for long books;
  - P(pass | null) reported with every result;
  - random-selection placebos for any selection claim;
  - the corrected-data re-measurement rule;
  - forward evidence counted only through the anchored registry.
- `reports/future_lab/monitoring_rule_spec.json`: kill/revert/promote rule, registered before any
  forward data.

### Highest-value next moves

1. **User, now, costs nothing: make forward evidence real.**
   - Anchor the registry head (git push or email).
   - Run `research.forward.record --strategy momentum_gold_v1 --date 2026-10-01` in the 10-01
     post-close window, then anchor again.
   - Decide PEAD's entry convention as pead_bot_v2 (decide before the close, or fill at the next
     open), and register it.
   - Run zero-capital random-selection shadow books alongside it. That makes PEAD's forward test a
     kill test against P1, not a test against SPY.
2. **User, ~$500–1,100: buy Sharadar, optionally ORATS.** Then, in order:
   - run the acceptance tests;
   - re-measure the frozen fundamentals and momentum dev results on delisted-inclusive data (audits);
   - run one pre-registered validation of frozen option specs on 2007–2014, which the project has
     never viewed.
3. **Research, next cycle: new information, not new constructions.**
   - Candidates:
     - forward-collected borrow fees;
     - FINRA short interest with publication dates;
     - 13F changes;
     - option open interest (with ORATS).
   - Each gets a pre-registration under the new gates, a null-lab calibration and a placebo control.
   - Expect most to fail. A candidate reaches layer 6 only through the registry.

---

## Cycle 3: research-organization run (2026-09-23, 23:00–23:50 PDT)

Appended by the director; the sections above are unchanged. Three workstreams ran in parallel, with subagents doing
the scouting, implementation, audits and labs, and the director writing hypotheses, registrations, interpretation and
synthesis.

### Ex-ante rankings (written before any return; from scout outputs `data/scout_A`, `data/scout_B`)

**A. Structural risk premia**

| Rank | Candidate | Decision |
|---|---|---|
| 1 | Commodity roll / term structure via same-commodity ETF pairs (no contract curves on LSE or yfinance) | **Tested (A1)** |
| 2 | MBS negative-convexity premium (MBB vs PIT Treasury hedge) | **Tested (A2)** |
| 3 | Treasury betting-against-beta (SHY vs IEF) | Rejected: the parallel session already saw its 2003–14 Sharpes |
| 4 | EM local-currency bond carry (EMLC, 2010+) | Deferred: short sample, no EM short rates |
| 5 | Credit rating/term premium | Deferred: index-only history, legs not tradable |
| 6 | CurrencyShares FX carry | Redundant: G10 carry is spent |

**B. Market structure / information flow**

| Rank | Candidate | Decision |
|---|---|---|
| 1 | Month-end index extension in non-Treasury bond ETFs (LQD/MBB/TIP), rate-hedged | **Tested (B1)** |
| 2 | Month-end FX hedge-rebalancing flow (Melvin–Prins) | **Tested (B2)**: a forced flow, preferred over information timing |
| 3 | FOMC-cycle equity returns | Deferred: heavily published |
| 4 | Quarter-end USD funding pressure | Deferred |
| 5 | OpEx-week pinning | Deferred: no open interest |
| 6 | Bond-ETF ex-dividend flows | Dropped: ex-dates fall on day 1 of the month |

### Results

| Family | Development | Audit | Validation | Status |
|---|---|---|---|---|
| A1 commodity_roll | **PASS** 0.596 (gate 0.557, p 0.0064) | **WEAKENED** | **FAIL** 0.21 vs 0.75; p 0.24; V1/V4/V5 fail | SPENT |
| A2 mbs_convexity | FAIL 0.40 vs 0.61, p 0.043 | — | locked | SPENT |
| B1 sector_month_end | FAIL: active −0.43; stress −3.1%/yr | — | locked | SPENT |
| B2 fx_hedge_rebal | FAIL 0.09 vs 0.72, permutation p 0.18 | — | locked | SPENT |

**A1 audit detail.**
- The director's front-basket hedge test (alpha t 1.04) was biased; the auditor corrected it. The spot-hedged alpha
  was 7.2%/yr (t 3.09), but the tradable pure-roll version was t 1.6.
- The stricter binding criteria V1–V6 were frozen in code and registered before unlock (23:38:11).
- Validation result: 2020 super-contango +34%; ex-2020 Sharpe −0.10; 2026 −19.5% as crude backwardated.
- The spot-hedged alpha stayed positive (6.6%/yr, t 1.87), mostly natgas (t 3.2). That is **post hoc and not a
  candidate**.

**tsy_month_end (existing, re-audited).** An independent adversarial audit rates it **WEAKENED**:
- the result reproduces from independent code and LSE closes, and the yield move is real;
- but the rule was published in 2019. Post-publication active Sharpe is 0.56 (p 0.059), and the last 36 months 0.25;
- the combined p was never pre-registered;
- the open-to-open execution test cuts the validation window return from 30.6 to 17 bp (t 1.5).

It stays FORWARD OBSERVATION. The earlier "strongest evidence" and "survives multiple testing" claims are withdrawn
([addendum](../reports/tsy_month_end/ADDENDUM_AUDIT_2026-09-23.md)).

### Workstream C: the certification lab

- **C1 gate consistency** (`reports/null_lab2/`):
  - 35 families and 91 gate-evaluable candidates; 198 trials estimated in total (182–215), not about 111;
  - the old flat 0.5 gate false-passes 12.3% at zero net mean; the post-amendment gates 2.6–5.1%;
  - 16 dev passes vs 11.1 expected under the null;
  - **no gate in the registry has even 35% joint power at a true Sharpe of 0.7**;
  - flags: the null in `sector_month_end` and `fx_news` is not mean-zero; `letf_rebalancing` L2 was bypassed after
    failing its gate.
- **C2 promotion guards and trust scorecard** (`research/certify/`, `reports/certify/`):
  - guards G1–G7, 20 tests;
  - `tsy_month_end` fails G3 (60% of P&L in the top 5% of months) and G6 (post-publication t 1.55);
  - `commodity_roll` failed G1 and G3 already in development;
  - under the guards, **nothing is promotable**.
- **C3 forward-infrastructure audit** (`research/forward_audit/`): `tsy_month_end_v1` is registered in the
  hash-chained registry (seq 2, head `0f2c2c1d…`).
  - The forward price path uses LSE 30-minute regular-session bars and yfinance official closes, so it is immune to
    the partial-day TLT parquet row the audit found.
- **C4 alternate-futures v2** (`reports/future_lab2/`): explicit null / pre-publication / post-publication / decay /
  regime / cost worlds.
  - For `tsy_month_end_v1`, 80% power needs 6 years if the pre-publication strength returns, but **23.5 years** at
    post-publication strength.
  - For momentum_gold_v1 vs its control: 14.5–113 years.
  - The frozen Bayesian rule never fires `kill_sharpe` or `revert` for SPMO/GLD; only the drawdown kill works.
  - An SPRT kill/confirm rule for `tsy_month_end_v1` is now **registered** (23:42:15).
- **Protocol amendment 2** (registered 23:45:46): mean-zero nulls, workstream-batch Bonferroni, gated same-null
  P(pass | null), power disclosure, and guards G1–G7 required before any promotion.

### Trust scorecard after cycle 3 (L0 mechanism … L8 clean forward)

| Candidate | Mechanism | Dev | Null | Placebo | Validation | Audit | Alt. data | Post-publication | Forward | Standing |
|---|---|---|---|---|---|---|---|---|---|---|
| tsy_month_end | ✓ | ✓ | ✓ | ✓ | ✗ (0.69 vs 0.75) | weakened | ✓ (LSE) | ✗ (t 1.3–1.55) | registered, no data yet | Forward observation, no capital |
| commodity_roll | ✓ | ✓ | ✓ | partial | ✗ (0.21) | weakened | — | — | — | Spent |
| SPMO/GLD | benchmark | post hoc | — | — | — | beta/gold | ✓ | — | first decision 10-01 | Benchmark allocation |
| PEAD | ✗ | ✗ | — | ✗ | ✗ | ✗ | — | ✗ | ✗ | Not an edge |

**Record:** 0 of 11 development passes have validated. Nothing clears the promotion guards.

### What this means

1. **Portfolio.** No change: there is still no validated edge to add.
   - SPMO/GLD 50/50 remains a benchmark allocation. Its evidence is diversification and beta, not selection.
   - `tsy_month_end` is at most a future overlay candidate: invested about 14% of the time, equity-independent,
     cheap. It needs forward CONFIRM under the registered SPRT, then the guards, then a user decision. On the C4
     numbers that will take years, not months.
2. **The method is working as designed.** A plausible premium passed development, survived a hostile audit with a
   partial correction, had stricter criteria frozen before unlock, and still failed a truly locked window.
3. **The binding constraint is power, not ideas.** With 10-year windows and Sharpe 0.3–0.7 edges, the pipeline can
   neither certify nor reliably kill moderate edges. Future work needs more independent information per year: more
   assets per hypothesis, cross-sectional breadth, or genuinely new data. Longer backtests of the same price
   histories do not help.

### Data frontier (no purchases made)

- **EIA NYMEX futures, contracts 1–4** (free; crude from 1983, natgas from 1994; availability not re-verified in this
  session). This is the only free source of curve slope history that predates the ETF era (pre-2006). The commodity
  roll family is SPENT, so any curve work must be a new, distinct registration, carrying a multiple-testing charge and
  knowledge of the ETF result.
- **Breadth-increasing new information** (from the cycle-2 list):
  - forward-collected borrow fees;
  - FINRA short interest with publication dates;
  - 13F changes;
  - option open interest (needs ORATS; the user's decision).
- **Sharadar** (about $500/yr) remains the fix for survivorship. It is not required for the ETF and macro work done
  here.

### Next three tasks

1. **User (forward evidence).**
   - Anchor the registry head, seq 2 `0f2c2c1d…`, by git push or email; this is the user's action.
   - Record the `tsy_month_end_v1` entry after the 2026-09-24 close, and before the 2026-09-25 close
     (`{"TLT": 1.0}`).
   - Record the exit on 2026-09-30.
   - Record momentum_gold_v1 in the 2026-10-01 post-close window.
   - Anchor again after each record.
2. **Research (power first).** Before the next hypothesis, build the N5 power calculator into the PLAN template.
   Prefer designs with cross-sectional breadth (many assets or events per year) that reach ≥ 50% joint power at a
   Sharpe of 0.7.
3. **Research (new information).** Scout and register one breadth-rich, genuinely new-information hypothesis under
   amendment 2. Candidates: FINRA short-interest changes with publication-date timing on the liquid universe, or an
   EIA curve-slope test in the unviewed pre-2006 window as a new registration. It gets an independent audit if it
   passes development.

---

## Cycle 4: power first, new information (2026-09-24/25)

Reports: `reports/{power,trial_accounting,lse_breadth_scout,edgar_scout,public_scout,event_scout,xsec_scout,survivorship_audit,eia_futures,tsy_auction_demand,crypto_funding_xs}/REPORT.md`
and `reports/forward/CYCLE4_FORWARD_ACTIONS_2026-09-24.md`.

**Forward evidence.**
- tsy_month_end_v1's September entry was recorded at seq 3, 2026-09-25 04:58Z. It executes at the 9-25 close;
  market_asof was 9-24 and final. Head: `04dff2c7…`.
- The exit record (9-30, after the 9-29 close) and momentum_gold_v1 (10-01 post-close) are prepared, not recorded.

**Main finding: power.**
- The fixed 0.75 validation gate cannot reach 50% power at a true Sharpe of 0.7, for any window length.
- At a fixed net Sharpe, breadth does not add power; only years do. Breadth raises the Sharpe that a given per-bet edge
  can reach.
- Past families had 21–32% joint power, so their validation FAILs were the expected result even for real edges.
- Amendment 3 makes the power check binding and replaces the 0.75 gate with the size-calibrated, most-powerful test
  (p < 0.05/k_val, stress > 0, Sharpe ≥ 0.3).

**Frontier.**
- About 60 datasets and families were examined across LSE, SEC/EDGAR, FINRA, CFTC, Binance, Treasury, EIA,
  Wikipedia, OECD/BIS, and the event families.
- New free sources verified:
  - Binance archive, with delisted contracts retained;
  - FINRA Reg SHO daily files from 2018-08, and bulk short interest;
  - Treasury auction results;
  - EIA NYMEX contracts 1–4, 1983–2024 (quarantined, never viewed);
  - EDGAR acceptance timestamps;
  - LSE declaration-dated dividends, which include delisted payers.
- **Binding constraints:**
  - there are no free delisted US stock prices, so US cross-sections are survivor-biased;
  - US anomaly knowledge is contaminated by the OSAP graveyard;
  - most cross-sections have an effective breadth of about 20–30.

**Experiments (batch k = 2).**
- **E2, Treasury auction demand:** DECISIVE design; clean dev FAIL (−0.42). An informative null.
- **E1, crypto funding cross-section:** dev Sharpe 1.65 against the 1.22 gate, but bootstrap p 0.038 against 0.025,
  so FAIL. It is one-year dependent (2021), and its validation is locked and unviewed.
- **No survivor.**

**Highest-power next directions.**
1. **Forward-only registration of the frozen E1 rule** (the user's decision). It gives about 1,100 new daily
   observations per 3 years, and is the only honest route for this family. Jurisdiction flag: Binance is not
   available to US persons.
2. **Long-history, many-market designs** with genuinely new information. Under amendment 3 this is the only way to
   be DECISIVE at Sharpe 0.5–0.7: more than 20 years in each window.
3. **If the user ever buys delisted-inclusive equity data:** the FINRA short-volume and EDGAR 8-K designs become
   testable without survivorship. Even then, at realistic turnover their power is MARGINAL at best.

---

## Cycle 5: evidence quality (2026-09-25)

**Power framework.**
- Two independent audits: `reports/power_audit_a1`, `reports/power_audit_a2`.
- Amendment 3's size control is sound on correctly gated series, and section 7 reproduces within 1.3 pp.
- **Flaws found:**
  - long-only books gated on raw returns;
  - HAC-t and block-bootstrap oversizing on monthly, short or skewed series;
  - an inert stress leg;
  - D < 1 inputs;
  - breadth-parameter semantics;
  - k_val;
  - the prior.
- Amendment 4 is PROPOSED; it needs the user's approval.
- The 54th Monte Carlo check: +1.1 pp is a real correlated-inclusion bias, and about 2 pp is simulation noise.

**Data.**
- **Crypto:** survivor-free archives exist on Binance and Bybit (2020+) and BitMEX (2014+). Free contract-level
  futures curves exist only for crypto (Binance, Deribit, BitMEX).
- **Free survivor-free US equity returns:** not possible. The universe can be rebuilt; prices for delisted names
  cannot.
- **Collectors:** 8 built, at about 11.6 MB/day; not scheduled.
- **Binance archive:** a completeness defect was found and fixed.

**Crypto funding.**
- Corrected-data development PASS, with two audits returning SURVIVES and WEAKENED.
- Bybit 2020–22 is not an independent replication, and 2023–26 on any venue is locked.
- A forward-only protocol is prepared but not registered; it needs a dynamic-universe adapter and the user's approval.

**New experiments.** One run, `pd_inventory` (DECISIVE): FAIL. About 20 structural families were assessed; all
crypto structural families are INCAPABLE for lack of years.

**Next.**
1. The user decides on amendment 4 and the crypto validation: park it, or a one-shot closure test.
2. Schedule the collectors.
3. Build the dynamic-universe forward adapter and register forward-only crypto observation if wanted.
