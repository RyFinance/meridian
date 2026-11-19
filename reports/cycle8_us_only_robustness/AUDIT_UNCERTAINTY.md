# Independent audit: uncertainty around P3’s 3.71% breach estimate

Research only. Audit date: 2026-10-01. Frozen code, old reports, and old numerical results were not edited. No new portfolio, weight search, or leverage search is proposed.

## Finding

The persisted `reports/cycle8_us_only_followup/daily_risk.csv` reports **371 breaches in 10,000 paths: 3.71%** for P3 at 1x, under the C2 forward lens, for a daily-observed drawdown exceeding 50% in either USD or CAD over 20 years. The recorded 95% Wilson interval is **3.357%–4.099%**. This is simulation uncertainty conditional on one fitted historical distribution, one forward scenario, one 24-month mean block length, one horizon, and the existing daily reconstruction. It is not a 95% interval for the real-world breach probability. The threshold is strict `drawdown > 0.50`; the decision threshold remains `probability < 0.10`.

The same row gives USD-only 1.74%, CAD-only 2.90%, and either-currency 3.71%; the either event is the pathwise union, not the sum. Its monthly-observed probability is 2.60%. Daily observation raises estimated risk by 1.11 percentage points, or about 43% relative, already demonstrating meaningful model sensitivity that exceeds Monte Carlo uncertainty. Historical daily either-currency risk is 0.18%; the much larger forward value shows sensitivity to the assumed return drift.

## What the current computation establishes

`research/cycle8_us_only_followup/analyze.py:daily` samples 396 jointly indexed months, discards the first 36, and uses 240 subsequent months. Within-month daily shapes are carried jointly across funded assets and FX, with missing daily histories reconstructed by the frozen spreading method. The portfolio rebalances at each sampled month start; drawdowns are evaluated daily and at month ends. The fixed monthly arithmetic means are imposed before sampling; financing is 5% annual arithmetic and cash 3.5%. The FX mean log change is zero. P3 at 1x has no external borrowing; its margin spread assumptions consequently do not drive this particular result.

C2 consistently fits arithmetic means derived from the declared geometric scenarios using `g + variance/2 − fee`. It then forms overlay excess returns from the same transformed funded primitive minus cash. This repairs the original overlay inconsistency. Its implied geometric means need not equal the geometric inputs exactly: the moment conversion is a second-order approximation and the transformation also rescales variance. In persisted moment checks, P3 equity has arithmetic mean 6.53526% and implied geometric mean 5.43223%, versus its geometric input net of fee 5.4055%; bonds have arithmetic mean 4.36993% and implied geometric 4.12486%, versus input net of fee 4.10%. These small differences should remain visible, rather than labeling both conventions exact.

## Fixed sensitivity protocol, before additional results

Use the same P3 at 1x as the primary uncertainty subject; keep the original entire fixed menu unchanged for any parallel ranking. Do not select a favorable scenario, block length, seed, observation frequency, or horizon after results are available. Save a dated, hashed protocol before computing these additional scenarios.

Run **27 declared conditions**: three coherent forward scenarios × three mean block lengths × three horizons. This is an uncertainty diagnostic, not an allocation optimization:

| Parameter | Fixed values |
|---|---|
| Forward scenario | Original low / central / high, without changing the existing numerical inputs |
| Equity geometric, gross | 4.2% / 5.5% / 6.7% |
| Treasury geometric, gross | 3.7% / 4.25% / 4.8% |
| Gold geometric, gross, if menu comparison required | 2.0% / 3.0% / 5.5% |
| Trend geometric, net, if menu comparison required | 3.0% / 4.5% / 6.0% |
| Cash | 3.0% / 3.5% / 4.0% |
| External borrowing, where applicable | Scenario cash + frozen 1.5 percentage point spread |
| Mean stationary block length | 12 / 24 / 36 months |
| Evaluation horizon | 10 / 20 / 30 years |
| Observation | Daily, also report monthly from identical paths |
| Drawdown event | More than 25%, 35%, or 50%; USD, CAD, and pathwise either currency |
| Paths | 10,000 per scenario/block combination; fixed seed 20260928 |

For each scenario/block pair, draw one 30-year continuation (plus the unchanged 36-month discard) and use nested 10-, 20-, and 30-year prefixes. Use the same sampled index matrix across the three drift scenarios at a given block length. This makes differences attributable to assumptions rather than random resampling. Expected means, cash and financing must switch coherently with the scenario; do not alter only equity. For leveraged rows, lower cash means cheaper financing, so “low scenario” need not automatically be worst on every outcome. Report all results without assuming monotonicity across scenarios or block lengths. Horizon and drawdown-threshold probability monotonicity must hold on nested identical paths.

The existing `daily` function is hard-coded to 240 months and central means; a new supplemental implementation must parameterize those quantities, its CAGR exponent, and output field names together. Keep the frozen function intact. Preserve the same rebalancing, spread/fee assumptions, within-month joint paths and absorbing insolvency behavior. Check exact monthly reconstruction for every sleeve and FX, matching central 24-month/20-year result, and daily risk at least monthly risk on identical paths.

Report a 27-row table with breach counts, probability, Wilson Monte Carlo interval, median terminal CAGR, and margin/ruin counts. The three horizons are different questions, not observations to pool. Do not average providers, scenarios or horizons or assign probabilities to these scenario labels without a separate justified model. The min/max range is a **sensitivity envelope**, not a confidence interval.

## Decision wording and unresolved uncertainty

Keep 20 years as the primary predeclared decision horizon. A separate robust diagnostic may require every 20-year scenario/block combination’s upper Monte Carlo bound to remain below 10%; clearly distinguish that conservative diagnostic from the original point-probability screen. If any condition fails, say the central result passes but robustness is not established. Preserve the original Sharpe hurdle and state that it is a historical point-estimate requirement, not proof of future Sharpe superiority. P3 at 1x equals its benchmark by construction; its own Sharpe uncertainty does not imply proven positive forward excess return.

Even all 27 conditions passing would not establish a guaranteed 50% drawdown ceiling. The runs condition on the observed crisis inventory and frequency, retain historical dependence except for drift changes, and cannot manufacture missing crises. Blocks can truncate crises at boundaries; the expected number of new blocks over 20 years is about 20, 10, or 6.7 for the three block settings, but that is not an estimate of the number of independent economic regimes. Current CMAs describe roughly 5–15 years; applying their means unchanged for 20–30 years is a modeling extrapolation. Zero expected FX log drift, synthetic bond/close conventions, unreconstructed intraday movement, tax/distribution treatment, and policy/market regime changes remain structural risks outside Wilson intervals. An outer bootstrap of the historical source could quantify one kind of estimation uncertainty but would remain conditional on the same historical crisis inventory; do not silently interpret the proposed simple sensitivity envelope as that outer bootstrap.

Appropriate current conclusion: **“P3 at 1x has a 3.71% modeled daily 20-year chance of exceeding 50% drawdown in either currency under the central C2 assumptions. Monte Carlo error is small relative to unquantified parameter and model uncertainty. Low/central/high and clustering/horizon robustness must be reported before treating the central pass as durable.”**
