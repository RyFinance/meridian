# Data-integrity note

Before the protocol was written, a basic dataset inventory displayed the daily
file's schema, date coverage, and terminal rows to confirm that the file was
the intended MSTR price source. It did not calculate issuance-event returns,
candidate performance, benchmarks, or any rule-selection statistic.

The actual development program then uses a parquet predicate filter ending on
2023-12-29 and asserts that no later row is present; its manifest records that
fence. No rule passed development, so no 2024–2026 issuance-event P&L was
calculated. This report therefore makes **no claim of a blind positive
out-of-sample performance validation**. It is a clean negative screening result
for this issuance-event family.
