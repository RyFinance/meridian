"""Stop/target management grid for the top dev H1 rule (agent btc_self).

Rule (H1|hz150|down|q0.75|rev): if the overnight move (prev 16:00 ET -> 09:30 ET) is
a drop of at least the dev 75th percentile of |move|, go long at the 09:30 open and
exit at the 12:00 open. Management grid adds a stop and a target (percent of entry)
with the 12:00 time exit. Costs: spot 10 bp round trip; IBIT proxy 6 bp round trip
(all trades are regular-hours).
"""
import numpy as np
import pandas as pd

SRC_PATH = "/Users/rytty/CCP/quant_v7/research/btc_ah/btc_self/study.py"
src = open(SRC_PATH).read()
# reuse the sealed loader, calendar, and H1 setup (everything before the H2 section)
exec(src[: src.index("# H2: weekend gap")], globals())

OUT_DIR = OUT
sel_mask_base = valid_o & oke & ex[150][1]
dir_rev = -np.sign(Ov)  # reversal of an overnight drop/rise
mode_thr = thr_h1[0.75]
sel = (Ov <= -mode_thr) & sel_mask_base  # down-move trades only
i0 = np.searchsorted(ts, R.t0930.values, side="left")
iex = np.searchsorted(ts, R.t1200.values, side="left")
idx = np.where(sel & (iex < N) & (i0 < N))[0]
print("H1 base trades (down q0.75 hz150, rev):", len(idx))

def path_exit(a, b, entry, dirn, stop, tgt):
    lo = LO[a:b]
    hi = HI[a:b]
    op = OP[a:b]
    if lo.size == 0:
        return None
    if dirn > 0:
        s_hit = np.where(lo <= stop)[0] if stop is not None else np.array([], int)
        t_hit = np.where(hi >= tgt)[0] if tgt is not None else np.array([], int)
    else:
        s_hit = np.where(hi >= stop)[0] if stop is not None else np.array([], int)
        t_hit = np.where(lo <= tgt)[0] if tgt is not None else np.array([], int)
    js = s_hit[0] if s_hit.size else None
    jt = t_hit[0] if t_hit.size else None
    if js is None and jt is None:
        return None
    if jt is None or (js is not None and js <= jt):
        o = op[js]
        return min(stop, o) if dirn > 0 else max(stop, o)
    o = op[jt]
    return max(tgt, o) if dirn > 0 else min(tgt, o)

rows_out = []
dev_flags = R.dev.values
yrs_all = R.year.values
d_all = R.d.values
for sp in (None, 0.005, 0.01, 0.02):
    for tp in (None, 0.005, 0.01, 0.02):
        gross = []
        yrs = []
        devs = []
        for k in idx:
            dirn = int(dir_rev[k])
            e = float(ent[k])
            stop = None if sp is None else e * (1 - dirn * sp)
            tgt = None if tp is None else e * (1 + dirn * tp)
            xp = path_exit(int(i0[k]), int(iex[k]), e, dirn, stop, tgt)
            if xp is None:
                xp = float(OP[int(iex[k])])
            gross.append(dirn * (xp / e - 1))
            yrs.append(yrs_all[k])
            devs.append(dev_flags[k])
        gross = np.array(gross)
        yrs = np.array(yrs)
        devs = np.array(devs, bool)
        row = dict(name=f"MGMT|H1down_q0.75_rev_hz150|stop{sp}|tgt{tp}", stop=sp, target=tp)
        for split, m in (("dev", devs), ("chk", ~devs)):
            g = gross[m]
            n = len(g)
            net = g - 0.0010
            ibit = g - 0.0006
            sd = net.std(ddof=1) if n > 1 else np.nan
            t = net.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan
            row[f"{split}_n"] = n
            row[f"{split}_mean_net"] = float(net.mean()) if n else np.nan
            row[f"{split}_t"] = float(t)
            row[f"{split}_win"] = float((net > 0).mean()) if n else np.nan
            row[f"{split}_ibit_mean_net"] = float(ibit.mean()) if n else np.nan
            row[f"{split}_mirror_mean_net"] = float((-g - 0.0010).mean()) if n else np.nan
            row[f"{split}_years"] = {int(y): round(float(v - 0.0010), 5) for y, v in
                                     pd.Series(g).groupby(yrs[m]).mean().items()}
        rows_out.append(row)

M = pd.DataFrame(rows_out)
M.to_pickle(f"{OUT_DIR}/mgmt_variants.pkl")
show = M[["name", "dev_n", "dev_mean_net", "dev_t", "dev_win", "dev_ibit_mean_net", "chk_n", "chk_mean_net",
          "chk_t", "chk_win", "chk_ibit_mean_net", "dev_mirror_mean_net"]].copy()
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
print(show.round(4).to_string())
