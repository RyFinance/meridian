# Audit: Treasury month-end index-extension book M (`tsy_month_end`)

*Written by the independent adversarial-audit agent (2026-09-23). Saved to disk by the main (director) session because the harness blocks subagents from writing report files. Code: `research/audit_tsy/`; outputs beside this file.*

**Verdict: WEAKENED.** The measurement is correct and does not depend on the price source. The pattern is real in Treasury yields. But the evidence is much thinner than the report says:
- the rule is a published, practitioner-known trade, and the dev window plus 2015–2019 lie inside or before the published samples;
- the only truly out-of-sample stretch is post-publication, and there the TLT book is not significant;
- the last 3 years are about zero.

The project's own "FAIL, forward observation only" status stands. The report's claims of "strongest evidence" and "survives project-wide multiple-testing correction" should be downgraded.

Everything below is a diagnostic of the frozen specification; nothing was re-specified. Scripts are in `/Users/rytty/CCP/quant_v7/research/audit_tsy/`, outputs in `/Users/rytty/CCP/quant_v7/reports/audit_tsy/`.

## 1. Independent re-implementation

My implementation (`common.py`, `a_reproduce.py`, `b_lse.py`) does not import the audited `core.py`.

| Source | Dev active Sharpe (base) | Val active Sharpe (base) |
|---|---:|---:|
| Project (reported) | 0.664 | 0.692 |
| My code, project prices | 0.664 (daily max diff 1e−16) | 0.692 |
| (a) yfinance raw close + dividends on ex-date, yfinance IRX | 0.664 (gross 0.764, stress 0.461) | 0.692 (gross 0.795, stress 0.486) |
| (b) LSE last regular-session trade (1h bars) | 0.837 on 2007–14 (official closes, same span: 0.833) | 0.713 (official: 0.692) |

- **Window return, project vs raw + dividends:** they never differ by more than 0.45 bp in any month.
- **LSE coverage:** 4,948 sessions, 2007-01 → 2026-09.
  - The LSE close is the last continuous trade, not the auction print.
  - Its difference from the official close has mean +0.07 bp, median absolute 1.1 bp, 99th percentile 13 bp.
  - On the last session of the month the mean is +0.34 bp.
- **Discrepancies:** none that matter.

## 2. Dividends and ex-dates

- **Where ex-dates fall:** of 282 ex-dates, 259 (92%) are on the first session of the next month, i.e. the session right after the window ends.
- **Ex-dates inside the window:** 7, all in December 2003–2009. The adjusted and raw-plus-dividend returns on ex-dates differ by at most 1.3 bp. On the sessions just before and just after an ex-date they differ by at most 0.02 bp. So there is no mis-applied adjustment at month boundaries.
- **Treating ex-dates as not held:** 0.65 / 0.69.
- **Raw price only (no dividends):** 0.74 / 0.77, so the effect does not come from dividend accounting.
- **Next session is an ex-date or not:** in development, windows followed by an ex-date earn 37 bp and the others 63 bp (n = 13). In validation it is 34 bp vs −9 bp (n = 12). The two periods point opposite ways, so there is no dividend-capture effect.

## 3. Close-price realism and execution (validation, bp per window)

| Execution | Dev 2007–14 | Val 2015–26 |
|---|---:|---:|
| Close → close (as specified) | 51.2 (t 3.2) | 30.6 (t 2.9) |
| Next open → last close | 47.3 (t 3.2) | 23.1 (t 2.3) |
| Close → next open after month-end | 46.4 (t 2.6) | 24.8 (t 2.0) |
| Next open → next open | 42.9 (t 2.6) | 17.0 (t 1.5) |

- **Auction vs last trade:** about 1 bp. The first after-hours bar vs the official close (2026 only, n = 128) differs by a median of 1.2 bp.
- **Fills:** a market-on-close / limit-on-close fill is realistic.
- **Execution risk:** in validation the edge depends on getting close-to-close fills. A one-session open lag removes 25–45% of it.

## 4. Concentration

- **Top 5% of months (7 of about 140):** they make 59% (dev) and 54% (val) of the active P&L. Without them, the monthly active Sharpe falls from 0.69 to 0.34 (dev) and from 0.78 to 0.42 (val).
- **But it is not only the tails:**
  - positive months: 87/144 (sign-test p 0.008) and 83/140 (p 0.017);
  - Wilcoxon p: 0.004 and 0.007;
  - median month: +29 bp and +31 bp.
- **Quarter-end vs other months:**
  - dev: 44.5 vs 34.9 bp;
  - val: **27.9 vs 28.6 bp**, so the quarter-end amplification did not replicate;
  - Feb/May/Aug/Nov (refunding months, a proxy for bigger index extension): 48 vs 33 (dev), 36 vs 25 (val). This mechanism proxy is directionally consistent.
- **Rate regime** (6-month change in the T-bill yield, dev / val):
  - hiking: 23 / 24 bp;
  - cutting: 20 / 35 bp;
  - flat: 48 / 28 bp;
  - development's strength comes from the flat, zero-rate years (t 3.6). No regime is significant on its own in validation.
- **Episodes:**
  - March 2020: window +1.0%, but the month's active was −0.1%.
  - 2022 is the best validation year (+7.1% active), driven by Jan, Feb, Mar, Jun and Sep. Dropping 2022 and 2018 leaves 0.55.
  - 2026: 5 of 8 windows negative, −3.4%.
- **Leave-one-year-out active Sharpe:** 0.54–0.74 (dev), 0.62–0.79 (val).

## 5. Hidden exposures (window excess return, bp; robust t)

- **SPY return in the same window:**
  - intercept 42.2 (t 3.6) dev, 29.8 (t 2.7) val;
  - slope negative, not significant.
  - TLT does earn more when SPY's window is down (69 vs 19 bp dev; 39 vs 20 val). That is the ordinary stock–bond correlation, not the source of the alpha.
- **VIX level and TLT's own trailing 21-session return:** R² ≤ 0.004; no exposure.
- **10-year yield, instrument-free** (LSE `bonds` US10Y, cross-checked against CBOE ^TNX; correlation 0.92–0.96):

| | Dev | Val | After Oct 2019 |
|---|---:|---:|---:|
| Window yield change vs the average 3-session change (LSE) | −1.7 bp (t −2.2) | −2.9 bp (t −4.2) | −3.1 bp (t −3.1) |

- **Timing caveat:** yields are date-level, fixed at a different time than TLT's 4 pm close.
- **TLT vs yields:** after controlling for the yield change, TLT's intercept is +14.8 bp (t 2.2) in dev and −7.7 bp (t −1.6) in val. In validation the TLT return is fully explained by the rate move, which fits IEF's stronger validation result (0.95).

## 6. Publication and decay

**Publication history:**
- Government-bond turn-of-month effect: Research in International Business and Finance, around 2009.
- Hartley & Schwarz, "Predictable End-of-Month Treasury Returns", SSRN August 2019. Sample 1990–2018; Sharpe about 1 for the last few days of the month; mechanism is insurer and benchmark buying on index-rebalancing dates.
- AllocateSmartly, 24 October 2019: **TLT, last three trading days, the exact rule tested here**, data since 1999.
- Month-end index-extension flows have long been standard practitioner knowledge.

**Consequence:** development (2003–14) and 2015–2019 are inside, or before, the published samples. Only the period from October 2019 is out of sample relative to discovery.

| Period | Window excess (bp) | Active Sharpe | Shift p | M excess Sharpe |
|---|---:|---:|---:|---:|
| 2003-01 → 2019-09 | 38.9 (t 4.2) | 0.73 | — | 0.87 |
| 2015-01 → 2019-09 | 41.0 (t 2.9) | 0.95 | — | 1.04 |
| **2019-10 → 2026-08** | **19.6 (t 1.3)** | **0.56** | **0.059** | **0.36** |
| 2023-09 → 2026-08 | 7.9 (t 0.4) | 0.25 | 0.28 | — |

- **Sub-periods (raw window / active):** 29/16, 47/36, 39/28, 18/26 bp.
- **Trend in active over time:** about zero (t 0.13).
- **Why active looks stable in 2021–26:** TLT's excess return was −10.3%/yr, and the active measure subtracts that drift. M's own excess Sharpe over 2021–26 was 0.31.
- **Where in the window the return comes from:** in development, the last session earned 24 bp; in validation, 10 bp (t 1.5), with the return shifted to the 3rd-to-last session. That is consistent with front-running, but not conclusive.

## 7. Multiple testing

- **Registered plans:** `preregistrations.jsonl` has 63 entries: 39 plans plus 24 amendments, unlocks or holdouts.
- **Trial counts:**
  - ledger: "~111", plus about 8 rows since;
  - unregistered exploratory batches:
    - return_search: 20 + 4;
    - edge_search: 8 and 15;
    - higher_sharpe: 37;
    - sleeve_blend: 37;
  - I have not verified which of these the "~111" already includes.
- **The claimed correction:** Fisher combination of shift-null p 0.006 and 0.005 gives 0.00034. Bonferroni ×120 gives 0.041; the break-even N is **146**. At N = 150 it is 0.051; at N = 200, 0.068.
- **Problems:**
  - The combined p was not pre-registered. It was introduced after the registered Sharpe gate failed.
  - Dev p alone ×120 is 0.72.
  - The project has run about 7 validation unlocks. The validation p of 0.005 × 7–12 gives 0.035–0.06.
  - Most importantly, because the rule came from the literature, the right correction is for publication selection. By that standard only the post-2019 sample counts as confirmation (p 0.059).
- **Independent shift-null re-run (2,000 draws):** dev p 0.0065, val p 0.0025. The project's p-values reproduce.

## 8. Data bugs

- **Duplicates:** none.
- **Missing sessions:** only the 6 unscheduled NYSE closures (2004-06-11, 2007-01-02, 2012-10-29/30, 2018-12-05, 2025-01-09); the data correctly has no prices on those days.
- **One stale price:** one window session, 2006-01-27, shows a zero return.
- **Short months:** none inside the windows.
- **Good Friday month-ends (2013-03, 2018-03, 2024-03):** the window ends on Thursday while the bond market is still open on Friday. These are a specification limit, not a bug; all three windows were positive.
- **One real pipeline bug, outside the windows:** the project's `data/multiasset/etf/TLT.parquet` last row, 2026-09-18, is a partial-day snapshot. It shows close 81.2256 and volume 23.2M against the official 81.25 and 41.1M. Forward recording must use official closes; the September window is set at the 9/25 close and closed at the 9/30 close.

## 9. Process notes

- **Timeline:** PLAN registered 22:31:39, dev results 22:31:41, unlock registered 22:32:42, validation 22:32:45.
- **Missing code:** the unlock's "adversarial checks", the deflated Sharpe, the Fisher p and the 5-year stationary bootstrap have no code under `research/tsy_month_end/`.
- **The figures I could re-check match:** quarter-end 44.5 vs 34.9 bp, alpha after SPY beta 42 bp, 7 in-window ex-dates.
- **Related follow-on trial:** `research/sector_month_end/PLAN.md` (LQD/MBB/TIP index extension) was registered at 23:16, after this result. It is a related trial, not independent corroboration.

## Bottom line

- It is a real, cheap, equity-independent, close-to-close pattern, visible in yields.
- As a TLT trade, it has not shown significant out-of-sample returns since publication, and it has been about zero for the last three years.
- Keep it as forward observation with no capital. Judge it only on data after 2026-09-24, with official closes.

Sources:
- [Hartley & Schwarz, Predictable End-of-Month Treasury Returns (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3440417)
- [Hartley & Schwarz, author PDF](https://www.kristaschwarz.com/EOM.pdf)
- [AllocateSmartly, Predictable End-of-Month Treasury ETF Returns (Oct 2019)](https://allocatesmartly.com/predictable-end-of-month-treasury-etf-returns/)
- [Turn-of-the-month and intramonth effects in government bond markets (RIBAF)](https://www.sciencedirect.com/science/article/abs/pii/S0275531909000178)
- [NY Fed Liberty Street, End-of-Month Liquidity in the Treasury Market (2024)](https://libertystreeteconomics.newyorkfed.org/2024/09/end-of-month-liquidity-in-the-treasury-market/)