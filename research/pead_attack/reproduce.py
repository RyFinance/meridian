"""Reproduction gate (allowed before registration: it only reproduces already-published numbers).

1. Every calibrated probability the recorded replay logged (live_backtest/state/sweep_wide_5p0_cycle_log.jsonl)
   equals the probability re-scored here from the pinned inputs.
2. The engine, fed the production scores, reproduces the recorded sweep_wide_5p0 ledger trade for trade and
   the cycle log's decision for every candidate.
3. Marking the engine's ledger with research.pead_audit.mtm_audit.mtm_book reproduces the published 0.70
   marked excess Sharpe; the numpy transcription (marking.mark_book) equals mtm_book to float precision.

Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.reproduce   (writes reports/pead_attack/reproduction.json)
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from research.pead_attack.common import OUT, STATE, Inputs, read_jsonl
from research.pead_attack.engine import simulate
from research.pead_attack.marking import mark_book, mark_with_mtm_audit
from research.pead_audit.mtm_audit import mtm_book, positions, stats

PUBLISHED = OUT.parent / "pead_audit" / "results.json"
REASON_MAP = {"executed": None, "no_conviction": "no_conviction", "risk_blocked": "risk_blocked",
              "circuit_breaker_halt": "circuit_breaker_halt"}


def recorded_ledger() -> pd.DataFrame:
    p = positions("wide_5p0")
    return p.sort_values(["entry_date", "ticker"]).reset_index(drop=True)


def run_real(inp: Inputs, collect: bool = True) -> dict:
    return simulate(inp.stream, inp.p_real, inp.size_real, inp.sign_prod, collect_decisions=collect)


def main() -> dict:
    inp = Inputs()
    ev = inp.events
    out: dict = {}

    # -- 1. scores ------------------------------------------------------------------------------
    log = read_jsonl(STATE / "sweep_wide_5p0_cycle_log.jsonl")
    ent = pd.DataFrame([dict(as_of=r["as_of_date"], **e) for r in log for e in r["entries"]])
    ent["key"] = ent["ticker"] + "|" + pd.to_datetime(ent["earnings_date"]).dt.date.astype(str)
    ev_key = ev["ticker"] + "|" + pd.to_datetime(ev["earnings_date_raw"]).dt.date.astype(str)
    mine = pd.Series(ev["calibrated_proba"].to_numpy(), index=ev_key)
    matched = ent["key"].map(mine)
    out["scores"] = {"logged_candidates": int(len(ent)), "rescored_scorable_events": int(ev["scorable"].sum()),
                     "missing": int(matched.isna().sum()),
                     "max_abs_diff": float(np.nanmax(np.abs(matched.to_numpy() - ent["calibrated_proba"].to_numpy()))),
                     "exact_equal": bool((matched.to_numpy() == ent["calibrated_proba"].to_numpy()).all())}

    # -- 2. ledger and decisions ----------------------------------------------------------------
    t0 = time.time()
    res = run_real(inp)
    out["engine_seconds"] = round(time.time() - t0, 3)
    tr = res["trades"].copy()
    tr["entry_date"] = inp.dates[tr["entry_i"].to_numpy()]
    tr["exit_date"] = inp.dates[tr["exit_i"].to_numpy()]
    tr = tr.sort_values(["entry_date", "ticker"]).reset_index(drop=True)
    rec = recorded_ledger()
    same_shape = len(tr) == len(rec)
    cmp = {"n_engine": int(len(tr)), "n_recorded": int(len(rec)), "open_at_end": int((res["trades"]["exit_i"] < 0).sum())}
    if same_shape:
        cmp["identity_match"] = bool((tr["ticker"].to_numpy() == rec["ticker"].to_numpy()).all()
                                     and (tr["entry_date"].to_numpy() == rec["entry_date"].to_numpy()).all()
                                     and (tr["exit_date"].to_numpy() == rec["exit_date"].to_numpy()).all()
                                     and (tr["sign"].to_numpy() == rec["sign"].to_numpy()).all())
        for c in ["fill_price", "exit_price", "notional", "realized_pnl"]:
            cmp[f"max_abs_diff_{c}"] = float(np.max(np.abs(tr[c].to_numpy() - rec[c].to_numpy())))
        cmp["max_abs_diff_size"] = float(np.max(np.abs(tr["size_fraction"].to_numpy() - rec["size_fraction"].to_numpy())))
    cmp["final_cash_nav_engine"] = res["final_cash_nav"]
    cmp["final_cash_nav_recorded"] = float(log[-1]["nav_after"])
    out["ledger"] = cmp
    dec = pd.DataFrame(res["decisions"], columns=["i", "event", "reason"])
    dec["as_of"] = [str(d.date()) for d in inp.dates[dec["i"].to_numpy()]]
    dec["key"] = ev_key.to_numpy()[dec["event"].to_numpy()]
    rec_dec = ent.assign(reason=ent["reason"].map(REASON_MAP))[["as_of", "key", "reason"]]
    m = dec.merge(rec_dec, on=["as_of", "key"], how="outer", suffixes=("_engine", "_recorded"), indicator=True)
    out["decisions"] = {"n_engine": int(len(dec)), "n_recorded": int(len(rec_dec)),
                        "unmatched": int((m["_merge"] != "both").sum()),
                        "reason_mismatch": int((m["_merge"].eq("both") & ~(m["reason_engine"].fillna("x") == m["reason_recorded"].fillna("x"))).sum())}

    # -- 3. marking -----------------------------------------------------------------------------
    rf = inp.calendar["rf"]
    ref = mark_with_mtm_audit(res["trades"], inp.px_mark_df, inp.dates, rf)
    fast = mark_book(res["trades"], inp.px_mark, inp.col, inp.rf)
    published = json.loads(PUBLISHED.read_text())["wide_5p0"]
    # the audit's own ledger through the audit's own code, as a third check
    audit_ref = mtm_book(positions("wide_5p0"), inp.px_mark_df, inp.dates, rf, 0.0005, 0.0, cash_earns_rf=True)
    s_ref = stats(ref["ret"] - rf, inp.calendar["mkt_rf"])
    out["marking"] = {
        "fast_vs_mtm_book_max_abs_ret_diff": float(np.max(np.abs(fast["ret"] - ref["ret"].to_numpy()))),
        "engine_ledger_vs_audit_ledger_max_abs_ret_diff": float(np.max(np.abs(ref["ret"].to_numpy() - audit_ref["ret"].to_numpy()))),
        "mtm_final_nav": float(ref["nav"].iloc[-1]),
        "excess_sharpe_reproduced": s_ref["sharpe"], "excess_sharpe_published": published["C_mtm_excess_cash_earns_rf"]["sharpe"],
        "alpha_reproduced": s_ref["alpha_ann"], "beta_reproduced": s_ref["beta"],
        "alpha_t_reproduced": s_ref["alpha_t"], "alpha_t_published": published["C_mtm_excess_cash_earns_rf"]["alpha_t"],
    }
    out["gate_passed"] = bool(
        out["scores"]["max_abs_diff"] < 1e-12 and out["scores"]["missing"] == 0 and same_shape and cmp.get("identity_match")
        and cmp["max_abs_diff_realized_pnl"] < 1e-6 and out["decisions"]["unmatched"] == 0
        and out["decisions"]["reason_mismatch"] == 0 and out["marking"]["fast_vs_mtm_book_max_abs_ret_diff"] < 1e-12
        and abs(out["marking"]["excess_sharpe_reproduced"] - out["marking"]["excess_sharpe_published"]) < 1e-9)
    (OUT / "reproduction.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=float))
