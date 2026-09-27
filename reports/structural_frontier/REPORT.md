# Structural-return frontier: three preregistered development tests

2026-09-23. The [ranked map](../../research/structural_frontier/RANKING_2026-09-23.md) and [single frozen plan](../../research/structural_frontier/PLAN.md) preceded every candidate/control return. The plan's registered SHA-256 is `ee99196aa672009171c999d4aba36028fb2238ae23feabca6dbacd12c9aab186`. Development code refused an unregistered or modified plan. No validation input was used in a strategy calculation. No trading, paid data, production change, commit or push.

## LSE feasibility findings

Live LSE Terminal/MCP provided 2010+ USD credit-index levels, decades of date-level Treasury yields, and historical TLT OPRA option trade prints. The TLT archive pull has 1,067,797 contract-days across 2,163 dates; every one of the 102 preregistered monthly development decisions had a next-month put with **prior-day volume ≥100** and a next-session print. Selected contract prior-day volume had median 613; entry strike/spot moneyness had median +0.04% (range −3.61% to +2.09%, reflecting next-day moves). The option close is a last trade, without bid/ask or a precise print time. A numeric option result therefore has execution uncertainty even with the plan's spread stress. LSE continuous futures charts are not historical contract curves: commodity futures roll/convenience yield cannot be honestly inferred from `GC.F` alone. Contract searches for `GCZ26`, `CLZ26` and `ESZ26` returned no instruments; direct `get_history` on `GCZ26` and `CLZ26` returned 404. The other 68-symbol futures set mostly starts in 2025–26. G10 spot-week forwards exist from 2015; EM forwards needed for untested EM carry do not.

## Development outcomes

The gate was the project's strict active Sharpe ≥ `1.8/√T`, positive stress-cost active mean, and a one-sided centered-block p-value **< 0.0167** for three planned independent families. Credit also had to beat a fixed equity-beta control; TLT puts had to beat bills. Null worlds use 5,000 paired, mean-centered circular block resamples (21 trading days for holdings, three cycles for puts). The observed bootstrap p-values were independently reproduced exactly by the existing `research.null_lab.gates.BootstrapP` implementation.

| Family and development | Candidate net mean / Sharpe | Primary investable control | Net active mean / Sharpe | Gate, p, stress | Verdict |
|---|---:|---:|---:|---:|---|
| **A: IEF vs SHY duration premium**, 2003–2014, 3,020 daily marks | 5.56% / 0.82 | SHY 2.25% / 1.40 | **+3.31% / 0.57** | Sharpe gate 0.520 **passes**; p=**0.0230** fails 0.0167; stress active mean +3.30% | **FAIL preregistered batch gate** |
| **B: HYG credit carry**, 2008–2016, 2,266 daily marks | 6.28% / 0.53 | 1/3 LQD + 2/3 SHY 2.84% / 0.83 | **+3.43% / 0.30** | Sharpe gate 0.600 fails; p=0.186; stress active mean +3.41% | **FAIL** |
| **C: monthly TLT put insurance**, June 2014–December 2022, 102 cycles | 2.66% / 0.34 | 50% TLT + bills 2.36% / 0.36 | **+0.30% / 0.07** | Sharpe gate 0.618 fails; p=0.427; stress active mean **−1.15%** | **FAIL** |

Here means are annualized arithmetic means, Sharpe is at daily frequency for A/B and cycle frequency for C, and the primary comparison is net candidate return minus the named control on identical dates. The bootstrap 95% intervals for annual active mean were A **+0.13% to +6.54%**, B **−4.33% to +10.94%**, C **−2.39% to +2.94%**. The 5,000 zero-premium worlds passed the **full** preregistered development gate in 1.64%, 1.64% and 1.60% of draws, respectively, with Monte-Carlo SE about 0.18 percentage points. Low null false-pass probability does not rescue a failed observed gate.

### What the controls expose

- **A** is the only moderate signal of a return source. It had +1.41%/year net mean over a fixed 1/3 TLT + 2/3 SHY duration barbell, and its active daily return correlated **−0.39** with SPY-minus-SHY. That could diversify equity risk, but it missed the declared three-test p threshold, and removal of its best 12 or 24 months reduced active Sharpe to **0.39 / 0.35**. Preserve this as suggestive measurement, **not** a validation-eligible component. Do not change the correction or test a nearby maturity now.
- **B** beat the fixed 25% SPY / 75% SHY control by 3.13%/year, but HYG-minus-bond-control still had SPY-minus-SHY beta **0.32** and correlation **+0.60**. Removing March 2009–March 2010 made its active annual mean **−0.89%** and Sharpe **−0.08**. This is not a robust standalone credit premium in the chosen window.
- **C** had positive mean option premium above bills (+1.85%/year), but only +0.30%/year beyond a 50%-TLT directional control. Assignment occurred in **52%** of cycles. The worst cycle entered 2022-09-19 and lost **10.5%** of collateral capital; higher spread stress erased the active mean. The lack of executable historical quotes would be an additional barrier even if the numeric gate had passed.

## Decision and next frontier

**No candidate survives the registered development gate; all three validation windows stay locked.** The result supports the user's strategic shift—risk premia can yield modest positive means—while showing why controls and execution are decisive. The highest-value untouched structural data would be **historical futures contracts by expiry, settlement and roll rule**, especially a diversified commodity curve panel. LSE currently exposes continuous charts rather than that contract panel. Verify whether the provider can expose it before testing convenience yield or producer hedging pressure; do not manufacture a curve from continuous prices. In the meantime, accumulate clean forward execution quotes for option-premium studies instead of fitting another print-based backtest.

Detailed immutable result files: [A](term_dev_results.json), [B](credit_dev_results.json), [C](option_dev_results.json), and [option cycle audit](option_dev_cycles.csv). Raw-source hashes are in each JSON and the LSE data manifests under `data/lse/structural_frontier/`.
