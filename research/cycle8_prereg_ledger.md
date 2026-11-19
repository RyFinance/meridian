# Cycle 8 preregistration ledger (append-only)

Each entry is written before the first return it governs. Cycle 8 = portfolio construction from known premia
(max expected return under a drawdown limit, Canadian retail). Not alpha research.

| UTC | Kind | ID | File | SHA-256 | Note |
|---|---|---|---|---|---|
| 2026-09-28T06:41:37Z | framework | FRAMEWORK | research/cycle8/FRAMEWORK.md | 933ec68b5e432c0bd4f881d489766645854f9e3523f15e0233eb44e5f491aa1f | menu, data, costs, leverage/margin model, metrics, answer rule; no cycle-8 return computed yet |
| 2026-09-28T07:09:39Z | framework | ADDENDUM-1 | research/cycle8/ADDENDUM_1.md | e4b4d089f3724cd08124ece2c2a2aca063577ae01b0d7bb5a0ea10749dbda5ce | engine clarifications + data decisions + CMA mapping rules; no portfolio return computed yet |
| 2026-09-28T07:09:39Z | code | ENGINE+RUNNER | research/cycle8/engine/*.py + research/cycle8/run.py (concatenated) | 1118dda9ebee4fb33a66a4404e6050e90044b731c4b3413515244844a1f7093a | 9 engine + bond unit tests pass; smoke-tested on randomised synthetic data only |
| 2026-09-28T07:09:39Z | snapshot | cycle8_v1 | data/cycle8/snapshot_store | 207cc70443c4435cd9e26f6ac7c680a4a7196a666edff1c9a8a14b51ab197c21 | frozen before any portfolio return; registered as experiment cycle8_main |
| 2026-09-28T07:10:56Z | code | FORWARD+ANSWER | research/cycle8/forward.py | 14eab80d84b3ed499470536d4f620c252310d239dc3b7b11a3be032dce860053 | written before main outputs were viewed; implements ADDENDUM_1 §8/§10.1 and FRAMEWORK §6; EQ_GH forward = EQ_G (UIP, no FX view) + 0.10 hedge cost |
| 2026-09-29T06:08:27.809357+00:00 | US-only framework | US1 | research/cycle8_us_only/PREREG.md | 959f33191f8305e844ba987c9062c2e07e3df4d5d4010a0411dbdded518122cf | separate current US mandate; no US1 portfolio return computed; existing global study preserved |
| 2026-09-29T06:11:14.252047+00:00 | US-only code+snapshot | US1-FROZEN | research/cycle8_us_only/code_receipt.json | fe0dfe7e17605c17a0ec40ad000f3f7727aec44c41f4a90f8be4588cc8a60563 | 6 accounting tests pass; before first US1 return; source snapshot manifest and code hashes |

## US1 follow-up correction receipt

UTC: 2026-10-02T06:00:59.465988+00:00; client date: 2026-10-01. Receipt SHA-256: `3c1e2baffa639cf895bf7f07d043b10aa54ce85b207f3db1fd4d5d04d3c638be`. Post-result audit, unchanged menu/levels; C1 overlay mean correction, C2 coherent arithmetic moments, daily-path risk supplement. Files: reports/cycle8_us_only_followup/receipt.json and research/cycle8_us_only_followup/PREREG.md. Original US1 results preserved.

## C3 gold source repair

UTC: 2026-10-02T06:06:33.337382+00:00; receipt SHA-256 `f99e7619e4275027796ac31eef5dad9be0a49f8f70497e5ff842a466cecabc86`. Fixed P4/P5 rows; replace pre-GLD monthly-average gold with observed London PM month ends. New files only, post-result correction. reports/cycle8_us_only_followup/gold_receipt.json.
