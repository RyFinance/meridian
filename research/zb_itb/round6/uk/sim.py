"""Rule grid on the frozen panel (panel.pkl from analysis.py). Dev selects; check reports."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent
src = (HERE / "analysis.py").read_text().split("def fname")[0]
ns = {"__file__": str(HERE / "analysis.py")}; exec(src, ns)
DEV, CHK, RT, STAMP, HB, PLACEBO, CONTROL, UK_SHARES = (ns[k] for k in ["DEV", "CHK", "RT", "STAMP", "HB", "PLACEBO", "CONTROL", "UK_SHARES"])
R = pd.read_pickle(HERE / "panel.pkl")
R = R[(R.date >= DEV[0]) & (R.date <= CHK[1])]
SIGS = ["ZB_LON", "ZN_LON", "ZB_US"]
EXS = {"x08": ("entry", "x08"), "x09": ("entry", "x09"), "x1630": ("entry", "x1630"), "x1d": ("d_open", "x1d")}
NAMES = HB + PLACEBO + CONTROL


def stat(x):
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return n, np.nan, np.nan
    return n, x.mean() * 1e4, x.mean() / x.std(ddof=1) * np.sqrt(n)


def legs(df, sig, ex, name):
    e_col, x_col = EXS[ex]
    s = df[(df.sym == name)].set_index("date")
    sg = s[f"sig_{sig}"]
    d = np.sign(sg).where(sg.notna() & (sg != 0))
    g = d * np.log(s[x_col] / s[e_col])
    g = g.where(d.notna() & s[x_col].notna() & s[e_col].notna())
    stamp = STAMP * (name in UK_SHARES)
    ls_net = g - RT - stamp * (d > 0)
    ls_nost = g - RT
    lo_net = (g - RT - stamp).where(d > 0)
    lo_nost = (g - RT).where(d > 0)
    flip_net = -g - RT - stamp * ((-d) > 0)
    return dict(d=d, gross=g, ls_net=ls_net, ls_nost=ls_nost, lo_net=lo_net, lo_nost=lo_nost, flip_net=flip_net)


rows = []
for sig in SIGS:
    for ex in EXS:
        per = {n: legs(R, sig, ex, n) for n in NAMES}
        basket = {}
        for k in ["gross", "ls_net", "ls_nost", "lo_net", "lo_nost", "flip_net"]:
            basket[k] = pd.DataFrame({n: per[n][k] for n in HB}).mean(axis=1, skipna=True)
        per["HB_BASKET"] = basket
        for name in NAMES + ["HB_BASKET"]:
            L = per[name]
            for split, (a, b) in {"dev": DEV, "chk": CHK}.items():
                r = dict(sig=sig, ex=ex, name=name, split=split)
                for k in ["gross", "ls_net", "ls_nost", "lo_net", "lo_nost", "flip_net"]:
                    s = L[k]; s = s[(s.index >= a) & (s.index <= b)]
                    n_, mu, t = stat(s)
                    r[f"{k}_n"], r[f"{k}_bp"], r[f"{k}_t"] = n_, mu, t
                rows.append(r)

T = pd.DataFrame(rows)
T.to_csv(HERE / "grid.csv", index=False)
dev = T[T.split == "dev"].set_index(["sig", "ex", "name"])
chk = T[T.split == "chk"].set_index(["sig", "ex", "name"])
pd.set_option("display.width", 250)
cols = ["gross_n", "gross_bp", "gross_t", "ls_net_bp", "ls_net_t", "lo_net_bp", "lo_net_t", "lo_nost_bp", "flip_net_bp", "flip_net_t"]
core_idx = [i for i in dev.index if i[2] in HB + ["HB_BASKET"]]
core = dev.loc[core_idx].sort_values("lo_net_t", ascending=False)
print("DEV, sorted by dev lo_net_t (long-only with stamp):")
print(core[cols].head(12).round(2).to_string())
print("\nCHECK for the same cells:")
print(chk.loc[core.index[:12], cols].round(2).to_string())
print("\nPLACEBO/CONTROL, gross and LS-net, dev | check")
pc = [i for i in dev.index if i[2] in PLACEBO + CONTROL]
print(pd.concat([dev.loc[pc, ["gross_bp", "gross_t", "ls_net_bp", "ls_net_t"]], chk.loc[pc, ["gross_bp", "gross_t", "ls_net_bp", "ls_net_t"]]], axis=1, keys=["dev", "chk"]).round(2).to_string())
