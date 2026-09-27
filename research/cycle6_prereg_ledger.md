# Cycle 6 preregistration ledger (append-only)

Each entry is written before the first return it governs. Format: UTC time | kind | id | file | SHA-256 | note.
Owner registration of Amendments 4 and 5 is waived for cycle 6; these hashes serve as registration.

| UTC | Kind | ID | File | SHA-256 | Note |
|---|---|---|---|---|---|
| 2026-09-26T19:45:41Z | reference | A4 | research/PROTOCOL_AMENDMENT_4_2026-09-26.md | 0ce12a84f560bc895eff04177e4d358577bc3ab439e9f183fe306b46cf10062a | adopted as written, deviations in FRAMEWORK §9 |
| 2026-09-26T19:45:41Z | reference | A5 | research/PROTOCOL_AMENDMENT_5_REPLICATION_2026-09-25.md | 33a9becbffdafe5e97f8852b9edd0f0e1591ee1eb1d1e4e587940d3cc55328d6 | Sol's file, read only |
| 2026-09-26T19:45:41Z | reference | A5-C1 | research/CORE_PREMIA_COMPONENT_1_TREND_PREREG_AMENDMENT_5_2026-09-25.md | 7fd50331dd88dd50e4152ab92b21b3d459f647dcb3d21723ad80e95ac54dd617 | Sol's trend rule, read only |
| 2026-09-26T19:45:41Z | framework | FRAMEWORK | research/cycle6/FRAMEWORK.md | 2576bf12f23baa9f93a70257b5ae779cda21bda55ef8150d89983b8a297875aa | no strategy return computed yet |
| 2026-09-26T20:04:44Z | framework | ADDENDUM-1 | research/cycle6/FRAMEWORK_ADDENDUM_1.md | 72ea818058040cbee35d9531dab5d5baf841750a35a77d6828886d148a9037ae | data-pass decisions, before any strategy return |
| 2026-09-26T20:23:22Z | engine | ENGINE | research/cycle6/engine/*.py | e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422 | 24 synthetic tests pass |
| 2026-09-26T20:23:22Z | snapshot | cycle6_eval_v1 | data/cycle6/snapshot_store | ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be | frozen candidate list: 96 PASS rows |
| 2026-09-26T20:23:22Z | run-list | k | research/cycle6/FEASIBILITY.md | ba0385654691b0523e4c618e7120e974add46cbbca221eb05600c70c87d7e1ae | k = 20 components (CARRY-CM infeasible); Bonferroni 0.05/20 = 0.0025 |
| 2026-09-26T20:23:22Z | spec | TSMOM-EQ | research/cycle6/specs/TSMOM-EQ.md | ea524f95ff8f29decbb449e96b7ec2154910885a3b45a6ffe299d04b322dfa32 | before first return |
| 2026-09-26T20:23:22Z | spec | TSMOM-FI | research/cycle6/specs/TSMOM-FI.md | 188d8cc948c7f49d9428c01f322387a787f717abd223c8fbc1f98ae4b629409b | before first return |
| 2026-09-26T20:23:22Z | spec | TSMOM-FX | research/cycle6/specs/TSMOM-FX.md | 9e72dcd4743afd9a4528408cb699f4770edd1536c9104136e0b30a9de04afa7b | before first return |
| 2026-09-26T20:23:22Z | spec | TSMOM-CM | research/cycle6/specs/TSMOM-CM.md | 6bd6f56b5119f10e18b2d32837152cce65c977e2ebd668d6576bb73217e3ebdd | before first return |
| 2026-09-26T20:23:22Z | spec | XSMOM-EQ | research/cycle6/specs/XSMOM-EQ.md | d83fa03aa4e941163bb78341e69425a05c46a01f38508342bd0bc3391a66d8ee | before first return |
| 2026-09-26T20:23:22Z | spec | XSMOM-FI | research/cycle6/specs/XSMOM-FI.md | dfdae81deaabecbad65235f14a9dbe8c040790774b28fca09998af2020f75cbc | before first return |
| 2026-09-26T20:23:22Z | spec | XSMOM-FX | research/cycle6/specs/XSMOM-FX.md | 2f520f6af7c1129941966931bf27a5b184b9bc909586817dfc6ab98a5da54a5d | before first return |
| 2026-09-26T20:23:22Z | spec | XSMOM-CM | research/cycle6/specs/XSMOM-CM.md | 0b2c741e834b8529fa093f618b94e494bfcacdae229ba42c4ecf7a643afe08da | before first return |
| 2026-09-26T20:23:22Z | spec | VAL-EQ | research/cycle6/specs/VAL-EQ.md | 04864ea3c28c2d6465f78ba7605ebd6e04e87cb967e263714a703df27f9dac6d | before first return |
| 2026-09-26T20:23:22Z | spec | VAL-FI | research/cycle6/specs/VAL-FI.md | 9f221d33eec030eabc4dac9cd95119ddf0608d863af30af7a02f8450d8ff5d7f | before first return |
| 2026-09-26T20:23:22Z | spec | VAL-FX | research/cycle6/specs/VAL-FX.md | 285afa0d08373d508325707ef182ee7a2cfcd6df4f60e8b04dd48fe1d3d2b003 | before first return |
| 2026-09-26T20:23:22Z | spec | VAL-CM | research/cycle6/specs/VAL-CM.md | c338bd9da97e1e1835efb0687895e69603e7324fe4c24244029e66c2b9ae3dc9 | before first return |
| 2026-09-26T20:23:22Z | spec | CARRY-FI | research/cycle6/specs/CARRY-FI.md | b28c152f8f8e032cc035117ed92bc25cbfa1da0e580d6c91a5230c15ba28d93b | before first return |
| 2026-09-26T20:23:22Z | spec | CARRY-FX | research/cycle6/specs/CARRY-FX.md | 4b154993dfb8f9a1ec044b01778f0c9d4adbb3eb25bbc873b476944b24c017c3 | before first return |
| 2026-09-26T20:23:22Z | spec | BAB-EQ | research/cycle6/specs/BAB-EQ.md | 61978edc34f4db57fd95af27e9c79b3a61de27b4aac571aaa22b78d45ae93d2a | before first return |
| 2026-09-26T20:23:22Z | spec | BAB-FI | research/cycle6/specs/BAB-FI.md | 842dc68e2e1b2367e80da9b920c1ae4474b949a3c9474aa04cb0a134affddd77 | before first return |
| 2026-09-26T20:23:22Z | spec | SEAS-EQ | research/cycle6/specs/SEAS-EQ.md | d4786ef6a4f2c6ce1ec158b38e043b8b060b03d4e6dc0d67c11b9740719329a2 | before first return |
| 2026-09-26T20:23:22Z | spec | SEAS-FI | research/cycle6/specs/SEAS-FI.md | 9d6e5a8dd219b66c1a2540c59d02daca27aaff6cb24c7f6edb38b6e564e1a887 | before first return |
| 2026-09-26T20:23:22Z | spec | SEAS-FX | research/cycle6/specs/SEAS-FX.md | 3863dc7f62f4b95e43fb7192cb6712a4e1c9c7cab5b6770a3e1c72fa5374495b | before first return |
| 2026-09-26T20:23:22Z | spec | SEAS-CM | research/cycle6/specs/SEAS-CM.md | a35b021fed62c20f8f337e0156b9f8e19e323eb3aca2b18418029579436bcff3 | before first return |
| 2026-09-26T20:23:22Z | spec | BOOK | research/cycle6/specs/BOOK.md | 8843f97fe7eb6137f338f458eb9d09f406daea082d19e186cc37a577601a706b | before first return |
| 2026-09-27T03:30:06Z | code | TRADABLE | research/cycle6/tradable/*.py | 82cbf4258647ad57d1a51e506eadd48348504a1512ec81b5da5f1f9877060809 | 17 synthetic tests pass |
| 2026-09-27T03:30:06Z | snapshot | cycle6_trade_v1 | data/cycle6/snapshot_store | 940335bf4f1a3d188587b9b55c03ba151b598332a8865de4f9ad527d404787c6 | ETF/FX/futures-sizing data |
| 2026-09-27T03:30:06Z | spec | TRADE-ETF-LF | research/cycle6/specs/TRADE-ETF-LF.md | 172112e35996e03a2ca4b703ab34109da58652d7c7ec463de5ac50b9c644ec84 | tradable variant, never replaces paper BOOK |
| 2026-09-27T03:30:06Z | spec | TRADE-MARGIN | research/cycle6/specs/TRADE-MARGIN.md | c78fd4b107bea115990096e55a83bb497bd995c4933db4df9c3630407e5d0761 | tradable variant, never replaces paper BOOK |
