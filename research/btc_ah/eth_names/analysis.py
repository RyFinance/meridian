"""ETH overnight move -> ETH-linked US stock intraday rules (v2, cleaned).

Signal (decision at 09:25 ET): m = ETH(09:25 ET bar open) / ETH(16:00 ET prev trading day bar open) - 1.
Entries/exits at the next bar's price. Costs: 3 bp/side, 10 bp/side if entry price < $5.
Data hygiene: yfinance 1d and 60m series are NOT mutually consistent for some names (different
split factors), so every stock rule uses ONE series. Days with a >30% move in a single leg are dropped
as data artifacts. BTCS daily is excluded (corrupt: 142 open->close moves >30%, closes to 2.1m).

Families:
  set1  daily open(09:30) -> close(16:00), full daily history, follow/fade sign(m), |m| >= k
  set2  60m 09:30 open -> 10:30 open (first-hour exit), 60m window, follow/fade sign(m), |m| >= k
  set3  residual gap on 60m: rs = 09:30 open / prev 16:00 close - 1; re = ETH(09:30)/ETH(prev 16:00) - 1;
        resid_N = rs - beta_N*re, beta_N = rolling cov/var over the PAST N 60m-days (shift(1)).
        Trade 10:30 open -> 16:00 close, follow/fade sign(resid).
  uncond long baselines per family.
Dev = first 60% of each name's calendar for that family, check = remainder.
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CUT = pd.Timestamp("2026-08-10")
TICKERS = ["BMNR", "SBET", "BTCS", "GAME", "BTBT", "ETHA", "ETHE", "FETH", "ETHU", "COIN"]  # ETHZ: no yfinance data
DAILY_EXCLUDE = {"BTCS"}
GLITCH = 0.30
KS = [0.0, 0.005, 0.01, 0.02]
NS = [60, 120]

# ---------- ETH 5m (ET naive), sealed at 16:00 ET 2026-08-10 ----------
eth_raw = pd.read_parquet(os.path.join(DATA, "eth_5m.parquet"))
eth_raw["ts_et"] = (eth_raw["ts_utc"].dt.tz_localize("UTC")
                    .dt.tz_convert("America/New_York").dt.tz_localize(None))
eth_raw = eth_raw[eth_raw["ts_et"].dt.normalize() <= CUT]  # SEALED filter
ETH = eth_raw.set_index("ts_et")["open"].sort_index()
ETH = ETH[~ETH.index.duplicated()]


def eth_px(ts):
    return ETH.reindex(pd.DatetimeIndex(ts)).values


def eth_frame(idx):
    """ETH-derived columns for trading days in idx (DatetimeIndex of midnights)."""
    prev = pd.Series(idx, index=idx).shift(1)
    e16p = eth_px(prev + pd.Timedelta(hours=16))
    e0925 = eth_px(idx + pd.Timedelta(hours=9, minutes=25))
    e0930 = eth_px(idx + pd.Timedelta(hours=9, minutes=30))
    return pd.DataFrame({"m": e0925 / e16p - 1, "re": e0930 / e16p - 1}, index=idx)


def build_daily(t):
    d = pd.read_parquet(os.path.join(DATA, f"{t}_1d.parquet"))
    d = d[d.index <= CUT]
    d.index = pd.DatetimeIndex(d.index).normalize()
    d = d[~d.index.duplicated()]
    out = pd.DataFrame({"open": d["open"], "close": d["close"]})
    out = out.join(eth_frame(out.index))
    out["ret_oc"] = out["close"] / out["open"] - 1
    out["rs"] = out["open"] / d["close"].shift(1).reindex(out.index) - 1
    out["glitch"] = (out["ret_oc"].abs() > GLITCH) | (out["rs"].abs() > GLITCH)
    return out


def build_60m(t):
    h = pd.read_parquet(os.path.join(DATA, f"{t}_60m.parquet"))
    h = h[h.index <= CUT]
    day = h.index.normalize()
    tm = h.index.strftime("%H:%M")
    def pick(col, hhmm):
        s = pd.Series(h[col].values[tm == hhmm], index=day[tm == hhmm])
        return s[~s.index.duplicated()]
    df = pd.DataFrame({"o930": pick("open", "09:30"), "b1030": pick("open", "10:30"),
                       "c1530": pick("close", "15:30")})
    df = df.join(eth_frame(df.index))
    prev_c = df["c1530"].shift(1)
    df["rs"] = df["o930"] / prev_c - 1
    df["ret_1h"] = df["b1030"] / df["o930"] - 1
    df["ret_rest"] = df["c1530"] / df["b1030"] - 1
    df["glitch_rs"] = df["rs"].abs() > GLITCH
    rs_clean = df["rs"].where(~df["glitch_rs"])
    for N in NS:
        x = df["re"].shift(1)
        y = rs_clean.shift(1)
        beta = y.rolling(N, min_periods=N).cov(x) / x.rolling(N, min_periods=N).var()
        df[f"resid{N}"] = rs_clean - beta * df["re"]
    return df


def cost_side(entry):
    return np.where(entry < 5.0, 0.0010, 0.0003)


def trades_for(family, name, cal, sig, entry, exit_, params, rule_fn):
    """cal: DataFrame index=dates. sig/entry/exit: arrays aligned to cal."""
    rows = []
    n = len(cal)
    split = cal.index[int(0.6 * n)]
    dev = np.asarray(cal.index < split)
    cs = cost_side(entry)
    ret = exit_ / entry - 1
    base_net = ret - 2 * cs
    rows.append(pd.DataFrame({"family": family, "name": name, "rule": "uncond", "param": 0.0,
                              "date": cal.index, "dev": dev, "gross": ret, "net": base_net,
                              "flip": np.nan}))
    sgn = np.sign(sig)
    valid = (sgn != 0) & ~np.isnan(sig)
    for p in params:
        mask = valid & (np.abs(sig) >= p) if rule_fn == "thr" else valid
        for side, label in [(1, "follow"), (-1, "fade")]:
            gross = side * sgn * ret
            net = gross - 2 * cs
            flip = -gross - 2 * cs
            part = pd.DataFrame({"family": family, "name": name, "rule": label, "param": p,
                                 "date": cal.index, "dev": dev, "gross": gross, "net": net,
                                 "flip": flip})
            rows.append(part[mask])
    return pd.concat(rows, ignore_index=True)


def main():
    all_trades, cal_info, dropped = [], [], []
    for t in TICKERS:
        # set1: daily open->close, full history
        if t not in DAILY_EXCLUDE:
            out = build_daily(t)
            bad = out["glitch"]
            dropped.append((t, "set1_daily", int(bad.sum())))
            c1 = out[out["m"].notna() & out["ret_oc"].notna() & ~bad]
            if len(c1):
                all_trades.append(trades_for("set1_daily_oc", t, c1, c1["m"].values,
                                             c1["open"].values, c1["close"].values, KS, "thr"))
                cal_info.append((t, "set1", len(c1), c1.index.min().date(), c1.index.max().date()))
        else:
            dropped.append((t, "set1_daily", "EXCLUDED"))
        # set2 / set3: 60m, one consistent series
        h = build_60m(t)
        dropped.append((t, "60m_rs_glitch", int(h["glitch_rs"].sum())))
        c2 = h[h["m"].notna() & h["o930"].notna() & h["b1030"].notna() & (h["ret_1h"].abs() <= GLITCH)]
        if len(c2):
            all_trades.append(trades_for("set2_1h_exit", t, c2, c2["m"].values,
                                         c2["o930"].values, c2["b1030"].values, KS, "thr"))
            cal_info.append((t, "set2", len(c2), c2.index.min().date(), c2.index.max().date()))
        for N in NS:
            c3 = h[h[f"resid{N}"].notna() & h["b1030"].notna() & h["c1530"].notna()
                   & (h["ret_rest"].abs() <= GLITCH)]
            if len(c3):
                all_trades.append(trades_for(f"set3_resid{N}", t, c3, c3[f"resid{N}"].values,
                                             c3["b1030"].values, c3["c1530"].values, [float(N)], "any"))
                cal_info.append((t, f"set3_N{N}", len(c3), c3.index.min().date(), c3.index.max().date()))

    tr = pd.concat(all_trades, ignore_index=True)
    tr["year"] = pd.DatetimeIndex(tr["date"]).year
    pooled = tr.copy()
    pooled["name"] = "ALL"
    tr = pd.concat([tr, pooled], ignore_index=True)
    tr.to_parquet(os.path.join(HERE, "trades.parquet"), index=False)

    print("DATA HYGIENE (name, series, dropped/flagged days):")
    print(pd.DataFrame(dropped, columns=["name", "check", "value"]).to_string(index=False)); print()
    ci = pd.DataFrame(cal_info, columns=["name", "family", "n_days", "first", "last"])
    print("CALENDARS"); print(ci.to_string(index=False)); print()

    def stats(s):
        n = len(s)
        if n < 2:
            return dict(n=n, mean=np.nan, t=np.nan, win=np.nan, avg_win=np.nan, avg_loss=np.nan)
        m = s.mean(); sd = s.std(ddof=1)
        return dict(n=n, mean=m, t=m / (sd / np.sqrt(n)) if sd > 0 else np.nan,
                    win=(s > 0).mean(), avg_win=s[s > 0].mean() if (s > 0).any() else np.nan,
                    avg_loss=s[s <= 0].mean() if (s <= 0).any() else np.nan)

    keys = ["family", "name", "rule", "param"]
    rows = []
    for k, g in tr.groupby(keys):
        rec = dict(zip(keys, k))
        for part, mask in [("dev", g["dev"]), ("chk", ~g["dev"])]:
            st = stats(g.loc[mask, "net"].dropna())
            for kk, vv in st.items():
                rec[f"{part}_{kk}"] = vv
            fl = g.loc[mask, "flip"].dropna()
            rec[f"{part}_flip_mean"] = fl.mean() if len(fl) else np.nan
            rec[f"{part}_flip_t"] = stats(fl)["t"] if len(fl) > 1 else np.nan
        rows.append(rec)
    V = pd.DataFrame(rows)
    V.to_csv(os.path.join(HERE, "variants.csv"), index=False)

    rules = V[V["rule"] != "uncond"]
    per_name = rules[rules["name"] != "ALL"]
    print(f"SEARCH UNIVERSE: {len(per_name)} name-level rule variants (uncond baselines and pooled excluded)")
    print(f"  by family: {per_name.groupby('family').size().to_dict()}")
    passd = per_name[(per_name.dev_n >= 30) & (per_name.dev_t > 2) & (per_name.dev_mean > 0)]
    print(f"  dev n>=30 & dev t>2 & dev mean>0: {len(passd)}; of those check mean>0: {(passd.chk_mean>0).sum()}, "
          f"check t>2: {(passd.chk_t>2).sum()}")
    print(f"  all variants: check mean>0 share {(per_name.chk_mean>0).mean():.2f}; "
          f"check t>2: {(per_name.chk_t>2).sum()}; check t<-2: {(per_name.chk_t<-2).sum()}")
    print()

    cols = ["family", "name", "rule", "param", "dev_n", "dev_mean", "dev_t", "dev_win",
            "dev_avg_win", "dev_avg_loss", "chk_n", "chk_mean", "chk_t", "chk_win",
            "chk_avg_win", "chk_avg_loss", "chk_flip_mean", "chk_flip_t"]
    top = passd.sort_values("dev_t", ascending=False).head(3)
    print("TOP 3 by dev t (dev n>=30, dev mean>0):")
    print(top[cols].round(4).to_string(index=False)); print()

    print("POOLED ALL (diagnostic, not in universe):")
    print(V[(V["name"] == "ALL")][cols].round(4).to_string(index=False)); print()

    print("UNCONDITIONAL long baselines:")
    u = V[V["rule"] == "uncond"][["family", "name", "dev_n", "dev_mean", "dev_t", "chk_n", "chk_mean", "chk_t"]]
    print(u.round(4).to_string(index=False)); print()

    for _, r in top.iterrows():
        g = tr[(tr.family == r.family) & (tr.name == r["name"]) & (tr.rule == r.rule) & (tr.param == r.param)]
        py = g.groupby("year")["net"].agg(["size", "mean"]).round(4)
        py["flip_mean"] = g.groupby("year")["flip"].mean().round(4)
        print(f"PER-YEAR {r.family} {r['name']} {r.rule} param={r.param}:")
        print(py.to_string()); print()


if __name__ == "__main__":
    main()
