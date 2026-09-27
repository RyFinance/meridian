# Macro-surprise plan, amendment 1: signal code matches PLAN section "Signal" item 4

Registered before any strategy, control or signal-return statistic was computed.

The `signals_code_sha256` recorded with PLAN.md (edd1134f…) was taken from a version of
`research/macro_surprise/signals.py` whose `diffusion()` still returned the plain mean vote,
sum(votes)/n, from the signal-only QA step. PLAN.md item 4 specifies z = sum(votes)/sqrt(n) and
gives the reason. The code is corrected to the plan: one line, plus the docstrings. No keyword,
window, threshold, universe or other rule changes. The corrected file's sha256 is recorded with
this amendment and is the frozen signal code for the development and validation runs.
