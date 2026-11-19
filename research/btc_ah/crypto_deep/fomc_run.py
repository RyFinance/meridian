"""Job 1: FOMC decision-day continuation, extended to 2017-09, BTC + ETH replication.
Signal: sign of the 14:00 -> 14:30 ET move (price at 14:30 = close of 14:15 bar). Entry at open of the
entry bar (14:30 / 14:45 / 15:00). Exits: same-day 16:00, next-day 09:30, next-day 16:00, day+2 16:00.
Control: identical rule on every non-FOMC weekday (same clock times).
FOMC decision dates are HARDCODED from memory (public Fed calendar), 2017-09..2026-07, scheduled meetings only
(emergency 2020-03-03 and 2020-03-15 excluded). Cross-checked against economic_calendar.csv below.
"""
import numpy as np
import pandas as pd
from common import load, Px, trades, cell_stats, yearly, DEV_END, CUT, ROOT

FOMC = """2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29""".split()
FOMC = pd.DatetimeIndex(pd.to_datetime(FOMC))
assert FOMC.is_monotonic_increasing and FOMC.max() <= pd.Timestamp("2026-08-10")

# cross-check against the local economic calendar (US Fed rate decisions, dates only)
cal = pd.read_csv("/Users/rytty/CCP/polymarket_arb/state/cache/economic_calendar.csv", low_memory=False)
cd = pd.to_datetime(cal.loc[(cal.region_code == "US") & cal.event.eq("Fed Interest Rate Decision"), "date"]).drop_duplicates()
cd = cd[(cd >= "2017-08-17") & (cd <= "2026-08-10")]
only_mine = sorted(set(FOMC) - set(cd))
only_cal = sorted(set(cd) - set(FOMC))
xcheck = dict(mine=len(FOMC), calendar=len(cd), in_both=len(set(FOMC) & set(cd)),
              only_hardcoded=[str(x.date()) for x in only_mine], only_calendar=[str(x.date()) for x in only_cal])
print("CROSS-CHECK", xcheck, flush=True)

# non-FOMC weekdays for the control
all_wd = pd.bdate_range("2017-08-17", "2026-08-10")
ctrl_days = all_wd.difference(FOMC)

ENTRIES = {"14:30": (0, 14, 30), "14:45": (0, 14, 45), "15:00": (0, 15, 0)}
EXITS = {"D 16:00": (0, 16, 0), "D+1 09:30": (1, 9, 30), "D+1 16:00": (1, 16, 0), "D+2 16:00": (2, 16, 0)}


def off(d, days, h, m):
    return d + pd.Timedelta(days=days, hours=h, minutes=m)


rows = []
for asset in ["BTC", "ETH"]:
    B = load(asset)
    P = Px(B)
    print(asset, "bars", len(B), B.index.min(), B.index.max(), flush=True)
    for kind, days in [("event", FOMC), ("control", ctrl_days)]:
        D = pd.DatetimeIndex(days)
        sig_ts = off(D, 0, 14, 30)
        sig = P.pc(sig_ts) / P.o(off(D, 0, 14, 0)) - 1.0
        for ek, (ed, eh, em) in ENTRIES.items():
            for xk, (xd, xh, xm) in EXITS.items():
                ent = off(D, ed, eh, em)
                ext = off(D, xd, xh, xm)
                valid, nw, na, ww = trades(P, sig, ent, ext)
                # sealed: exit must be on or before 2026-08-10 ET
                valid &= (ext <= CUT)
                r = pd.DataFrame(dict(asset=asset, kind=kind, entry_key=ek, exit_key=xk, date=D,
                                      entry=ent, nw=nw, na=na, ww=ww, sig=sig))[valid]
                rows.append(r)
R = pd.concat(rows, ignore_index=True)
R.to_csv(f"{ROOT}/out/fomc_trades.csv", index=False)

out = []
for (asset, ek, xk), g in R.groupby(["asset", "entry_key", "exit_key"]):
    ev = g[g.kind == "event"]
    ct = g[g.kind == "control"]
    for win, lo, hi in [("dev", pd.Timestamp("2000-01-01"), DEV_END), ("check", DEV_END + pd.Timedelta("1s"), CUT), ("full", pd.Timestamp("2000-01-01"), CUT)]:
        e = ev[(ev.entry >= lo) & (ev.entry <= hi)]
        c = ct[(ct.entry >= lo) & (ct.entry <= hi)]
        st = cell_stats(e, None)
        cs = cell_stats(c, None)
        out.append(dict(asset=asset, entry=ek, exit=xk, window=win, **st,
                        ctrl_n=cs.get("n"), ctrl_with_bp=cs.get("with_mean_bp"), ctrl_t=cs.get("with_t"),
                        yearly=yearly(e) if win == "full" else ""))
O = pd.DataFrame(out)
O.to_csv(f"{ROOT}/out/fomc_cells.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 200)
cols = ["asset", "entry", "exit", "window", "n", "win_pct", "with_mean_bp", "with_t", "avg_win_bp", "avg_loss_bp",
        "against_mean_bp", "against_t", "worst_with_bp", "ctrl_n", "ctrl_with_bp", "ctrl_t"]
print(O[cols].round(2).to_string(index=False))
print("\nFULL-window yearly (with-direction net bp, n):")
print(O[O.window == "full"][["asset", "entry", "exit", "yearly"]].to_string(index=False))
print("\nVariant rows (asset x entry x exit x dir):", 2 * 3 * 4 * 2, "| cells x windows:", len(O))
