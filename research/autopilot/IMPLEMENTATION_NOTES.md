# Rebalancing autopilot: implementation notes

`SPEC.md` is frozen and is never edited. This file records how the code resolves points that the SPEC leaves
open or where it contradicts itself. Each item names the code that implements it and the test that pins it.
Tests live in `tests/test_autopilot_engine.py` (synthetic inputs only).

## Usage

```
python -m research.autopilot.cli --config CONFIG.json --holdings HOLDINGS.(json|csv) \
    --price-store STORE --price-version VERSION --report-date YYYY-MM-DD --out OUT_DIR \
    [--log PAPER_LOG.jsonl] [--price-key KEY ...] [--replay] [--expect-manifest-sha256 SHA256]
```

Exit codes: 0 means accepted, with or without proposed trades. 1 means refused: the report, the JSON summary and
the log line are still written, and no trades are proposed. 2 means fatal and nothing is written. Fatal cases are
bad arguments, an unreadable config file, a paper-log chain that fails validation, a forbidden output path, an
existing report/summary with different content, and any unexpected error (item 30).

The price snapshot comes from `research.autopilot.prices.freeze_price_csv(csv, store, version, source=...,
source_identifier=..., retrieved_at=...)`. It is a thin wrapper around `research.data_snapshot.freeze`, and
`retrieved_at` must come from the owner's ingestion record, not from file mtime.

## Resolved ambiguities and decisions

1. **Position cap (SPEC §4, changed 2026-09-29).** Every ticker is capped at 65% of NAV after trades (SSO at 30%),
   except the diversified one-ticket funds XEQT.TO and ZAG.TO, whose cap is their target weight after the cash
   buffer + 5 pp (`config.position_cap`, `one_ticket_cap_addon` = 0.05). So the P3@1.25 / P3@1.5 / P4@1.5 margin
   recipes (XEQT.TO at 74.25% / 89.10% / 71.28% of NAV) now run, with XEQT.TO capped at 79.25% / 94.10% / 76.28%.
   Consequences of reading the SPEC literally: the one-ticket cap follows the target, so it can be tighter than
   65% (P3@1.0 XEQT.TO: 59.40% + 5 pp = 64.40%), and a held XEQT.TO/ZAG.TO that the recipe does not use (target 0,
   e.g. ZAG.TO in P6a) is capped at 5%. `max_position` overrides do not apply to XEQT.TO/ZAG.TO; the owner can
   tighten their cap with `one_ticket_cap_addon` (0 to 0.05). Because the declared drift band is also 5 pp, an
   XEQT.TO/ZAG.TO drift past its cap normally triggers a rebalance; it is refused when nothing triggers (e.g. a
   band widened by override) or the rebalance cannot restore it. `engine.recipe_cap_conflicts` now finds no
   conflict for any default recipe; it still names a conflict created by a tightening override (e.g.
   `max_position` 0.60 with P6a@1.25, whose recipe targets RSST at 61.875%). Tests:
   `test_every_recipe_from_cash_passes_checks`, `test_formerly_conflicting_margin_recipes_now_run`,
   `test_position_cap_per_ticker_rules`, `test_margin_xeqt_drift_beyond_target_plus_5pp_still_refused`,
   `test_tightened_cap_below_a_recipe_target_is_named_as_a_conflict`.
2. **A quarter-end report is a report dated in March, June, September or December**, on any day of that month
   (`engine.is_quarter_end`). The SPEC says "quarter-end reports (Mar, Jun, Sep, Dec)" and gives no day rule.
3. **Relative drift for a ticker with target 0** (held but not in the recipe, e.g. GDE) is treated as infinite.
   Such a ticker therefore triggers when its abs drift is > 1.0 pp (`band_rel_min_abs`). The 5 pp abs band still
   applies. Test: `test_band_decision`.
4. **The band edges are strict** (`>`), with a 1e-12 float tolerance. Alert levels use `>=`, as the SPEC says.
5. **Freshness**: the latest price on or before the report date must be at most `freshness_days` (5) calendar days
   old. This applies to every held ticker, every target ticker and USDCAD. The price file is future-dated, and
   refused, if **any** row in the verified snapshot is dated after the report date. A ticker listed in the
   holdings file counts as held even with 0 shares, so it needs a price. The holdings `as_of` must be 0 to 5 days
   before the report date. Tests: `test_stale_price_refused_and_boundary_accepted`,
   `test_future_dated_price_refused`, `test_stale_or_future_holdings_refused`, `test_holdings_freshness_boundary_accepted`.
6. **When no trade is triggered, the post-trade checks run on the current holdings.** A breach (leverage cap,
   equity/assets floor, position cap) is then a refusal, and the reason says no trades were triggered. The SPEC
   says "post-trade ... breached", and with no trades the post-trade state is the current state. If the band did
   fire but whole-share rounding, the minimum trade size or a lack of cash left no trade to propose, the reason
   says that instead. Tests: `test_leverage_cap_breach_refused`, `test_position_cap_breach_refused`,
   `test_triggered_but_untradeable_breach_says_why`.
   The historical replay shows what this costs: P6a@1.25 targets RSST at 61.875%, so RSST can drift past the 65%
   cap while still inside the 5 pp band. Those months are refused instead of rebalanced, and the refusals repeat
   until a band or quarter-end trigger fires (10 of 497 monthly reports in the CAD 100,000 TFSA replay, 6 in the
   margin replay). Treating a pre-trade cap breach as a rebalance trigger would change the SPEC, so it is left to
   the owner. A refused summary never carries `post_trade`; the state the checks failed on is under
   `checked_state` (item 29).
7. **Every run appends a line to the paper log, including refused runs.** A refused entry records the reasons and
   is `status: "refused"`. It never updates the unit ledger (`unit_ledger.carried = false`). Fatal runs write
   nothing.
8. **Unit accounting for drawdown.** The first accepted report of a `portfolio_id` in a log sets the unit value
   to 100.00. The declared flow on that first report is recorded but not applied. After that, units are issued or
   redeemed for `net_external_flow_cad` at the unit value of (NAV minus the flow). The running peak is the
   maximum unit value over accepted entries of that portfolio. If there are several accepted entries on the same
   date, the last one wins, so a same-day re-run does not double-count a flow. An accepted entry dated after the
   report date is a refusal, because the ledger cannot be rewound. `portfolio_id` defaults to
   `"<config_id>|<account_type>"`. Tests: `test_unit_accounting_flows_and_drawdown_alerts`,
   `test_unit_ledger_ignores_refused_and_other_portfolios_and_rejects_rewind`.
9. **Overrides may only make the engine more conservative.** Risk limits can only be tightened:
   `max_position <= 0.65`, `max_position_sso <= 0.30`, `one_ticket_cap_addon <= 0.05`, `leverage_cap_addon <= 0.15`,
   `equity_assets_floor >= 0.40`, `freshness_days <= 5` and `cash_buffer >= 0.01`. Cost estimates can only be
   raised: `fx_cost >= 0.001`, and `half_spread` can only go at or above the declared values. `commission_cad`,
   `min_trade_cad` and the band widths can be set within the ranges in `config.OVERRIDE_RANGES`. `alert_levels`
   and `calendar_months` cannot be overridden. Any other override is refused as an unsupported configuration.
   Every override is printed in the report. Test: `test_unsupported_or_loosened_config_is_refused`,
   `test_report_prints_overrides`.
10. **Cash buffer.** By default the 1% buffer stays as broker cash. The `cash_buffer_vehicle: "CASH.TO"` override
    holds it in CASH.TO instead, which is refused in margin accounts. In a margin account, CAD cash and the
    margin loan are netted into one CAD balance, so the buffer reduces the loan: the target loan is
    (Σ targets − 1) × NAV, e.g. 23.75% of NAV for L = 1.25. The target leverage for the §4 margin band is
    `max(1, Σ targets)`.
11. **Borrowing.** TFSA, RRSP and nonreg_cash accounts can never borrow. Any `margin_loan_cad > 0` is refused, and
    buys are funded from cash only (a CAD floor of 0). In `nonreg_margin` the borrowing capacity is the recipe loan
    × pre-trade NAV (0 for L = 1.0), and a margin holdings file must state `margin_loan_cad`. USD is never
    borrowed: USD buys are funded by converting CAD, which may be borrowed CAD in a margin account. Margin interest
    is not part of the cost estimate, and the report says so. Tests: `test_no_borrow_accounts_refuse_any_loan`,
    `test_margin_account_borrows_within_caps`, `test_fund_never_borrows_without_capacity`,
    `test_never_negative_cash_property_no_borrow_accounts`.
12. **Trade construction.** A full rebalance to target works as follows:
    - Sells come first, in ticker order. Quantities round toward zero, so the engine sells fewer shares, and a
      ticker with target 0 is sold in full.
    - Buys follow: USD-listed buys first, then CAD-listed buys, each group largest desired CAD value first, with
      the quantity floored. (Before the 2026-09-29 review buys ran largest-first regardless of currency, so a CAD
      buy could convert USD cash that a later USD buy then bought back: two conversion costs, and the report told
      the owner to convert in both directions. The real-price P4@1.5 margin sample showed it. Funding USD buys
      first means a run converts one way at most. Test: `test_buys_never_convert_currency_in_both_directions`.)
    - Each buy is then cut, by binary search, to the largest whole-share count the pools can fund. The cost of a
      buy includes the half-spread and the commission.
    - A trade whose CAD value (price × shares, before costs) is below `min_trade_cad` is skipped and listed in
      the report. So is a buy that was cut below the minimum.
    - Sale proceeds stay in the listing currency. Currency is converted only to fund a buy: own-currency cash is
      used first, then the other currency is converted at `fx_cost`.
    - In a margin account, USD sale proceeds can therefore sit as USD cash next to a CAD loan. Gross
      assets/equity then lands inside the 0.10 band but above target; `test_margin_leverage_trigger_end_to_end`
      shows 1.264 against 1.2375. The report adds a note that converting that cash would reduce the loan, and
      leaves the decision to the owner. The SPEC only calls for FX conversion to fund USD-listed ETFs, so the
      engine does not convert it on its own.
    - The Norbert's-gambit note (DLR.TO/DLR-U.TO) is printed whenever the proposed trades need any conversion.
    - Commission is charged per trade in CAD, and paid from the USD pool (converted at the snapshot USDCAD rate)
      for USD-listed tickers.
13. **The leverage cap uses effective gross exposure**: Σ value × (sum of the ticker's sleeve exposures) / NAV.
    Per unit, that is RSSB, RSST and SSO 2.0, GDE 1.8 and the others 1.0. The cap is the SPEC §1 target gross
    (e.g. 1.875 for P6a@1.25) + 0.15.
14. **Price files.** Without `--price-key`, every CSV record in the snapshot with the columns
    `date,ticker,close,currency` is read. A (ticker, date) pair may appear only once across those files. USDCAD is
    a row with ticker `USDCAD`, currency `CAD`, and close = CAD per USD. A ticker quoted in a currency other than
    its listing currency is refused. The bytes that are parsed are re-hashed against the verified manifest record.
    `--replay` skips only the live-source check, and the report labels the run REPLAY.
15. **Hash chain.** Each line is canonical JSON (sorted keys, no whitespace, no NaN). `entry_hash` is the SHA-256
    of the canonical JSON of the entry without `entry_hash`, and `prev_hash` is the previous line's `entry_hash`
    (64 zeros for the first line). The whole chain is validated before each append, and any failure is fatal. The
    CLI also checks that the chain did not change while the report was being computed.
16. **Forward-registry guard.** The paper log and every output path are refused if they name a file called
    `registry.jsonl`, lie in or under `reports/forward/`, or are the same file as the registry (symlink or hard
    link). Names and path components are compared case- and Unicode-normalisation-insensitively (APFS/HFS+ are
    both by default), and every existing ancestor of the target is checked with `samefile` against
    `reports/forward/`, so `Reports/Forward/x.jsonl` or `REPORTS/FORWARD/REGISTRY.JSONL` are refused whether or
    not the registry exists yet (item 28). The default log is `reports/autopilot/paper_log.jsonl`, as in SPEC §6.
17. **No network.** No module in the package imports a network, subprocess or async module (checked by an AST
    test and an import-side-effect test). A test runs the whole CLI with `socket` constructors and resolvers
    monkeypatched to raise.
18. **Determinism.** No clock is read. The report date is an input. Only file basenames and SHA-256s of the
    inputs appear in the outputs. The JSON uses sorted keys and fixed indentation. Identical inputs give
    byte-identical report, summary and log line (`test_determinism_byte_identical_report_json_and_log_entry`).

19. **Report label.** A config may carry an optional `label` (one line, at most 200 characters). The report prints
    it in bold under the title, and the JSON summary and log keep it in `config.label`. The real-price samples use
    it for "HYPOTHETICAL HOLDINGS — research sample, not a recommendation". An invalid label makes the config
    unsupported, so the run is refused. Test: `test_config_label_is_printed_under_the_title_and_validated`.

## SPEC §7 historical replay (`synth_prices.py`, `replay.py`)

Run `python -m research.autopilot.synth_prices` once to build and freeze the panel, then
`python -m research.autopilot.replay`. The replay writes `reports/cycle9/autopilot/replay_by_year.csv`,
`replay_summary.csv`, `replay_monthly.csv` and `replay_meta.json`. Tests are in `tests/test_autopilot_replay.py`.

20. **Synthetic prices.** The panel is month-end 1985-01..2026-05, and every series starts at 20.00 in its listing
    currency. XEQT.TO is EQ_G_tfsa, ZAG.TO is BOND, ZGLD.TO is GOLD and CASH.TO is CASH, all in CAD. DBMF is
    RF_USD + X_TREND in USD. RSSB is EQ_G_tfsa + (BOND − CASH), RSST is EQ_G_tfsa + X_TREND and GDE is
    0.9·EQ_G_tfsa + 0.9·(GOLD − CASH) + 0.1·CASH. Those three are built in CAD and then priced in USD via USDCAD, so
    their CAD value follows the CAD formula exactly. The current version is `autopilot_replay_synth_v2` (sources in
    `data/cycle9/autopilot_replay/source_v2/`). `autopilot_replay_synth_v1` (sources in `source/`) is frozen and
    kept unchanged; it left out the CASH earned on GDE's 10% collateral (a 90/90 fund holds 90% equity, 90% gold
    futures and 10% cash). Only the GDE rows differ between the versions, and no recipe holds GDE, so the replay
    results do not depend on the fix. Test: `test_synthetic_v2_changes_only_gde`. SSO compounds the daily `P7-2x_eq_letf` series of
    `p7_letf_daily_sim.parquet` by month (USD). USDCAD is the cycle-8 `fx_monthly` rate.
    The inputs are the frozen `cycle8_v1` view, verified before use, and the LETF simulation, whose SHA-256 is
    recorded. `retrieved_at` is the latest ingestion time among the cycle-8 records, never a file mtime.
    The stated approximations are frozen in `prices/synthetic_provenance.json`:
    - The stacked ETFs' equity legs use the global sleeve (real RSST and GDE are US-only).
    - Overlays are financed at the CAD T-bill rate.
    - RSSB's bond leg is the cycle-8 BOND sleeve, not US Treasuries.
    - Fees beyond those in the cycle-8 sleeves are ignored.
    - Prices never split.
    - Dates are calendar month-ends, some of them weekends.
21. **Point-in-time prices.** Each month the engine sees the verified snapshot cut to rows dated on or before the
    report date. The manifest hash is unchanged. Without the cut, every historical report would be refused as
    future-dated (§5).
22. **What the replay does each month.** It writes a holdings JSON (as-of = report date, flow 0) and parses it with
    the engine's parser. It runs `engine.evaluate`, renders the report and appends a `paperlog.make_entry` to an
    in-memory chain, which drives the unit ledger and alerts. At the end it writes that chain to a throwaway log
    (a temporary directory unless `--log-dir` is given) and re-validates it with `read_chain`.
    Accepted trades are filled at the report-date close with the declared half-spread, commission and FX cost. The
    engine's own `fund` routine is replayed in trade order. The replay then checks the shares, cash and loan
    against the engine's post-trade estimate, and checks the realised NAV change against the estimated cost.
    Refused months carry the holdings unchanged.
    Between reports, positive CAD cash earns cycle-8 CASH, a CAD loan costs cycle-8 MRATE, and USD cash earns
    cycle-8 RF_USD. SPEC §7 names no rate for USD cash, so RF_USD is used as the USD analogue of CASH.
    Balances are rounded to cents each month.
23. **Counting rules.**
    - A band event is an accepted report triggered by the drift band or the margin assets/equity band.
    - A calendar event is an accepted report triggered only by the quarter-end check.
    - The first report (buying from all cash) counts as a band event. It is also reported separately
      (`initial_*`) and left out of the `*_ex_initial` per-year averages.
    - Turnover and cost in bps are sums of traded value / pre-trade NAV and cost / pre-trade NAV.
    - FX converted is the CAD value of the currency sold to fund buys.
    - Alerts count the monthly reports at each level.
    - Replay CAGR and max drawdown use the month-end NAV after fills, measured from the start cash.
    - The cycle-8 ideal is `item_returns_monthly.parquet[config_id]` compounded over the same 496 return months.
      For L > 1 it is margin-financed at MRATE with the no-withholding equity sleeve. The stacked TFSA replay is
      financed at CASH inside the ETFs and uses EQ_G_tfsa. That difference in construction explains most of the
      gaps.
24. **Owner tolerance in the replay and samples.** It is the tightest cycle-8 tolerance in `answer.csv` under which
    the config was eligible: P4@* get 25, P3@1.0 and P6a@1.0 get 35, and P6a@1.25 gets 50. P3@1.25 and P3@1.5 were
    eligible at none, so they get 50. The alerts are descriptive only.
25. **Formerly conflicting margin configs.** Before the §4 change the P3@1.25, P3@1.5 and P4@1.5 margin replays
    were refused on every report and sat in cash. They now run all 497 reports with no refusal, and their replay
    CAGR is within 0.2 pp of the cycle-8 ideal. Test: `test_formerly_conflicting_margin_config_now_runs_every_month`.

## Real-price samples (`make_samples.py`)

`python -m research.autopilot.make_samples` does four things:
- It freezes `data/cycle9/autopilot_prices/source/prices_20250829_20260831.csv` into
  `data/cycle9/autopilot_prices/store` as version `autopilot_prices_20260831`. The file holds the cycle-8 view's
  split-adjusted `close` and `fx_daily` USDCAD, using the last row on or before 2025-08-29 and 2026-08-31.
- It writes configs and HYPOTHETICAL holdings to `research/autopilot/examples/`.
- It runs the real CLI in verified mode for the 10 samples and the 2 refusal examples.
- It writes the outputs to `reports/cycle9/autopilot/samples/{tfsa,nonreg_margin,refusals}/`, with
  `sample_paper_log.jsonl`. Outputs are staged in a temporary directory and copied over, so a re-run reproduces
  the same bytes.

26. **Hypothetical holdings.** CAD 100,000 is put at target on 2025-08-29: shares are floored at the close plus
    the half-spread, USD is bought at the 0.10% conversion cost, and any negative CAD remainder is the margin
    loan. Positions are then carried unchanged, with no flows, to a holdings file dated 2026-08-31, so the
    freshness rule applies. Until the 2026-09-29 review the cash was also carried unchanged, which overstated the
    margin samples' NAV (a year of interest on the loan was missing) and understated every sample's cash (a year
    of distributions was missing). `make_samples.carry` now walks the 12 month-ends: a CAD loan accrues the
    cycle-8 margin rate ((policy_cad at the previous month-end + 1.5%) / 12), then the month's per-share
    distributions from the cycle-8 view are paid in cash in the listing currency, with USD-listed funds net of
    15% US withholding. Positive cash earns nothing. Test:
    `test_sample_carry_accrues_margin_interest_then_pays_distributions`. SSO split 2:1 on 2025-11-20. Its 2025-08-29
    close is already split-adjusted, so share counts are in post-split units.
27. **Refusal examples.** A STALE-price report is dated 2026-09-08, 8 days after the last price. A TFSA holdings
    file shows a CAD 10,000 margin loan. The P4@1.5 and P6a@1.25 margin samples are accepted (the P4@1.5 one was
    refused before the §4 change).

## Reviewer findings (2026-09-29)

Each finding was reproduced with a probe in `$TMPDIR` before it was fixed.

28. **AP-SAFE-1, guard is case-sensitive: reproduced.** The exact example `REPORTS/FORWARD/registry.jsonl` was
    already refused by the file-name rule. But `Reports/Forward/x.jsonl` passed and would have written inside
    `reports/forward/`, and `reports/forward/REGISTRY.JSONL` passed whenever the registry did not exist yet. Fixed
    in `paperlog.guard_path` (item 16). Tests: `test_guard_path_is_case_insensitive_ap_safe_1`,
    `test_guard_path_file_identity_catches_what_names_miss_ap_safe_1`,
    `test_cli_refuses_case_variant_forward_log_and_writes_nothing`.
29. **AP-SAFE-2, refused runs kept the rejected rebalance: reproduced.** A run refused by a post-trade check kept
    `post_trade` ("after the proposed trades (estimated)") and the report said "Decision: full rebalance of all
    positions to target". Now a refused summary always has `post_trade: null`. The state the checks failed on
    moves to `checked_state`, with `kind` either `rejected_hypothetical_rebalance` (with `rejected_trade_count`
    and a REJECTED HYPOTHETICAL basis) or `current_holdings`. `decision.action` says `none: REFUSED ...`, and the
    report prints the state under "REJECTED hypothetical state after a full rebalance (NOT proposed)". Accepted
    runs record `decision.action` too. Test:
    `test_refused_after_checks_has_no_post_trade_and_labels_the_rejected_state_ap_safe_2`.
30. **AP-SAFE-5, unexpected exceptions exited 1: reproduced.** A valuation overflow (close 1e300 × 10^9 shares)
    raised `EngineError`, and Python exited 1, the "refused" code. `cli.main` now maps any unexpected exception to
    exit 2. `cli.run` is all-or-nothing: the report and summary are staged as fsynced temporary files and renamed
    into place, then the log line is appended. If anything fails before the append completes, the files and
    directories this run created are removed. Pre-existing identical outputs are left alone. Output files are
    0644. Tests: `test_unexpected_exception_is_fatal_and_writes_nothing_ap_safe_5`,
    `test_failure_after_writing_started_removes_outputs_ap_safe_5`.
31. **AP-SAFE-3, manifest not pinned: reproduced.** Two stores frozen under the same version name with different
    prices were both accepted into one log. Now the first paper-log entry that recorded a verified manifest for a
    `dataset_version` pins it (`engine.manifest_pin`). A later run of that version with a different manifest is
    refused. The refused entry does not move the pin, and a new version name is unaffected. The optional
    `--expect-manifest-sha256` refuses on any other manifest; a malformed value is fatal. The pin and the
    expectation are recorded in `inputs.prices` and printed with "(matches)" or "(MISMATCH)". Tests:
    `test_manifest_is_pinned_by_the_paper_log_ap_safe_3`, `test_expect_manifest_sha256_option_ap_safe_3`.
32. **AP-SAFE-4, silent truncation: reproduced.** Deleting trailing lines left a valid chain, and no output
    recorded the log position. Every summary now carries `paper_log` = {`seq`, `prev_entry_hash`,
    `entries_before`}, and the report prints it with the full hash. The CLI checks that the appended entry sits
    exactly there. `paperlog.check_summary_against_log(chain, summary)` reports a summary whose entry lies past
    the end of the log (truncated) or whose seq now holds a different body (re-appended after truncation). Test:
    `test_log_head_recorded_and_truncation_detectable_ap_safe_4`.
33. **AP-SAFE-6, absolute paths in refusal text: reproduced.** A missing store or version, or a tampered
    manifest, put the absolute store path into the refusal reason (`/private/tmp/.../store/versions/...`).
    `prices.location_free` rewrites the store, in both its absolute and resolved forms, to `<price-store>` and cuts
    any other absolute path to `<path>/<name>`. The same failure then gives the same text from any location or
    working directory. The FATAL stderr messages print only file names for the log and outputs. Test:
    `test_refusal_text_is_location_independent_ap_safe_6`.

## Math / replay review (2026-09-29)

Checked against SPEC §3/§4/§7 and the cycle-8 code:
- Recipes and §3 exposures: stacked Σ = 1, margin Σ = L, loan L − 1, exact (`test_recipes_reproduce_exposures_exactly`).
- Cash buffer: 0.99 × weights; nets against the loan in margin accounts (item 10).
- Drift rules: abs > 5 pp, or relative > 25% of target and abs > 1 pp; the calendar check runs at quarter-end
  at 1 pp. Margin accounts use assets/equity against max(1, Σ targets).
- Leverage: effective gross (RSSB/RSST/SSO 2.0, GDE 1.8) for every account, plus equity/assets for margin.
- Cost and FX identities in `fund`: CAD spent × (1 − cost) / USDCAD = USD received, and the reverse.
- Unit value, peak and drawdown with flows: flows are issued at NAV minus the flow; same-day re-runs supersede.
- Synthetic prices: USD close = I × USDCAD₀ / USDCAD_t, so the CAD value follows the CAD return. DBMF and SSO
  are USD assets, and the SSO simulation is USD (validated against real SSO in cycle 8). Carry rates use the rate
  at the previous month-end, so there is no look-ahead.
- Replay: fills, interest and aggregation, checked by the replay's own identity checks and the tests. The
  comparison with the cycle-8 ideal uses the same 496 months.

Two real defects were found and fixed: the GDE collateral income (item 20, a new frozen version), and the
two-way FX conversion in trade construction (item 12). The samples' missing interest and distributions were
also fixed (item 26).

