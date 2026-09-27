## Crypto funding cross-section audit: WEAKENED, statistically and economically (not killed)

*Hostile statistical/economic audit of the corrected crypto_funding_xs dev result (cycle 5). Saved by the director session.*

The full-sample result does not come from any factor I could build, and it holds up against every multiplicity correction short of the whole-project count. But nearly all of it was earned in one 11-month bull run with a small universe (Jul 2020 – Jun 2021). Over the last 18 months of the sample, when the universe was full at 100 names as it will be in validation, it is flat: Sharpe 0.12, p 0.45. The frozen bootstrap also understates the uncertainty for this series, and capacity is only a few million dollars.

Nothing was computed for any date after 2022-12-31. My data loader reads only monthly files up to 2022-12, which reproduces the frozen weights exactly. The only difference is the last day, which lacks the 2023-01-01 00:00 settlement (1.6 bp).

### Findings

| # | Test | Result | Effect on the claim |
|---|---|---|---|
| 1 | Where the data fix mattered | The 97 days it added (2020-07-26 → 10-30) have Sharpe **4.43** and 20% of all P&L, with about 32 names in the universe and **6 names per leg**. On the 792 days both runs share, Sharpe went 1.65 → 2.19 (daily correlation 0.85). Under the null, a jump from z 1.77 to z 2.79 has probability 0.011. | Weakens |
| 2 | Concentration by day and week | Top 5% of days = **99%** of P&L. Top 1% (9 days) = 33%. Top 5% of weeks = 46%. One DOGE day (2021-01-28, +390%, long leg) = 10.6% of P&L. Dropping the top 20 days gives Sharpe 1.28, p 0.039. | Weakens |
| 3 | Regimes | 2020-07-26 → 2021-06-30: Sharpe **4.73**. 2021-07 → 2022-12: Sharpe **0.12** (p 0.45). 2021-08 → 2022-12: Sharpe −0.44. On days with a full 100-name universe (588 days): Sharpe **0.27**. The sample starts 2020-07-26, so the **COVID crash is not in it at all**. 2021H1 leverage boom: Sharpe about 5. LUNA/3AC: −1.7. Jul–Oct 2022: −3.2. | **Weakens most** |
| 4 | Leave-one-out | By quarter, minimum Sharpe 2.03; by month, 2.10. By year: without 2020, Sharpe 1.83 (p 0.028); without 2021, 1.74 (p 0.044). The last five quarters are negative. | These are robust only because the early months dominate |
| 5 | Hidden factors (EW market, BTC, size, 7d and 30d momentum, 1-day reversal, low-vol, all built from the same universe) | Alpha 0.62/yr, HAC t **3.55**, R² 0.08. Momentum and reversal loadings are insignificant. The only significant loading is low-vol (−0.22, t −2.4). Price leg alpha t 2.76. Funding ranks barely correlate with past 7-day returns (−0.09). Sorting on the funding rank after removing 7d/30d return and 30d vol still gives Sharpe 1.94. | Survives: **not** momentum or reversal. The price leg (41%/yr) is **not** short-term reversal; it is mostly shorting high-funding coins (short leg +0.49/yr relative to market) |
| 6 | Null calibration | Skew **+1.94**, excess kurtosis **23**. Autocorrelation near zero at short lags, but the Ljung-Box test rejects at 21 lags (p 1e-5). NW long-run variance ratio 1.57. See the calibration table below. | Weakens |
| 7 | Per-asset | Largest single coin 12% (THETA). Top 10 of 155 coins = **71%** of P&L; without them, Sharpe **0.73**. | Weakens |
| 8 | Capacity and costs | Break-even cost 63 bp per side (turnover about 101×/yr). Stress at 20 bp is still positive. Square-root impact (7 bp fees plus spread, Y = 1): Sharpe 2.17 at $100k, 1.59 at $1M, 0.55 at $5M, **−1.33 at $20M**. With positions capped at 1% of daily volume, capacity in 2020H2 was about **$0.65M** (about $6.5M at 10% of volume). Held coins' daily volume in 2020H2: 5th percentile $4.2M, median $20M. After mid-2021 the Sharpe is negative even at $100k. | Weakens economically |
| 9 | Implementation | Binance is not available to US persons. The positive skew comes from the long leg (pumps). Short squeezes on the short leg: 2021-05-24 −14%, 2022-11-10 −9%. There is exchange and delisting risk (LUNA, FTT, ANC among the losers), plus auto-deleveraging risk. | Weakens |

**Frozen-test calibration (item 6).** The frozen 21-day block test at p < 0.025, run on synthetic null series:

| Null process | Size at nominal 0.025 | Full-gate pass under the null |
|---|---|---|
| Resampled actual returns (keeps the heavy tails) | 0.021 | 0.018 |
| GARCH with negative crash jumps | 0.042 | 0.035 |
| Stationary bootstrap of the actual series, mean block 63 days | **0.070** | **0.070** |
| Regime-switching mean, regimes about 180 days | 0.076 | 0.075 |
| Regime-switching mean, regimes about 365 days | 0.26 | 0.26 |

The same observed data gives different p-values under longer-dependence methods:

| Method | p |
|---|---|
| Frozen 21-day block bootstrap | 0.0026 |
| Circular block, 126 days | 0.031 |
| Stationary bootstrap, mean block 63 | 0.023 |
| Stationary bootstrap, mean block 126 | 0.032 |
| t-test on quarterly sums | 0.025 |
| t-test on half-year sums | 0.092 |
| HAC, lag 126 | 0.028 |

The run's P(pass | null) of 0.028 measures the test against its own bootstrap world. It is not calibrated for persistence longer than 21 days.

### Promotion guards G1–G7 on the corrected dev series

`guards.py` annualises daily data at 252 days, so guard Sharpes are about 0.83× the crypto figures; the ratios are unaffected.

| Guard | Result | Detail |
|---|---|---|
| G1 beta | PASS | Alpha t 3.55 against 7 factors; 3.49 against market and BTC only |
| G2 reduced exposure | FAIL | Vol-matched control t = 1.81. This guard means little for a dollar-neutral book |
| G3 concentration | **FAIL** | 2021 = 65% of P&L; monthly sign test p 0.099 |
| G4 one asset | PASS | But the top 10 coins carry 71% of P&L |
| G5 null calibration | **FAIL** | 0.075 under the calibrated null (0.028 as run) |
| G6 post-publication | FLAG or FAIL | See below |
| G7 execution lag | PASS | One-day-lagged Sharpe is 81% of the original (1.97 at 365-day annualisation) |

On G6: the BIS Working Paper 1087 "Crypto carry" is dated **2023-04-04**, so all post-publication data is inside the lock (FLAG). There is an earlier SSRN posting, abstract 4268371. I estimated its date as about November 2022 from the ID, but did not verify it. From 2022-11-01 the guard sees 60 days: Sharpe 0.68, t 0.33, which is a **FAIL**.

### Burden-adjusted evidence (one-sided p)

The first column is the frozen p. The second applies the forking-path penalty described below. The third uses the stationary-bootstrap (63-day) null. The fourth applies both.

| Adjustment | Frozen p | With forking-path penalty | Calibrated null | Calibrated + forking |
|---|---|---|---|---|
| Unadjusted | 0.0026 | 0.0031 | 0.013 | 0.016 |
| Batch k = 2 (Bonferroni) | 0.005 | 0.006 | 0.027 | 0.032 |
| Crypto information family, 3 shots | 0.008 | 0.009 | 0.040 | 0.048 |
| Šidák, M_eff 25 (range for 19–34) | 0.063 (0.048–0.085) | 0.075 | **0.29** | **0.33** |
| Bonferroni, 240 project trials | 0.62 | 0.75 | 1 | 1 |

**Forking-path model.** The as-run and corrected test statistics correlate at ρ = 0.80 under the null. Suppose the director searches for missing data only after a near-miss (p between 0.025 and 0.10) and never after a pass. Then the false-pass rate rises from 0.025 to **0.034 (1.38×)**. If the search followed any fail, it rises to 0.039 (1.56×). If a passing run would also have been re-checked half the time, the inflation drops to 1.10×.

This penalty is small next to the calibration and regime problems. The data defect was real and mechanically documented, and the missing files were already queued to download.

### Winner's curse
- **Conditional median-unbiased Sharpe:** 2.04 (95% CI −1.6 to 4.1) with the bootstrap-implied standard error of 0.87; 2.22 with the HAC standard error. The selection threshold is about 1.6–1.7, and the observed 2.44 sits well above it, so the correction shrinks it only a little. A path-conditional variant that conditions on the as-run result was numerically unstable (2 → 4.5 by one route). I dropped it.
- **Spike-and-slab, null mass 0.8:**

| Slab and assumption | P(no effect \| data) | Posterior median if an effect exists | P(Sharpe > 0.3) |
|---|---|---|---|
| Half-normal, sd 1 | 0.25 | 1.40 | 0.72 |
| Half-normal, sd 1, standard error inflated 1.25× for calibration | 0.48 | — | 0.48 |
| Half-normal, sd 0.5 | 0.49 | 0.65 | — |
| Half-normal, sd 0.5, standard error inflated 1.25× | **0.63** | — | 0.27 |

- **The regime-relevant estimate is much lower:** Sharpe 0.12–0.27 in the full-universe period, against about 2 in the sample overall.

### Validation power (2023-01 → 2026-08, 3.67 years)
- **The stress leg is the real hurdle.** It requires the stress mean to be positive. In the full-universe dev period, the stress drag was 23.9%/yr against a base volatility of 16.6%/yr. So validation effectively requires a **base Sharpe of at least about 1.44**, a far higher bar than the p < 0.05 leg (about 0.86–1.16).

| True Sharpe | Pass probability (NW variance ratio 1.57) | Pass probability if the stress leg were not binding |
|---|---|---|
| 0 | 0.014 | 0.05 |
| 0.3 | 0.04 | 0.12 |
| 0.7 | 0.13 | 0.28 |
| 1.0 | 0.25 | 0.45 |
| 2.04 (the corrected estimate) | 0.82 | — |

- **Predictive pass probability** (averaging over the spike-and-slab posteriors): **0.05–0.37**, with a central estimate of about **0.10–0.20**. If the full-universe Sharpe of 0.12–0.27 is the truth, it is about 0.02–0.04.
- **What a result would teach:**
  - A FAIL moves P(no effect) only from 0.25 to 0.39 (half-normal sd 1). It is weakly informative, as the PLAN already says ("FAIL, not certified (low power)").
  - A PASS would lower P(no effect) to 0.01–0.17.
- **Bybit 2020–22 adds nothing independent.** It re-draws the same 2021 and the same prices.

### Recommendation: do not unlock validation now
1. The most likely outcome is an uninformative FAIL, with a pass chance of about 10–20% at the central estimate. The bar is effectively a base Sharpe of 1.44, while the dev evidence for the full-universe setting that validation will face is a Sharpe near 0.1–0.3.
2. Even a PASS could not be promoted. Binance is not available to US persons, capacity is about $1–5M, and G3 and G5 fail on dev (G6 fails if the SSRN date is used). Spending the only clean 2023–26 sample on a result you cannot act on wastes it.
3. **If you want the family closed rather than parked,** unlock only as a registered one-shot **closure test**. First register a `VALIDATION_UNLOCK.md` stating:
   - the stress-leg bar is known to bind at about 1.44;
   - a FAIL permanently settles the family;
   - a PASS earns forward monitoring only, never promotion;
   - sub-period, top-days, per-coin and capacity reports are required.

   Either way, record the dev result as "PASS on the frozen gate; statistically WEAKENED (regime-concentrated in 2020H2–2021H1, bootstrap under-covers); economically capacity-limited and not accessible to US persons".

### Files
Code is in `/Users/rytty/CCP/quant_v7/research/audit_funding_stat/` (`lockpanel.py`, `analysis.py`, `null_calibration.py`, `burden.py`, `extras.py`). Outputs are in `/Users/rytty/CCP/quant_v7/reports/audit_funding_stat/`:
- `analysis.json`, `null_calibration.json`, `burden.json`, `extras.json`
- `series_dev.csv`, `factors_dev.csv`
- `_lockpanel_cache.pkl`, a cache of the dev-only data panel that you can delete

No existing files were edited, and I made no commits, trades or changes to `bot/` or `reports/forward/`.

Sources: [BIS WP 1087](https://www.bis.org/publ/work1087.htm), [SSRN 4268371](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4268371), [RePEc](https://ideas.repec.org/p/bis/biswps/1087.html)