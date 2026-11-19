# Cycle-6 independent reproduction: divergences and look-ahead checks

This was written by the reproduction auditor on 2026-09-27. The series were built from the spec text only: FRAMEWORK, ADDENDUM-1, specs/*.md and A5-C1 for the vol formula. No builder engine module was imported. The auditor read the builder code only after `sleeves.py`, `common.py` and `run_repro.py` were written and compared, and only to diagnose the two residual divergences below.

## Snapshot
- The SHA-256 of `manifest.json` as a file is `755ffe96…`, which is not the ledger value. The ledger value `ba67379b…` is the hash of the canonical manifest payload (`json.dumps(payload, sort_keys=True, separators=(",",":"))`). That hash equals both the embedded `manifest_sha256` and the ledger entry, so this is a hashing convention and not a tamper.
- All 23 files in the view match the manifest sha256. See `snapshot_verification.json`.

## Divergences (net and gross, tolerance 1e-6)
| Sleeve | Result | Cause |
|---|---|---|
| TSMOM-FI, TSMOM-CM, XSMOM-FX, CARRY-FX, CORE | identical (max abs diff ≤ 4e-15) | none |
| VAL-FX | 3 signal months differ: 1985-06, 1990-06, 1995-04. Net months 1985-07/08, 1990-07/08 and 1995-05/06 differ by up to 5.0e-3. The second month of each pair differs only through drift and turnover cost. The post-2009-04 window is identical. | **Convention.** The builder measures the 5-year CPI change against the window mean of **log** CPI (a geometric mean, `styles.fx_ppp_value`). The repro used the log of the arithmetic window mean, which is the same operator the paper and spec apply to spot. Each flip is a near-tie in rank: signal gaps are 1.2e-3, 8e-4 and 1.5e-4. With the builder's convention the repro matches to 1e-15 (`VAL-FX__cpi_geomean`). This is not look-ahead and not a cost error. The spec text ("CPI change measured with the same window mean") is ambiguous. Full-sample Sharpe is 0.424 (repro) vs 0.426 (builder). |
| SEAS-FX | 545 of 602 net months differ, max 3.4e-3, corr 0.99993. Signs and ranks are identical everywhere. | **Convention, arguably a small implementation bug.** In `styles.vol_size`, the sizing-vol floor is the 10% cross-sectional quantile of vols **only where the rank weight is non-zero** (`v.where(W != 0)`). When N is odd, that excludes the median asset. The asset is eligible and is counted in N, and the builder's own docstring says "eligible vols". The spec says "max(10% cross-sectional quantile, 2.5% p.a.)". The different floor changes the unscaled book's past returns and therefore the class vol scale, so every month moves slightly. With the builder's convention the repro matches to 1e-15 (`SEAS-FX__floor_excl_zero`). This is not look-ahead and not a cost error. Net Sharpe is -0.3045 vs -0.3037 (full) and -0.1854 vs -0.1833 (post-2019-02). |
| CORE, first pass only | fixed | The repro originally held the core in 2002-07, using IEF's single day, 2002-07-31. The builder's first holding month is 2002-08: the signal month-end is the first month-end at which both ETFs are priced, and the core is held from the next month, as for the components. This convention was adopted, and the repro then matched exactly. |

The accounting conventions were confirmed identical, with no divergence:
- Gross is calendar month t+1 close-to-close.
- Net runs from each instrument's first trading day close in t+1 to its first trading day close in t+2. The last month, 2026-09, is a partial period ending at the last snapshot close.
- Costs are bp per side times Σ|w_new − w_drifted|, with w_drifted = w(1+R)/(1+Σ wR). Rates are FI 2, CM 6, FX 3 and core 2 bp.
- The initial entry is charged in full.
- Rank weights use average ranks, scaled to $1 long and $1 short.

The TSMOM vol is the pandas `ewm(com=60, adjust=True).var(bias=True)` value times 261, on valid observations, including day t. Defined-month counts equal FEASIBILITY.md for all six sleeves: 403, 227, 615, 560, 626 and 603.

## Look-ahead
- **Perturbation.** Every daily return and every monthly signal input dated after a month-end cut was replaced with noise. Cuts were 1985-12, 1999-06, 2008-09, 2016-12 and 2024-03. Every repro weight with signal month ≤ cut is bit-identical (max change 0.0), and weights after the cut do move. The perturbed data includes day t+1, so this covers (a) future data in signals, (c) rate inputs and (e) vol including day t+1. See `lookahead_perturbation.csv`.
- **Builder weights.** `weights.parquet` for all six sleeves equals the repro weights, with builder conventions, to ≤ 1e-14 on every signal month. Zero weights are omitted by the builder. The same month sets were checked. The builder weights therefore carry the same no-look-ahead property. See `builder_weights_check.csv`.
- **(b) CPI.** The engine uses the PIT panel value at t only (`cpi_lag_months: 0`; perturbation-safe). The PIT panel lags by 2 months:
  - US_CPI(2020-02-29) / US_CPI(2020-01-31) = 0.99909, which equals CPI-U NSA Dec-2019/Nov-2019 (256.974/257.208).
  - The 2020-03/2020-02 ratio of 1.00388 equals Jan-2020/Dec-2019.
  - So the value at month-end t is reference month t−2, which was released in month t−1. That is conservative, not early.
  - Foreign CPI vintages are not in the snapshot, so their `available_date` cannot be checked independently from it.
- **(c) Rates.** The foreign and US rate rows are dated inside their own month. The last observation is 2026-09-18, before the snapshot as-of date. The rank depends only on i* at t, because (i*−i)/(1+i) is monotone in i* when i is common.
- **(d) Seasonality.** The signal uses months t+1−12k for k ≥ 1, so the holding month is excluded. The repro and the builder (`shift(12k−1)`) agree.
- **Book inputs.** `book/sleeves.csv` columns equal the builder's `net.csv` exactly, and the CORE column equals the repro core.
