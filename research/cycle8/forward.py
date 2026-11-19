"""Forward lens (FRAMEWORK §5.4, ADDENDUM_1 §8, §10.1) + answer rule (FRAMEWORK §6).

usage: python -m research.cycle8.forward --run reports/cycle8_max_return/out --proc <snapshot>/proc --cma <snapshot>/cma
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle8.engine.menu import ANSWER_ITEMS, MENU, RP_SLEEVES
from research.cycle8.engine import sleeves as SL

SOURCES = ["FP Canada PAG", "J.P. Morgan LTCMA", "Vanguard VCMM", "AQR", "BlackRock CMA"]
W_COMMON = ("1988-01", "2026-05")
FEE = {"EQ_G": 0.20, "EQ_GH": 0.20 + 0.10, "BOND": 0.10, "GOLD": 0.25, "TREND": 2.0, "CASH": 0.0}
SPREAD = 1.5
TOL = (0.25, 0.35, 0.50)


def sleeve_cmas(cma: pd.DataFrame, sig: pd.Series) -> pd.DataFrame:
    """Per source x sleeve forward ARITHMETIC nominal CAD %/yr, per ADDENDUM_1 §10.1."""
    rows = {}
    m = cma[cma.source.isin(SOURCES)]
    cash_pub = m[(m.sleeve == "CASH") & m.geo_nominal_cad.notna()].set_index("source").geo_nominal_cad
    cash_fill = float(cash_pub.median())
    infl_pub = m[(m.sleeve == "INFL_CAD") & m.geo_nominal_cad.notna()].set_index("source").geo_nominal_cad
    infl_fill = float(infl_pub.median())
    for s in SOURCES:
        g = m[m.source == s].set_index("sleeve")
        cash = float(cash_pub.get(s, cash_fill))
        infl = float(infl_pub.get(s, infl_fill))
        r = {"CASH": cash, "INFL": infl, "cash_borrowed": s not in cash_pub.index,
             "infl_borrowed": s not in infl_pub.index}
        # EQ_G
        if s == "BlackRock CMA":     # rule 2: BlackRock's own CAD figures, XEQT blend (Europe = dev ex-NA proxy)
            comp = {"US": (7.29, 16.53, .45), "CA": (6.12, 13.78, .25), "DX": (5.77, 15.47, .25),
                    "EM": (7.13, 19.79, .05)}
            r["EQ_G"] = sum(w * (gm + sd ** 2 / 200) for gm, sd, w in comp.values())
            r["EQ_G_note"] = "BlackRock CAD figures, XEQT blend, geo + own sigma^2/2"
        else:
            row = g.loc["EQ_G"]
            if isinstance(row.arith_nominal_cad, float) and np.isfinite(row.arith_nominal_cad):
                r["EQ_G"] = float(row.arith_nominal_cad)
                r["EQ_G_note"] = str(row.conversion_status)[:80]
            else:
                r["EQ_G"] = float(row.geo_nominal_cad) + 100 * sig["EQ_G"] ** 2 / 2
                r["EQ_G_note"] = "geo + W_COMMON sigma^2/2 (rule 3)"
        row = g.loc["BOND"]
        if isinstance(row.arith_nominal_cad, float) and np.isfinite(row.arith_nominal_cad):
            r["BOND"] = float(row.arith_nominal_cad)
        else:
            r["BOND"] = float(row.geo_nominal_cad) + 100 * sig["BOND"] ** 2 / 2
        r["GOLD"] = 5.73 if s == "J.P. Morgan LTCMA" else infl
        r["GOLD_fallback"] = s != "J.P. Morgan LTCMA"
        r["TREND_gross"] = cash + 2.0          # rule 4: fallback for every source
        rows[s] = r
    return pd.DataFrame(rows).T


def fwd_item(E: dict, item: str, L: float, w_rp: pd.Series, cov: pd.DataFrame, wht_fwd: float) -> tuple:
    cash = E["CASH"]
    exp = {"EQ_G": E["EQ_G"], "EQ_GH": E["EQ_G"], "BOND": E["BOND"], "GOLD": E["GOLD"],
           "TREND": E["TREND_gross"], "CASH": cash}
    spec = MENU[item]
    fw = dict(w_rp) if spec["funded"] == "RISK_PARITY" else dict(spec["funded"])
    ar = sum(L * w * (exp[k] - FEE[k]) for k, w in fw.items())
    ov = {"X_TREND": exp["TREND"] - FEE["TREND"] - cash, "X_BOND": exp["BOND"] - FEE["BOND"] - cash}
    ar += sum(L * o * ov[k] for k, o in spec["overlay"].items())
    ar -= (L - 1) * (cash + SPREAD)
    if L == 1.0:
        ar -= wht_fwd * sum(w for k, w in fw.items() if k.startswith("EQ"))
    # sigma from W_COMMON covariance (annual, decimal) of the sleeve columns used
    cols = {"EQ_G": "EQ_G_tfsa", "EQ_GH": "EQ_GH_tfsa", "BOND": "BOND", "GOLD": "GOLD", "TREND": "TREND",
            "CASH": "CASH"}
    vec = pd.Series(0.0, index=cov.index)
    for k, w in fw.items():
        vec[cols[k]] += w
    for k, o in spec["overlay"].items():
        vec[k] += o
    sd = L * float(np.sqrt(vec @ cov @ vec))
    geo = ar - 100 * sd ** 2 / 2
    return ar, geo, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--proc", required=True)
    ap.add_argument("--cma", required=True)
    a = ap.parse_args()
    out = Path(a.run)
    M = pd.read_parquet(out / "sleeves_monthly.parquet")
    tab = pd.read_csv(out / "item_table.csv", index_col=0)
    rets = pd.read_parquet(out / "item_returns_monthly.parquet")
    Mc = M.loc[W_COMMON[0]:W_COMMON[1]]
    cols = ["EQ_G_tfsa", "EQ_GH_tfsa", "BOND", "GOLD", "TREND", "CASH", "X_TREND", "X_BOND"]
    cov = Mc[cols].cov() * 12
    sig = pd.Series({"EQ_G": np.sqrt(cov.loc["EQ_G_tfsa", "EQ_G_tfsa"]), "BOND": np.sqrt(cov.loc["BOND", "BOND"])})
    cma = pd.read_csv(Path(a.cma) / "cma_mapped.csv")
    S = sleeve_cmas(cma, sig)
    med = {k: float(pd.to_numeric(S[k]).median()) for k in ["EQ_G", "BOND", "GOLD", "TREND_gross", "CASH", "INFL"]}
    S.loc["MEDIAN"] = pd.Series(med)
    S.to_csv(out / "forward_sleeves.csv")
    w_rp = pd.read_csv(out / "p5_weights.csv", index_col=0, parse_dates=True).loc[W_COMMON[0]:W_COMMON[1]].mean()
    w_rp.index = [c.replace("_tfsa", "") for c in w_rp.index]
    dp = pd.read_parquet(Path(a.proc) / "eq_monthly.parquet")["US_dp"].dropna().iloc[-1]
    wht_fwd = 100 * (0.45 * 0.15 * dp + 0.25 * 0.10 * 0.03 + 0.05 * 0.10 * 0.025)
    rows = []
    for key in tab.index:
        item, L = key.split("@")[0], float(key.split("@")[1])
        if item.startswith("P7"):
            k = 2 if "2x" in item else 3
            # approximate: 60% k x EQ_G + 40% k x BOND, daily-reset financing at cash + spread, ER; sigma = realised
            E = med
            ar = 0.6 * (k * E["EQ_G"] - (k - 1) * (E["CASH"] + 0.5) - 0.9) + \
                0.4 * (k * E["BOND"] - (k - 1) * (E["CASH"] + 0.25) - 1.0)
            sd = rets[key].loc[W_COMMON[0]:W_COMMON[1]].std() * np.sqrt(12)
            rows.append({"key": key, "fwd_arith": ar, "fwd_geo": ar - 100 * sd ** 2 / 2, "fwd_sd": sd,
                         "fwd_geo_min": np.nan, "fwd_geo_max": np.nan, "fwd_note": "approx (US proxies)"})
            continue
        res = {s: fwd_item(S.loc[s], item, L, w_rp, cov, wht_fwd) for s in SOURCES}
        ar, geo, sd = fwd_item(pd.Series(med), item, L, w_rp, cov, wht_fwd)
        geos = [v[1] for v in res.values()]
        rows.append({"key": key, "fwd_arith": ar, "fwd_geo": geo, "fwd_sd": sd, "fwd_geo_min": min(geos),
                     "fwd_geo_max": max(geos), "fwd_sharpe": (ar - med["CASH"]) / (100 * sd) if sd > 0 else np.nan,
                     **{f"fwd_geo_{s.split()[0]}": v[1] for s, v in res.items()}})
    F = pd.DataFrame(rows).set_index("key")
    T = tab.join(F)
    T["hist_rank"] = T["cagr"].rank(ascending=False)
    T["fwd_rank"] = T["fwd_geo"].rank(ascending=False)
    T["eligible_sharpe"] = T["sharpe"] >= T["hurdle_p3_sharpe"] - 1e-12
    for tol in TOL:
        t = int(tol * 100)
        T[f"eligible_{t}"] = T["item"].isin(ANSWER_ITEMS) & (T[f"p_dd{t}_20y"] < 0.10) & T["eligible_sharpe"]
    T.to_csv(out / "final_table.csv")
    ans = []
    for tol in TOL:
        t = int(tol * 100)
        el = T[T[f"eligible_{t}"]].sort_values(["fwd_geo", "L"], ascending=[False, True])
        best = el.index[0] if len(el) else None
        best_lev = el[el.L > 1].index[0] if (el.L > 1).any() else None
        ans.append({"tolerance": t, "answer": best, "n_eligible": len(el), "best_levered_eligible": best_lev,
                    "eligible": ";".join(el.index)})
    pd.DataFrame(ans).to_csv(out / "answer.csv", index=False)
    print(pd.DataFrame(ans).to_string())


if __name__ == "__main__":
    main()
