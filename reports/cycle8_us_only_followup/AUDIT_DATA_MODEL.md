# Independent frozen US1 model audit

Audited October 1, 2026; no frozen source/output files edited. Scope: research/cycle8_us_only/run.py, core.py, metrics.py, supplement.py, preregistration and saved results. Small synthetic examples were run using the existing virtual environment. This is an audit of implementation, not a newly optimized portfolio study.

## Confirmed accounting bug: liquidation can leave negative wealth without recording ruin

In core.simulate, insolvency is checked before margin_call, but not after liquidation costs. A near-insolvent account can lose its last equity to the declared 1% liquidation haircut. Reproduction: one funded asset, leverage 2, two steps with returns [0, -0.499], zero carry/costs otherwise, rebalance only at inception. Output wealth is [1, 1, -0.00802], calls=1, ruined=False. The next rebalance can reset negative positions because alive remains true. This violates the absorbing-ruin convention and can produce drawdowns exceeding 100%. Fix in a new engine: check E<=0 again after liquidation, record ruin, zero positions and loan, and cap limited-liability wealth at zero. If broker debt liability is modeled instead, explicitly record the deficit and do not permit reinvestment. No claim is made that this synthetic edge case occurred in the saved winning rows; it can matter in bootstrapped tail paths and P7 stress.

## Confirmed reporting/metric inconsistency: cash Sharpe is not undefined in saved output

The report and preregistration say cash against identical cash has undefined Sharpe. In hist, 10bp entry and exit costs are inserted only into the first/last monthly returns. P8@1 therefore has nonzero excess-return variance and evades stat's degeneracy test. Saved output gives Sharpe -0.189832 and 95% interval [-0.222281,-0.102109], driven by two deterministic transaction-cost dates rather than cash risk. P8 is explicitly excluded from selection, so this does not alter the current winner. Report the cash Sharpe as NA by instrument identity, separately report conversion costs, or clearly label the ratio as a finite-horizon cash implementation statistic. Levered cash is different: its negative spread produces a legitimate financing-loss diagnostic.

## Confirmed helper bug: incomplete crisis end can pass

metrics.crisis_table checks the first date and NaNs, but not the last required date or the full monthly calendar. A one-row series containing only February 2020 at -10% is reported as a complete 2020 COVID result even though March is absent. Correctness requires an exact required monthly index and full endpoint coverage. Existing menu inception patterns generally make unavailable early crises fail the start check; this finding is about the incomplete-window safety gate, not proof of a wrong saved COVID row.

## Material approximation: daily historical paths are changed using month-end information

hist.spread shifts every daily log return so each sleeve matches its monthly source. The weights use lagged information, so this is not lookahead in P5's trading signal. It is nonetheless a synthetic risk path: month-end information changes earlier daily values, which affect margin checks and liquidation. Example raw daily [+10%, -10%] with a declared flat month becomes [+10.55416%, -9.54660%]. Missing trend/gold paths are flat daily compounds by construction. Consequently daily drawdown/margin counts are approximate, not observations of an implementable path. The existing report discloses this limitation. Monthly bootstrap also checks maintenance only at month-end and cannot establish daily solvency. A stronger follow-up should use unmodified observed daily sleeves where available, and keep monthly-only and daily-tested results distinct.

## CAD financed overlay translation is approximate in a consequential way

cad_finance applies X_day * (1+daily FX change). For overlay notionals fixed at the beginning of the month, USD P&L translated into CAD must use current FX divided by month-start FX, not just the one-day change. Example FX rises 10% on day 1, is flat on day 2, and overlay earns 10% on day 2: correct translated P&L is 11% of the initial CAD notional; implemented expression gives 10%. This concerns the CAD-financing sensitivity, not the primary USD-financed account translated at final wealth. The code flags an approximation, but it does not quantify this error.

## Forward selection interpretation must remain explicit

run.main's model_eligible flags use historical breach probability and historical point Sharpe in both currencies. The report separately applies the forward breach test. There is no forward Sharpe>=forward 60/40 test. This is preregistered and disclosed, so it is not an accidental code deviation; it is a narrower answer than a forward joint Sharpe-and-drawdown mandate. The saved P3@1 forward 50% breach probability is 2.65%; P4@1 0.83%; P4@1.25 8.28%; P6a@1 35.96%. Historical and future Sharpe comparisons should not be conflated. A4 intervals are diagnostic individual Sharpe intervals; overlapping/nonoverlapping intervals do not supply a paired noninferiority test.

## Checks that passed

- Joint bootstrap uses a single stationary index tensor to sample each portfolio's funded sleeves, overlays, rates and FX together. I found no independent-asset sampling error. Different coverage windows intentionally imply different calendar samples.
- P5 weights exclude the current return. Cumulative-sum variance for rows t-36 through t-1 agrees with pandas rolling(36).std().shift(1), maximum absolute weight difference 2.72e-15 on the saved data. No P5 lag bug found.
- The historical Sharpe hurdle uses P3@1 reindexed to the portfolio's available months and converted with the same FX/risk-free series. P3@1 equals its own hurdle in both currencies.
- Forward sleeve fee handling for the main E/B/G/T menu subtracts one fee and treats trend assumptions as already net of the declared implementation drag. Real RSST mapping includes a deliberately conservative extra fee allowance disclosed in code/report.

## Unresolved data limitations remain material

AQR is monthly 1985–May2026; no actual 1970s trend path. Pre-GLD gold is a monthly average in frozen US1. IEF proxy is a ten-year par bond: saved overlap tracking error 1.37%/yr and proxy CAGR 2.795% versus IEF 3.484%. TMF proxy tracking error 8.843%/yr and proxy CAGR -2.812% versus actual -5.493%. These are not interchangeable histories. DBMF/KMLM correlations to trend are only .601/.655 and tracking errors about 11.34%/10.78% annual. Official auction provenance remains unverified. No recalibration to improve these overlaps was attempted.
