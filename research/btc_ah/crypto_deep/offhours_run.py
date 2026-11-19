"""Job 2: off-hours sessions as traded assets (BTC, ETH, SOL), 10 bp round trip.
Families (all times US/Eastern):
  Weekend (Fri 16:00 -> Sun 18:00 -> Mon 09:30):
    F1a  sign(Fri16 -> Sun18), enter Sun18 open, exit Mon09:30 open
    F1b  sign(Fri16 -> Mon09:30), enter Mon09:30 open, exit Mon16:00 open
    F1d  drift: long Fri16 open -> Mon09:30 open (no signal; 'against' = short)
  Sunday CME reopen hour (18:00-19:00):
    F2a  sign(Sun17 -> Sun18), enter Sun18, exit Sun19
    F2b  sign(Fri16 -> Sun18), enter Sun18, exit Sun19
    F2c  sign(Sun18 -> Sun18:30), enter Sun18:30, exit Sun19
    F2d  sign(Sun18 -> Sun19), enter Sun19, exit Mon09:30
    F2d0 drift: long Sun18 -> Sun19 (no signal)
  Asia open (20:00 ET, Mon-Fri evenings) after the US cash session:
    F3-1h / F3-4h / F3-8h  sign(09:30 -> 16:00 move), |move| >= thr, enter 20:00 open, exit 21:00 / 00:00 / 04:00 open
    F3d-*  drift: long 20:00 open -> same exits (no signal)
Signal thresholds |sig| >= 0, 1%, 2%. Each row reports both directions: 'with' = trade with the sign of the signal
(or long for drift), 'against' = the flipped-direction control (the opposite trade).
Dev = entry <= 2022-12-31; check = 2023-01-01..2026-08-10. Nothing after 2026-08-10 is loaded (common.load).
"""
import numpy as np
import pandas as pd
from common import load, Px, trades, cell_stats, yearly, DEV_END, CUT, ROOT

H = lambda d, days=0, h=0, m=0: d + pd.Timedelta(days=days, hours=h, minutes=m)
THR = [0.0, 0.01, 0.02]
rows = []


def add(asset, fam, thr, sig, ent, ext, dates):
    valid, nw, na, ww = trades(P, sig, ent, ext)
    valid &= ext <= CUT
    rows.append(pd.DataFrame(dict(asset=asset, family=fam, thr=thr, date=dates, entry=ent, nw=nw, na=na, ww=ww))[valid])


def signal_family(asset, fam, sig, ent, ext, dates):
    s = np.asarray(sig, float)
    for thr in THR:
        keep = np.abs(s) >= thr
        keep &= np.isfinite(s)
        add(asset, fam, thr, s[keep], ent[keep], ext[keep], dates[keep])


def drift_family(asset, fam, ent, ext, dates):
    add(asset, fam, "none", np.ones(len(ent)), ent, ext, dates)


def run(asset):
    global P
    B = load(asset)
    P = Px(B)
    print(asset, "bars", len(B), B.index.min(), B.index.max(), flush=True)
    days = pd.date_range("2017-08-13", "2026-08-10", freq="D")
    fri = days[days.dayofweek == 4]
    sun = days[days.dayofweek == 6]
    wd = days[days.dayofweek < 5]
    # ---- weekend
    sig = P.pc(H(fri, h=16)) if False else None
    f16 = P.o(H(fri, h=16))
    s_sun18 = P.pc(H(sun.shift(0, freq=None) if False else pd.DatetimeIndex(fri) + pd.Timedelta(days=2, hours=18)))
    f_sun18 = pd.DatetimeIndex(fri) + pd.Timedelta(days=2, hours=18)
    f_mon0930 = pd.DatetimeIndex(fri) + pd.Timedelta(days=3, hours=9, minutes=30)
    f_mon1600 = pd.DatetimeIndex(fri) + pd.Timedelta(days=3, hours=16)
    f_16 = pd.DatetimeIndex(fri) + pd.Timedelta(hours=16)
    # F1a
    sig1a = P.pc(f_sun18) / P.o(f_16) - 1
    signal_family(asset, "F1a_wkd_Fri16-Sun18", sig1a, f_sun18, f_mon0930, fri)
    # F1b
    sig1b = P.pc(f_mon0930) / P.o(f_16) - 1
    signal_family(asset, "F1b_wkd_Fri16-Mon0930", sig1b, f_mon0930, f_mon1600, fri)
    # F1d drift
    drift_family(asset, "F1d_drift_long_Fri16-Mon0930", f_16, f_mon0930, fri)
    # ---- Sunday CME reopen
    s17 = pd.DatetimeIndex(sun) + pd.Timedelta(hours=17)
    s18 = pd.DatetimeIndex(sun) + pd.Timedelta(hours=18)
    s1830 = pd.DatetimeIndex(sun) + pd.Timedelta(hours=18, minutes=30)
    s19 = pd.DatetimeIndex(sun) + pd.Timedelta(hours=19)
    smon = pd.DatetimeIndex(sun) + pd.Timedelta(days=1, hours=9, minutes=30)
    fri_before = pd.DatetimeIndex(sun) - pd.Timedelta(days=2) + pd.Timedelta(hours=16)
    signal_family(asset, "F2a_sun_Sun17-18", P.pc(s18) / P.o(s17) - 1, s18, s19, sun)
    signal_family(asset, "F2b_sun_Fri16-Sun18", P.pc(s18) / P.o(fri_before) - 1, s18, s19, sun)
    signal_family(asset, "F2c_sun_Sun18-1830", P.pc(s1830) / P.o(s18) - 1, s1830, s19, sun)
    signal_family(asset, "F2d_sun_Sun18-19_hold_Mon0930", P.pc(s19) / P.o(s18) - 1, s19, smon, sun)
    drift_family(asset, "F2d0_drift_long_Sun18-19", s18, s19, sun)
    # ---- Asia open 20:00 after US session
    d930 = pd.DatetimeIndex(wd) + pd.Timedelta(hours=9, minutes=30)
    d1600 = pd.DatetimeIndex(wd) + pd.Timedelta(hours=16)
    d2000 = pd.DatetimeIndex(wd) + pd.Timedelta(hours=20)
    r_us = P.pc(d1600) / P.o(d930) - 1
    exits = {"1h": pd.DatetimeIndex(wd) + pd.Timedelta(hours=21),
             "4h": pd.DatetimeIndex(wd) + pd.Timedelta(days=1),
             "8h": pd.DatetimeIndex(wd) + pd.Timedelta(days=1, hours=4)}
    for k, ext in exits.items():
        signal_family(asset, f"F3_asia20_US-move_hold{k}", r_us, d2000, ext, wd)
        drift_family(asset, f"F3d_asia20_drift_long_hold{k}", d2000, ext, wd)


for a in ["BTC", "ETH", "SOL"]:
    run(a)
R = pd.concat(rows, ignore_index=True)
R.to_csv(f"{ROOT}/out/offhours_trades.csv", index=False)

out = []
for (asset, fam, thr), g in R.groupby(["asset", "family", "thr"]):
    for win, lo, hi in [("dev", pd.Timestamp("2000-01-01"), DEV_END), ("check", DEV_END + pd.Timedelta("1s"), CUT),
                        ("full", pd.Timestamp("2000-01-01"), CUT)]:
        e = g[(g.entry >= lo) & (g.entry <= hi)]
        st = cell_stats(e, None)
        out.append(dict(asset=asset, family=fam, thr=thr, window=win, **st,
                        yearly=yearly(e) if win == "full" else ""))
O = pd.DataFrame(out)
O.to_csv(f"{ROOT}/out/offhours_cells.csv", index=False)
n_lines = O.groupby(["asset", "family", "thr"]).ngroups
print("TOTAL (asset,family,thr) lines:", n_lines, "| variants (x2 directions):", 2 * n_lines,
      "| signal-only (excl drift):", 2 * len([1 for (a, f, t) in O[["asset", "family", "thr"]].drop_duplicates().itertuples(index=False) if t != "none"]))
pd.set_option("display.width", 260, "display.max_columns", 30, "display.max_colwidth", 200, "display.max_rows", 500)
cols = ["asset", "family", "thr", "window", "n", "win_pct", "with_mean_bp", "with_t", "avg_win_bp", "avg_loss_bp",
        "against_mean_bp", "against_t", "worst_with_bp"]
print(O[O.window != "full"][cols].round(1).to_string(index=False))
