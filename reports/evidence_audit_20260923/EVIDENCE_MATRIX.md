# Trust evidence matrix — repository snapshot, 2026-09-23

This is a factual status map, not a numerical score. `Y` means demonstrated, `N` means failed or absent, `?` means not established, `L` means legitimately locked. A historical backtest or simulated future is never counted as a genuine forward observation. The canonical details remain in each named report and registered plan. Concurrent research can change a row after this snapshot.

| Candidate / family | Implementation audited | Preregistered | Development | Appropriate control | Null world | Validation | Alternate future | Genuine forward | Known contamination / classification |
|---|---|---|---|---|---|---|---|---|---|
| Treasury duration IEF−SHY | Y, independently replicated | Y | Sharpe gate Y; batch p N | SHY Y; duration barbell diagnostic | p=.023 > .0167 | L | Year-block 3/5y stress; losses possible | N | **Suggestive, failed dev gate**; duration exposure |
| Commodity deferred-vs-front ETF pairs | Y; independent audit reproduced returns exactly | Y | **Provisional pass** (SR .596, p=.0064) | Dollar-neutral; spot/beta attribution weakens mechanism | Reported P(pass|null)=.006; tail-null caution | L pending decision | ? | N | 59% P&L in worst-decile spot months; no short rebate or ~1.4% borrow makes Sharpe gate fail; **weakened, not certified** |
| Treasury month-end TLT | Y; independent adversarial audit complete | Y | Y (active SR .66) | Exposure-matched TLT | shift p=.006 | **N** (.69 < .75) | ? | N | Exact rule was published in 2019; post-publication active SR .56, shift p=.059; forward observation only |
| SPMO/GLD benchmark | Y | Forward paper spec Y | Retrospective selection | SPY/GLD advantage weak | ? | N | ? | N | Regime and selection dependence; benchmark only |
| PEAD production model | Trade-replay and placebo audit Y | Y for placebo | historical raw Sharpe .70 | **N**, random selection p=.113 | Y, failed selection claim | Earlier pre-reg test failed | ? | **N**, decisions post fill/backfill | Event exposure product, not demonstrated edge |
| High-yield credit carry | Y | Y | N (active SR .30) | Duration/equity alternatives | p=.186 | L | ? | N | 2009 contribution, equity correlation .60; spent |
| TLT monthly put insurance | Y on prints; execution quotes absent | Y | N (active SR .07) | 50% TLT/bills | p=.427 | L | ? | N | Quote/time/assignment uncertainty; spent |
| SPY monthly put writing | Y on prints | Y | N (active SR −.05) | 0.5×SPY | p=.56 | L | ? | N | Beta explains raw return; spent |
| Bond ETF basis liquidity | Y | Y | N (active SR .34) | Exposure-matched, own reversal | shift p=.10 | L | ? | N | HY/2014/16 concentration; spent |
| Agency MBS convexity | Y in concurrent trial | Y | N (SR .40 < .61) | Rate-matched hedge | p=.043 > .025 | L | ? | N | Distinct risk, failed gate |
| Credit→SPY lead/gate | Y | Y | N | Matched exposure/own trend | shift nulls fail | L | ? | N | Directional family spent |
| Index option-volume timing | Y on prints | Y | N | Matched static mix | shift null fails | L | ? | N | Prints not quotes; spent |
| COT / hedging pressure | Y on ETF proxy | Y | N | Costed commodity ETF basket | ? | L | ? | N | Continuous futures unavailable; spent ETF proxy |
| G10 FX carry / carry-to-IV | Y | Y | N | Plain carry comparator | ? | L | ? | N | G10 family spent; EM forwards unavailable |
| FX month-end hedge flow | Y in concurrent trial | Y | N (net SR .09) | USD-short window control | permutation planned | L | ? | N | Stress mean negative; spent |
| Sector month-end bond flow | Y in concurrent trial | Y | N (active SR −.43) | Rate/exposure matched | bootstrap p=.993 | L | ? | N | Mechanism transfer failed; spent |
| Ordinary/residual momentum and variants | Multiple audits | Y | Mixed | SPMO, equal-weight and factor controls | Multiple | N | ? | N | Closely related trials, selection/regime risk; spent |
| Macro surprise / policy / FX news continuation | Y | Y | N | Reaction/trend controls | permutations/shift nulls fail | L | ? | N | Directional signals spent |
| Japan→US flow | Y | Y | N | Matched controls | null fails | L | ? | N | Clean null; spent |

No row has validation pass, alternate-future robustness **and** genuine forward evidence. The commodity ETF result is a **provisional development candidate** whose independent audit reproduced it but materially weakened the claim; no validation outcome is inferred here.
