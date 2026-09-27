# FX continuation after scheduled macro/policy news: development FAIL, validation not run

Run 2026-09-23. Plan: `research/fx_news/PLAN.md`, registered at 18:43:43 with code hashes, before any
directional statistic. Code: `research/fx_news/`. Tests: `tests/test_fx_news.py` (22 pass).
Output: `dev_results.json`, `dev_F{1,2}_events.parquet`. The ledger grows by 2 trials.

## Result (events 2015–2020; 7,929 / 7,936 priced event groups; 6 majors and a USD basket)

| | F1: +15m → +2h | F2: +15m → +24h |
|---|---:|---:|
| Gross drift, bp per event (news direction) | **−0.41** | **−0.29** |
| Gross daily Sharpe | −0.81 | −0.20 |
| Net Sharpe, 1 bp/side | −4.71 | −1.61 |
| Stress Sharpe, 3 bp/side | −11.5 | −4.28 |
| Hit rate (net) | 42.5% | 48.3% |
| Control C_REACT (trade the first-15-minute move), net Sharpe | −4.15 | −1.37 |
| Control C_ALL (always long the news currency), net Sharpe | −3.98 | −1.01 |
| Permutation p (surprise sign vs shuffled signs) | 0.94 | 0.69 |
| P(pass gate \| null) | 0.0% | 0.0% |

**Gate:** net Sharpe must be ≥ 1.8/√6 = 0.722. **FAIL** for both. Nothing is selected, and
validation (2021–2026) stays locked.

## Reading

- **No drift after the first 15 minutes.** The direction of the consensus surprise tells nothing
  about the currency's move from +15 minutes to +2 hours or +24 hours.
  - This holds in every year (−2.0 to −2.9 bp net for F1) and every currency.
  - It holds for growth and for inflation releases.
  - It holds at every size of initial reaction: gross −0.8 to +0.6 bp across quintiles, with no
    monotonic pattern.
- **The information is priced within minutes.** The timestamp QA showed the volatility spike at
  minute 0. The surprise sign agrees with the direction of the first 15-minute move 14% more often
  than chance (correlation +0.14), so the news does move the price. Nothing is left afterwards. This
  matches Andersen, Bollerslev, Diebold and Vega (2003).
- **Retail costs make any residual irrelevant.** A tradable edge would need more than 2 bp gross per
  event; the measured drift is below zero.
- **Policy decisions:** only 11 event groups carry a policy surprise in these years. Their +39 to
  +44 bp mean is anecdotal (n = 11) and is not a finding. Central-bank surprise drift would need its
  own registered test with enough events.

## Classification

Post-news FX continuation (intraday to 1-day) after scheduled growth and inflation releases is
**SPENT**, as a bounded null with high power (~8,000 events). Do not re-specify the entry lag, hold,
taxonomy or sign.

Calendar consensus is now used for country equities (monthly) and FX (intraday). Both show the
news priced on arrival.
