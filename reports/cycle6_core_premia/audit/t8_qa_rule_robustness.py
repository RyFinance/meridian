"""Test 8 (robustness report, labelled; cannot create a pass): could Addendum-1's QA-rule changes (history truncation
instead of FAIL; WTI TE month filter) have steered which components entered the book? Re-evaluate the 20 components'
fidelity and the book under the LITERAL FRAMEWORK §3 rule (instruments whose notes say STRICT full-history FAIL are
removed) and, separately, with CM_WTI removed. In-memory only: no ledger rows, no builder outputs touched."""
from common import *
import json, re
from research.cycle6.engine import guards, component
VIEWROOT = VIEW.parent
MEMB = VIEW / "candidate_list.csv"
rates = pd.read_csv(REPO / "data/cycle6/rates/candidates.csv")
strict_fail = set(rates.market_id[rates.notes.astype(str).str.contains("STRICT full-history status would be FAIL")])
scen = {"strict_rule": strict_fail, "no_WTI": {"CM_WTI"}}
rows, sleeves = [], {k: {} for k in scen}
for cid in ALL20:
    params = guards.parse_params((REPO / f"research/cycle6/specs/{cid}.md").read_text())
    params["inference"]["B"] = 999                      # robustness only; p not used for any decision here
    base = json.load(open(COMP / cid / "metrics.json"))
    data0 = component.load_inputs(params, VIEWROOT, MEMB)
    for sname, drop in scen.items():
        keep = [c for c in data0["daily"].columns if c not in drop]
        if len(keep) == len(data0["daily"].columns):
            rows.append(dict(id=cid, scenario=sname, dropped=0, fid_base=base["fidelity"]["pass"], fid_robust=base["fidelity"]["pass"],
                             post_sharpe_base=base["net_post"]["sharpe_ann"], post_sharpe_robust=base["net_post"]["sharpe_ann"]))
            if base["fidelity"]["pass"]:
                sleeves[sname][cid] = load_component(cid)
            continue
        data = dict(data0); data["daily"] = data0["daily"][keep]
        data["signal_inputs"] = {k: v[[c for c in v.columns if c in keep]] for k, v in data0["signal_inputs"].items()}
        try:
            res = component.compute_component(params, data)
            m = res["metrics"]; net = res["net"]
            rows.append(dict(id=cid, scenario=sname, dropped=len(data0["daily"].columns) - len(keep),
                             fid_base=base["fidelity"]["pass"], fid_robust=m["fidelity"]["pass"],
                             fid_reason=";".join(m["fidelity"].get("reasons", [])), post_sharpe_base=base["net_post"]["sharpe_ann"],
                             post_sharpe_robust=m["net_post"]["sharpe_ann"]))
            if m["fidelity"]["pass"]:
                sleeves[sname][cid] = net
        except Exception as e:
            rows.append(dict(id=cid, scenario=sname, dropped=len(data0["daily"].columns) - len(keep), fid_base=base["fidelity"]["pass"],
                             fid_robust="infeasible/error", fid_reason=str(e)[:80]))
o = pd.DataFrame(rows); pd.set_option("display.width", 250); print(o.round(3).to_string())
o.to_csv(OUT / "t8_qa_rule_robustness.csv", index=False)
tb = tbill_monthly(); core = pidx(pd.read_csv(BOOKDIR / "sleeves.csv", index_col=0))["CORE"]
for sname, sl in sleeves.items():
    R = pd.DataFrame({c: d["ret"] for c, d in sl.items()}); G = pd.DataFrame({c: d["gross_exposure"] for c, d in sl.items()})
    R.index = pd.PeriodIndex(R.index.astype(str), freq="M"); G.index = R.index
    R["CORE"] = core; G["CORE"] = 1.0
    idx = pd.period_range(R.index.min(), R.index.max(), freq="M"); R, G = R.reindex(idx), G.reindex(idx)
    x = build_book(R, G, tb).excess.loc[POST:]; c = calib_ci(x.to_numpy(), 0.90, seed=20260946)
    print(sname, "book sleeves:", list(sl), f"post Sharpe {stats(x)['sharpe']:.2f} CI90 [{c[0]:.2f}, {c[1]:.2f}]")
