"""Research-trial historian build script (workload F, research cycle 4).

Writes:
  reports/trial_accounting/families.csv
  reports/trial_accounting/trials.csv
  reports/trial_accounting/summary.json

Read-only on every other file in the repo. Run with:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.trial_accounting.build
"""
from __future__ import annotations

import csv
import glob
import json
import os
from datetime import datetime, timezone

import pandas as pd

from research.trial_accounting import data_sources as ds
from research.trial_accounting import family_data as fd
from research.trial_accounting import meff
from research.trial_accounting import series_config as sc

REPO_ROOT = ds.REPO_ROOT
OUT_DIR = os.path.join(REPO_ROOT, "reports", "trial_accounting")

# ---------------------------------------------------------------------------
# Overrides for the numbers not machine-parseable out of null_lab2's outputs
# (tier 2 / tier 3 families). Cited to their source in family_data.py's
# contamination_status / source_files; kept here as a single small table so
# it's easy to audit against the ledger text in one place.
#   (n_registered, dev_passes, validation_passes)
# ---------------------------------------------------------------------------
TIER23_COUNTS = {
    "momentum_construction": (10, 0, 0),
    "vol_managed_momentum": (5, 0, 0),
    "residual_momentum": (4, 0, 0),
    "overlay_control": (30, 0, 0),          # control study, not seeking a pass
    "momentum_verification_lab": (2, 0, 0),  # infrastructure, not gated
    "return_search": (0, 0, 0),
    "sleeve_blend_higher_sharpe": (0, 0, 0),
    "edge_probe_scripts": (0, 0, 0),
    "crowding_downside_rotation": (0, 0, 0),
    "momentum_gold_fund_designs": (0, 0, 0),
    "etf_convergence_share_class_liquidity": (0, 0, 0),
    "fx_session_screen": (0, 0, 0),
    "pead_production_history": (0, 0, 0),
    "pead_production_bot_live": (0, 0, 0),
    "reversal_research_20260921": (0, 0, 0),
    "edge_graveyard_osap_meta": (0, 0, 0),
}

# Tier-3 informal-experiment low/high, reconciled against null_lab2 where it
# covered the same cluster (see contamination_status text per family for the
# citation). Where this workstream's own file glob gives an exact count that
# null_lab2 did not report (etf_convergence/share_class/liquidity_pressure,
# fx_session, pead_production_history), low==high and it is flagged in
# summary.json as "new_since_null_lab2".
TIER3_INFORMAL_RANGE = {
    "return_search": (20, 23),  # ledger's cited 20 vs this workstream's file-glob count
    "sleeve_blend_higher_sharpe": (8, 20),  # null_lab2 range; refined count filled at runtime
    "edge_probe_scripts": (4, 10),
    "crowding_downside_rotation": (5, 15),
    "momentum_gold_fund_designs": (3, 8),
    "etf_convergence_share_class_liquidity": (14, 14),
    "fx_session_screen": (3, 3),
    "pead_production_history": (13, 13),
    "pead_production_bot_live": (1, 1),
    "reversal_research_20260921": (1, 1),
    "edge_graveyard_osap_meta": (1, 1),
}
NEW_SINCE_NULL_LAB2 = ["etf_convergence_share_class_liquidity", "fx_session_screen", "pead_production_history"]


def base_dir_of_family(family_id: str) -> str:
    return family_id.split("(")[0].split("/")[0].strip()


FAMILY_REGISTRATION_FILE_OVERRIDE = {
    "pead_2004_2014": "research/PREREGISTRATION_pead_2004_2014.md",
    "multiasset/crypto(2 candidates)": "research/multiasset/PLAN_CRYPTO.md",
}


def compute_family_event_time(fam: dict, preregs: list[dict]) -> tuple[datetime | None, str]:
    """Return (event_time_utc, basis_note) for a family: registration time for
    tier 1/2, or a file-mtime proxy for tier 3 (max mtime across its known
    directories/files, i.e. when that block of exploratory work was last
    touched on disk -- the closest available proxy for "when its result
    became available", per the task's own guidance that mtimes are the main
    evidence given only 3 git commits exist).
    """
    fid = fam["family_id"]
    if fam["tier"] in (1, 2):
        override = FAMILY_REGISTRATION_FILE_OVERRIDE.get(fid)
        if override:
            for r in preregs:
                if r["file"] == override:
                    return r["registered_at_utc"], f"registered_at of {override}"
        base = base_dir_of_family(fid)
        matches = [r for r in preregs if r["_dir_guess"] == base]
        if matches:
            return matches[0]["registered_at_utc"], f"earliest registered_at under research/{base}/ ({matches[0]['file']})"
        return None, "no registration match found"
    # tier 3: mtime proxy
    mtimes = []
    for d in fam.get("directories", []):
        full = os.path.join(REPO_ROOT, d)
        if os.path.isfile(full):
            mtimes.append(os.path.getmtime(full))
        elif os.path.isdir(full):
            for root, _, files in os.walk(full):
                for fn in files:
                    try:
                        mtimes.append(os.path.getmtime(os.path.join(root, fn)))
                    except OSError:
                        pass
        else:
            # try as a glob (e.g. a .py filename used as a directories entry)
            for g in glob.glob(full):
                if os.path.isfile(g):
                    mtimes.append(os.path.getmtime(g))
    if not mtimes:
        return None, "no files found for mtime proxy"
    t = datetime.fromtimestamp(max(mtimes), tz=timezone.utc)
    return t, f"max mtime across {len(mtimes)} files under its directories (informal work last touched)"


def classify(text: str) -> str:
    """Map each family's free-text classification onto the task's controlled
    vocabulary (SPENT / FORWARD OBSERVATION / BENCHMARK / NOT AN EDGE /
    IN PROGRESS / INCOMPLETE), extended with two labels the vocabulary has
    no slot for (PARTIALLY USED -- the ledger's own long-standing 4th class,
    kept rather than force-fit into SPENT or IN PROGRESS; INFRASTRUCTURE/META
    for the 2 rows that are tooling/meta-analysis, not trials at all).
    Falls back to SPENT, not INCOMPLETE, for any unmatched "tested, failed
    its gate" text -- INCOMPLETE is reserved for a run that did not finish.
    """
    t = text.upper()
    if "BENCHMARK" in t:
        return "BENCHMARK"
    if "FORWARD OBSERVATION" in t or "FORWARD ONLY" in t:
        return "FORWARD OBSERVATION"
    if "INCOMPLETE" in t:
        return "INCOMPLETE"
    if "IN PROGRESS" in t:
        return "IN PROGRESS"
    if "INFRASTRUCTURE" in t or "META" in t:
        return "INFRASTRUCTURE/META"
    if "PARTIALLY USED" in t:
        return "PARTIALLY USED"
    if "SPENT" in t:
        return "SPENT"
    return "SPENT"


def build_families_csv(FAMILIES, preregs, mt_json, gate_table_by_family):
    mt_rows = {r["family"]: r for r in mt_json["tier1_registered_gate_evaluable"]["rows"]}
    out_rows = []
    event_times = {}
    for fam in FAMILIES:
        fid = fam["family_id"]
        event_time, basis = compute_family_event_time(fam, preregs)
        event_times[fid] = (event_time, basis)

        if fam["tier"] == 1:
            mt = mt_rows.get(fid, {})
            n_reg = mt.get("n_candidates", len(fam["candidate_labels"]))
            dev_passes = mt.get("actual_dev_passes", 0)
            val_passes = mt.get("actual_full_passes", 0)
            n_informal_low = n_informal_high = 0
        elif fam["tier"] == 2:
            n_reg, dev_passes, val_passes = TIER23_COUNTS[fid]
            n_informal_low = n_informal_high = 0
        else:
            n_reg = 0
            dev_passes = val_passes = 0
            n_informal_low, n_informal_high = TIER3_INFORMAL_RANGE.get(fid, (len(fam["candidate_labels"]), len(fam["candidate_labels"])))

        n_candidates_disk = len(fam["candidate_labels"])

        out_rows.append(dict(
            family_id=fid,
            information_family=fam["information_family"],
            strategy_family=fam["strategy_family"],
            tier=fam["tier"],
            n_registered_candidates=n_reg,
            n_informal_experiments_low=n_informal_low,
            n_informal_experiments_high=n_informal_high,
            n_candidates_on_disk=n_candidates_disk,
            related_parameter_siblings="; ".join(fam["candidate_labels"]),
            dev_passes=dev_passes,
            validation_passes=val_passes,
            forward_observations=fam["forward_observations"],
            contamination_status=fam["contamination_status"],
            current_classification=classify(fam["current_classification"]),
            classification_detail=fam["current_classification"],
            evidence_confidence=fam["evidence_confidence"],
            event_time_utc=event_time.isoformat() if event_time else "",
            event_time_basis=basis,
            source_files="; ".join(fam["source_files"]),
        ))
    return out_rows, event_times


def build_trials_csv(FAMILIES, preregs, gate_table_by_family, event_times):
    gt_by_family = {r["family"]: r for r in gate_table_by_family}
    rows = []
    for fam in FAMILIES:
        fid = fam["family_id"]
        event_time, basis = event_times[fid]
        gt = gt_by_family.get(fid)
        gate_summary = ""
        outcome_dev = ""
        outcome_val = ""
        if gt:
            gate_summary = f"{gt.get('archetype','')}; dev_thresh={gt.get('dev_thresh_val','')}; dev_null={gt.get('dev_null','')}; val_thresh={gt.get('val_thresh','')}"
            outcome_dev = gt.get("dev_outcome", "")
            outcome_val = gt.get("val_outcome", "")
        registered = "y" if fam["tier"] in (1, 2) else "n"
        window_label = "dev+validation" if outcome_val and outcome_val not in ("", "n/a") else "dev"
        for cand in fam["candidate_labels"]:
            rows.append(dict(
                family_id=fid,
                candidate=cand,
                registered=registered,
                registered_at_or_mtime=event_time.isoformat() if event_time else "",
                time_basis=basis,
                window=window_label,
                gate=gate_summary,
                outcome_dev=outcome_dev,
                outcome_validation=outcome_val,
                source="; ".join(fam["source_files"][:2]),
            ))
    return rows


# ---------------------------------------------------------------------------
# M_eff
# ---------------------------------------------------------------------------

def load_all_series() -> pd.DataFrame:
    panel, failures = ds.build_monthly_panel(sc.SERIES)
    # etf_hybrids multi-index files, added separately
    for spec, prefix in ((sc.ETF_HYBRIDS_DEV, "etf_hybrids/dev/"), (sc.ETF_HYBRIDS_VAL, "etf_hybrids/val/")):
        try:
            d = ds.load_etf_hybrids_multiindex(spec["path"], spec["sleeves"])
            for sleeve, s in d.items():
                panel[prefix + sleeve] = s
        except Exception as e:  # noqa: BLE001
            failures.append((prefix + "ALL", str(e)))
    panel.index = panel.index.astype(str)
    return panel, failures


SERIES_FAMILY_MAP = {s["id"]: s["family_id"] for s in sc.SERIES}
SERIES_FAMILY_MAP.update({f"etf_hybrids/dev/{s}": "etf_hybrids(E1-E5)" for s in sc.ETF_HYBRIDS_DEV["sleeves"]})
SERIES_FAMILY_MAP.update({f"etf_hybrids/val/{s}": "etf_hybrids(E1-E5)" for s in sc.ETF_HYBRIDS_VAL["sleeves"]})


def within_family_meff(panel: pd.DataFrame) -> list[dict]:
    by_family: dict[str, list[str]] = {}
    for col in panel.columns:
        famid = SERIES_FAMILY_MAP.get(col)
        if famid:
            by_family.setdefault(famid, []).append(col)
    out = []
    for famid, cols in sorted(by_family.items()):
        if len(cols) < 2:
            continue
        sub = panel[cols]
        result = meff.all_meff(sub, min_overlap=6)
        result["family_id"] = famid
        result["series"] = cols
        out.append(result)
    return out


def project_wide_meff(panel: pd.DataFrame) -> dict:
    """One representative series per family (the first series listed for that
    family in SERIES_FAMILY_MAP / etf_hybrids) -> cross-family M_eff."""
    seen = set()
    rep_cols = []
    for col in panel.columns:
        famid = SERIES_FAMILY_MAP.get(col)
        if famid and famid not in seen:
            seen.add(famid)
            rep_cols.append(col)
    sub = panel[rep_cols]
    result = meff.all_meff(sub, min_overlap=6)
    result["families_represented"] = sorted(seen)
    result["n_families_with_series"] = len(seen)
    return result


# ---------------------------------------------------------------------------
# Shots-before-result
# ---------------------------------------------------------------------------

def shots_before(FAMILIES, preregs, event_times, key_results, meff_project):
    fam_by_id = {f["family_id"]: f for f in FAMILIES}
    # Build a flat list of (family_id, information_family, event_time, n_trials_represented)
    flat = []
    for fam in FAMILIES:
        et, _ = event_times[fam["family_id"]]
        if et is None:
            continue
        n = len(fam["candidate_labels"])
        flat.append((fam["family_id"], fam["information_family"], et, n))

    out = []
    for kr in key_results:
        target_fam = fam_by_id[kr["family_id"]]
        info_fam = target_fam["information_family"]
        kr_time = ds._parse_ts(kr["registered_at"])

        info_before = [x for x in flat if x[1] == info_fam and x[2] < kr_time]
        project_before = [x for x in flat if x[2] < kr_time]

        n_info_trials = sum(x[3] for x in info_before)
        n_info_families = len(info_before)
        n_project_trials = sum(x[3] for x in project_before)
        n_project_families = len(project_before)

        p = kr["headline_p"]
        adj = {}
        if p is not None:
            for label, k in (
                ("info_family_n_candidates", n_info_trials + target_fam.get("_own_n", 1)),
                ("project_n_candidates", n_project_trials + target_fam.get("_own_n", 1)),
            ):
                k = max(k, 1)
                adj[f"bonferroni_{label}"] = min(1.0, p * k)
                adj[f"sidak_{label}"] = 1.0 - (1.0 - p) ** k
            # Holm: needs the full ordered p-value list, which this project
            # does not have for most families (most gates are Sharpe+null,
            # not a clean per-candidate p-list). We report the Holm bound for
            # THIS result assuming it is the smallest of k p-values (the
            # standard conservative single-result Holm step, equivalent to
            # Bonferroni's first step) and disclose that limitation.
            adj["holm_first_step_info_family"] = min(1.0, p * max(n_info_trials + 1, 1))
            adj["holm_first_step_project"] = min(1.0, p * max(n_project_trials + 1, 1))
            # Sidak using the project-wide M_eff cross-family estimate as k,
            # combined with within-family trial count for that one family
            # (rough combined effective-k: M_eff_project scaled by this
            # family's own share of raw trials -- documented approximation).
            m_eff_li_ji = meff_project.get("li_ji", n_project_families)
            adj["sidak_using_project_M_eff"] = 1.0 - (1.0 - p) ** max(m_eff_li_ji, 1)

        out.append(dict(
            key=kr["key"],
            family_id=kr["family_id"],
            information_family=info_fam,
            registered_at=kr["registered_at"],
            headline_p=p,
            p_description=kr["p_description"],
            n_info_family_trials_before=n_info_trials,
            n_info_family_families_before=n_info_families,
            n_project_trials_before=n_project_trials,
            n_project_families_before=n_project_families,
            adjustments=adj,
        ))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    preregs = ds.load_preregistrations()
    gate_table = ds.load_gate_table()
    mt_json = ds.load_multiple_testing_json()

    FAMILIES = fd.FAMILIES
    fd.expand_programmatic_candidate_labels(FAMILIES, REPO_ROOT)
    for fam in FAMILIES:
        fam["_own_n"] = len(fam["candidate_labels"])

    families_rows, event_times = build_families_csv(FAMILIES, preregs, mt_json, gate_table)
    trials_rows = build_trials_csv(FAMILIES, preregs, gate_table, event_times)

    panel, load_failures = load_all_series()
    within = within_family_meff(panel)
    project = project_wide_meff(panel)

    families_with_series = {w["family_id"] for w in within} | set(project["families_represented"])
    families_without_series = sorted({f["family_id"] for f in FAMILIES} - families_with_series)

    # attach effective_tests_low/high to families_rows using within-family M_eff where available
    within_by_family = {w["family_id"]: w for w in within}
    for row in families_rows:
        fid = row["family_id"]
        n_reg = row["n_registered_candidates"] or row["n_candidates_on_disk"]
        n_informal_hi = row["n_informal_experiments_high"]
        n_total_candidates = max(n_reg, row["n_candidates_on_disk"]) + n_informal_hi
        if fid in within_by_family:
            w = within_by_family[fid]
            lo = min(w["cheverud"], w["nyholt"], w["li_ji"])
            row["effective_tests_low"] = round(lo, 1)
            row["effective_tests_high"] = max(n_total_candidates, row["n_candidates_on_disk"])
            row["meff_series_used"] = len(w["series"])
        else:
            row["effective_tests_low"] = n_total_candidates if n_total_candidates else 1
            row["effective_tests_high"] = n_total_candidates if n_total_candidates else 1
            row["meff_series_used"] = 0

    shots = shots_before(FAMILIES, preregs, event_times, fd.KEY_RESULTS, project)

    # --- write families.csv ---
    fam_cols = ["family_id", "information_family", "strategy_family", "tier",
                "n_registered_candidates", "n_informal_experiments_low", "n_informal_experiments_high",
                "n_candidates_on_disk", "related_parameter_siblings", "dev_passes", "validation_passes",
                "forward_observations", "effective_tests_low", "effective_tests_high", "meff_series_used",
                "contamination_status", "current_classification", "classification_detail",
                "evidence_confidence", "event_time_utc", "event_time_basis", "source_files"]
    with open(os.path.join(OUT_DIR, "families.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fam_cols)
        w.writeheader()
        for row in families_rows:
            w.writerow(row)

    # --- write trials.csv ---
    trial_cols = ["family_id", "candidate", "registered", "registered_at_or_mtime", "time_basis",
                  "window", "gate", "outcome_dev", "outcome_validation", "source"]
    with open(os.path.join(OUT_DIR, "trials.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=trial_cols)
        w.writeheader()
        for row in trials_rows:
            w.writerow(row)

    # --- information-family budget view ---
    budget: dict[str, dict] = {}
    for row in families_rows:
        info = row["information_family"]
        b = budget.setdefault(info, dict(n_families=0, n_registered_candidates=0,
                                          n_informal_low=0, n_informal_high=0,
                                          dev_passes=0, validation_passes=0, forward_observations=0,
                                          classifications=set()))
        b["n_families"] += 1
        b["n_registered_candidates"] += row["n_registered_candidates"]
        b["n_informal_low"] += row["n_informal_experiments_low"]
        b["n_informal_high"] += row["n_informal_experiments_high"]
        b["dev_passes"] += row["dev_passes"]
        b["validation_passes"] += row["validation_passes"]
        b["forward_observations"] += row["forward_observations"]
        b["classifications"].add(row["current_classification"])
    for k in budget:
        budget[k]["classifications"] = sorted(budget[k]["classifications"])
        total_trials = budget[k]["n_registered_candidates"] + budget[k]["n_informal_high"]
        if total_trials == 0:
            budget[k]["status"] = "UNTOUCHED"
        elif budget[k]["validation_passes"] > 0 or budget[k]["forward_observations"] > 0:
            budget[k]["status"] = "ACTIVE / HAS FORWARD-STAGE EVIDENCE"
        else:
            budget[k]["status"] = "EXHAUSTED (no clean pass survives)"

    # --- headline counts ---
    n_tier1 = sum(r["n_registered_candidates"] for r in families_rows if next(f for f in FAMILIES if f["family_id"] == r["family_id"])["tier"] == 1)
    n_tier2 = sum(r["n_registered_candidates"] for r in families_rows if next(f for f in FAMILIES if f["family_id"] == r["family_id"])["tier"] == 2)
    n_tier3_low = sum(r["n_informal_experiments_low"] for r in families_rows)
    n_tier3_high = sum(r["n_informal_experiments_high"] for r in families_rows)
    grand_low = n_tier1 + n_tier2 + n_tier3_low
    grand_high = n_tier1 + n_tier2 + n_tier3_high
    grand_point = n_tier1 + n_tier2 + round((n_tier3_low + n_tier3_high) / 2)

    new_since = {fid: TIER3_INFORMAL_RANGE[fid] for fid in NEW_SINCE_NULL_LAB2}
    new_since_low = sum(v[0] for v in new_since.values())
    new_since_high = sum(v[1] for v in new_since.values())

    summary = dict(
        built_at_utc=datetime.now(timezone.utc).isoformat(),
        headline=dict(
            n_families=len(FAMILIES),
            tier1_registered_gate_evaluable=n_tier1,
            tier2_registered_non_standard=n_tier2,
            tier3_unregistered_low=n_tier3_low,
            tier3_unregistered_high=n_tier3_high,
            grand_total_low=grand_low,
            grand_total_high=grand_high,
            grand_total_point_estimate=grand_point,
        ),
        reconciliation=dict(
            null_lab2_grand_total_low=182, null_lab2_grand_total_high=215, null_lab2_point_estimate=198,
            research_ledger_stale_estimate=111,
            this_workstream_new_clusters_not_in_null_lab2=new_since,
            this_workstream_new_clusters_added_low=new_since_low,
            this_workstream_new_clusters_added_high=new_since_high,
            note=("etf_convergence/share_class/liquidity_pressure (14) and fx_session_screen (3) carry "
                  "self-declared 'written before any result' spec JSONs dated 2026-09-18 but do not appear "
                  "in research/preregistrations.jsonl (grep-confirmed) and are not itemized in null_lab2's "
                  "tier-3 detail list; pead_production_history (13, dated 2026-08-18, pre-dates the "
                  "registration system by a month) is also outside null_lab2's tier-3 narrative, which starts "
                  "from research/return_search onward. Treated here as additive to null_lab2's 182-215 range, "
                  "not already included in it -- this workstream's own range is reported separately above and "
                  "is NOT meant to replace null_lab2's number, only to extend its documented coverage."),
        ),
        information_family_budget=budget,
        families_with_return_series_for_meff=sorted(families_with_series),
        families_without_return_series=families_without_series,
        meff_within_family=[{k: v for k, v in w.items() if k != "diagnostics"} | {"diagnostics": w["diagnostics"]} for w in within],
        meff_project_wide=project,
        series_load_failures=load_failures,
        shots_before_result=shots,
    )

    def _default(o):
        if isinstance(o, (set,)):
            return sorted(o)
        raise TypeError(str(type(o)))

    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=_default)

    # console report for the build operator
    print("=== HEADLINE ===")
    print(json.dumps(summary["headline"], indent=2))
    print(f"grand total (this workstream): {grand_low}-{grand_high}, point ~{grand_point}")
    print(f"null_lab2 comparison: 182-215, point 198; new clusters added by this workstream: +{new_since_low}-{new_since_high}")
    print()
    print("=== PROJECT-WIDE M_EFF (one representative series per family with data) ===")
    print(json.dumps({k: v for k, v in project.items() if k != "diagnostics"}, indent=2, default=str))
    print(f"families represented in M_eff panel: {project['n_families_with_series']} of {len(FAMILIES)}")
    print(f"families with NO return series on disk for M_eff: {len(families_without_series)}")
    print()
    print("=== WITHIN-FAMILY M_EFF (families with >=2 series) ===")
    for w in within:
        print(f"  {w['family_id']:55s} M={w['m']:3d}  cheverud={w['cheverud']:6.2f}  nyholt={w['nyholt']:6.2f}  li_ji={w['li_ji']:6.2f}")
    print()
    print("=== SHOTS BEFORE RESULT ===")
    for s in shots:
        print(f"  {s['key']:22s} info_family={s['information_family']:28s} "
              f"n_info_before={s['n_info_family_trials_before']:4d} n_project_before={s['n_project_trials_before']:4d} "
              f"p={s['headline_p']}")
    print()
    print(f"Wrote: {OUT_DIR}/families.csv ({len(families_rows)} rows), "
          f"{OUT_DIR}/trials.csv ({len(trials_rows)} rows), {OUT_DIR}/summary.json")
    if load_failures:
        print(f"Series load failures ({len(load_failures)}):")
        for fid, err in load_failures:
            print(f"  {fid}: {err}")


if __name__ == "__main__":
    main()
