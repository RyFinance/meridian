# EIA "Contract 1" is not a return series without roll splicing (director QA, 2026-09-26)

## The error

`eia_trend_audit.py` treats the day-over-day change in EIA's C1 as the paper-rolled return. That is wrong: C1
switches contract after each expiry, so the change on each roll day is the price gap between two different contracts
(the curve slope). It is not a return on a held position.

## The correct construction

On the first trading day after each CL expiry, the return is C1(t) / C2(t−1) − 1. CL expiry is the 3rd business day
before the 25th of the prior month; if the 25th is not a business day, it is 3 business days before the preceding
business day. On all other days the return is the plain C1 change.

## QA against USO (2006-05 → 2016-12, daily, 128 roll days)

| Construction | Tracking error vs USO | Correlation | Annual mean difference |
|---|---:|---:|---:|
| Raw C1 (agent) | 17.2% | 0.900 | +15.8%/yr |
| Spliced held contract | 14.1% | 0.930 | +4.2%/yr |

- **What the remaining gap reflects:**
  - USO's earlier roll window;
  - fees;
  - the timing difference between the 14:30 ET settlement and the 16:00 ET ETF close.
  - Daily tracking error overstates the monthly construction error.
- **Verdict:** EIA crude and natural-gas contract-1 series are usable for trend ONLY with explicit roll splicing
  (natural gas: expiry 3 business days before the 1st of the delivery month). The agent's "clean as-is" statement is
  withdrawn.
