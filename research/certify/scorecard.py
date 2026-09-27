"""Trust scorecard (Workstream C2, edge certification): candidate x evidence-layer table.

This module does not re-run any evaluation. Every score below is a curated summary of an existing
report file already on disk (dev_results.json / validation_results.json / REPORT.md / audit
summaries / the forward registry), each cited by path. Running this module re-derives nothing; it
only re-serialises the table to reports/certify/scorecard.csv and reports/certify/scorecard.json,
and checks that every cited file still exists.

Evidence layers (fixed order):
  L0 mechanism / economic rationale
  L1 pre-registered dev pass
  L2 null calibrated (P(pass | null) <= 5%)
  L3 placebo / random-selection test passed
  L4 validation pass by the registered rule
  L5 independent adversarial audit (verdict)
  L6 alternate data source reproduction
  L7 post-publication or out-of-discovery sample
  L8 clean forward evidence in the anchored registry (reports/forward/registry.jsonl)

Status values: PASS, FAIL, PARTIAL, NOT-RUN.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "reports" / "certify"

LAYERS = [
    ("L0", "mechanism / economic rationale"),
    ("L1", "pre-registered dev pass"),
    ("L2", "null calibrated (P(pass|null) <= 5%)"),
    ("L3", "placebo / random-selection test passed"),
    ("L4", "validation pass by the registered rule"),
    ("L5", "independent adversarial audit (verdict)"),
    ("L6", "alternate data source reproduction"),
    ("L7", "post-publication / out-of-discovery sample"),
    ("L8", "clean forward evidence in the anchored registry"),
]

# Each candidate: list of (layer_code, status, file, note), one tuple per layer actually filled in
# below (layers not listed default to NOT-RUN with no file). Every `file` is relative to ROOT and
# is checked to exist when this module runs.

SCORECARD: dict[str, list[tuple[str, str, str, str]]] = {

    "tsy_month_end": [
        ("L0", "PASS", "research/tsy_month_end/PLAN.md",
         "calendar-forced index-extension flow at month end (Hartley & Schwarz); quarter-end months "
         "stronger (44.6 vs 34.9 bp), SPY correlation -0.23 so it is not simply the equity turn-of-month"),
        ("L1", "PASS", "reports/tsy_month_end/dev_results.json",
         "dev active Sharpe 0.664 vs gate 0.520 (base cost); shift-null p 0.006"),
        ("L2", "PASS", "reports/tsy_month_end/validation_results.json",
         "P(pass|null): dev 0.020, val 0.017, both <= 0.05 (shift_null.P_pass_given_null)"),
        ("L3", "PASS", "reports/tsy_month_end/dev_results.json",
         "window-position placebo (k=3..15): month-end (M) ranks 1st of 14 candidate windows "
         "(placebo_rank 0.071); every non-month-end position in validation is flat or negative"),
        ("L4", "FAIL", "reports/tsy_month_end/validation_results.json",
         "registered gate: validation active Sharpe >= 0.75; actual 0.692 (VALIDATION_UNLOCK.md criteria)"),
        ("L5", "PARTIAL", "reports/audit_tsy/audit_summary.json",
         "independent audit verdict: WEAKENED (not confirmed, not refuted)"),
        ("L6", "PASS", "reports/audit_tsy/audit_summary.json",
         "LSE last-trade-close reproduction: active Sharpe 0.713 (val) vs project's 0.692; "
         "yfinance-raw-plus-dividends reproduction matches project figures to <0.5bp"),
        ("L7", "PARTIAL", "reports/audit_tsy/e_postpub.json",
         "post-pub (2019-10 to 2026-08) active Sharpe 0.560, shift p 0.059 (misses 0.05); "
         "last 36 months Sharpe 0.252, shift p 0.279 (clearly weaker); own G6 guard t=1.55 < 1.65 "
         "-- see reports/certify/guards_tsy_month_end.json"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl",
         "spec_registration only (tsy_month_end_v1); no decision/outcome entries yet"),
    ],

    "commodity_roll": [
        ("L0", "PASS", "research/commodity_roll/PLAN.md",
         "roll/term-structure return from same-commodity ETF pairs (Mou 2011; Gorton-Rouwenhorst; Erb-Harvey)"),
        ("L1", "PASS", "reports/commodity_roll/dev_results.json",
         "dev net base Sharpe 0.596 vs gate 0.557; bootstrap p 0.0064"),
        ("L2", "PASS", "reports/commodity_roll/dev_results.json",
         "P(pass|null) = 0.006 <= 0.05 (mean-centred block bootstrap)"),
        ("L3", "NOT-RUN", "research/commodity_roll/PLAN.md",
         "no random-selection or window-position placebo was registered for this family (only a "
         "shift/bootstrap null); own G1 guard found the NW-HAC alpha t-stat drops to 1.04 once the "
         "front-month basket and SPY are controlled jointly -- see reports/certify/guards_commodity_roll.json"),
        ("L4", "NOT-RUN", "research/commodity_roll/PLAN.md",
         "validation window 2017-01-03..2026-09-17 is locked and was not run"),
        ("L5", "NOT-RUN", "reports/audit_commodity_roll/raw",
         "independent audit IN PROGRESS: raw source data (FRED/yfinance) has been pulled; no results "
         "file exists yet"),
        ("L6", "NOT-RUN", "reports/audit_commodity_roll/raw",
         "alternate-source reproduction not yet attempted (part of the in-progress audit)"),
        ("L7", "NOT-RUN", "research/commodity_roll/PLAN.md", "not published; no post-hoc sample exists"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl", "no forward spec registered for commodity_roll"),
    ],

    "spmo_gld_5050": [
        ("L0", "PARTIAL", "research/RESEARCH_LEDGER_2026-09-23.md",
         "the known stock/gold diversification effect, not a distinct edge (ledger section 1)"),
        ("L1", "FAIL", "reports/momentum_gold_20260919/REPORT.md",
         "\"Development status: none. It is a post-hoc follow-up on already-viewed years, chosen after "
         "three other fund designs.\""),
        ("L2", "NOT-RUN", "reports/momentum_gold_20260919/REPORT.md", "no P(pass|null) was computed"),
        ("L3", "NOT-RUN", "reports/momentum_gold_20260919/REPORT.md", "no placebo/random-selection test was run"),
        ("L4", "NOT-RUN", "reports/momentum_gold_20260919/REPORT.md",
         "not a gated strategy; it is a fixed benchmark allocation with no registered pass/fail rule"),
        ("L5", "PARTIAL", "reports/momentum_gold_audit_20260921/REPORT.md",
         "independent audit ran and reproduced the ledger exactly, but its verdict is \"retain as a "
         "research benchmark ... not a validated trading edge. Do not promote on full-period performance.\""),
        ("L6", "PASS", "reports/momentum_gold_audit_20260921/REPORT.md",
         "official SPDR GLD historical-archive API reproduction within 0.000572 bp of the cached series"),
        ("L7", "NOT-RUN", "reports/momentum_gold_20260919/forward_paper_spec.json",
         "first forward decision due 2026-10-01 (not yet reached as of 2026-09-23); 0 fills so far "
         "(forward_paper_events.jsonl)"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl",
         "spec_registration only (momentum_gold_v1); no decision/outcome entries yet"),
    ],

    "pead": [
        ("L0", "FAIL", "reports/pead_attack/results.json",
         "SUE-sign direction contributes -0.58%/yr (decomposition_capm); the filter correlates -0.63 "
         "with the stock's own 20-day pre-event return, i.e. it is a dip-buying filter, not PEAD"),
        ("L1", "NOT-RUN", "research/PREREGISTRATION_pead_2004_2014.md",
         "the production model predates the project's pre-registration protocol; no pre-registered "
         "dev-pass artifact exists for the original fit"),
        ("L2", "NOT-RUN", "reports/pead_attack/results.json",
         "no formal null-world P(pass|null) was computed for PEAD (only placebo distributions P1/P1L/P1G/P2/P3)"),
        ("L3", "FAIL", "reports/pead_attack/results.json",
         "real Sharpe 0.700 vs random-selection placebo mean 0.459, p=0.113 (pre-registered); "
         "classification \"C: EXPOSURE EDGE WITHOUT MODEL SKILL\""),
        ("L4", "FAIL", "reports/pead_2004_2014/REPORT.md",
         "pre-registered 2004-2014 replication, Outcome: FAIL (alpha HAC t=1.12 < 2 required; fails "
         "\"beats all events control\")"),
        ("L5", "FAIL", "reports/pead_audit/REPORT.md",
         "accounting-corrected true Sharpe 0.70 (reported was 1.34); deflated-Sharpe probability 0.85 "
         "(0.95 needed); edge over control concentrated in one 2021-10..2023-10 episode "
         "(reports/future_lab/REPORT.md: IR 0.30 -> -1.29 with that window removed, p 0.02)"),
        ("L6", "NOT-RUN", "reports/forward/lse_reconstruction_check.json",
         "an LSE-vs-yfinance mark check exists but is not a formal alternate-source backtest "
         "reproduction; it found LSE 1d bars off by up to 253bp from official closes"),
        ("L7", "FAIL", "reports/forward/PEAD_FORWARD_DIAGNOSIS.md",
         "\"not trustworthy as clean forward evidence today\": n=1 genuinely-forward decision (AZO), "
         "89 of 92 ledger events are backfilled, live decisions logged ~3.5h after the close they fill at"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl",
         "zero PEAD entries in the anchored registry; excluded pending an entry-convention fix (pead_bot_v2)"),
    ],

    "mbs_convexity": [
        ("L0", "PASS", "research/mbs_convexity/PLAN.md",
         "negative-convexity premium: long MBB, point-in-time OLS Treasury hedge (IEF/SHY)"),
        ("L1", "FAIL", "reports/mbs_convexity/dev_results.json",
         "dev net base Sharpe 0.402 vs gate 0.609; bootstrap p 0.043 (selected: false)"),
        ("L2", "NOT-RUN", "reports/mbs_convexity/dev_results.json", "dev failed; no further layer computed"),
        ("L3", "NOT-RUN", "reports/mbs_convexity/dev_results.json", "dev failed; no further layer computed"),
        ("L4", "NOT-RUN", "reports/mbs_convexity/REPORT.md", "validation (2017-2026) stays locked, not run"),
        ("L5", "NOT-RUN", "reports/mbs_convexity/REPORT.md", "no audit requested"),
        ("L6", "NOT-RUN", "reports/mbs_convexity/REPORT.md", "no audit requested"),
        ("L7", "NOT-RUN", "reports/mbs_convexity/REPORT.md", "not published"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl", "no forward spec registered"),
    ],

    "sector_month_end": [
        ("L0", "PARTIAL", "reports/sector_month_end/REPORT.md",
         "\"a mechanism-informed follow-on to tsy_month_end, not independent corroboration\""),
        ("L1", "FAIL", "reports/sector_month_end/dev_results.json",
         "dev base active Sharpe -0.433 (negative); selected: false"),
        ("L2", "NOT-RUN", "reports/sector_month_end/dev_results.json", "dev failed; no further layer computed"),
        ("L3", "NOT-RUN", "reports/sector_month_end/dev_results.json", "dev failed; no further layer computed"),
        ("L4", "NOT-RUN", "reports/sector_month_end/REPORT.md", "validation (2015-01..2026-08) stays locked, not run"),
        ("L5", "NOT-RUN", "reports/sector_month_end/REPORT.md", "no audit requested"),
        ("L6", "NOT-RUN", "reports/sector_month_end/REPORT.md", "no audit requested"),
        ("L7", "NOT-RUN", "reports/sector_month_end/REPORT.md", "not published"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl", "no forward spec registered"),
    ],

    "fx_hedge_rebal": [
        ("L0", "PASS", "reports/fx_hedge_rebal/REPORT.md",
         "hedge-rebalancing flow at month end (Melvin & Prins 2015 mechanism)"),
        ("L1", "FAIL", "reports/fx_hedge_rebal/dev_results.json",
         "dev base Sharpe 0.090 vs gate 0.722; selected: false"),
        ("L2", "NOT-RUN", "reports/fx_hedge_rebal/dev_results.json", "dev failed; no further layer computed"),
        ("L3", "NOT-RUN", "reports/fx_hedge_rebal/dev_results.json", "dev failed; no further layer computed"),
        ("L4", "NOT-RUN", "reports/fx_hedge_rebal/REPORT.md", "validation (2021-01..2026-08) stays locked, not run"),
        ("L5", "NOT-RUN", "reports/fx_hedge_rebal/REPORT.md", "no audit requested"),
        ("L6", "NOT-RUN", "reports/fx_hedge_rebal/REPORT.md", "no audit requested"),
        ("L7", "NOT-RUN", "reports/fx_hedge_rebal/REPORT.md", "not published"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl", "no forward spec registered"),
    ],

    # "Any other family marked promising" (research/RESEARCH_LEDGER_2026-09-23.md, row 12): the only
    # other family the ledger classifies FORWARD-ONLY rather than SPENT, besides tsy_month_end and
    # SPMO/GLD (both already scored above). Included for completeness; it in fact misses its own dev gate.
    "letf_rebalancing": [
        ("L0", "PARTIAL", "reports/letf_rebalancing/REPORT.md",
         "monotone dose-response with predicted close flow (Cheng & Madhavan 2009; Shum et al. 2016), "
         "but the top-flow bucket is noisy (t=1.5)"),
        ("L1", "FAIL", "reports/letf_rebalancing/REPORT.md",
         "L1 net Sharpe 0.39, L2 0.48, both miss the 0.50 development gate; validation not run, stays locked"),
        ("L2", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "dev failed; no further layer computed"),
        ("L3", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "dev failed; no further layer computed"),
        ("L4", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "validation (2021-2026) stays locked, not run"),
        ("L5", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "no audit requested"),
        ("L6", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "no audit requested"),
        ("L7", "NOT-RUN", "reports/letf_rebalancing/REPORT.md", "not published"),
        ("L8", "NOT-RUN", "reports/forward/registry.jsonl", "no forward spec registered"),
    ],
}


def build_rows() -> list[dict]:
    layer_names = dict(LAYERS)
    rows = []
    for candidate, entries in SCORECARD.items():
        given = {code: (status, file, note) for code, status, file, note in entries}
        for code, name in LAYERS:
            status, file, note = given.get(code, ("NOT-RUN", "", "not evaluated for this candidate"))
            if file:
                p = ROOT / file
                if not p.exists():
                    raise FileNotFoundError(f"scorecard cites a missing file: {file} ({candidate} {code})")
            rows.append({
                "candidate": candidate,
                "layer": code,
                "layer_name": name,
                "status": status,
                "file": file,
                "note": note,
            })
    return rows


def write(out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows()

    csv_path = out_dir / "scorecard.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate", "layer", "layer_name", "status", "file", "note"])
        w.writeheader()
        w.writerows(rows)

    json_path = out_dir / "scorecard.json"
    by_candidate: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_candidate.setdefault(r["candidate"], {})[r["layer"]] = {
            "layer_name": r["layer_name"], "status": r["status"], "file": r["file"], "note": r["note"],
        }
    with open(json_path, "w") as f:
        json.dump({"layers": dict(LAYERS), "candidates": by_candidate}, f, indent=2)

    return csv_path, json_path


if __name__ == "__main__":
    csv_path, json_path = write()
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
