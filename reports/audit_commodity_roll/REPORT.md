# Adversarial audit: commodity_roll (A1), development window only

*Written by the independent adversarial-audit agent (2026-09-23). Saved to disk by the main (director) session because the harness blocks subagents from writing report files. Code: `research/audit_commodity_roll/`; numbers: files beside this report. The auditor loaded nothing after 2016-12-30.*

**Director's outcome (2026-09-23 23:38–23:45 PDT).** The recommended stricter criteria were frozen as `research/commodity_roll/validation_checks.py` and registered in `VALIDATION_UNLOCK.md`, and validation was then run once. It **FAILED** on the registered gate (Sharpe 0.21 vs 0.75) and on V1, V4 and V5. See `reports/commodity_roll/REPORT.md`.

**Verdict: WEAKENED.** The director's main red flag (alpha t 1.03 after the front-basket hedge) comes from a biased test. With roll-free spot proxies the book has a real term-structure alpha in dev: about 7%/yr, NW t 3.1. It is not a hidden bet on commodity prices falling. But the gate pass is fragile. The tradable beta-neutral "pure roll" version fails the gate. Half of the P&L comes from 6 crash/contango months. The pass also disappears if short financing costs more than about 1.4%/yr.

Nothing after 2016-12-30 was loaded. Every loader truncates at that date and asserts it, the FRED pulls used `coed=2016-12-30`, and the yfinance pulls used `end=2016-12-31`. No existing file was edited. The code is in `research/audit_commodity_roll/` and the numbers are in `reports/audit_commodity_roll/` (`summary.json` plus files `a_` to `e_`).

## Key numbers (DEV 2006-07-21 → 2016-12-30, base costs unless noted)

| Item | Value |
|---|---|
| Reproduction vs `dev_daily.csv` | exact (max daily diff 1e-16); Sharpe 0.596 vs gate 0.557 |
| Director front-basket regression | reproduced: β −0.248 (t −20.8), alpha 2.0%/yr (t 1.03), short-front-only Sharpe 0.600 |
| Book vs roll-free spot composite (monthly) | **alpha +7.2%/yr, NW t 3.09**; β −0.168 (t −8.6), R² 0.42 |
| Same, daily with lead/lag terms | alpha +7.4%/yr, t 3.65 |
| Spot-drift contribution | about −1%/yr (it hurt the book); a same-beta short-spot strategy has Sharpe −0.20 |
| **"Pure roll", vol-matched, tradable** | Sharpe 0.38 (rolling ratio) / 0.43 (full-sample ratio); **NW t 1.60 / 1.79**; residual spot β ≈ 0 |
| Beta-neutral, rolling 252-day beta | Sharpe 0.36, t 1.40 (residual β +0.07) |
| Up-spot / down-spot months | −0.70%/mo (t −3.4) / +1.88%/mo (t +7.4) |
| Top 5% of months (6) | 50% of P&L; without them, t 1.58 |
| Worst-decile spot months (13) | 59% of P&L |
| Leave-one-year-out | fails the gate without 2006, 2008 or 2015; without 2006 and 2008: Sharpe 0.36, t 1.41 |
| Spot alpha, subsamples | without 2006 and 2008: 5.4%/yr, t 2.43; 2010–16 only: 4.1%/yr, t 1.94 |
| Bootstrap p by block length | iid 0.026 · 5: 0.009 · **21: 0.0064 (lowest daily)** · 63: 0.018 · 126: 0.024 · stationary: 0.016 |
| Sign test, monthly | 73/125 positive, p 0.037 |
| Borrow that breaks the gate (10bp) | 1.42%/yr; with no short rebate, Sharpe 0.516 (fails) |
| Break-even per-side cost | 419bp (turnover is only 1.2–1.8× notional/yr) |
| Stress book bootstrap p | 0.12 |

## Attack results

**1. Reproduction.** My own code matches exactly. A rebuild from raw yfinance closes plus dividends gives Sharpe 0.597 (the difference is Yahoo's convention on DBC's dividend days). I found no second free vendor:
- Stooq returned a bot-check page, and I did not bypass it.
- The LSE Terminal has no candle data for USO, GSG or DBC.
- The `data/multiasset` copies of USO, UNG and DBC are the same Yahoo feed.

**2. Data integrity.**
- No daily move above 15% in any of the six ETFs.
- UNG's reverse splits (2011-03-09 1:2, 2012-02-22 1:4) and DBC's three distributions (2006–08) are handled correctly. No adjustment artefact creates return.
- No calendar mismatches between legs.
- Start dates: USL 2007-12-06, UNL 2010-01-04 (the fund listed in Nov 2009, but Yahoo data starts 2010-01-04).
- USL volume was very thin in 2008: median about $0.11M/day, 1,800 shares, 10 zero-volume days and stale runs (e.g. 2008-11-04/05). The crude pair's +18% in 2008 was earned in that market.
- UNL traded $0.09–0.65M/day, with 2 zero-volume rebalance days.
- Small-size fills near 10–30bp are plausible, but not at institutional size.
- Stale or noisy prints give the daily book lag-1 autocorrelation of −0.17 (variance ratio 0.53). The monthly Sharpe is 0.84 versus 0.60 daily, so the daily gate is conservative.

**3. Beta.**
- **Samuelson effect:**

  | Pair | Leg vols (long / short) | Monthly spot betas (long / short) | Net beta |
  |---|---|---|---|
  | Crude (USL/USO) | 30.7% / 36.3% | 0.82 / 0.96 | −0.14 |
  | Natgas (UNL/UNG) | 25.9% / 39.0% | 0.36 / 0.58 | −0.21 |
  | Broad (DBC/GSG) | 20.4% / 24.6% | 0.82 / 0.98 | −0.155 |

- The front ETFs bled roll yield: USO −14%/yr, UNG −24%/yr and GSG −8%/yr, while spot drift was about zero. So shorting the front basket is itself a roll-harvesting trade, and the director's hedge removes the premium being measured.
- Per-pair spot alphas (gross): crude 8.0%/yr (t 3.40), natgas 6.9%/yr (t 1.80), broad 6.7%/yr (t 2.86).
- The payoff is linear in spot, with no convexity (Henriksson–Merton down-leg t −0.10).
- Hedged on the long-leg basket instead: alpha 5.8%/yr, t 2.44 daily / 1.90 monthly.
- The tradable version is much weaker than the spot alpha. Offsetting the Samuelson beta means holding net-long front-fund exposure, which bleeds the same contango. Beta-neutral natgas is negative (Sharpe −0.41 gross).

**4. Concentration.** The best months are 2009-01/02/03 (super-contango), 2006-10, 2007-01 and 2015-01. The spot-hedged alpha is broader: it is positive in 9 of 11 years, and still t 2.95 after dropping the top 6 months.

**5. Broad-pair composition.**
- On sector proxies (2007 onward) the broad pair loads WTI −0.18, gold +0.07, base metals (DBB) +0.06 and ags (DBA) +0.10. That matches DBC being underweight energy relative to the GSCI. Alpha is still 5.0%/yr (t 3.16).
- A tilt factor raises R² from 0.27 to 0.41 but adds about −0.6%/yr to the mean. So the tilt adds noise, not return.
- In H2 2006, only the broad pair was live: DBC −1.2%, GSG −18.6%. That period is part tilt and part roll, and the book fails the gate without it.

**6. Costs.**
- Trading costs don't matter; financing does.
- Stress (30bp + 4%) mean is +3.1%/yr, but its p is 0.12.
- The high-low spread estimators are unusable here: Corwin–Schultz gives 26–86bp for USO, which is implausible.
- I couldn't verify historical borrow for USO, UNG or GSG.

**7. Null and placebo.**
- The p-value is below 0.025 for every block length tested, but the registered 21-day block gives the lowest daily p. The iid version (0.026) would fail.
- Across all 30 ordered ETF pairs, returns follow "short the fund with the worst contango". 1 of 27 non-registered pairs passes the gate (DBC–UNG). None of the 3 registered pairs passes on its own (0.47, 0.26, 0.49); only the averaged book does.
- A same-beta short on spot fails the gate (Sharpe −0.20).

**8. Literature.**
- Mou (2011) found index-roll front-running earned up to a 4.39 Sharpe in 2000–2010.
- Irwin, Sanders & Yan (2023) find that roll price impact disappeared after 2011.
- Bessembinder et al. (2016) found no predatory trading around USO's rolls.
- Academic term premia are 1–3%/yr (Szymanowska et al. 2014), well below the dev estimate.
- USL, UNL and DBC's optimum-yield index were launched specifically to avoid contango, and long-USL/short-USO was widely discussed from 2009.
- So the Mou roll-pressure mechanism the plan cites is largely arbitraged away. What remains is a storage/contango-regime return whose sign depends on the state of the futures curve.

## Recommendation on validation

I recommend unlocking validation, but only after registering an amendment first. The fair beta test supports a real dev component, and the audit found no bug or leak. Add these criteria before unlocking:
- **V1 (primary, binding):** regress the validation base book, monthly, on the matched roll-free spot composite as frozen in `b_beta.py` (FRED WTI spot, Henry Hub spot and the broad proxy). Require **alpha > 0 with NW(4) t ≥ 2.0**. If V1 fails, the result is a null even if the registered Sharpe gate passes.
- **V2:** the rolling-252-day vol-matched book (base costs, excess of cash) has mean > 0.
- **V3:** the book with no short rebate plus a 1% borrow fee has mean > 0.
- **V4:** the top 5% of months deliver less than 50% of validation P&L, and at least 2 of 3 pairs have positive spot-hedged alpha.
- **V5:** block-bootstrap p < 0.025 at both 21-day and 63-day blocks.

Two points to settle before unlocking:
- **USO's 2020 change.** From my general knowledge of USCF's filings (not checked in data), USO moved to multi-month holdings in April–May 2020. After that the crude short leg is no longer a front-month fund. Keep the registered pairs, but decide now to report pre- and post-May-2020 results descriptively.
- **Power is modest.** If the 2010–16 alpha (4.1%/yr) persists, V1 passes about 60% of the time. At an academic 2%/yr premium, it passes about 20%. The registered validation Sharpe gate of 0.75 is already above the dev result of 0.60.

## Limitations
- Only one price vendor (Yahoo), and no NAV or premium/discount data.
- Henry Hub spot is a noisy stand-in for gas futures, which weakens the natgas beta and probably overstates its alpha.
- About 37% of the broad proxy uses futures-based ETFs (DBB/DBA), and the GSCI weights are approximate fixed values.
- The spot-hedged alpha can't be traded directly, since spot oil and gas need physical storage.
- There is no borrow or spread history.
- Monthly regressions have n = 125.

Sources: [Mou 2011 (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1716841) · [Irwin, Sanders & Yan 2023](https://onlinelibrary.wiley.com/doi/abs/10.1002/aepp.13297) · [Bessembinder et al. 2016](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2026802) · [Szymanowska et al. 2014](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12096) · [Two Sigma, roll-return "tax"](https://www.twosigma.com/articles/the-commodity-futures-roll-return-tax-addressing-a-recent-headwind/) · [etf.com on contango and oil ETFs](https://www.etf.com/sections/news/what-contango-means-oil-etfs)