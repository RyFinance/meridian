# MSTR convertible / common-ATM announcement drift — negative result

## Result

No tradeable issuance-flow rule was found. Under a strict SEC-timestamped
workflow, neither initial convertible-note announcements nor new MSTR
common-stock ATM programs produced a development result robust enough to
freeze. Accordingly, **no 2024–2026 return validation was run**. This is a
protocol stop, not a hidden failed holdout.

The closest result was a five-session short after a new common-stock ATM
program: +4.66% mean net return across five development events and +6.71%
versus matched ordinary MSTR shorts. It is not credible as an edge: its 95%
bootstrap interval crosses zero (−6.03%, +14.28%), t=0.82, and one September
2022 event generated 55.95% of the gross positive profit. With no historical
borrow-availability series, the already-conservative 30% annual borrow charge
does not solve the implementation risk either.

## Scope and causal source record

This study is completely fenced inside the verified subdirectory;
parent-directory files that pre-dated the study are not inputs. The source
crawler retrieved 290 relevant SEC form filings and primary documents directly
from EDGAR, then a hand-reviewed ledger retained only earliest SEC sources for
a new convertible offering or a new MSTR Class A ATM program:

| Segment | Convertible initial | Common-ATM initial | Total |
| --- | ---: | ---: | ---: |
| Development through 2023 | 2 | 5 | 7 |
| Future-source ledger, 2024–26 | 6 | 4 | 10 |

The event ledger carries the EDGAR acceptanceDateTime, filing accession, source
URL, primary-document SHA-256, and source cache path for every retained event.
When a prospectus and an 8-K cover the same ATM program, the earlier accepted
SEC document is the event source. Later offering-completion filings, weekly
ATM/BTC-update disclosures, and preferred-stock ATM programs are excluded.
A program consolidation that only re-papers remaining capacity (the 2025-11-04
Omnibus Sales Agreement annex, which carried over the prior program's
$15,854,365,265 remaining) and administrative amendments or sales-agent
joinders are likewise excluded; an additional-program addendum that registers
new Class A capacity (2026-03-23, up to $21bn) is retained as an event. This
avoids re-running the separate BTC-purchase event study.

Some primary 8-Ks recite a press release dated before the SEC acceptance time.
The study intentionally acts only on the SEC acceptance timestamp, so any such
filing latency is a conservative limitation rather than an early-information
assumption.

## Development design

The development program predicate-filters the parquet at read time through
2023-12-29 and asserts that no later row is present. An SEC event before
09:25 ET can enter that session's regular open; every other event enters the
next regular open. All qualifying historical events in this study were entered
next open. Exit is the regular close after 1, 3, or 5 trading sessions.

Costs are 3 bp adverse auction slippage on **each** side plus $0.005 per share
on **each** side. Short candidates additionally pay a 30% annualized borrow
charge for every held session. The daily series is split-adjusted, making the
$0.005-share cost conservative for pre-split rows.

The essential benchmark is not buy-and-hold MSTR. Each event is compared with
all same-weekday ordinary MSTR episodes of the same horizon and direction that
do not overlap any issuance-event window, using the same costs. The reported
excess is the event return minus that matched distribution's mean.

## Development results

| Family / trade direction | Sessions | n | Net mean | Net median | t | 95% bootstrap mean CI | Matched-MSTR excess mean | Selection result |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| Convertible initial / long | 1 | 2 | +0.87% | +0.87% | 1.03 | +0.02%, +1.71% | +1.02% | Fail: n < 5 |
| Convertible initial / long | 3 | 2 | −3.81% | −3.81% | −2.19 | −5.56%, −2.07% | −4.08% | Fail: n < 5 |
| Convertible initial / long | 5 | 2 | −3.53% | −3.53% | −0.42 | −11.85%, +4.79% | −5.30% | Fail: n < 5 |
| Common ATM initial / short | 1 | 5 | −1.98% | −4.93% | −0.87 | −5.38%, +2.47% | −1.63% | Fail |
| Common ATM initial / short | 3 | 5 | +1.02% | −1.13% | +0.19 | −8.37%, +10.41% | +2.30% | Fail |
| Common ATM initial / short | 5 | 5 | +4.66% | +4.30% | +0.82 | −6.03%, +14.28% | +6.71% | Fail |

The five original common-ATM events were 2021-06-14, 2022-09-09, 2023-05-01,
2023-08-01, and 2023-11-30. Net five-session short results were +2.38%,
+20.93%, +4.30%, +9.79%, and −14.10%, respectively. Thus even the apparent
five-day effect has an economically meaningful losing event and no reliable
sample size.

## Decision and reproducibility

FROZEN_RULES.md records the rule-freeze decision made before any holdout
issuance-event return calculation. The development manifest confirms 1,027 price rows ending
2023-12-29 and records the input data SHA-256. Reproduce the study with:

    cd /Users/rytty/CCP/quant_v7
    PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/agent_issuance/verified/collect_sec_sources.py
    PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/agent_issuance/verified/build_event_ledger.py
    PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/agent_issuance/verified/dev_research.py

Registration status: the protocol was written before the development run, but
this track had **no central `preregistrations.jsonl` entry before that run**
(the 2019–2023 price window had been viewed by earlier registered studies). A
disclosed `late_registration_record` was added during review on 2026-10-17;
evidentiary status is weaker than a centrally registered unlock. No 2024+
issuance-event return was calculated at any point, nothing is promoted, and no
holdout run is authorized from this tree.

The source collection needs network access to SEC EDGAR. The supplied source
cache allows the ledger and development analysis to be reproduced without
another fetch. No live orders were placed.

DATA_INTEGRITY_NOTE.md records the limited initial input inventory and why this
negative screen does not claim a blinded positive out-of-sample result.
