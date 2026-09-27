"""Project-wide multiple-testing accounting (task 4). Writes reports/null_lab2/multiple_testing.json.

Three tiers, because the registry mixes genuinely different kinds of "trial":
  Tier 1 -- registered, gate-evaluable candidates: every row in families.ROWS, i.e. everything in
            reports/null_lab2/gate_table.csv. This is the only tier this workstream has calibrated
            false-pass rates for (reports/null_lab2/calibration.csv), so it is the only tier with a
            quantitative expected-vs-actual comparison.
  Tier 2 -- registered plans that were preregistered (a PLAN.md/DECISION_RULE.md hash is in
            research/preregistrations.jsonl) but whose pass criterion is not a Sharpe-threshold +
            null-p gate (momentum_construction, vol_managed_momentum, residual_momentum,
            overlay_control, momentum_verification/momentum_lab). Counted, not calibrated.
  Tier 3 -- never preregistered at all: research/return_search (no PLAN.md hash in
            preregistrations.jsonl), research/higher_sharpe.py, research/blend_sleeves.py, the
            research/edge_*.py scripts, research/downside_rotation.py,
            research/crowding_unwind_*.py, research/strategy_research, and similar. These are
            estimated, not counted exactly, because doing so exactly would mean reading and
            interpreting every ad hoc script's internal sweep -- outside this workstream's budget.
            The estimate is deliberately a range, sourced line by line below.
"""
from __future__ import annotations

import csv
import json
import pathlib

from research.null_lab2.families import ROWS

# Tier-1 candidate count per row can differ from the Bonferroni divisor `k` when several rows
# share one *registered batch* (structural_frontier A/B/C: k=3 is the Bonferroni divisor for each,
# but each row is itself only 1 candidate, not 3).
N_CANDIDATES_OVERRIDE = {
    "structural_frontier(A: Treasury term premium)": 1,
    "structural_frontier(B: HY credit carry)": 1,
    "structural_frontier(C: TLT put insurance)": 1,
}

# Manual, cited count of ACTUAL recorded development passes per row (from families.ROWS.dev_outcome,
# cross-checked against reports/<family>/dev_results.json / RESEARCH_LEDGER). "Pass" here means the
# full registered dev gate (all legs), except multiasset's sleeve inclusion (a single Sharpe>=0.30
# leg -- counted as its own family passing 5/17, exactly as registered) and crypto (both candidates
# cleared their own screening bar and moved to hold-out).
ACTUAL_DEV_PASSES = {
    "intraday(I1-I4)": 1, "insider(N1-N4)": 2, "rebalancing(R1-R3)": 2, "etf_hybrids(E1-E5)": 2,
    "tsy_month_end(M)": 1, "commodity_roll": 1,
    "multiasset(17-sleeve inclusion + 5-sleeve holdout)": 5,
    "multiasset/crypto(2 candidates)": 2,
}
ACTUAL_FULL_PASSES = {}  # none: every dev pass above either failed validation or was never unlocked
                          # for validation (tsy_month_end validation Sharpe 0.69 < 0.75 gate).

TIER2_REGISTERED_NON_STANDARD = [
    {"family": "momentum_construction", "n_trials": 10,
     "source": "research/momentum_construction/PLAN.md 'Variants -- exactly these ten, no others'"},
    {"family": "vol_managed_momentum", "n_trials": 5,
     "source": "research/vol_managed_momentum/PLAN.md 'Variants to run -- exactly these five'"},
    {"family": "residual_momentum", "n_trials": 4,
     "source": "research/residual_momentum/PLAN.md 'Variants -- exactly these four, and no others'"},
    {"family": "overlay_control", "n_trials": 30,
     "source": "research/overlay_control/PLAN.md '5 overlays x each underlying = 30 variants, no others'"
                " (a registered CONTROL study, not a search for a pass -- see notes)"},
    {"family": "momentum_verification / momentum_lab", "n_trials": 2,
     "source": "research/momentum_verification/PLAN.md, research/momentum_lab/DECISION_RULE.md "
               "(infrastructure / decision-rule registrations, not Sharpe-gated candidates)"},
]

TIER3_UNREGISTERED_ESTIMATE = [
    {"source": "research/return_search (20 candidates)", "low": 20, "high": 20,
     "note": "Explicitly counted in RESEARCH_LEDGER row 22 ('Return search, 20 candidates'); no "
             "PLAN.md hash for research/return_search appears in preregistrations.jsonl."},
    {"source": "research/higher_sharpe.py, research/blend_sleeves.py, research/strategy_research, "
               "research/sleeve_blend", "low": 8, "high": 20,
     "note": "reports/higher_sharpe/, reports/strategy_research/, reports/sleeve_blend/ all exist "
             "with results.json but no matching preregistration; RESEARCH_LEDGER row 31 lists them "
             "jointly as 'assorted sleeves 2021-25', without a per-script trial count."},
    {"source": "research/edge_executable_probe.py, edge_first_backtest.py, edge_timing_probe.py, "
               "edge_sue_placebo.py", "low": 4, "high": 10,
     "note": "Each is a single unregistered probe script; edge_sue_placebo.py alone reports several "
             "placebo families (s2, s3, long-short, large-SUE) per research/pead_attack/PLAN.md sec.2."},
    {"source": "research/crowding_unwind_20260919 (14 markets), research/downside_rotation_20260919",
     "low": 5, "high": 15,
     "note": "RESEARCH_LEDGER row 10 cites '14 commodity-ETF markets' for crowding_unwind; treated "
             "as a single screened family rather than 14 independent trials, but the screen itself "
             "was never preregistered."},
    {"source": "momentum_gold / momentum fund design follow-ups (Codex sessions)",
     "low": 3, "high": 8,
     "note": "RESEARCH_LEDGER row 28 'momentum fund designs (Codex): vol-scaled, trend, defensive "
             "rotation' cites 3 named configs plus several audit/finalize follow-up scripts under "
             "research/momentum_verification/codex_*.py."},
]


def _calib_lookup(calib_rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(r["family"], r["cell"]): r for r in calib_rows}


def build(calib_path: str = "reports/null_lab2/calibration.csv",
          out_path: str = "reports/null_lab2/multiple_testing.json") -> dict:
    calib_rows = list(csv.DictReader(open(calib_path)))
    lut = _calib_lookup(calib_rows)

    tier1_rows = []
    total_candidates = 0
    total_actual_dev_pass = 0
    total_actual_full_pass = 0
    exp_false_dev_b = exp_false_dev_a = 0.0
    exp_false_full_b = 0.0

    for row in ROWS:
        n = N_CANDIDATES_OVERRIDE.get(row.family, row.k)
        total_candidates += n
        actual_dev = ACTUAL_DEV_PASSES.get(row.family, 0)
        actual_full = ACTUAL_FULL_PASSES.get(row.family, 0)
        total_actual_dev_pass += actual_dev
        total_actual_full_pass += actual_full

        cb = lut.get((row.family, "b_zero_net"))
        ca = lut.get((row.family, "a_zero_gross_cost_drag"))
        p_dev_b = float(cb["P_pass_dev"]) if cb and cb["P_pass_dev"] != "" else 0.0
        p_dev_a = float(ca["P_pass_dev"]) if ca and ca["P_pass_dev"] != "" else 0.0
        p_full_b = float(cb["P_pass_dev_and_val"]) if cb and cb["P_pass_dev_and_val"] not in ("", None) else 0.0

        exp_false_dev_b += n * p_dev_b
        exp_false_dev_a += n * p_dev_a
        exp_false_full_b += n * p_full_b

        tier1_rows.append({
            "family": row.family, "n_candidates": n,
            "actual_dev_passes": actual_dev, "actual_full_passes": actual_full,
            "P_pass_dev_given_null_zero_net": round(p_dev_b, 4),
            "P_pass_dev_given_null_cost_drag": round(p_dev_a, 4),
            "expected_false_dev_passes_zero_net": round(n * p_dev_b, 3),
            "P_pass_dev_and_val_given_null_zero_net": round(p_full_b, 4),
            "expected_false_full_passes_zero_net": round(n * p_full_b, 3),
        })

    tier2_total = sum(t["n_trials"] for t in TIER2_REGISTERED_NON_STANDARD)
    tier3_low = sum(t["low"] for t in TIER3_UNREGISTERED_ESTIMATE)
    tier3_high = sum(t["high"] for t in TIER3_UNREGISTERED_ESTIMATE)

    result = {
        "tier1_registered_gate_evaluable": {
            "n_candidates": total_candidates,
            "n_family_rows": len(ROWS),
            "actual_dev_passes": total_actual_dev_pass,
            "expected_false_dev_passes_under_null_b_zero_net": round(exp_false_dev_b, 2),
            "expected_false_dev_passes_under_null_a_cost_drag": round(exp_false_dev_a, 2),
            "actual_full_dev_and_val_passes": total_actual_full_pass,
            "expected_false_full_passes_under_null_b_zero_net": round(exp_false_full_b, 3),
            "rows": tier1_rows,
        },
        "tier2_registered_non_standard_gate": {
            "n_trials": tier2_total,
            "detail": TIER2_REGISTERED_NON_STANDARD,
        },
        "tier3_unregistered_exploratory_estimate": {
            "n_trials_low": tier3_low,
            "n_trials_high": tier3_high,
            "detail": TIER3_UNREGISTERED_ESTIMATE,
        },
        "grand_total": {
            "low": total_candidates + tier2_total + tier3_low,
            "high": total_candidates + tier2_total + tier3_high,
            "point_estimate": total_candidates + tier2_total + (tier3_low + tier3_high) // 2,
        },
        "comparison_to_prior_ledger_estimate": {
            "RESEARCH_LEDGER_2026-09-23_approx_trial_count": 111,
            "note": ("The ledger's ~111 was current as of this session's start and predates the 17 "
                     "new post-amendment candidates registered in the last 24h "
                     "(japan_us_flow..fx_hedge_rebal). This workstream's own count uses a different "
                     "methodology (explicit tiering by registration/gate status) and should not be "
                     "expected to match to the trial -- both are estimates, and the gap itself "
                     "(mostly Tier 3) is the point: a large share of exploratory work in this project "
                     "was never preregistered and so was never gated at all."),
        },
    }
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    return result


if __name__ == "__main__":
    build()
