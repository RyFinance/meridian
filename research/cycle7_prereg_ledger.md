# Cycle 7 preregistration ledger (append-only)

Each entry is written before the first return it governs.

| UTC | Kind | ID | File | SHA-256 | Note |
|---|---|---|---|---|---|
| 2026-09-27T09:51:13Z | reference | cycle-6 ledger | research/cycle6_prereg_ledger.md | 9ee061d6e30fc2c5cf05699710bb4f0caecd6d8895128790863c4fbd834cda47 | source of the six frozen spec hashes |
| 2026-09-27T09:51:13Z | reference | ENGINE | research/cycle6/engine/*.py | e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422 | frozen engine, must be unchanged |
| 2026-09-27T09:51:13Z | reference | TSMOM-FI | research/cycle6/specs/TSMOM-FI.md | 188d8cc948c7f49d9428c01f322387a787f717abd223c8fbc1f98ae4b629409b | frozen spec |
| 2026-09-27T09:51:13Z | reference | TSMOM-CM | research/cycle6/specs/TSMOM-CM.md | 6bd6f56b5119f10e18b2d32837152cce65c977e2ebd668d6576bb73217e3ebdd | frozen spec |
| 2026-09-27T09:51:13Z | reference | XSMOM-FX | research/cycle6/specs/XSMOM-FX.md | 2f520f6af7c1129941966931bf27a5b184b9bc909586817dfc6ab98a5da54a5d | frozen spec |
| 2026-09-27T09:51:13Z | reference | VAL-FX | research/cycle6/specs/VAL-FX.md | 285afa0d08373d508325707ef182ee7a2cfcd6df4f60e8b04dd48fe1d3d2b003 | frozen spec |
| 2026-09-27T09:51:13Z | reference | CARRY-FX | research/cycle6/specs/CARRY-FX.md | 4b154993dfb8f9a1ec044b01778f0c9d4adbb3eb25bbc873b476944b24c017c3 | frozen spec |
| 2026-09-27T09:51:13Z | reference | SEAS-FX | research/cycle6/specs/SEAS-FX.md | 3863dc7f62f4b95e43fb7192cb6712a4e1c9c7cab5b6770a3e1c72fa5374495b | frozen spec |
| 2026-09-27T09:51:13Z | framework | FRAMEWORK | research/cycle7/FRAMEWORK.md | abc598e48bf7a19332e343f45491581122d1c14d22501d9b6c29d984e09325c4 | no cycle-7 return computed yet |
| 2026-09-27T10:00:48Z | framework | ADDENDUM-1 | research/cycle7/ADDENDUM_1.md | 9921e7f3fda97a2d07e1b9353a8ee4d631ef5e891a37377fb05485766f899f33 | FX exclusion masking + runner definitions |
| 2026-09-27T10:00:48Z | code | RUNNER | research/cycle7/runner/*.py | b1db5652903b8a4be0708d53d162f5fb5d9d0c6d2889cb5f14946f0e633a690e | 20 synthetic tests pass |
| 2026-09-27T14:32:56Z | framework | ADDENDUM-2 | research/cycle7/ADDENDUM_2.md | a20977e1b0fd8ed8b899c513c7d0f0929326ddab3e31e3321772e737ebfedc96 | data-pass decisions |
| 2026-09-27T14:32:56Z | snapshot | cycle7_fx_em_v1 | data/cycle7/snapshot_store | 93ef8e0f0fbe6aebbe0eb4bf82a4a50c2c19de4461b426b7c63f09808cbba0c3 | frozen before any return |
| 2026-09-27T14:32:56Z | snapshot | cycle7_cm_new_v1 | data/cycle7/snapshot_store | de67e9f2b10bd49687f7801de7029f60c9ca08ad47ea0fbb0544eeddbb8d628f | frozen before any return |
| 2026-09-27T14:32:56Z | snapshot | cycle7_cm_deep_v1 | data/cycle7/snapshot_store | 3db28c32308b52fa631ac3176ae1cdce77b8930fb7d503e1a513a57aff464e18 | frozen before any return |
| 2026-09-27T14:32:56Z | snapshot | cycle7_fi_new_v1 | data/cycle7/snapshot_store | 67aba1106c304193835f15354eca245e14cbc2c77da13325ecbe0cfe1ceffe4b | frozen before any return |
| 2026-09-27T14:32:56Z | snapshot | cycle7_fi_deep_v1 | data/cycle7/snapshot_store | a7387d19fd5ba59825ea2769b694599cd70c2e9ae6159f7e9232e43be365bd09 | frozen before any return |
| 2026-09-27T14:32:56Z | infeasible | FX-DEEP | data/cycle7/fx/feasibility_counts.json | a3368c1f5bd5e4180bb95fe67908370b9bfb6729c0929437f6cebaed75c9fba2 | all four FX specs <= 17 months < 24 floor; not run |
| 2026-09-27T14:32:56Z | k | k | research/cycle7/FRAMEWORK.md | - | k=6 (every spec has >=1 feasible new sample); threshold 0.05/6 = 0.00833 |
| 2026-09-27T14:32:56Z | sample | CARRY-FX__FX-EM | research/cycle7/samples/CARRY-FX__FX-EM.md | cac87c1ef77b4f5660a98142020d2b9cc03782fbdf4c37edeb48eeb16f35315f | before first return |
| 2026-09-27T14:32:56Z | sample | SEAS-FX__FX-EM | research/cycle7/samples/SEAS-FX__FX-EM.md | 4d0853d2b51c72651f9e50331716ae5e07a5217a9294895ee643b32e85c7a00e | before first return |
| 2026-09-27T14:32:56Z | sample | TSMOM-CM__CM-DEEP | research/cycle7/samples/TSMOM-CM__CM-DEEP.md | def5cf6b01aa8905f8fdbb58e1612a253de41964235b50b079d3bd32d82e1f0c | before first return |
| 2026-09-27T14:32:56Z | sample | TSMOM-CM__CM-NEW | research/cycle7/samples/TSMOM-CM__CM-NEW.md | cef5b1eedf6d112769b80cc17db97d0f9d98e687b11db346467d3ed092c1c462 | before first return |
| 2026-09-27T14:32:56Z | sample | TSMOM-FI__FI-DEEP | research/cycle7/samples/TSMOM-FI__FI-DEEP.md | c9bc26039b0c679aeb3ef9303e035557bd85594122480edea116bc677c4d5d19 | before first return |
| 2026-09-27T14:32:56Z | sample | TSMOM-FI__FI-NEW | research/cycle7/samples/TSMOM-FI__FI-NEW.md | a10cca65932a8f0a3a62acbc37de293dcd681cc5f2213cc54cfae2fdf18c773d | before first return |
| 2026-09-27T14:32:56Z | sample | VAL-FX__FX-EM | research/cycle7/samples/VAL-FX__FX-EM.md | bee6a2a4e833ad1f185311d078d51f39f6b0de10218641fc0958353f9323635f | before first return |
| 2026-09-27T14:32:56Z | sample | XSMOM-FX__FX-EM | research/cycle7/samples/XSMOM-FX__FX-EM.md | ca4261ed357e9621657343bd37e538055383fe6a5ba5cfdaf0386ec190201d25 | before first return |
