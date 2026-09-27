"""Gate table for every registered family with evaluable development-gate logic.

Hand-extracted from `research/<family>/PLAN.md` (and amendments), `research/<family>/evaluate.py`
where the plan text alone was ambiguous, `research/preregistrations.jsonl` (registered_at), and the
existing `reports/<family>/*results*.json` files. NO validation-window data was computed here; every
"validation outcome" below is copied from a `validation_results.json` / `results.json` that already
existed on disk (per the workstream's hard constraint). NO commodity ETF price after 2016-12-30 and
no other raw price/return series were loaded to build this table.

Field meanings
--------------
family            : directory name (or script name) under research/
registered_at     : from preregistrations.jsonl, earliest relevant entry
dev_years         : development window length in years (as stated in the plan / results json)
val_years         : validation window length in years, or None if never unlocked
dev_thresh        : the development Sharpe threshold (float), as a *formula string* for provenance
dev_thresh_val    : the threshold's numeric value at this family's actual dev_years
dev_kind          : "absolute" (raw/absolute Sharpe gate) or "active" (active return vs a control
                    or exposure-matched benchmark)
k                 : number of candidates registered together in the family (for Bonferroni /
                    2.4-vs-1.8 multiplier context)
dev_null          : "none" | "bootstrap" | "shift" | "permutation" | "placebo_rank" | "reported_only"
                    "reported_only" = a null probability is computed and reported, but is NOT a
                    hard pass/fail condition of the development gate itself (found in credit_lead,
                    index_option_breadth).
dev_alpha         : the p-value threshold applied at development, or None if dev_null is none/reported_only
stress_cond       : the stress-cost condition attached to the development gate
val_thresh        : validation Sharpe threshold, or None if never unlocked
val_null          : validation null type
val_alpha         : validation p threshold (already Bonferroni-adjusted where applicable)
n_candidates_family: k again, kept explicit for the CSV
dev_outcome       : pass/fail summary with the actual numbers, from the registered results file
val_outcome       : pass/fail summary with the actual numbers, or "not run (dev failed / locked)"
protocol          : "pre-2026-09-23" (old 0.5/0.75 protocol) or "post-2026-09-23" (1.8/sqrt(T) protocol)
source            : files actually read to fill this row
notes             : anything material: missing p-threshold, weak controls, mechanism-answers-
                    wrong-question nulls, etc. Left "" when nothing extra to say.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import math


@dataclass
class GateRow:
    family: str
    registered_at: str
    dev_years: Optional[float]
    val_years: Optional[float]
    dev_thresh_formula: str
    dev_thresh_val: Optional[float]
    dev_kind: str          # absolute | active
    k: int
    dev_null: str           # none | bootstrap | shift | permutation | placebo_rank | reported_only
    dev_alpha: Optional[float]
    stress_cond: str
    val_thresh: Optional[float]
    val_null: str
    val_alpha: Optional[float]
    dev_outcome: str
    val_outcome: str
    protocol: str
    archetype: str
    source: str
    notes: str = ""

    def as_row(self) -> dict:
        return asdict(self)


def _old(t):
    """Old-protocol dev threshold is a flat absolute 0.5 with no null test."""
    return 0.5


def _new(T, k):
    """New-protocol (2026-09-23 amendment) dev threshold: 1.8/sqrt(T) per candidate,
    2.4/sqrt(T) per member when k >= 4."""
    mult = 2.4 if k >= 4 else 1.8
    return mult / math.sqrt(T)


ROWS: list[GateRow] = []


def add(**kw):
    ROWS.append(GateRow(**kw))


# ---------------------------------------------------------------------------
# PRE-AMENDMENT FAMILIES (protocol_2026-09-18): dev = absolute Sharpe >= 0.5,
# NO null / p-value requirement at development. Validation = Sharpe >= 0.75,
# stress mean > 0, mean-centred block-bootstrap p < 0.05/k.
# ---------------------------------------------------------------------------

add(family="pead_2004_2014", registered_at="2026-09-17T18:44:54-0700",
    dev_years=10.96, val_years=None,
    dev_thresh_formula="n/a (replication test, not a dev/val split)", dev_thresh_val=None,
    dev_kind="active", k=1, dev_null="bootstrap", dev_alpha=None,
    stress_cond="none specified",
    val_thresh=None, val_null="bootstrap CI + HAC t", val_alpha=None,
    dev_outcome="n/a", val_outcome="FAIL: alpha HAC t=1.12 (<2.0); Sharpe 0.52",
    protocol="pre-2026-09-23", archetype="TSTAT_REPLICATION",
    source="research/PREREGISTRATION_pead_2004_2014.md; RESEARCH_LEDGER row 1",
    notes="Pass criteria are HAC t>=2.0 + bootstrap CI excludes 0 + alpha positive both halves; "
          "not a Sharpe-threshold gate in the project's usual style.")

add(family="options_signals(H1-H4)", registered_at="2026-09-18T12:42:23-0700",
    dev_years=5.50, val_years=6.71,
    dev_thresh_formula="0.5 (absolute, flat)", dev_thresh_val=_old(5.50),
    dev_kind="absolute", k=4, dev_null="none", dev_alpha=None,
    stress_cond="none at dev (stress used only at validation)",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 4,
    dev_outcome="FAIL: 0/4 (H1..H4 net -0.37/-0.91/-0.94/-1.08)", val_outcome="not run (0/4 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/options_signals/PLAN.md; RESEARCH_LEDGER row 6")

add(family="putwrite(P1-P3)", registered_at="2026-09-18T13:13:05-0700",
    dev_years=5.58, val_years=6.71,
    dev_thresh_formula="0.5", dev_thresh_val=_old(5.58),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: 0/3 (0.21/0.15/0.04)", val_outcome="not run (0/3 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/putwrite/PLAN.md; RESEARCH_LEDGER row 8",
    notes="Validation also requires max drawdown no worse than SPY buy-and-hold.")

add(family="cot(C1-C3)", registered_at="2026-09-18T13:24:31-0700",
    dev_years=5.0, val_years=6.71,
    dev_thresh_formula="0.5", dev_thresh_val=_old(5.0),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: 0/3 (0.25/0.33/0.05; C1 gross 0.94)", val_outcome="not run (0/3 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/cot/PLAN.md; RESEARCH_LEDGER row 9")

add(family="intraday(I1-I4)", registered_at="2026-09-18T20:49:34-0700",
    dev_years=4.58, val_years=5.71,
    dev_thresh_formula="0.5", dev_thresh_val=_old(4.58),
    dev_kind="absolute", k=4, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 4,
    dev_outcome="PASS 1/4: I4 0.55 (I1 -0.12, I2 0.38, I3 -0.96)",
    val_outcome="FAIL: I4 val Sharpe -0.09 (< 0.75, and below 0.70 benchmark requirement)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/intraday/PLAN.md; reports/intraday/*; RESEARCH_LEDGER row 11",
    notes="Validation also requires Sharpe above the 0.70 PEAD benchmark.")

add(family="fx_carry_vol(F2,F3 vs F1)", registered_at="2026-09-18T21:06:48-0700",
    dev_years=5.0, val_years=6.71,
    dev_thresh_formula="0.5 AND above F1's Sharpe", dev_thresh_val=_old(5.0),
    dev_kind="absolute", k=2, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 2,
    dev_outcome="FAIL: 0/2 (F2 -0.22, F3 -0.33; F1 baseline -0.03)", val_outcome="not run (0/2 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/fx_carry_vol/PLAN.md; RESEARCH_LEDGER row 15",
    notes="k treated as 2 (F2, F3 challengers against F1) per the plan's own alpha=0.05/2.")

add(family="pead_portfolio(B1-B5)", registered_at="2026-09-18T22:02:19-0700",
    dev_years=3.87, val_years=None,
    dev_thresh_formula="Sharpe > PEAD's 0.70 (point estimate)", dev_thresh_val=0.70,
    dev_kind="active", k=5, dev_null="bootstrap", dev_alpha=0.05 / 5,
    stress_cond="none stated; drawdown-matched, not cost-stressed",
    val_thresh=None, val_null="n/a (single-window, 4-criterion gate; no separate validation split)",
    val_alpha=None,
    dev_outcome="FAIL: best B3 Sharpe 0.74, paired p=0.47 (needs <0.01)",
    val_outcome="n/a (single-stage design)",
    protocol="pre-2026-09-23", archetype="PAIRED_VS_BENCHMARK",
    source="research/pead_portfolio/PLAN.md; RESEARCH_LEDGER row 2",
    notes="4 criteria all required: beat PEAD Sharpe, paired p<0.01, DD no worse than PEAD, "
          "old-window Sharpe > PEAD. No independent held-out validation window at all -- "
          "the whole test is one development-style pass.")

add(family="insider(N1-N4)", registered_at="2026-09-19T01:43:31-0700",
    dev_years=10.0, val_years=10.5,
    dev_thresh_formula="0.5 AND beats control", dev_thresh_val=_old(10.0),
    dev_kind="active", k=4, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 4,
    dev_outcome="PASS 2/4: N3 0.77, N4 0.51 (N1, N2 fail)",
    val_outcome="FAIL: N3 0.49, N4 0.51 (both < 0.75)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/insider/PLAN.md; reports/insider/*; RESEARCH_LEDGER row 18",
    notes="Validation also needs paired p<0.0125 against its own control.")

add(family="rebalancing(R1-R3)", registered_at="2026-09-19T03:17:37-0700",
    dev_years=11.91, val_years=11.72,
    dev_thresh_formula="0.5", dev_thresh_val=_old(11.91),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="PASS 2/3: R2 0.74, R3 0.82 (R1 0.47 fails)",
    val_outcome="FAIL: R2 0.63, R3 0.45 (both < 0.75; also below 0.70 benchmark)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/rebalancing/PLAN.md; reports/rebalancing/*; RESEARCH_LEDGER row 13")

add(family="letf_rebalancing(L1-L2)", registered_at="2026-09-19T03:18:39-0700",
    dev_years=4.58, val_years=5.71,
    dev_thresh_formula="0.5", dev_thresh_val=_old(4.58),
    dev_kind="absolute", k=2, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 2,
    dev_outcome="FAIL (strictly): 0/2 (L1 0.39, L2 0.48, both < 0.50 gate)",
    val_outcome="not run (0/2 strictly pass); L2 was nonetheless promoted informally to a forward "
                "suggestion despite not clearing the registered 0.50 gate",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/letf_rebalancing/PLAN.md; reports/letf_rebalancing/*; RESEARCH_LEDGER row 12",
    notes="INCONSISTENCY: the ledger classifies this row 'FORWARD ONLY' with a monotone "
          "dose-response cited as support, even though L2's dev Sharpe (0.48) is below its own "
          "registered 0.50 gate. This is a gate that was not actually cleared.")

add(family="iv_changes(V1-V3)", registered_at="2026-09-19T06:42:59-0700",
    dev_years=5.42, val_years=6.67,
    dev_thresh_formula="0.5", dev_thresh_val=_old(5.42),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: 0/3 (-0.28/-1.01/-1.69)", val_outcome="not run (0/3 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/iv_changes/PLAN.md; RESEARCH_LEDGER row 7")

add(family="pead_streak(S1-S2)", registered_at="2026-09-19T06:43:51-0700",
    dev_years=6.25, val_years=4.0,
    dev_thresh_formula="0.5 AND beats control", dev_thresh_val=_old(6.25),
    dev_kind="active", k=2, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 2,
    dev_outcome="MIXED: S1 0.13 fails; S2 0.79 clears 0.5 but below its own all-events control",
    val_outcome="locked (S2 not selected: fails 'beats control' leg)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/pead_streak/PLAN.md; RESEARCH_LEDGER row 3")

add(family="auction_cycle(A1-A3)", registered_at="2026-09-19T06:44:15-0700",
    dev_years=5.0, val_years=6.72,
    dev_thresh_formula="0.5", dev_thresh_val=_old(5.0),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: 0/3 (-0.23/0.03/-0.18)", val_outcome="not run (0/3 dev pass)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/auction_cycle/PLAN.md; reports/auction_cycle/dev_results.json")

add(family="fundamentals(F1-F3)", registered_at="2026-09-19T06:45:52-0700",
    dev_years=11.9, val_years=11.6,
    dev_thresh_formula="0.5", dev_thresh_val=_old(11.9),
    dev_kind="absolute", k=3, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: 0/3 (all negative)", val_outcome="locked (2015+ unviewed for these signals)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/fundamentals/PLAN.md; RESEARCH_LEDGER row 19")

add(family="survivor_hybrid(H1-H4)", registered_at="2026-09-19T11:47:18-0700",
    dev_years=10.0, val_years=None,
    dev_thresh_formula="0.75 AND CI lower bound>0 AND DSR>=0.95 @ N=84", dev_thresh_val=0.75,
    dev_kind="absolute", k=4, dev_null="bootstrap+DSR", dev_alpha=0.05,
    stress_cond="R=30 haircut on net Sharpe; R=20/40 reported not gated",
    val_thresh=None, val_null="n/a (single-stage gate; a pass unlocks a forward test only)",
    val_alpha=None,
    dev_outcome="FAIL: H1 0.72, H4 0.70 (both below 0.75 gate)",
    val_outcome="n/a (single-stage)",
    protocol="pre-2026-09-23", archetype="DSR_SINGLE_STAGE",
    source="research/survivor_hybrid/PLAN.md; RESEARCH_LEDGER row 20",
    notes="Single-stage gate combining a Sharpe threshold, a bootstrap-CI floor and a deflated-"
          "Sharpe-ratio (DSR) floor at N=84 trials -- economically the strictest gate of any "
          "pre-amendment family, but it is not compared against a genuinely independent hold-out.")

add(family="etf_hybrids(E1-E5)", registered_at="2026-09-19T11:49:00-0700",
    dev_years=12.0, val_years=11.7,
    dev_thresh_formula="0.5 AND above benchmark B", dev_thresh_val=_old(12.0),
    dev_kind="active", k=5, dev_null="none", dev_alpha=None,
    stress_cond="none at dev",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.01,
    dev_outcome="PASS 2/5: E1 0.663, E2 0.570 (E3 0.470, E4 0.505-but-below-B, E5 0.412 fail)",
    val_outcome="FAIL: E1 0.377, E2 0.442 (both < 0.75)",
    protocol="pre-2026-09-23", archetype="OLD_ABS_NO_NULL",
    source="research/etf_hybrids/PLAN.md; reports/etf_hybrids/*; RESEARCH_LEDGER row 21",
    notes="alpha = 0.05/5 = 0.01 explicitly Bonferroni-adjusted at validation; E4's failure shows "
          "the benchmark-relative dev leg binds even when the flat 0.5 Sharpe leg is cleared.")

add(family="macro_surprise(M1,M2)", registered_at="2026-09-23T00:13:25-0700",
    dev_years=5.58, val_years=5.8,
    dev_thresh_formula="0.50 (M1); M2 conditional on M1", dev_thresh_val=_old(5.58),
    dev_kind="active", k=2, dev_null="none", dev_alpha=None,
    stress_cond="stress mean net excess > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.025,
    dev_outcome="FAIL: M1 net -0.50 (gross -0.20); M2 not eligible (M1 not selected)",
    val_outcome="not run (M1 failed dev)",
    protocol="mixed: registered 2026-09-23T00:13, i.e. 10 hours BEFORE the 2026-09-23T10:04 "
             "protocol amendment -- still used the 0.5 dev gate.",
    archetype="OLD_ABS_NO_NULL",
    source="research/macro_surprise/PLAN.md; RESEARCH_LEDGER cycle-2 update",
    notes="Registered same calendar day as the protocol amendment but ~10 hours earlier, so it "
          "correctly used the old 0.5 gate under the timestamp rule ('applies to registrations "
          "made after this file is registered'). Flagged only for visibility, not as a violation.")

add(family="multiasset(17-sleeve inclusion + 5-sleeve holdout)", registered_at="2026-09-18T11:52:15-0700",
    dev_years=10.0, val_years=8.71,
    dev_thresh_formula="0.30 (sleeve inclusion, >=3yr history)", dev_thresh_val=0.30,
    dev_kind="absolute", k=17, dev_null="none", dev_alpha=None,
    stress_cond="none at inclusion",
    val_thresh=None, val_null="HAC t-test (Newey-West 20 lags), not Sharpe/bootstrap",
    val_alpha=None,
    dev_outcome="PASS (inclusion): 5/17 sleeves >= 0.30 (combined book dev Sharpe 0.57)",
    val_outcome="FAIL: hold-out mean HAC t and alpha-vs-SPY HAC t both need >=2.0; book Sharpe "
                "went to -0.02",
    protocol="pre-2026-09-23", archetype="SLEEVE_INCLUSION",
    source="research/multiasset/PLAN.md; PREREGISTRATION_holdout.md; RESEARCH_LEDGER row 4",
    notes="INCONSISTENCY: dev inclusion threshold (0.30 Sharpe, 17 candidates, no null, no "
          "multiple-testing correction) is far weaker than every other family's 0.5 dev gate, let "
          "alone the post-amendment 1.8/sqrt(T)-2.4/sqrt(T) standard. 17 candidates at a flat 0.30 "
          "bar is exactly the 'best of N nulls' scenario the null lab warns about.")

add(family="multiasset/crypto(2 candidates)", registered_at="2026-09-18T12:08:28-0700",
    dev_years=3.5, val_years=4.0,
    dev_thresh_formula="best-of-N selection (see notes)", dev_thresh_val=None,
    dev_kind="absolute", k=2, dev_null="none", dev_alpha=None,
    stress_cond="none stated",
    val_thresh=None, val_null="none (beta-implied benchmark, normal approx.)", val_alpha=None,
    dev_outcome="dev Sharpe 1.24 (long-only, = BTC buy-and-hold) and 1.11 (tsmom_multi)",
    val_outcome="FAIL: long_only 0.40 vs beta-implied 0.18 (p=0.32, normal approx.); tsmom_multi 0.17",
    protocol="pre-2026-09-23", archetype="SLEEVE_INCLUSION",
    source="research/multiasset/PLAN_CRYPTO.md; reports/null_lab/REPORT.md record table")


# ---------------------------------------------------------------------------
# POST-AMENDMENT FAMILIES (2026-09-23 amendment): dev = active/absolute Sharpe
# >= 1.8/sqrt(T) [2.4/sqrt(T) if k>=4], stress mean>0, null-test required
# (bootstrap / shift / permutation) except credit_lead and index_option_breadth,
# which compute but do not gate on P(pass|null).
# ---------------------------------------------------------------------------

add(family="japan_us_flow(J1)", registered_at="2026-09-23T13:04:23-0700",
    dev_years=4.58, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(4.58, 1),
    dev_kind="active", k=1, dev_null="bootstrap", dev_alpha=0.05,
    stress_cond="stress-cost annualized mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05,
    dev_outcome="FAIL: J1 base Sharpe 0.30 vs gate 0.84; J1-C1 bootstrap p=0.166",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/japan_us_flow/PLAN.md; reports/japan_us_flow/dev_results.json",
    notes="Also reports a 5,000-world shift-null (P1) for P(pass|null)=0.0128, in addition to (not "
          "instead of) the bootstrap gate.")

add(family="credit_lead", registered_at="2026-09-23T13:19:50-0700",
    dev_years=9.0, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(9.0, 1),
    dev_kind="active", k=1, dev_null="reported_only", dev_alpha=None,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="bootstrap (diagnostic only at dev)", val_alpha=0.05,
    dev_outcome="FAIL: active vs C0 Sharpe 0.296 vs gate 0.60 (raw strategy Sharpe 0.73, but its "
                "matched control C0 alone scores 1.26)",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_NOPGATE",
    source="research/credit_lead/PLAN.md; reports/credit_lead/dev_results.json",
    notes="INCONSISTENCY: the plan's own pass criteria (Sharpe>=gate, stress mean>0, beat C1 & C2) "
          "contain no p-value threshold at all -- P(pass|null) is to be 'reported', not gated on. "
          "This is weaker than sibling families registered the same day (japan_us_flow, "
          "index_option_breadth is the same pattern; tsy_month_end/credit_gate/policy_trend/fx_news "
          "DO gate on p<alpha).")

add(family="index_option_breadth", registered_at="2026-09-23T13:24:34-0700",
    dev_years=4.49, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(4.49, 1),
    dev_kind="active", k=1, dev_null="reported_only", dev_alpha=None,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05,
    dev_outcome="FAIL: active vs C0 Sharpe -1.21 vs gate 0.85",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_NOPGATE",
    source="research/index_option_breadth/PLAN.md; reports/index_option_breadth/dev_results.json",
    notes="Same 'no p-threshold in the actual pass criteria' pattern as credit_lead.")

add(family="policy_trend(P1)", registered_at="2026-09-23T14:27:32-0700",
    dev_years=7.5, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(7.5, 1),
    dev_kind="absolute (long-short, self-financed)", k=1, dev_null="permutation", dev_alpha=0.05,
    stress_cond="stress mean > 0",
    val_thresh=0.75, val_null="bootstrap + permutation", val_alpha=0.05,
    dev_outcome="FAIL: net Sharpe 0.03 (gross 0.07) vs gate 0.657; permutation p=0.39, shift p=0.42",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_PERMUTATION",
    source="research/policy_trend/PLAN.md; reports/policy_trend/dev_results.json; RESEARCH_LEDGER row 33")

add(family="fx_news(F1,F2)", registered_at="2026-09-23T18:43:43-0700",
    dev_years=6.0, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(6.0, 2),
    dev_kind="active", k=2, dev_null="permutation", dev_alpha=0.05,
    stress_cond="stress mean > 0",
    val_thresh=0.75, val_null="bootstrap + permutation", val_alpha=0.025,
    dev_outcome="FAIL: F1 net Sharpe -4.71 (perm p=0.94), F2 net Sharpe -1.61 (perm p=0.69)",
    val_outcome="locked (dev failed both)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_PERMUTATION",
    source="research/fx_news/PLAN.md; reports/fx_news/dev_results.json; RESEARCH_LEDGER cycle-3")

add(family="credit_gate(G)", registered_at="2026-09-23T22:07:40-0700",
    dev_years=7.7, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(7.7, 1),
    dev_kind="active", k=1, dev_null="shift", dev_alpha=0.05,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05,
    dev_outcome="FAIL: active Sharpe -0.04 vs gate 0.647; also fails G vs C_TREND leg",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_SHIFT",
    source="research/credit_gate/PLAN.md; reports/credit_gate/dev_results.json; RESEARCH_LEDGER cycle-3")

add(family="structural_frontier(A: Treasury term premium)", registered_at="2026-09-23T22:17:02-0700",
    dev_years=12.0, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(12.0, 3),
    dev_kind="active", k=3, dev_null="bootstrap", dev_alpha=0.05 / 3,
    stress_cond="stress-cost mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL ON P-VALUE ONLY: active Sharpe 0.569 clears gate 0.520, but bootstrap "
                "p=0.023 misses the batch threshold 0.01667",
    val_outcome="locked (dev failed on multiplicity-adjusted p, despite clearing the Sharpe bar)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/structural_frontier/PLAN.md; reports/structural_frontier/term_dev_results.json; "
           "RESEARCH_LEDGER row 36",
    notes="The cleanest example in the registry of the Sharpe gate and the (Bonferroni) p-gate "
          "disagreeing: an economically real-looking 0.57 Sharpe still fails once family size is "
          "priced in.")

add(family="structural_frontier(B: HY credit carry)", registered_at="2026-09-23T22:17:02-0700",
    dev_years=9.0, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(9.0, 3),
    dev_kind="active", k=3, dev_null="bootstrap", dev_alpha=0.05 / 3,
    stress_cond="stress-cost mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: active Sharpe 0.296 vs gate 0.60; p=0.186",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/structural_frontier/PLAN.md; reports/structural_frontier/credit_dev_results.json")

add(family="structural_frontier(C: TLT put insurance)", registered_at="2026-09-23T22:17:02-0700",
    dev_years=8.48, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(8.48, 3),
    dev_kind="active", k=3, dev_null="bootstrap", dev_alpha=0.05 / 3,
    stress_cond="stress-cost mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05 / 3,
    dev_outcome="FAIL: active Sharpe 0.072 vs gate 0.618; p=0.427",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/structural_frontier/PLAN.md; reports/structural_frontier/option_dev_results.json")

add(family="vrp_putwrite(PW)", registered_at="2026-09-23T22:27:35-0700",
    dev_years=5.60, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(5.60, 1),
    dev_kind="active", k=1, dev_null="bootstrap", dev_alpha=0.05,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.05,
    dev_outcome="FAIL: active (PW - 0.5xSPY) Sharpe approx -0.05, active bootstrap p=0.56; "
                "gross Sharpe 0.74 driven almost entirely by the 0.50 SPY beta",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/vrp_putwrite/PLAN.md; reports/vrp_putwrite/dev_results.json; RESEARCH_LEDGER row 36")

add(family="etf_basis(B)", registered_at="2026-09-23T22:29:55-0700",
    dev_years=6.0, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(6.0, 1),
    dev_kind="active", k=1, dev_null="shift", dev_alpha=0.05,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="shift", val_alpha=0.05,
    dev_outcome="FAIL: active-vs-exposure Sharpe 0.337 vs gate 0.735; shift p=0.104; "
                "B-C_REV mean positive (that leg alone passes)",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_SHIFT",
    source="research/etf_basis/PLAN.md; reports/etf_basis/dev_results.json; RESEARCH_LEDGER row 37")

add(family="tsy_month_end(M)", registered_at="2026-09-23T22:31:39-0700",
    dev_years=12.0, val_years=11.63,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(12.0, 1),
    dev_kind="active", k=1, dev_null="shift", dev_alpha=0.05,
    stress_cond="stress-cost active mean > 0",
    val_thresh=0.75, val_null="shift + bootstrap", val_alpha=0.05,
    dev_outcome="PASS: active Sharpe 0.664 (base) vs gate 0.520; shift p approx 0.006",
    val_outcome="FAIL (narrow): active Sharpe 0.69 vs gate 0.75; shift p=0.005, bootstrap p=0.004, "
                "10/12 years positive; combined p 0.00034 x120 trials = 0.041",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_SHIFT",
    source="research/tsy_month_end/PLAN.md; reports/tsy_month_end/{dev,validation}_results.json; "
           "RESEARCH_LEDGER row 38",
    notes="Only family with a genuine dev PASS under the new protocol; validation misses by 0.06 "
          "Sharpe despite very low null p-values on both legs -- 'strongest evidence to date; not "
          "validated' per the ledger.")

add(family="commodity_roll", registered_at="2026-09-23T23:16:05-0700",
    dev_years=10.44, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(10.44, 2),
    dev_kind="absolute (market-neutral spread, no long-only control needed)", k=2,
    dev_null="bootstrap", dev_alpha=0.025,
    stress_cond="stress mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.025,
    dev_outcome="PASS: base Sharpe 0.596 vs gate 0.557; bootstrap p=0.0064 (<0.025)",
    val_outcome="locked (VALIDATION_UNLOCK.md not registered in this workstream's window; not run)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/commodity_roll/PLAN.md; reports/commodity_roll/dev_results.json",
    notes="Workstream-A pair with mbs_convexity; alpha=0.05/2=0.025 by design. This is one of only "
          "two dev passes under the full post-amendment protocol (with tsy_month_end).")

add(family="mbs_convexity", registered_at="2026-09-23T23:16:05-0700",
    dev_years=8.75, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(8.75, 2),
    dev_kind="absolute (hedged spread)", k=2, dev_null="bootstrap", dev_alpha=0.025,
    stress_cond="stress mean > 0",
    val_thresh=0.75, val_null="bootstrap", val_alpha=0.025,
    dev_outcome="FAIL: base Sharpe 0.402 vs gate 0.609; bootstrap p=0.043 (misses 0.025 too)",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_BOOTSTRAP",
    source="research/mbs_convexity/PLAN.md; reports/mbs_convexity/dev_results.json")

add(family="sector_month_end", registered_at="2026-09-23T23:16:05-0700",
    dev_years=10.90, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(10.90, 1),
    dev_kind="active", k=1, dev_null="shift", dev_alpha=0.05,
    stress_cond="stress active mean > 0",
    val_thresh=0.75, val_null="shift + bootstrap", val_alpha=0.05,
    dev_outcome="FAIL ON SHARPE (PASS ON SHIFT-p): base active Sharpe -0.433 vs gate 0.545 "
                "(fails); mean-centred bootstrap p=0.993 (fails); BUT the shift-null p=0.038 "
                "(<0.05, 'passes') because the shift-null's own mean is -0.965, not 0",
    val_outcome="locked (dev failed the Sharpe leg, which is the binding one)",
    protocol="post-2026-09-23", archetype="NEW_ACTIVE_SHIFT",
    source="research/sector_month_end/PLAN.md; reports/sector_month_end/dev_results.json",
    notes="TEXTBOOK 'null answers the wrong question' case named in this workstream's brief: the "
          "shift-null distribution here is centred at active Sharpe approx -0.96 because ANY random "
          "3-day window pays similar turnover cost, so a shift-null p<0.05 only shows the tested "
          "window is 'less bad than random', not that it is profitable. The overall gate still "
          "fails here only because the Sharpe threshold is separately binding -- a family that "
          "gated on the shift-null p alone would have passed with net Sharpe -0.43.")

add(family="fx_hedge_rebal", registered_at="2026-09-23T23:16:05-0700",
    dev_years=6.21, val_years=None,
    dev_thresh_formula="1.8/sqrt(T)", dev_thresh_val=_new(6.21, 1),
    dev_kind="absolute (book Sharpe; not explicitly active vs C_USDSHORT)", k=1,
    dev_null="permutation", dev_alpha=0.05,
    stress_cond="stress mean > 0",
    val_thresh=0.75, val_null="permutation", val_alpha=0.05,
    dev_outcome="FAIL: base Sharpe 0.090 vs gate 0.722; permutation p=0.180",
    val_outcome="locked (dev failed)",
    protocol="post-2026-09-23", archetype="NEW_ABS_PERMUTATION",
    source="research/fx_hedge_rebal/PLAN.md; reports/fx_hedge_rebal/dev_results.json",
    notes="The Sharpe gate binds on the raw book, not on book-minus-C_USDSHORT, even though the "
          "protocol amendment's item A2 requires long/directionally-biased books to gate on active "
          "return vs an exposure-matched control. This book is direction-switching rather than "
          "long-biased, which is a plausible reason, but the plan text never states the exemption.")
