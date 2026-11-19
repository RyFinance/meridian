# Gross-BTC mNAV dynamics: sealed daily long-only research result

## Verdict

**Narrow research pass, not a live-trading approval.** Three rules frozen using only the 2020-11-02 through 2022-12-30 development sample all produced positive, costed returns in the sealed 2023-01-03 through 2026-08-10 sample. M1 and M3 had higher full-period Sharpe and far lower drawdown than cost-matched MSTR buy-and-hold, though M1's absolute sealed return was slightly lower than buy-and-hold. The finding is therefore evidence for a **risk-managed timing candidate**, not proof of absolute alpha or an enterprise-mNAV edge.

No order was sent or proposed. The recommended next step is a forward, paper-only daily monitor after replacing the quarterly/stale proxy inputs with a fully auditable daily holdings/share-count feed and a continuous 16:00-ET BTC feed.

## Navigation note

The project knowledge graph and its wiki entry point were unavailable for this assignment, so this study used only targeted raw inputs and cached primary-source SEC filings. No project files outside this `agent_mnav` directory were changed.

## Data actually used

| Input | Use in this study | Audit trail |
|---|---|---|
| `../mstr_daily_yf.parquet` | Split-adjusted daily MSTR open and close. Study use: 2020-11-02–2026-08-10. | SHA-256 pinned in `FROZEN_RULES.json`. |
| `../../../../BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet` | Last BTC/USD quote no later than 16:00 America/New_York for each MSTR session. | SHA-256 pinned in `FROZEN_RULES.json`; no stale value was carried into the proxy. |
| 24 cached MSTR/Strategy 10-Q/10-K filings | Explicit BTC held and Class A/B cover-page share counts. The first usable observation is the 2020-10-27 10-Q and the last is the 2026-08-03 10-Q. | `ALL_SEC_OBSERVATIONS.csv` gives filing date, as-of date, numbers, accession, and direct SEC source URL. Original HTML and manifests are in `sec_source/`. |

The 2024 official 10-for-1 Class A/B split is sourced in the frozen specification from Strategy's [official announcement](https://www.strategy.com/press/microstrategy-announces-10-for-1-stock-split_07-11-2024). The raw SEC filing URLs for every observation are in `ALL_SEC_OBSERVATIONS.csv`; for example, the 2020 annual report explicitly reports the BTC holding history in [its SEC 10-K](https://www.sec.gov/Archives/edgar/data/1050446/000156459021005783/mstr-10k_20201231.htm).

### Proxy definition and limitations

The study uses the following **gross-BTC mNAV proxy**:

`MSTR close × (Class A shares + Class B shares, price-basis adjusted) / (BTC held × BTC/USD at or before 16:00 ET)`.

This is deliberately **not enterprise mNAV** and not company-reported mNAV. It excludes debt, preferred claims, cash, the software business, taxes, and other assets/liabilities. Class A and B shares are treated as equal economic claims while using the Class A market price; that is an explicit approximation. A Class-A-only diagnostic is reported below.

Each filing becomes available only at the close of the first MSTR session strictly after its filing date, even when the filing was earlier. The next session's open is the earliest execution. This avoids treating an after-close filing as intraday knowledge.

## Frozen rules and execution

The pre-validation specification is preserved in `FROZEN_RULES.json` (SHA-256 in `SEALED_RUN_MANIFEST.json`). Exactly three long/cash rules were frozen:

| Rule | Long after close when | Development rationale |
|---|---|---|
| M1 | 10-session log gross-proxy momentum > 0 **and** proxy > 50-session SMA | Best Sharpe in the small predeclared 3×3×3 trend grid. |
| M2 | 20-session log gross-proxy momentum > 0 **and** proxy > 50-session SMA | Adjacent setting; second-best development Sharpe. |
| M3 | M2 conditions **and** 20-session BTC log momentum > 0 | Conservative BTC-regime control; lower development drawdown. |

The decision is made after session `t` close and is filled at session `t+1` open. The portfolio is always either 100% MSTR or 100% cash; there are no shorts, leverage, borrow assumptions, or borrow costs.

Baseline cost model on every entry and exit:

- 3 bp adverse slippage each side.
- $0.005 per actual share commission each side.
- The historical price series is 10-for-1 split-adjusted, so pre-2024-08-08 commission is correctly represented as $0.0005 per split-adjusted pseudo-share.
- Any final position is liquidated at the last included open under the same costs.

`FROZEN_RULES_AMENDMENT_01.json` records a mechanical correction made before any sealed strategy result: the share multiplier follows the active report's **share-as-of date**, rather than the current trading date. Its filesystem timestamp is `2026-10-17T00:05:52-0700`, its reason and non-changes are embedded in the file, and its SHA-256 is pinned in `SEALED_RUN_MANIFEST.json`. That prevents the pre-split August 2024 filing from creating a false 90% proxy collapse after the split. It changes no rule, cost, source, or selection criterion.

## Development versus sealed validation

All values below are net of the baseline costs. “Return” is cumulative net return; buy-and-hold is entered and realized using the identical cost convention.

| Period | Strategy | Net return | CAGR | Annualized Sharpe | Max drawdown | Round trips | Time long |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development: 2020-11-02–2022-12-30 (545 sessions) | M1 | +119.3% | +43.9% | 0.93 | −40.9% | 16 | 24.8% |
|  | M2 | +109.5% | +40.9% | 0.89 | −43.7% | 12 | 26.4% |
|  | M3 | +30.0% | +12.9% | 0.50 | −30.8% | 16 | 14.5% |
|  | MSTR buy-and-hold | −20.8% | −10.3% | 0.43 | −88.8% | 1 | 100.0% |
| **Sealed: 2023-01-03–2026-08-10 (903 sessions)** | **M1** | **+534.2%** | **+67.0%** | **1.15** | **−47.0%** | **37** | **36.0%** |
|  | **M2** | **+316.1%** | **+48.6%** | **0.94** | **−50.6%** | **34** | **43.7%** |
|  | **M3** | **+392.5%** | **+55.7%** | **1.08** | **−44.0%** | **32** | **31.0%** |
|  | MSTR buy-and-hold | +582.3% | +70.5% | 1.05 | −84.5% | 1 | 100.0% |

The sealed period began with all three frozen signals flat, so it did not inherit an uncharged long position from development.

### Sealed calendar subperiods: net return

Each row is an independently realized calendar slice, using the causal prior-close state at the first open and its own end-of-slice exit cost.

| Strategy | 2023 | 2024 | 2025 | 2026 through Aug. 10 |
|---|---:|---:|---:|---:|
| M1 | +67.5% | +97.7% | +68.1% | +17.1% |
| M2 | +15.4% | +149.7% | +40.0% | +6.0% |
| M3 | +46.8% | +148.5% | +35.2% | +2.6% |
| MSTR buy-and-hold | +363.0% | +357.4% | −48.0% | −35.7% |

All three frozen rules are net-positive in each sealed calendar slice. That is stronger evidence than a single one-off OOS gain, though it is still one issuer and one market regime rather than a broad independent replication.

## Robustness and implementation checks

### Cost sensitivity (sealed period)

| Rule | Frictionless return | Baseline return | Double-cost return (6 bp/side + $0.01/share) |
|---|---:|---:|---:|
| M1 | +549.2% | +534.2% | +519.5% |
| M2 | +325.1% | +316.1% | +307.3% |
| M3 | +402.5% | +392.5% | +382.7% |

Returns remain positive under the higher-cost cases; the result is not a narrow 3 bp fill assumption.

### Adjacent-parameter diagnostic

The ten nearby trend settings in `SEALED_ADJACENT_PARAMETER_DIAGNOSTIC.csv` were evaluated only after the frozen test as a fragility diagnostic, not selected as new rules. All ten have positive sealed return (+42.0% to +605.0%). The result is not isolated to M1, but it is not parameter-invariant: the much slower 80-session trend variants are materially weaker (+42.0% without, +67.5% with the BTC gate). This is a reason to keep the conclusion cautious.

### BTC source gaps

The supplied 1-minute BTC cache lacks a valid 16:00-ET quote for 43 MSTR sessions: 2024-07-01–2024-07-31 (22 sessions) and 2024-12-02–2024-12-31 (21 sessions). No BTC quote was forward-filled or interpolated. The frozen rule holds the prior stance, still books every MSTR open-to-open return, and waits for actual rolling inputs before issuing a fresh signal.

The post-freeze diagnostic that instead exits during unavailable-BTC sessions is also positive (M1 +606.7%, M2 +363.7%, M3 +497.5%). It is **not** a replacement rule, but it indicates the frozen results do not depend on holding through those cache gaps.

### Share-class and split checks

The Class-A-only diagnostic remains close to the frozen A+B proxy result: M1 +562.0%, M2 +335.8%, and M3 +388.3% sealed net return. Thus the equal-economic-claim A+B approximation is not driving the conclusion.

The split sanity table confirms a sensible proxy across the August 2024 split: 1.951 on 2024-08-07 and 1.963 on 2024-08-08 under the corrected treatment. The incorrect trading-date-only treatment would have mechanically dropped it to 0.196. See `SPLIT_SANITY_CHECK.csv`.

Finally, the frictionless M1 event-driven execution engine equals the independent causal next-open return-vector calculation to 3.55e-15; see `VALIDATION_EXECUTION_AUDIT.json`.

## Recommendation

Treat M1 and M3 as **paper-trading candidates only**. They pass this limited OOS screen on net positivity, cost tolerance, multiple frozen variants, and risk reduction versus buy-and-hold. Do not characterize this as a validated enterprise-mNAV alpha, and do not allocate real capital yet:

1. Replace quarterly/stale count inputs with an audited dated feed of BTC purchases, common issuance, debt, and preferred claims; then test a genuine enterprise-value mNAV proxy.
2. Replace the BTC cache with a continuous independently verifiable 16:00-ET source before operational use; retain the fail-safe cash/hold behavior explicitly.
3. Forward paper trade without parameter changes and compare actual next-open fills, spread, and market impact against this 3 bp/$0.005 model.
4. Require another truly unseen interval before making any deployment decision. M1 does not beat buy-and-hold on absolute return over the current sealed window, even though it improves Sharpe and maximum drawdown.

## Reproducible artifacts

| Artifact | Purpose |
|---|---|
| `fetch_sec_sources.py`, `download_dev_filings.py`, `download_holdout_filings.py` | Cache and manifest primary SEC data. |
| `mnav_core.py` | Causal panel construction, split/commission mechanics, next-open simulator. |
| `dev_research.py`, `DEV_GRID.csv`, `DEV_AUDIT.json` | Development-only rule grid and boundary audit. |
| `FROZEN_RULES.json`, `FROZEN_RULES_AMENDMENT_01.json` | Immutable candidate/timing/cost specification and pre-result split clarification. |
| `validate_frozen.py`, `SEALED_RUN_MANIFEST.json`, `sealed_run.log` | Sealed run and reproducibility hashes. |
| `ALL_SEC_OBSERVATIONS.csv`, `SEALED_PANEL.parquet`, `SEALED_SIGNALS.parquet` | Input ledger, causal proxy panel, and frozen signals. |
| `DEV_VS_SEALED_SUMMARY.csv`, `SUBPERIOD_RESULTS.csv` | Headline and yearly metrics. |
| `SEALED_COST_SENSITIVITY.csv`, `SEALED_ADJACENT_PARAMETER_DIAGNOSTIC.csv`, `GAP_POLICY_SENSITIVITY.csv`, `SHARE_CLASS_SENSITIVITY.csv` | Robustness outputs. |
| `BTC_SOURCE_GAPS.csv`, `SPLIT_SANITY_CHECK.csv`, `VALIDATION_EXECUTION_AUDIT.json` | Data-quality, split, and execution verification. |
