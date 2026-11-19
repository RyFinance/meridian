"""Cycle 9 item 1: apply the FRAMEWORK Part A inclusion rule mechanically and build the live panel.

Inputs (data/cycle9/live_trend): yahoo_raw/*.json, funds/<id>/{monthly.csv,meta.json}, facts/*.json,
classify_A.json, classify_B.json, verify_pools.json; US T-bill from the frozen cycle-8 snapshot.
Outputs (data/cycle9/live/): panel_monthly_total.csv, panel_monthly_excess.csv, daily_ew.csv, inclusion_table.csv.
No statistic is computed here (only returns from NAV/prices and membership decisions).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LT = ROOT / "data/cycle9/live_trend"
OUT = ROOT / "data/cycle9/live"
PROC8 = ROOT / "data/cycle8/snapshot_store/versions/cycle8_v1/view/proc"

# fund_id -> Yahoo share class (I6: longest monthly history; ties -> lowest fee). Declared in ADDENDUM_1.
YAHOO_CLASS = {
    "aqr_managed_futures_strategy": "AQMIX", "aqr_managed_futures_strategy_hv": "QMHIX",
    "american_beacon_ahl_managed_futures_strategy": "AHLIX", "amg_systematica_managed_futures_strategy": "SMFIX",
    "arrow_managed_futures_strategy": "MFTFX", "goldman_sachs_managed_futures_strategy": "GMSSX",
    "locorr_market_trend": "LOTIX", "pimco_trends_managed_futures_strategy": "PQTIX",
    "virtus_alphasimplex_managed_futures_strategy": "ASFYX", "winton_managed_futures_trend": "EVOIX",
    "guggenheim_managed_futures_strategy": "RYMFX", "credit_suisse_manteio_mast_managed_futures_strategy": "CSAIX",
    "abbey_capital_futures_strategy": "ABYIX", "campbell_systematic_macro": "EBSIX",
    "catalyst_millburn_hedge_strategy": "MBXIX", "catalyst_systematic_alpha": "ATRFX",
    "rational_dynamic_momentum_return_stacked_bal_macro": "RDMIX", "standpoint_multi_asset": "BLNDX",
    "wisdomtree_managed_futures": "WTMF", "first_trust_managed_futures": "FMF", "imgp_dbi_managed_futures": "DBMF",
    "kraneshares_mount_lucas_managed_futures": "KMLM", "simplify_managed_futures": "CTA",
    "blueprint_chesapeake_multi_asset_trend": "TFPN",
}
# I6 same-program duplicates: (dropped, kept) — same sponsor and program, keep the longer record.
SAME_PROGRAM = {"aqr_managed_futures_strategy_hv": "aqr_managed_futures_strategy"}


def yahoo_daily(sym: str) -> pd.Series:
    d = json.load(open(LT / "yahoo_raw" / f"{sym}.json"))["chart"]["result"][0]
    idx = pd.to_datetime(d["timestamp"], unit="s").normalize()
    adj = pd.Series(d["indicators"]["adjclose"][0]["adjclose"], index=idx, dtype=float)
    return adj[~adj.index.duplicated(keep="last")].dropna()


def yahoo_monthly(adj: pd.Series) -> pd.Series:
    me = adj.groupby(adj.index.to_period("M")).last()
    r = me.pct_change().iloc[1:]           # first return = first FULL month after the listing month
    r.index = r.index.to_timestamp("M")
    return r[r.index <= "2026-08-31"]      # 2026-09 incomplete


def pool_monthly(fid: str) -> pd.Series:
    m = pd.read_csv(LT / "funds" / fid / "monthly.csv")
    idx = pd.PeriodIndex(m["month"], freq="M").to_timestamp("M")
    r = pd.Series(m["ret"].values, index=idx, dtype=float)
    if r.isna().any() and "nav" in m and m["nav"].notna().any():
        nav = pd.Series(m["nav"].values, index=idx, dtype=float)
        r = r.fillna(nav.pct_change())
    return r.dropna()


def longest_consecutive(idx: pd.DatetimeIndex) -> int:
    p = idx.to_period("M").astype(int) if hasattr(idx.to_period("M"), "astype") else None
    per = np.array([x.ordinal for x in idx.to_period("M")])
    best = cur = 1
    for a, b in zip(per[:-1], per[1:]):
        cur = cur + 1 if b == a + 1 else 1
        best = max(best, cur)
    return best if len(per) else 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    A = {d["fund_id"]: d for d in json.load(open(LT / "classify_A.json"))["decisions"]}
    B = {d["fund_id"]: d for d in json.load(open(LT / "classify_B.json"))["decisions"]}
    V = {}
    if (LT / "verify_pools.json").exists():
        V = {d["id"]: d for d in json.load(open(LT / "verify_pools.json"))["checked"]}
    rf = pd.read_parquet(PROC8 / "rates_monthly.parquet")["rf_usd_ret"]
    rf.index = rf.index.to_period("M").to_timestamp("M")
    series, daily, rows = {}, {}, []
    cands = set(A) | set(B)
    for fid in sorted(cands):
        row = {"fund_id": fid, "A": A.get(fid, {}).get("passes_I2_I3"), "B": B.get(fid, {}).get("passes_I2_I3")}
        pool = (LT / "funds" / fid / "monthly.csv").exists()
        try:
            if pool:
                r = pool_monthly(fid)
                row["source"] = "pool (sponsor/Wayback)"
            elif fid in YAHOO_CLASS and (LT / "yahoo_raw" / f"{YAHOO_CLASS[fid]}.json").exists():
                adj = yahoo_daily(YAHOO_CLASS[fid])
                r = yahoo_monthly(adj)
                daily[fid] = adj.pct_change().dropna()
                row["source"] = f"Yahoo {YAHOO_CLASS[fid]}"
            else:
                r = pd.Series(dtype=float)
                row["source"] = "no free record"
        except Exception as e:  # unreadable record
            r = pd.Series(dtype=float)
            row["source"] = f"unreadable: {e}"
        row["first"] = f"{r.index[0]:%Y-%m}" if len(r) else ""
        row["last"] = f"{r.index[-1]:%Y-%m}" if len(r) else ""
        row["months"] = len(r)
        row["longest_consecutive"] = longest_consecutive(r.index) if len(r) else 0
        reasons = []
        if not len(r):
            reasons.append("I1: no free verifiable record")
        if not (row["A"] and row["B"]):
            reasons.append("I2/I3: " + ("both classifiers fail" if (row["A"] is False and row["B"] is False)
                                          else "classifiers disagree or missing"))
        if row["longest_consecutive"] < 36:
            reasons.append("I4: < 36 consecutive months")
        if fid in SAME_PROGRAM:
            reasons.append(f"I6: same program as {SAME_PROGRAM[fid]} (longer record kept)")
        if pool and fid in V and not V[fid].get("extraction_ok", False):
            reasons.append("verification failed")
        if pool and fid not in V:
            reasons.append("not verified")
        row["included"] = not reasons
        row["reasons"] = "; ".join(reasons)
        rows.append(row)
        if row["included"]:
            series[fid] = r
    tab = pd.DataFrame(rows).set_index("fund_id")
    tab.to_csv(OUT / "inclusion_table.csv")
    tot = pd.DataFrame(series).sort_index()
    tot.index.name = "month"
    ex = tot.sub(rf.reindex(tot.index), axis=0)
    tot.to_csv(OUT / "panel_monthly_total.csv")
    ex.to_csv(OUT / "panel_monthly_excess.csv")
    dd = pd.DataFrame({k: v for k, v in daily.items() if k in series})
    ew = pd.DataFrame({"ew_ret": dd.mean(1), "n": dd.notna().sum(1)}).dropna()
    ew.index.name = "date"
    ew.to_csv(OUT / "daily_ew.csv")
    print(tab[["source", "first", "last", "months", "A", "B", "included", "reasons"]].to_string())


if __name__ == "__main__":
    main()
