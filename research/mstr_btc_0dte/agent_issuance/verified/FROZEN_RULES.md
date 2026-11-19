# Freeze decision — no issuance-event rule advances

**Decision timestamp:** 2026-10-17  
**Development price fence:** 2019-12-02 through 2023-12-29 only  
**Sealed price period:** 2024-01-02 onward — no event return calculated or
used for selection

The protocol permitted two economically pre-specified families:

1. long MSTR after an initial convertible-note announcement; and
2. short MSTR after a newly established MSTR common-stock ATM program, with a
   deliberately demanding 30% annual stock-borrow charge.

For each, development tested only the pre-specified 1-, 3-, and 5-session
Open-to-Close horizons. A rule needed at least five independent events,
positive net and matched-MSTR excess return, and no one event contributing over
50% of total positive profit.

| Family / side | Hold | Events | Net mean | Matched-MSTR excess mean | Largest positive-profit share | Freeze? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Convertible initial / long | 1 | 2 | +0.87% | +1.02% | 98.61% | No: only two events |
| Convertible initial / long | 3 | 2 | −3.81% | −4.08% | n/a | No |
| Convertible initial / long | 5 | 2 | −3.53% | −5.30% | 100.00% | No |
| Common ATM initial / short | 1 | 5 | −1.98% | −1.63% | 100.00% | No |
| Common ATM initial / short | 3 | 5 | +1.02% | +2.30% | 51.49% | No: unstable and just over concentration limit |
| Common ATM initial / short | 5 | 5 | +4.66% | +6.71% | 55.95% | No: small, concentrated, CI crosses zero |

The superficially attractive five-session ATM short is not frozen: its
bootstrap 95% interval for the mean net return is **−6.03% to +14.28%**;
matched excess is **−3.90% to +16.39%**; its t statistic is only **0.82**; and
the September 2022 episode supplies 55.95% of all positive profit. Selecting
it anyway would violate the pre-written concentration screen.

**Frozen rules: none.** Because the development screen yielded no rule, no
2024–2026 issuance-event return was calculated or presented. The future source
ledger exists only to demonstrate a mechanically stable SEC event definition;
it is not a performance validation.

---

**Amendment note (2026-10-17, review-completion pass).** The "Matched-MSTR
excess mean" column and the five-session excess interval are aligned here with
the committed final development outputs (`development_candidate_summary.csv`;
controls block every retained issuance-event window, as PROTOCOL.md specifies).
An earlier transcription used a same-family-blocking iteration. Corrections:
convertible 3-session `−4.16% → −4.08%`, convertible 5-session `−5.25% →
−5.30%`, ATM 3-session `+2.21% → +2.30%`, ATM 5-session `+6.56% → +6.71%`,
excess interval `−4.08%..+16.26% → −3.90%..+16.39%`. Net returns,
profit-concentration shares, and the rule-freeze decision (none frozen) are
unchanged; no 2024+ price was read before or after this note. Central-registry
disclosure: the 2026-10-17 `late_registration_record` for this track.
