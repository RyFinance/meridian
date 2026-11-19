"""Round 7 premarket: can ITB or the builders be entered in pre-market at a better price than the 09:30 MOO?

Run from repo root:  PYTHONPATH=. .venv/bin/python research/zb_itb/round7/premarket/premarket.py

Conventions
- Signal d = sign(ZB 08:00 ET close / prior 15:00 ET close), from verify/f3_canonical.build("ITB"). Known before 09:00.
- Baseline (MOO): buy at official 09:30 open, sell at the 10:30 close (last bar with label <= 10:29). Costs 2 bp/side.
- Only a bar with volume > 0 counts as a real print. Yahoo prepost bars with volume 0 are flat fill-ins and are ignored.
- Price known at minute T = close of the last real print with timestamp < T.
  - 1m vault bars: a bar labeled m is known at m, so close_known_at = m.
  - 5m yfinance bars: a bar labeled m covers [m, m+5), so its close is known at m+4 (usable from m+5).
- Limit rule: at minute To, L = last print before To * (1 + 5 bp). Filled at the first real bar in [To, 09:29] whose
  low <= L. Fill price = bar open if open <= L, else L. No fill -> MOO. The rule's improvement vs MOO per trade is
  fill * d * ln(P930 / F) minus fill * (c_pm - 2 bp), where c_pm is the all-in pre-market entry cost per side.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/zb_itb/verify")
import f3_canonical as f3  # noqa: E402

V = "research/zb_itb/verify/vault/"
YF = "research/zb_itb/verify/yf_cache/"
OUT = Path("research/zb_itb/round7/premarket")
DATA = OUT / "data"
ET = "America/New_York"
DEV_END = pd.Timestamp("2025-06-30")
EXIT_M, LAST_M, OPEN_M = 629, 569, 570  # exit label 10:29 (close 10:30); last pre-mkt minute 09:29; open 09:30
ENTRY_T = {"0915": 555, "0916": 556, "0920": 560, "0925": 565}  # buy at last print before this minute
LIM_T = {"0915": 555, "0920": 560, "0925": 565}  # limit placed at this minute
LIM_OFF = 0.0005
COSTS_BP = [2, 5, 10, 15, 20]  # all-in pre-market entry cost per side (bp)

sig = f3.build("ITB")
D_FULL = sig["d"]
D_LAG = D_FULL.shift(1)  # placebo: yesterday's signal


def vault_days(sym):
    fs = [V + f"{sym}_1m_{y}.parquet" for y in (2024, 2025, 2026)]
    x = pd.concat([pd.read_parquet(f) for f in fs])
    x.index = pd.to_datetime(x["ts"]).dt.tz_localize("UTC").dt.tz_convert(ET)
    x = x[~x.index.duplicated()].sort_index()
    x = x[x["volume"] > 0].rename(columns={"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"})
    x["date"] = x.index.tz_localize(None).normalize()
    x["m_o"] = x.index.hour * 60 + x.index.minute
    x["m_c"] = x["m_o"]
    for dt, g in x.groupby("date"):
        yield dt, g[["m_o", "m_c", "o", "l", "c", "v"]], np.nan


def yf_days(sym):
    x = pd.read_parquet(DATA / f"{sym}_5m_pp.parquet")
    x.index = x.index.tz_convert(ET)
    x = x[x["Volume"] > 0].rename(columns={"Open": "o", "High": "h", "Low": "l", "Close": "c", "Volume": "v"})
    x["date"] = x.index.tz_localize(None).normalize()
    x["m_o"] = x.index.hour * 60 + x.index.minute
    x["m_c"] = x["m_o"] + 4
    d1 = pd.read_parquet(YF + f"{sym}_1d.parquet")
    d1.index = pd.to_datetime(d1.index)
    d1.index = d1.index.tz_localize(None) if d1.index.tz is None else d1.index.tz_convert(ET).tz_localize(None)
    for dt, g in x.groupby("date"):
        p930 = d1.Open.get(dt, np.nan)  # official daily open = MOO price
        yield dt, g[["m_o", "m_c", "o", "l", "c", "v"]], p930


def engine(b, p930, sym, dt, d):
    grid = np.arange(240, EXIT_M + 1)
    cl = pd.Series(b["c"].values, index=b["m_c"].values)
    cl = cl[~cl.index.duplicated(keep="last")].reindex(grid)
    pf = cl.ffill()  # last real print at or before minute m (known at m)
    rm = pd.Series(np.where(cl.notna(), grid, np.nan), index=grid).ffill()  # last real-print minute
    if np.isnan(p930) and (b["m_o"] == OPEN_M).any():
        p930 = b.loc[b["m_o"] == OPEN_M, "o"].iloc[0]
    row = dict(sym=sym, date=pd.Timestamp(dt), d=d, P930=p930)
    row["exit"] = pf.loc[EXIT_M]
    row["pm_last"] = pf.loc[LAST_M]
    row["gap_bp"] = 1e4 * np.log(row["pm_last"] / p930)
    w = b[(b["m_o"] >= 540) & (b["m_o"] <= LAST_M)]
    row["n_0900"] = len(w)
    row["vol_0900"] = w["v"].sum()
    row["vol_0915"] = b[(b["m_o"] >= 555) & (b["m_o"] <= LAST_M)]["v"].sum()
    for k, T in ENTRY_T.items():
        P = pf.loc[T - 1]
        lm = rm.loc[T - 1]
        row[f"pm{k}"] = P
        row[f"age{k}"] = (T - 1) - lm if not np.isnan(lm) else np.nan
        row[f"imp{k}"] = d * np.log(p930 / P) if not np.isnan(P) else np.nan
    for k, T in LIM_T.items():
        P = pf.loc[T - 1]
        L = P * (1 + LIM_OFF) if not np.isnan(P) else np.nan
        w2 = b[(b["m_o"] >= T) & (b["m_o"] <= LAST_M)]
        hit = w2[w2["l"] <= L] if not np.isnan(L) else w2.iloc[0:0]
        if hit.empty:
            fill, F, imp = 0, np.nan, 0.0
        else:
            r = hit.iloc[0]
            F = r["o"] if r["o"] <= L else L
            fill, imp = 1, d * np.log(p930 / F)
        row[f"fill{k}"], row[f"F{k}"], row[f"lim{k}"] = fill, F, imp
    return row


def run(sym, gen):
    rows = []
    sigd = D_FULL.dropna()
    sigd = sigd[sigd != 0]
    for dt, b, p930 in gen:
        if dt not in sigd.index:
            continue
        d = float(sigd.loc[dt])
        if np.isnan(p930) and not (b["m_o"] == OPEN_M).any():
            continue
        r = engine(b, p930, sym, dt, d)
        r["d_lag"] = float(D_LAG.loc[dt]) if dt in D_LAG.index and not np.isnan(D_LAG.loc[dt]) else np.nan
        rows.append(r)
    out = pd.DataFrame(rows).set_index("date")
    for k in ENTRY_T:  # placebo: lagged signal on the same entries
        out[f"lagimp{k}"] = out["d_lag"] * np.log(out["P930"] / out[f"pm{k}"])
    return out


def tstat(x):
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return n, np.nan, np.nan
    return n, x.mean(), x.mean() / x.std(ddof=1) * np.sqrt(n)


def main():
    sources = {}
    for s in ["DHI", "LEN", "PHM", "TOL", "KBH"]:
        sources[s] = run(s, vault_days(s))
    for s in ["ITB", "XHB"]:
        sources[s] = run(s, yf_days(s))
    sources["SPY"] = run("SPY", vault_days("SPY"))  # placebo
    for s, df in sources.items():
        df.to_csv(OUT / f"per_day_{s}.csv")
    B = pd.concat([sources[s] for s in ["DHI", "LEN", "PHM", "TOL", "KBH"]])
    sources["BUILDERS_pooled_trades"] = B

    print("=== Pre-market microstructure (09:00-09:29), shares per day ===")
    rows = []
    for s, df in sources.items():
        df = df.dropna(subset=["P930", "exit"])
        rows.append(dict(src=s, days=len(df), med_vol_0900_0929=df["vol_0900"].median(),
                         mean_vol_0900_0929=df["vol_0900"].mean(), med_prints_bars=df["n_0900"].median(),
                         med_vol_0915_0929=df["vol_0915"].median(), days_no_print_0900=(df["n_0900"] == 0).mean(),
                         med_abs_gap_bp=df["gap_bp"].abs().median(), mean_gap_bp=df["gap_bp"].mean(),
                         med_age_at_0925_min=df["age0925"].median()))
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    print("\n=== Entry at pre-market price vs 09:30 MOO (gross incremental bp per trade, positive = better) ===")
    rows = []
    for s, df in sources.items():
        for k in ENTRY_T:
            x = df.dropna(subset=[f"imp{k}"])
            for lab, msk in [("all", x.index.notna()), ("dev", x.index <= DEV_END), ("chk", x.index > DEV_END)]:
                n, m, t = tstat(x.loc[msk, f"imp{k}"] * 1e4)
                rows.append(dict(src=s, entry=k, win=lab, n=n, mean_bp=m, t=t))
    res = pd.DataFrame(rows)
    print(res.pivot_table(index=["src", "entry"], columns="win", values=["n", "mean_bp", "t"], aggfunc="first").round(2).to_string())

    print("\n=== Controls (all sample): flip (-d) and lagged-signal placebo, and SPY placebo (bp) ===")
    rows = []
    for s, df in sources.items():
        for k in ["0915", "0925"]:
            x = df.dropna(subset=[f"imp{k}"])
            rows.append(dict(src=s, entry=k, flip_bp=-x[f"imp{k}"].mean() * 1e4,
                             lagged_signal_bp=x[f"lagimp{k}"].mean() * 1e4))
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    print("\n=== Break-even all-in pre-market entry cost per side (bp), where mean net improvement = 0 ===")
    rows = []
    for s, df in sources.items():
        for k in ENTRY_T:
            x = df.dropna(subset=[f"imp{k}"])
            rows.append(dict(src=s, entry=k, breakeven_cost_bp=2 + x[f"imp{k}"].mean() * 1e4))
    print(pd.DataFrame(rows).round(2).pivot_table(index="src", columns="entry", values="breakeven_cost_bp").to_string())

    print("\n=== Limit rule (buy last print + 5 bp; MOO fallback). Net improvement vs MOO per trade (bp) ===")
    rows = []
    for s, df in sources.items():
        df = df.dropna(subset=["P930"])
        for k in LIM_T:
            fill = df[f"fill{k}"]
            g = df[f"lim{k}"] * 1e4  # gross improvement on fills (0 if no fill)
            for c in COSTS_BP:
                net = g - fill * (c - 2)
                for lab, msk in [("all", df.index.notna()), ("dev", df.index <= DEV_END), ("chk", df.index > DEV_END)]:
                    n, m, t = tstat(net[msk])
                    rows.append(dict(src=s, order=k, cost=c, win=lab, n=n, fill_rate=fill[msk].mean(),
                                     mean_net_bp=m, t=t, gross_per_fill_bp=g[msk][fill[msk] == 1].mean(),
                                     fill_px_vs_open_bp=(df.loc[msk & (fill == 1), "lim" + k] * 1e4).mean()))
    res = pd.DataFrame(rows)
    print(res[res.win == "all"].round(2).to_string(index=False))
    print("\n--- dev / chk for cost 2 and 10 bp ---")
    print(res[(res.win != "all") & res.cost.isin([2, 10])].round(2).to_string(index=False))

    print("\n=== Builders pooled, DAY level (equal-weight across the 5 names; t on days) ===")
    days = pd.concat(
        [sources[s].dropna(subset=["P930"]).assign(src=s) for s in ["DHI", "LEN", "PHM", "TOL", "KBH"]]
    )
    rows = []
    for k in ENTRY_T:
        day = days.groupby(level=0)[f"imp{k}"].mean() * 1e4
        n, m, t = tstat(day)
        rows.append(dict(entry=k, n_days=n, mean_bp=m, t=t))
    print(pd.DataFrame(rows).round(2).to_string(index=False))
    rows = []
    for k in LIM_T:
        for c in [2, 5, 10, 15]:
            per = days.assign(net=days[f"lim{k}"] * 1e4 - days[f"fill{k}"] * (c - 2)).groupby(level=0)["net"].mean()
            n, m, t = tstat(per)
            rows.append(dict(order=k, cost=c, n_days=n, mean_net_bp=m, t=t))
    print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
