# Addendum to the tsy_month_end report: independent adversarial audit (2026-09-23)

This addendum sits beside `REPORT.md`, which is not edited. The full audit is in
[`reports/audit_tsy/REPORT.md`](../audit_tsy/REPORT.md); its code is in `research/audit_tsy/`.

## Verdict: WEAKENED

The measurement is correct and does not depend on the price source. The trust level is downgraded.

**What held up:**
- **Reproduction:** independent code, with yfinance raw closes plus dividends on their ex-dates, reproduces active
  Sharpe 0.664 / 0.692 exactly.
- **Other price source:** closes rebuilt from LSE 1-hour bars give 0.71 in validation.
- **No artefacts:** no dividend or ex-date artefact; 92% of ex-dates fall on the session after the window.
- **Equity-independent:** alpha after SPY beta is 42 / 30 bp per window (t 3.6 / 2.7).
- **Visible in yields:** 10-year yields fall 2–3 bp more than normal over the window, and still do after 2019
  (t −3.1).

**What weakens it:**
- **Published rule:** it appeared in 2019 (Hartley & Schwarz SSRN, Aug 2019; AllocateSmartly posted the exact TLT
  last-3-days rule in Oct 2019). The development window and 2015–2019 are inside or before the published samples.
- **Post-publication (2019-10 → 2026-08):** window excess 19.6 bp (t 1.3), active Sharpe 0.56, shift p 0.059.
  - Last 36 months: active 0.25, p 0.28.
  - 2026 to date: −3.4%.
- **Flattered active measure:** in 2021–26 TLT fell about 10%/yr, and the active measure subtracts that. M's own
  excess Sharpe over the period was 0.31.
- **Execution:** the effect needs close-to-close fills. Open-to-open execution cuts validation to 17 bp (t 1.5).
- **Concentration:** the top 5% of months make 54–59% of active P&L, although the monthly sign tests are still
  significant.
- **Quarter-end amplification** did not repeat in validation (27.9 vs 28.6 bp).
- **The combined p of 0.00034 (×120 = 0.041) was not pre-registered** and was introduced after the gate failed. Two
  further problems:
  - it survives Bonferroni only if the project has fewer than 146 trials, and the total probably exceeds that;
  - the right correction for a published rule is out-of-discovery data, where p is 0.059.
- **Process:** the validation unlock was registered 61 s after the dev result. The unlock's cited "adversarial
  checks", the combined p and the deflated Sharpe have no code in the repo.
- **Data pipeline:** the last row of `data/multiasset/etf/TLT.parquet` (2026-09-18) is a partial-day snapshot. Forward
  recording must use official closes.

## Director's decision

- Status stays **FORWARD OBSERVATION, no capital.** The earlier descriptions "strongest evidence to date" and
  "survives project-wide multiple-testing correction" are withdrawn. It is now described as: a real, cheap,
  equity-independent pattern in Treasury yields that has not shown significant tradeable returns out of sample since
  it was published.
- Forward judgement uses only data after 2026-09-24, with official closes, under the registered spec
  `research/forward_audit/tsy_month_end_v1_spec.json` (registry seq 2).
