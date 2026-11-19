"""Live-era check (FRAMEWORK §7): actual ETFs since inception in CAD vs simulated sleeves/items. Descriptive only."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle8.engine import metrics as MX

REPO = Path(__file__).resolve().parents[2]
VIEW = REPO / "data/cycle8/snapshot_store/versions/cycle8_v1/view"
OUT = REPO / "reports/cycle8_max_return/out"

# ETF -> simulated comparator (sleeve column or item key)
PAIRS = {
    "XEQT.TO": "P1u@1.0", "VEQT.TO": "P1u@1.0", "ZEQT.TO": "P1u@1.0",
    "XGRO.TO": "P2@1.0", "VGRO.TO": "P2@1.0", "VBAL.TO": "P3@1.0", "XBAL.TO": "P3@1.0",
    "ZAG.TO": "BOND", "XBB.TO": "BOND", "VAB.TO": "BOND", "CGL-C.TO": "GOLD", "ZGLD.TO": "GOLD", "GLD": "GOLD",
    "DBMF": "TREND", "KMLM": "TREND", "CTA": "TREND", "AQMIX": "TREND",
    "NTSX": "P6b@1.0", "RSSB": "P6b@1.0", "RSST": None, "GDE": None, "RGBM.TO": None,
    "SSO": None, "UPRO": None, "UBT": None, "TMF": None, "SPY": None, "VT": "P1u@1.0", "TLT": None, "IEF": None,
    "USSL.TO": None, "HEQL.TO": None,
}


def main():
    M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
    R = pd.read_parquet(OUT / "item_returns_monthly.parquet")
    px = pd.read_parquet(VIEW / "proc/etf_monthly_adj.parquet")
    inv = pd.read_csv(VIEW / "proc/etf_inventory.csv").set_index("ticker")
    fx = pd.read_parquet(VIEW / "proc/fx_monthly.parquet")["USDCAD"]
    fx.index = fx.index.to_period("M").to_timestamp("M")
    px.index = pd.DatetimeIndex(px.index).to_period("M").to_timestamp("M")
    fxr = fx / fx.shift(1) - 1
    rows = []
    for t, comp in PAIRS.items():
        if t not in px:
            continue
        r = px[t].pct_change()
        r = r[px[t].shift(1).notna()].dropna()
        # drop the first (partial) month after inception
        r = r.iloc[1:]
        if t == "XGRO.TO" or t == "XBAL.TO":
            r = r.loc["2018-09":]           # mandate change 2018-08
        if inv.loc[t, "currency"] == "USD":
            r = (1 + r) * (1 + fxr.reindex(r.index)) - 1
        r = r.dropna()
        if len(r) < 12:
            continue
        s = MX.summary(r, M["CASH"], sharpe_ci=False)
        row = {"ticker": t, "ccy": inv.loc[t, "currency"], "er_yahoo": inv.loc[t, "er_yahoo"], "from": s["start"],
               "to": s["end"], "months": s["months"], "cagr_cad": s["cagr"], "vol": s["vol"],
               "sharpe": s["sharpe"], "maxdd": s["maxdd"], "comparator": comp}
        if comp is not None:
            sim = (R[comp] if comp in R else M[comp]).reindex(r.index)
            ok = sim.notna()
            if ok.sum() >= 12:
                a, b = r[ok], sim[ok]
                n = ok.sum() / 12
                row.update({"sim_cagr_overlap": (1 + b).prod() ** (1 / n) - 1,
                            "etf_cagr_overlap": (1 + a).prod() ** (1 / n) - 1,
                            "corr": a.corr(b), "te": (a - b).std() * np.sqrt(12)})
                row["gap_etf_minus_sim"] = row["etf_cagr_overlap"] - row["sim_cagr_overlap"]
        rows.append(row)
    live = pd.DataFrame(rows).set_index("ticker")
    live.to_csv(OUT / "live_era.csv")

    # daily-reset LETF simulation vs actual (USD, monthly)
    sim = pd.read_parquet(OUT / "p7_letf_daily_sim.parquet")
    simm = (1 + sim).groupby(sim.index.to_period("M")).prod().sub(1).to_timestamp("M")
    lrows = []
    for t, col in {"SSO": "P7-2x_eq_letf", "UBT": "P7-2x_tsy_letf", "UPRO": "P7-3x_eq_letf",
                   "TMF": "P7-3x_tsy_letf"}.items():
        a = px[t].pct_change().dropna().iloc[1:]
        b = simm[col].reindex(a.index)
        ok = b.notna()
        a, b = a[ok], b[ok]
        n = len(a) / 12
        lrows.append({"etf": t, "from": f"{a.index[0]:%Y-%m}", "to": f"{a.index[-1]:%Y-%m}",
                      "etf_cagr_usd": (1 + a).prod() ** (1 / n) - 1, "sim_cagr_usd": (1 + b).prod() ** (1 / n) - 1,
                      "corr": a.corr(b), "te": (a - b).std() * np.sqrt(12)})
    pd.DataFrame(lrows).to_csv(OUT / "letf_validation.csv", index=False)
    print(live.round(3).to_string())
    print(pd.DataFrame(lrows).round(4).to_string())


if __name__ == "__main__":
    main()
