"""Wikipedia attention tests: H1 spike event study, H2 weekly cross-sectional sort, H3 market attention -> SPY.

Timing: pageviews for calendar day d are complete after UTC midnight d+1 (before next open),
so a signal dated d is traded at the open of the first trading day > d (open-to-open holds).
Costs: 5 bp per side (every unit of weight traded pays 5 bp).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from universe import UNIVERSE

BASE = Path(__file__).resolve().parent
CACHE = BASE / "cache"
COST = 0.0005
DEV = (pd.Timestamp("2019-01-01"), pd.Timestamp("2022-12-31"))
CHK = (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-10-16"))
rng = np.random.default_rng(7)

op = pd.read_pickle(CACHE / "open.pkl")
tdays = op.index
spy_o = op["SPY"]

# ---------- pageviews ----------
cols = {}
for t in UNIVERSE:
    p = CACHE / "pv" / f"{t}.json"
    if not p.exists():
        continue
    d = json.loads(p.read_text())["views"]
    s = pd.Series(d, dtype=float)
    s.index = pd.to_datetime(s.index, format="%Y%m%d")
    cols[t] = s
cal = pd.date_range("2019-01-01", "2026-10-16", freq="D")
views = pd.DataFrame(cols).reindex(cal)
cov = views.notna().mean()
views = views[cov[cov >= 0.95].index]
TK = [t for t in views.columns if t in op.columns and op[t].notna().sum() > 1000]
views = views[TK]
lv = np.log1p(views)
print(f"names with pageviews+prices: {len(TK)} (of {len(UNIVERSE)})")

# ---------- helpers ----------
def next_td_pos(d):
    """Position in tdays of first trading day strictly after date d."""
    return np.searchsorted(tdays.values, np.datetime64(d), side="right")


def tstat(x, lag):
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 30:
        return dict(n=n, mean=np.nan, t=np.nan)
    fit = sm.OLS(x, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    return dict(n=n, mean=float(x.mean()), t=float(fit.tvalues[0]))


def summarize(df, col, lag):
    out = {}
    for name, (a, b) in {"dev": DEV, "chk": CHK}.items():
        sub = df[(df.date >= a) & (df.date <= b)]
        out[name] = tstat(sub[col].values, lag)
    return out


def per_year(df, col):
    g = df.assign(y=df.date.dt.year).groupby("y")[col]
    return {int(y): round(float(v.mean()) * 1e4, 1) for y, v in g if len(v) >= 5}


# ---------- H1: abnormal-attention spike event study ----------
def spike_events(z, thr, gap_days=10):
    ev = []
    for t in z.columns:
        zs = z[t].dropna()
        hits = zs[zs > thr].index
        last = None
        for d in hits:
            if last is not None and (d - last).days < gap_days:
                continue
            last = d
            ev.append((t, d))
    return ev


def h1(thr, h, z):
    ev = spike_events(z, thr)
    rows = []
    for t, d in ev:
        p = next_td_pos(d)
        if p + h >= len(tdays) or d < DEV[0]:
            continue
        e0, e1 = tdays[p], tdays[p + h]
        s0, s1 = op[t].iloc[p], op[t].iloc[p + h]
        m0, m1 = spy_o.iloc[p], spy_o.iloc[p + h]
        if np.isnan([s0, s1, m0, m1]).any():
            continue
        ar = (s1 / s0 - 1) - (m1 / m0 - 1)
        rows.append((d, t, ar))
    df = pd.DataFrame(rows, columns=["date", "tk", "ar"]).sort_values("date")
    df["rev"] = -df.ar - 2 * COST    # reversal strategy: short spike name, cover after h days
    df["cont"] = df.ar - 2 * COST    # flip control: long spike name (continuation)
    return df


def placebo_h1(thr, h, z_orig, draws=20):
    """Circular shift each name's attention series by a random offset (breaks link to returns)."""
    means = []
    for _ in range(draws):
        zs = pd.DataFrame(index=z_orig.index)
        for t in z_orig.columns:
            k = int(rng.integers(60, 900))
            zs[t] = z_orig[t].shift(k)
        d = h1(thr, h, zs)
        means.append(d.rev.mean() * 1e4 if len(d) else np.nan)
    means = np.array(means)
    return dict(median_bp=round(float(np.nanmedian(means)), 1),
                q95_bp=round(float(np.nanpercentile(means, 95)), 1))


base = lv.shift(1).rolling(60, min_periods=45)
med = base.median()
sd = base.std().clip(lower=0.05)
Z = (lv - med) / sd

results = {}
for thr in [3.0, 2.5]:
    for h in [1, 5, 10]:
        df = h1(thr, h, Z)
        key = f"H1 z>{thr} h={h}d"
        res = {
            "events": len(df),
            "rev_net": summarize(df, "rev", lag=max(h, 1)),
            "flip_cont_net": summarize(df, "cont", lag=max(h, 1)),
            "gross_ar": summarize(df, "ar", lag=max(h, 1)),
            "rev_per_year_bp": per_year(df, "rev"),
        }
        if thr == 3.0 and h == 5:
            res["placebo_rev_bp"] = placebo_h1(thr, h, Z)
            df.to_csv(BASE / "h1_events_z3_h5.csv", index=False)
        results[key] = res

# ---------- H2: weekly cross-sectional attention-change sort ----------
fridays = pd.date_range("2019-01-04", "2026-10-16", freq="W-FRI")
m = {}
for name, short, long_ in [("1w_vs_4w", 7, 28), ("2w_vs_8w", 14, 56)]:
    recent = lv.rolling(short).mean()
    prior = lv.shift(short).rolling(long_).mean()
    m[name] = recent - prior


def h2(dA):
    recs = []
    for i, F in enumerate(fridays[:-1]):
        if F not in dA.index:
            continue
        p = next_td_pos(F)
        p2 = next_td_pos(fridays[i + 1])
        if p2 >= len(tdays):
            break
        ret = op[TK].iloc[p2] / op[TK].iloc[p] - 1
        sig = dA.loc[F, TK]
        ok = ret.notna() & sig.notna()
        if ok.sum() < 50:
            continue
        s = sig[ok].rank(pct=True)
        r = ret[ok]
        w = pd.Series(0.0, index=s.index)
        w[s <= 0.2] = 1 / (s <= 0.2).sum()
        w[s >= 0.8] = -1 / (s >= 0.8).sum()
        recs.append((F, float((w * r).sum()), w))
    dates = [r[0] for r in recs]
    gross = np.array([r[1] for r in recs])
    turn = [0.0] + [float((recs[k].__getitem__(2).reindex(TK).fillna(0)
                           - recs[k - 1][2].reindex(TK).fillna(0)).abs().sum())
                    for k in range(1, len(recs))]
    df = pd.DataFrame({"date": dates, "gross": gross, "turn": turn})
    df["net"] = df.gross - COST * df.turn      # long low attention, short high attention
    df["flip"] = -df.gross - COST * df.turn    # flip control: long high, short low
    return df


for name in m:
    df = h2(m[name])
    key = f"H2 weekly {name}"
    results[key] = {
        "weeks": len(df),
        "net_long_low": summarize(df, "net", lag=4),
        "flip_long_high": summarize(df, "flip", lag=4),
        "avg_turnover": round(float(df.turn.mean()), 2),
        "net_per_year_bp": per_year(df, "net"),
    }

# ---------- H3: aggregate (universe-average) weekly abnormal attention -> next-week SPY ----------
wa = lv.rolling(7).mean() - lv.shift(7).rolling(60).median()
M = wa.mean(axis=1)
Mz = (M - M.rolling(52, min_periods=26).mean().shift(1)) / M.rolling(52, min_periods=26).std().shift(1)
rows = []
for i, F in enumerate(fridays[:-1]):
    if F not in Mz.index or np.isnan(Mz.loc[F]):
        continue
    p = next_td_pos(F)
    p2 = next_td_pos(fridays[i + 1])
    if p2 >= len(tdays):
        break
    rows.append((F, Mz.loc[F], float(spy_o.iloc[p2] / spy_o.iloc[p] - 1)))
h3 = pd.DataFrame(rows, columns=["date", "Mz", "spy"])
h3["pos"] = np.where(h3.Mz > 0, 1.0, -1.0)           # continuation: long after high attention
h3["turn"] = h3.pos.diff().abs().fillna(1.0)
h3["strat"] = h3.pos * h3.spy - COST * h3.turn
h3["flip"] = -h3.pos * h3.spy - COST * h3.turn
slope = {}
for name, (a, b) in {"dev": DEV, "chk": CHK}.items():
    sub = h3[(h3.date >= a) & (h3.date <= b)]
    fit = sm.OLS(sub.spy.values, sm.add_constant(sub.Mz.values)).fit(
        cov_type="HAC", cov_kwds={"maxlags": 4})
    slope[name] = dict(n=len(sub), beta_bp_per_sd=round(float(fit.params[1]) * 1e4, 1),
                       t_nw=round(float(fit.tvalues[1]), 2))
results["H3 SPY next-week on Mz (regression)"] = slope
results["H3 strategy long if Mz>0 (continuation)"] = {
    "net": summarize(h3, "strat", lag=4), "flip": summarize(h3, "flip", lag=4),
    "weeks": len(h3)}

out = BASE / "results.json"
out.write_text(json.dumps(results, indent=1, default=float))


def fmt(s):
    return "  ".join(
        f"{k}: n={v['n']} mean={v['mean']*1e4:.1f}bp t={v['t']:.2f}"
        if v["mean"] == v["mean"] else f"{k}: n={v['n']} NA"
        for k, v in s.items() if isinstance(v, dict) and "n" in v and "mean" in v
    )


for k, v in results.items():
    print("\n==", k)
    for kk, vv in v.items():
        if isinstance(vv, dict) and "dev" in vv and "mean" in vv.get("dev", {}):
            print(f"  {kk}: dev {vv['dev']['mean']*1e4:.1f}bp t={vv['dev']['t']:.2f} n={vv['dev']['n']} | "
                  f"chk {vv['chk']['mean']*1e4:.1f}bp t={vv['chk']['t']:.2f} n={vv['chk']['n']}")
        elif isinstance(vv, dict) and "dev" in vv and isinstance(vv["dev"], dict) and "t" in vv["dev"]:
            print(f"  {kk}: dev {vv['dev']}  chk {vv['chk']}")
        else:
            print(f"  {kk}: {vv}")
