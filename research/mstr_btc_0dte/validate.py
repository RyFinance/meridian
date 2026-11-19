"""One-shot validation of the frozen candidates in CANDIDATES.md on 2024-01-01..2026-09-17 1-minute data."""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from research.mstr_btc_0dte.engine import prepare, COMM
from research.mstr_btc_0dte.pct import Short, backtest

H = Path(__file__).parent
CANDS = {"V1": Short("safe", 0.06, None, 15), "V2": Short("both", 0.04, None, 5), "V3": Short("safe", 0.04, None, 15, 0.01)}
T_BONF = 2.13


def summarize(t):
    x = t.ret
    eq = (1 + x).cumprod()
    return {"n": int(len(x)), "win": float((x > 0).mean()), "mean": float(x.mean()),
            "t": float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else None,
            "worst": float(x.min()), "sum": float(x.sum()), "compounded_1x": float(eq.iloc[-1] - 1),
            "max_dd_1x": float((eq / eq.cummax() - 1).min()),
            "by_year": {int(y): {"n": int(len(g)), "mean": float(g.mean()), "min": float(g.min())} for y, g in x.groupby(x.index.year)}}


if __name__ == "__main__":
    cache = H / "val_days.pkl"
    days = pickle.load(open(cache, "rb")) if cache.exists() else prepare("validation")
    pickle.dump(days, open(cache, "wb"))
    days = [d for d in days if d.d <= pd.Timestamp("2026-05-21")]  # 2026-05-22.. is a second holdout
    print("validation days", len(days), days[0].d.date(), "..", days[-1].d.date())
    out = {}
    for cid, s in CANDS.items():
        res = {}
        for f in ("base", "worst"):
            t = backtest(days, Short(**{**s.__dict__, "fills": f}))
            res[f] = summarize(t)
            if f == "worst":
                harsh = t.assign(ret=(t.pnl - 0.10 * (t.credit + COMM)) / t.margin)
                res["harsh"] = summarize(harsh)
                t.to_csv(H / f"val_trades_{cid}.csv")
        b, w = res["base"], res["worst"]
        res["PASS"] = bool(b["mean"] > 0 and w["mean"] > 0 and (b["t"] or 0) >= T_BONF
                           and all(v["mean"] >= -0.10 for v in b["by_year"].values()))
        out[cid] = res
        print(f"\n{cid} {s}")
        for f in ("base", "worst", "harsh"):
            r = res[f]
            print(f"  {f:5s} n={r['n']} win={r['win']:.3f} mean={r['mean']*100:+.2f}% t={r['t']:+.2f} worst={r['worst']*100:+.1f}% "
                  f"compounded={r['compounded_1x']*100:+.0f}% maxDD={r['max_dd_1x']*100:.0f}%")
        print("  by year (base):", {y: (v["n"], round(v["mean"] * 100, 2), round(v["min"] * 100, 1)) for y, v in res["base"]["by_year"].items()})
        print("  PASS" if res["PASS"] else "  FAIL")
    (H / "validation_results.json").write_text(json.dumps(out, indent=2))
