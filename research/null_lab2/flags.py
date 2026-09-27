"""Inconsistency flags across the registry (task 3). Writes reports/null_lab2/flags.csv.

Flags come from two sources:
  1. Programmatic checks against families.ROWS and reports/null_lab2/calibration.csv (weak/no dev
     null, no family-size p-adjustment, <50% validation power at Sharpe 0.7, null mean far from 0).
  2. A short hand-curated list of specific process/consistency findings that need the plan text
     itself to see (found while building families.py) -- each cites the exact source line.
"""
from __future__ import annotations

import csv
import pathlib

from research.null_lab2.families import ROWS, GateRow

FIELDS = ["severity", "category", "family", "description", "evidence"]


def _read_calibration(path: str = "reports/null_lab2/calibration.csv") -> list[dict]:
    p = pathlib.Path(path)
    if not p.exists():
        return []
    return list(csv.DictReader(open(p)))


def programmatic_flags(calib_rows: list[dict]) -> list[dict]:
    flags = []

    # (1) Development gate has no null / p-value requirement at all.
    for row in ROWS:
        if row.dev_null == "none" and row.archetype not in ("TSTAT_REPLICATION",):
            zero_world = next((r for r in calib_rows if r["family"] == row.family
                                and r["cell"] == "b_zero_net"), None)
            p_dev = zero_world["P_pass_dev"] if zero_world else None
            flags.append({
                "severity": "high",
                "category": "no_dev_null_test",
                "family": row.family,
                "description": ("Development gate is a flat Sharpe threshold with no p-value / null "
                                 "test of any kind (pre-amendment protocol). Calibrated false-dev-pass "
                                 "probability under a true-zero-net-mean world is reported alongside."),
                "evidence": f"dev_thresh={row.dev_thresh_val}, P(pass dev | zero net mean)={p_dev}",
            })

    # (2) Family size k >= 2 but no Bonferroni/Sidak adjustment anywhere in the dev gate.
    for row in ROWS:
        if row.k >= 2 and row.dev_alpha is None and row.dev_null not in ("none", "reported_only"):
            continue  # would already be flagged by (4) if relevant; keep this branch for future use
    for row in ROWS:
        if row.k >= 4 and row.protocol.startswith("pre") and row.dev_null == "none":
            flags.append({
                "severity": "medium",
                "category": "no_family_size_adjustment_at_dev",
                "family": row.family,
                "description": (f"Family of k={row.k} candidates registered together with a flat "
                                 f"per-candidate dev bar and no p-value at all, so there is no "
                                 f"Bonferroni/Sidak correction for screening {row.k} candidates at "
                                 f"development (only validation applies alpha/k)."),
                "evidence": f"k={row.k}, dev_null=none, dev_thresh={row.dev_thresh_val}",
            })

    # (3) p-value is computed/reported but not gated on (reported_only).
    for row in ROWS:
        if row.dev_null == "reported_only":
            flags.append({
                "severity": "medium",
                "category": "null_reported_not_gated",
                "family": row.family,
                "description": ("P(pass|null) is computed and reported for this family, but the "
                                 "registered pass criteria do not include a p-value threshold -- "
                                 "sibling families registered the same week (e.g. japan_us_flow, "
                                 "tsy_month_end, credit_gate) DO gate on p<alpha. Same protocol "
                                 "version, inconsistent application of amendment item A4 ('every "
                                 "result reports P(pass|null)') vs. the de-facto stricter practice "
                                 "elsewhere of also gating on it."),
                "evidence": f"dev_kind={row.dev_kind}, dev_thresh={row.dev_thresh_val}",
            })

    # (4) Shift/permutation null whose own reference mean is far from 0 (answers a different
    #     question than "is the return positive").
    from research.null_lab2 import sim_params as SP
    for row in ROWS:
        if row.dev_null in ("shift", "permutation"):
            params = SP.get(row.family, row.dev_kind, row.dev_null)
            if abs(params.shift_perm_offset) >= 0.5:
                flags.append({
                    "severity": "high",
                    "category": "null_answers_wrong_question",
                    "family": row.family,
                    "description": (f"The {row.dev_null}-null's own reference distribution is "
                                     f"centred far from zero (~{params.shift_perm_offset:+.2f} "
                                     f"annualised Sharpe), so 'p < alpha' mostly shows the tested "
                                     f"window beats a bad random benchmark, not that its own return "
                                     f"is positive."),
                    "evidence": f"shift/perm reference mean ~ {params.shift_perm_offset:+.2f} SR "
                                f"(matched to the family's own reported null mean_sd where available)",
                })

    # (5) <50% joint dev+val power at true Sharpe 0.7.
    by_family_power = {}
    for r in calib_rows:
        if r["cell"] == "power_true_sr_0.7" and r["P_pass_dev_and_val"] not in ("", None):
            by_family_power[r["family"]] = float(r["P_pass_dev_and_val"])
    for fam, p in sorted(by_family_power.items(), key=lambda kv: kv[1]):
        if p < 0.50:
            flags.append({
                "severity": "medium" if p >= 0.25 else "high",
                "category": "low_validation_power",
                "family": fam,
                "description": (f"Joint P(pass dev AND pass validation | true net Sharpe 0.7) = "
                                 f"{p:.1%}, well under 50%. A genuinely tradable 0.7-Sharpe edge is "
                                 f"more likely to be missed than caught by this family's two-stage "
                                 f"gate."),
                "evidence": f"P(pass dev & val | SR=0.7) = {p:.4f}",
            })
    if by_family_power:
        worst = max(by_family_power.values())
        flags.append({
            "severity": "high",
            "category": "low_validation_power_systemic",
            "family": "ALL (project-wide)",
            "description": (f"Every family with a simulated joint dev+val stage has <{worst:.0%} "
                             f"power at true net Sharpe 0.7 (range across {len(by_family_power)} "
                             f"families: {min(by_family_power.values()):.1%} - {worst:.1%}). This is "
                             f"a structural property of a short development window plus an "
                             f"independent, equally short validation window, not a one-off."),
            "evidence": f"n_families_with_both_stages_simulated={len(by_family_power)}",
        })

    return flags


def curated_flags() -> list[dict]:
    return [
        {
            "severity": "high",
            "category": "gate_bypassed_after_failing",
            "family": "letf_rebalancing(L1-L2)",
            "description": ("L2's development Sharpe (0.48) is below the family's own registered "
                             "0.50 development gate, i.e. it did not pass development. The ledger "
                             "nonetheless classifies this row 'FORWARD ONLY' and recommends L2 for a "
                             "forward test, citing a monotone dose-response as informal support. This "
                             "is the one case in the registry where a family was promoted past its "
                             "own registered gate."),
            "evidence": "reports/letf_rebalancing/dev/results.json L2 sharpe=0.48 < gate 0.50; "
                        "RESEARCH_LEDGER_2026-09-23.md row 12 'FORWARD ONLY'",
        },
        {
            "severity": "medium",
            "category": "weakest_inclusion_bar_in_registry",
            "family": "multiasset(17-sleeve inclusion + 5-sleeve holdout)",
            "description": ("The multi-asset book's sleeve-inclusion rule (Sharpe>=0.30, >=3 years "
                             "history, no null test, 17 sleeves screened) is the weakest development "
                             "bar of any family in the registry -- weaker than even the old flat 0.5 "
                             "gate, let alone the post-amendment 1.8-2.4/sqrt(T) standard, and it "
                             "screens the most candidates (17) with zero multiple-testing correction."),
            "evidence": "research/multiasset/PLAN.md 'Development-phase inclusion rule': Sharpe>=0.30",
        },
        {
            "severity": "low",
            "category": "p_gate_correctly_binding",
            "family": "structural_frontier(A: Treasury term premium)",
            "description": ("Noted for completeness, not as a defect: A's development active Sharpe "
                             "(0.569) clears its Sharpe gate (0.520), but its Bonferroni-adjusted "
                             "bootstrap p (0.023) misses the batch threshold (0.01667), so the family "
                             "correctly failed overall. This is the clearest example in the registry "
                             "of the p-gate doing real work beyond the Sharpe threshold."),
            "evidence": "reports/structural_frontier/term_dev_results.json: active_sharpe_gate=0.5197, "
                        "candidate active sharpe~0.569 (>gate), p_observed_one_sided=0.02300 (>0.01667)",
        },
        {
            "severity": "medium",
            "category": "control_not_gated",
            "family": "fx_hedge_rebal",
            "description": ("The development gate binds on the raw book's absolute Sharpe, not on "
                             "the book minus its own reported C_USDSHORT control, even though the "
                             "protocol amendment (item A2) requires long/directionally-biased books "
                             "to gate on active return vs. an exposure-matched control. The plan does "
                             "not state why this family is exempt (it is direction-switching, which "
                             "is a plausible reason, but it is not written down)."),
            "evidence": "research/fx_hedge_rebal/PLAN.md Gates section gates on the book Sharpe "
                        "directly; C_USDSHORT is listed under Controls, not Gates",
        },
        {
            "severity": "medium",
            "category": "same_day_protocol_split",
            "family": "macro_surprise(M1,M2)",
            "description": ("Registered 2026-09-23T00:13, about 10 hours before the protocol "
                             "amendment (2026-09-23T10:04) on the SAME calendar day, so it correctly "
                             "used the old flat-0.5 gate under the amendment's own 'applies to "
                             "registrations made after this file is registered' rule. Flagged only "
                             "so a reader does not mistake this for a violation; it is a same-day "
                             "boundary case worth naming."),
            "evidence": "research/preregistrations.jsonl entries 42-43 vs 47 (amendment)",
        },
    ]


def build(calib_path: str = "reports/null_lab2/calibration.csv",
          out_path: str = "reports/null_lab2/flags.csv") -> list[dict]:
    calib_rows = _read_calibration(calib_path)
    flags = programmatic_flags(calib_rows) + curated_flags()
    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: (order.get(f["severity"], 9), f["category"], f["family"]))
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for fl in flags:
            w.writerow(fl)
    print(f"wrote {len(flags)} flags to {out}")
    return flags


if __name__ == "__main__":
    build()
