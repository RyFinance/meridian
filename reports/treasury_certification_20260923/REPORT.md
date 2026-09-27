# Treasury duration premium: independent development certification

2026-09-23. Two independent implementations, `research/treasury_certification_20260923/{replicate,certify}.py`, read the frozen ETF parquet files directly and do not import the earlier structural evaluator. Both predicate-filter to dates no later than 2014-12-31. The four input hashes match the registered result. `certify.py` also checks the source tag (`yfinance auto_adjust=True`), every calendar-year omission, best 12/24-month removal, and 21/63-session block alternate futures; output is `independent_replication.json`.

| Quantity | Independent reproduction | Frozen result |
|---|---:|---:|
| Common open-to-open intervals | 3,020 | 3,020 |
| IEF minus SHY annual active mean, after 3 bp entry/exit | 3.3060% | 3.3060% |
| Active Sharpe | 0.569318 | 0.569318 |
| Stress annual active mean, 9 bp entry/exit | 3.2960% | 3.2960% |
| Centered 21-session block p, 5,000 worlds | 0.0229954 | 0.0229954 |
| Correlation with SPY minus SHY | −0.388186 | −0.388186 |
| Annual excess over 1/3 TLT + 2/3 SHY monthly barbell | 1.4122% | 1.4122% |

The year-by-year contributions also reproduce exactly once open-to-open intervals are attributed to their entry date. The original best-24-month removal drops active Sharpe to 0.3495. The frozen batch threshold is p < 0.016667, so **development failed and validation stays locked**. The independently rebuilt monthly duration barbell leaves only 1.41% annual active mean; this stream is largely nominal-duration exposure, not an IEF-specific arbitrage.

The second implementation independently reproduces the 95% annual-mean block interval **+0.13% to +6.54%** and the original null-world full-gate false-pass estimate **1.64% ± 0.18%**. Removing calendar 2011 drops active Sharpe to **0.42**; removing both 2008 and 2011 drops it to **0.28**. This concentration does not change the frozen gate, but it reduces confidence in a persistent premium.

As a nonoptimizing alternate-future check, 10,000 paths sampled complete calendar-year blocks with replacement from the 2003–2014 development period. Active total return was negative in **19.0% of 3-year** and **11.2% of 5-year** paths; worst-decile active total returns were −3.1% and −1.1%. The 3-year and 5-year worst-decile max drawdowns were −11.4% and −14.3%. These are conditional stress scenarios, not new observations or evidence that the original p gate should be relaxed. Year-block sampling cannot create inflation/rate regimes absent in 2003–2014.

Independent 21- and 63-session circular-block scenarios agree on substantial uncertainty: only about **37% of 3-year** and **34% of 5-year** paths reach a 0.75 active Sharpe, before any bootstrap p requirement. These are simulated development-law futures, not validation probabilities.

Data and implementation limits: the parquet opens are Yahoo `auto_adjust=True` adjusted prices, incorporating distributions and vendor revisions. The first/last open costs are explicitly subtracted. The SHY control is given zero trading costs, making the active comparison conservative. No funding or leverage is assumed. The LSE yield series is an economic cross-check and does not drive execution or returns.
