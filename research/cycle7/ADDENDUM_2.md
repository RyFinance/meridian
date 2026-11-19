# Cycle 7 addendum 2: data-pass decisions (before any cycle-7 return)

2026-09-27. No return of any style was computed. These decisions use only data-quality information and source
availability.

## Adopted as built by the data agents

| Area | Rule |
|---|---|
| FX | NDF currencies use BIS daily central-bank (onshore) spot. |
| FX | Short-rate fallback to the BIS daily policy rate when no OECD or LSE rate exists for that day. |
| FX | Controls episodes were chosen by the agent from IRR/AREAER (ARS, RUB 2022-03+, TRY 2005-01 redenomination). |
| FX | IRR classifications after 2019 are carried forward only where AREAER 2023 agrees. |
| FX | Mechanical fails stand: TWD (no classification), CZK after 2019 (IRR/AREAER disagree), and CNY and HKD (pegs). |
| FX | The BIS BRL 2000-02-11 one-day print is kept: no cycle-6 or cycle-7 rule removes it. Disclosed. |
| FX | CPI is the latest vintage with the cycle-6 two-month rule. No free foreign first releases exist. |
| CM | London-listed WisdomTree single-commodity ETCs count as single-commodity ETNs (total-return index incl. collateral). |
| CM | A series starts after its last bad print (a move over 15% reversing the next day) or unit break (a move over 50%). The LME nickel squeeze of 2022-03 is whitelisted. |
| CM | One line per market: the longest history after truncation. |
| CM | EIA heating oil and propane are spliced on the first trading day of the month. No free traded proxy exists to check them against. |
| FI | A history starts after its last month with fewer than 10 daily observations (daily-frequency truncation). |
| FI | Euro members use their national OECD short rate before joining. |
| FI | UK FI-DEEP uses par yields derived from BoE zero curves (vs IUDMNPY: mean −0.9bp, p95 5.6bp). DE before 1997 uses the Bundesbank 8–15y bucket. |
| FI | FI-DEEP extensions are QA'd against the same market's cycle-6 series where they overlap. |
| FI | Malaysia's policy-rate steps were hand-transcribed from an inline LSE reply. This is the only hand-typed data and is disclosed. |

## New, by the director

- **Russian bonds:** `FI_RU_10Y` rows from 2022-03-01 are removed (962 rows) in `data/cycle7/fi/eval_new_v2`. This is
  the FX FRAMEWORK §3(c) capital-control episode (RUB 2022-03+) applied to the same market's bonds.
- **Greece:** the 2012 restructuring is kept, because no rule excludes it. Disclosed.
