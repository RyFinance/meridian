"""Daily-bar gap study: classic gap fill / fade grid, regime continuation test, leveraged ETFs.

Sealed holdout: every series is cut at 2026-08-10. Dev = dates <= 2022-06-30, check = 2022-07-01..2026-08-10.
Prices are dividend/split adjusted (raw OHLC * AdjClose/Close). Entry = the open (gap known at the open print).
Stop ordering: if stop and target are both touched inside the daily bar, STOP is assumed to hit first.
Costs: 2 bp per side (liquid ETF rule) = 4 bp round trip.
"""
import math
import numpy as np
import pandas as pd

C = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps/cache"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps"
END = pd.Timestamp("2026-08-10")
SPLIT = pd.Timestamp("2022-06-30")
RT = 0.0004  # round trip cost, 2 bp per side

VIX = pd.read_parquet(f"{C}/VIX_1d.parquet")
VIX.index = pd.to_datetime(VIX.index).tz_localize(None)
VIX = VIX[VIX.index <= END].Close


def load(sym):
    d = pd.read_parquet(f"{C}/{sym}_1d.parquet")
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d = d[d.index <= END].astype(float)
    f = d["Adj Close"] / d["Close"]
    o = pd.DataFrame({"O": d.Open * f, "H": d.High * f, "L": d.Low * f, "C": d.Close * f})
    o["PC"] = o.C.shift(1)
    o["gap"] = o.O / o.PC - 1
    o["roc"] = o.C / o.O - 1
    lr = np.log(o.C).diff()
    o["rv20"] = lr.rolling(20).std().shift(1) * np.sqrt(252)  # known at prior close
    o["vix"] = VIX.reindex(o.index).ffill().shift(1)            # prior close VIX
    return o.dropna(subset=["PC", "vix", "rv20"])


def sim(o, p, tgt_kind, tgt, stp):
    """p: +1 long / -1 short array. tgt_kind 'fill' -> prior close; 'pct' -> open*(1+p*tgt).
    stp: stop fraction from open (None = no stop). Worst case: stop before target."""
    O, H, L, C_, PC = o.O.values, o.H.values, o.L.values, o.C.values, o.PC.values
    T = PC.copy() if tgt_kind == "fill" else O * (1 + p * tgt)
    lng = p > 0
    if stp is None:
        S = np.where(lng, -np.inf, np.inf)
    else:
        S = O * (1 - p * stp)
    hs = np.where(lng, L <= S, H >= S)
    ht = np.where(lng, H >= T, L <= T)
    X = np.where(hs, S, np.where(ht, T, C_))
    return p * (X / O - 1) - RT


def flip_gross(o, p, tgt_kind, tgt, stp):
    return sim(o, p, tgt_kind, tgt, stp)  # costs included; flip uses same function with mirrored p


def st(net, dates):
    net = np.asarray(net, float)
    n = len(net)
    if n < 2:
        return dict(n=n, win=np.nan, mean_bp=np.nan, t=np.nan, avgW=np.nan, avgL=np.nan, yr_pos=np.nan, yr_med_bp=np.nan)
    m = net.mean()
    sd = net.std(ddof=1)
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    w = net > 0
    yr = pd.Series(net).groupby(np.asarray(dates.year)).mean()
    return dict(n=n, win=w.mean(), mean_bp=m * 1e4, t=t,
                avgW=net[w].mean() * 1e4 if w.any() else np.nan,
                avgL=net[~w].mean() * 1e4 if (~w).any() else np.nan,
                yr_pos=(yr > 0).mean(), yr_med_bp=yr.median() * 1e4)


BUCKETS = [(0.0025, 0.005), (0.005, 0.01), (0.01, 0.015)]
TARGETS = [("fill", None), ("pct", 0.001), ("pct", 0.0025), ("pct", 0.005)]
STOPS = [0.005, 0.01, 0.015, None]
TLAB = {("fill", None): "fill_prevclose", ("pct", 0.001): "tgt0.10%",
        ("pct", 0.0025): "tgt0.25%", ("pct", 0.005): "tgt0.50%"}


def fade_grid(sym, o, rows):
    """Fade the gap: long gap-down, short gap-up. Also records the flipped (trade with the gap) control."""
    ag = o.gap.abs()
    for dname, dsign in [("up", 1), ("down", -1)]:
        for lo, hi in BUCKETS:
            m = (np.sign(o.gap) == dsign) & (ag >= lo) & (ag < hi if hi < 0.015 else ag <= hi)
            sub = o[m]
            if len(sub) < 30:
                continue
            p_fade = np.where(sub.gap.values > 0, -1, 1)  # fade direction
            p_flip = -p_fade
            fill_prob = np.where(sub.gap.values > 0, sub.L.values <= sub.PC.values, sub.H.values >= sub.PC.values)
            for tk, tg in TARGETS:
                for stp in STOPS:
                    net = sim(sub, p_fade, tk, tg, stp)
                    if tk == "fill":
                        # mirrored distance: trade with the gap, target = |gap| away from the open
                        flip = sim(sub, p_flip, "pct", np.abs(sub.gap.values), stp)
                    else:
                        flip = sim(sub, p_flip, tk, tg, stp)
                    s = st(net, sub.index)
                    fs = st(flip, sub.index) if flip is not None else {}
                    rows.append(dict(sym=sym, gap_dir=dname, gap_bin=f"{lo*100:.2f}-{hi*100:.2f}%",
                                     target=TLAB[(tk, tg)], stop=("none" if stp is None else f"{stp*100:.1f}%"),
                                     fill_prob=fill_prob.mean(),
                                     dev_n=None, **{f"all_{k}": v for k, v in s.items()},
                                     flip_mean_bp=fs.get("mean_bp", np.nan), flip_t=fs.get("t", np.nan),
                                     net_dates_min=str(sub.index.min().date()),
                                     _net=net, _dates=sub.index, _flip=flip))
    return rows


def split_stats(r):
    """Attach dev and check stats to a row using its stored net array and dates."""
    out = {}
    dates = r.pop("_dates")
    net = r.pop("_net")
    flip = r.pop("_flip")
    dev = dates <= SPLIT
    chk = dates > SPLIT
    for tag, mask in [("dev", dev), ("chk", chk)]:
        s = st(net[mask], dates[mask])
        out.update({f"{tag}_{k}": v for k, v in s.items()})
        if flip is not None:
            fs = st(flip[mask], dates[mask])
            out[f"{tag}_flip_mean_bp"] = fs["mean_bp"]
            out[f"{tag}_flip_t"] = fs["t"]
    r.update(out)
    return r


def main():
    rows = []
    for sym in ["SPY", "QQQ", "IWM"]:
        o = load(sym)
        print(sym, "days", len(o), o.index.min().date(), o.index.max().date())
        fade_grid(sym, o, rows)
    res = pd.DataFrame([split_stats(r) for r in rows])
    res.to_csv(f"{OUT}/fade_grid_index.csv", index=False)
    print("FADE VARIANTS (index):", len(res))

    # fill probability by bucket (no stop, dev/check split)
    fp = []
    for sym in ["SPY", "QQQ", "IWM"]:
        o = load(sym)
        for lo, hi in BUCKETS:
            for dname, dsign in [("up", 1), ("down", -1)]:
                m = (np.sign(o.gap) == dsign) & (o.gap.abs() >= lo) & (o.gap.abs() < hi)
                sub = o[m]
                if len(sub) == 0:
                    continue
                f = np.where(sub.gap.values > 0, sub.L.values <= sub.PC.values, sub.H.values >= sub.PC.values)
                fp.append(dict(sym=sym, dir=dname, bin=f"{lo*100:.2f}-{hi*100:.2f}%", n=len(sub),
                               fill_all=f.mean(), fill_dev=f[sub.index <= SPLIT].mean(),
                               fill_chk=f[sub.index > SPLIT].mean()))
    pd.DataFrame(fp).to_csv(f"{OUT}/fill_probability.csv", index=False)
    print(pd.DataFrame(fp).round(3).to_string())

    # (2) regime: gap follow-through, gross open->close in the gap direction (cost-free) and net of 4bp
    reg = []
    for sym in ["SPY", "QQQ", "IWM"]:
        o = load(sym)
        for lo, hi in BUCKETS:
            for dname, dsign in [("up", 1), ("down", -1)]:
                m = (np.sign(o.gap) == dsign) & (o.gap.abs() >= lo) & (o.gap.abs() < hi)
                base = o[m]
                if len(base) < 30:
                    continue
                for rname, rcol in [("vix", "vix"), ("rv20", "rv20")]:
                    if rname == "vix":
                        cuts = [(-1, 15), (15, 25), (25, 1e9)]
                        labs = ["VIX<15", "VIX15-25", "VIX>=25"]
                    else:
                        q1, q2 = base.rv20[base.index <= SPLIT].quantile([1 / 3, 2 / 3])  # tercile cuts from DEV only
                        cuts = [(-1, q1), (q1, q2), (q2, 1e9)]
                        labs = ["rv20-low", "rv20-mid", "rv20-high"]
                    for (a, b), lab in zip(cuts, labs):
                        sub = base[(base[rcol] >= a) & (base[rcol] < b)]
                        if len(sub) < 20:
                            continue
                        cont = np.sign(sub.gap.values) * sub.roc.values  # gross follow-through
                        s_cont = st(cont - RT, sub.index)
                        s_rev = st(-cont - RT, sub.index)
                        reg.append(dict(sym=sym, dir=dname, gap_bin=f"{lo*100:.2f}-{hi*100:.2f}%", regime=lab,
                                        n=len(sub), cont_gross_bp=cont.mean() * 1e4,
                                        cont_net_t=s_cont["t"], cont_net_bp=s_cont["mean_bp"],
                                        rev_net_bp=s_rev["mean_bp"], rev_net_t=s_rev["t"],
                                        dev_cont_bp=st(cont[sub.index <= SPLIT] - RT, sub.index[sub.index <= SPLIT])["mean_bp"],
                                        chk_cont_bp=st(cont[sub.index > SPLIT] - RT, sub.index[sub.index > SPLIT])["mean_bp"]))
    regdf = pd.DataFrame(reg)
    regdf.to_csv(f"{OUT}/regime_continuation.csv", index=False)
    print("REGIME CELLS:", len(regdf))
    print(regdf.round(2).to_string())

    # unconditional open->close drift baseline (long and short, net of 4bp), to separate decay from gap effects
    base = []
    for sym in ["SPY", "QQQ", "IWM", "TQQQ", "SQQQ", "SOXL", "UVXY"]:
        o = load(sym)
        for pn, p in [("long", 1), ("short", -1)]:
            s_ = st(p * o.roc.values - RT, o.index)
            base.append(dict(sym=sym, side=pn, n=s_["n"], mean_bp=s_["mean_bp"], t=s_["t"], win=s_["win"]))
    pd.DataFrame(base).to_csv(f"{OUT}/unconditional_oc_baseline.csv", index=False)
    print(pd.DataFrame(base).round(3).to_string())

    # (4) leveraged ETFs: own-gap fade grid + tracking vs underlying gap
    lev_rows = []
    pairs = {"TQQQ": ("QQQ", 3), "SQQQ": ("QQQ", -3), "SOXL": ("SOXX", 3), "UVXY": ("VIX", None)}
    track = []
    for sym, (und, k) in pairs.items():
        o = load(sym)
        if und == "VIX":
            # UVXY tracks VIX futures, not spot; use the VIX spot gap only as a rough proxy
            uo = None
        else:
            uo = load(und)
            both = o.join(uo[["gap"]].rename(columns={"gap": "ugap"}), how="inner")
            if k is not None:
                e = both.gap - k * both.ugap
                track.append(dict(sym=sym, und=und, k=k, n=len(both), mean_track_bp=e.mean() * 1e4,
                                  mad_track_bp=e.abs().mean() * 1e4,
                                  ratio_med=(both.gap / both.ugap)[both.ugap.abs() > 0.003].median()))
        fade_grid(sym, o, lev_rows)
    lev = pd.DataFrame([split_stats(r) for r in lev_rows])
    lev.to_csv(f"{OUT}/fade_grid_leveraged.csv", index=False)
    pd.DataFrame(track).to_csv(f"{OUT}/leveraged_tracking.csv", index=False)
    print("LEVERAGED FADE VARIANTS:", len(lev))
    print(pd.DataFrame(track).round(3).to_string())


if __name__ == "__main__":
    main()
