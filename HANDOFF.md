# quant_v7 handoff for new models (Claude, Codex/Sol)

Updated 2026-09-27. Read this first, then the entry points below. This is a **research-only**, falsification-first
program. Nothing here authorizes trading.

## Standing rules (owner)

- **Preregister before the first return of anything.** Spec file → SHA-256 + UTC time in a ledger → run once. No
  reruns with changed parameters.
- **Bug fixes:** only when diagnosed against an external benchmark or the frozen paper rule (never our own Sharpe).
  Log the fix before the rerun.
- **Nulls stand.** Audits are for positives only. Do not re-mine spent families or rescue failures.
- **No live trading or orders.** No broker, credential, cron or launchd changes. No paid data. No crypto. The LSE
  Terminal MCP is read-only (never `place_order` etc.).
- **No forward-registry writes** except by the owner's scheduled process (`reports/forward/registry.jsonl`, hash
  chain, head seq 3 `04dff2c7…`).
- **Don't edit old reports** or another agent's files (Sol/Codex files belong to Sol).
- **Data:** LSE vault data is licensed and never committed (`.gitignore`). New large data dirs under `data/` are local
  only; the snapshot manifests pin their bytes.

## Protocol stack (in force)

| Doc | What it does |
|---|---|
| `research/PROTOCOL_AMENDMENT_2026-09-23.md` (A1), `_2_` (A2), `_3_` (A3) | Registered gates, guards G1–G7 (`research/certify/guards.py`), power check (`research/power`) |
| `research/PROTOCOL_AMENDMENT_4_2026-09-26.md` (A4) | Calibrated inference (`research/amendment4/`): active returns vs exposure-matched control, null-calibrated HAC t, crash layer, calibrated CIs, realistic power (nothing certifies Sharpe 0.25–0.40) |
| `research/PROTOCOL_AMENDMENT_5_REPLICATION_2026-09-25.md` (A5, Sol) | Replication of documented premia: fidelity tiers, post-publication estimates, book rule |
| `research/DATA_SNAPSHOT_POLICY.md` | `python -m research.data_snapshot` freeze/register/run before any return |

For cycle 6, the owner waived formal registration of A4/A5; the cycle-6 ledger hashes serve.

## Where things stand

**Cycle 6 (Claude): Styles-Everywhere book** — `reports/cycle6_core_premia/RESULTS.md`

| Item | Result |
|---|---|
| Components (style × asset class) | 20 run: 6 styles (trend, cross-sectional momentum, value, carry, BAB/defensive, seasonality) × up to 4 classes (equity indices, government bonds, FX, commodities) |
| POSITIVE components | **0 of 20** (Bonferroni 0.05/20; best p 0.021, FX carry) |
| Fidelity passes | 6: trend in bonds and commodities; FX momentum, value, carry and seasonality |
| Book | **POSITIVE by the frozen rule.** Post-publication (2019-02 on, 92 months) Sharpe 0.60 [0.05, 1.10]. Runs at ~3–4% vol because the A5 2× gross cap binds. **Pending owner audit.** |
| Canadian variants | ETF long/flat (TFSA/RRSP) post Sharpe 0.52 [−0.07, 1.16]; margin with micro futures 0.08 at CAD 100k. Neither excludes zero. |

Cycle-6 files:
- rules: `research/cycle6/FRAMEWORK.md`, `FRAMEWORK_ADDENDUM_1.md`;
- ledgers: `research/cycle6_prereg_ledger.md` and `research/cycle6/trial_ledger.csv` (23 runs, no reruns);
- specs: `research/cycle6/specs/`;
- engine and runners: `research/cycle6/engine/` (hash-guarded runner), `research/cycle6/tradable/`;
- data build: `research/cycle6/data_rates`, `data_equity`, `build_eval.py`;
- tests: `tests/test_cycle6_*`;
- snapshots (local): `cycle6_eval_v1` `ba67379b…`, `cycle6_trade_v1` `940335bf…`.

**Sol/Codex (2026-09-26): beyond-menu premia** — `reports/sol_beyond_menu/RESULTS.md`
- Candidates: factor momentum, overnight equity, aggregate short interest, FOMC risk.
- Development result: **POSITIVE none**.
- Ledger: `research/sol_prereg_ledger.md`.

**Codex momentum/gold verification** — `research/momentum_verification/` (`codex_*`) and the
`reports/momentum_gold_*` folders. momentum_gold_v1 is forward-only, with its first decision on 2026-10-01; the owner
records it.

**Earlier cycles** (`research/RESEARCH_LEDGER_2026-09-23.md`, `RESEARCH_DIRECTION_2026-09-23.md`):
- Record: 0 of 11 development passes validated.
- PEAD is not an edge.
- Treasury month-end: WEAKENED, forward observation only (exit after the 9-29 close, owner's process).
- Spent or dead:
  - commodity roll;
  - crypto funding cross-section (closed; validation window locked, `research/crypto_funding_xs/LOCK_2023_2026.md`);
  - dealer inventory;
  - the families listed in the ledger.
- Paid-data case (not bought): Sharadar/CRSP for delisted US equities.

## Key lessons (don't re-derive)

- **Power:** at realistic post-decay Sharpe (0.25–0.40), no free-data design can certify an edge (A4 §5). Only years
  add power; breadth does not multiply effective months.
- **Controls:** long-biased books must be gated on active returns versus an exposure-matched control. Raw returns
  false-pass about 6%.
- **Free-data limits** (`reports/core_premia_20260925/data_feasibility.md`):
  - no contract-level futures;
  - no free delisted US prices;
  - no free CAPE or BE/ME by country;
  - no commodity carry beyond energy (EIA ends 2024-04).
- **Retail implementation:** a CAD 25–100k futures book cannot hold its target risk, and there is no micro
  price-based Treasury future.

## Open decisions for the owner

1. Audit the cycle-6 book positive: short post-publication window, gross-cap-bound vol, and SEAS-FX included on
   fidelity alone.
2. Whether any paper-only forward observation of the book is registered (A5 §F).
3. The paid-data question (Sharadar ~$500/yr) remains open.

## How to run and verify

- Tests: `pytest tests/test_cycle6_engine.py tests/test_cycle6_tradable.py tests/test_amendment4.py`.
- Reproduce a component (it refuses duplicates by design):
  `python -m research.cycle6.run_component --spec research/cycle6/specs/<ID>.md --snapshot-root <view> --membership <view>/eval/candidate_list.csv --out <dir>`.
  This needs the local snapshot store `data/cycle6/snapshot_store`, which is not in git. Rebuild the inputs with
  `research/cycle6/data_*` and `build_eval.py`, then check the manifest hash.
