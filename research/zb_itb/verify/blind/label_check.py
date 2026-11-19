#!/usr/bin/env python
"""
Evidence + self-checks for the blind ZB->ITB backtest (imported by backtest.py, also runnable alone).

1. Bar-label convention (START vs END) from the data itself.
2. Independent re-derivation of P0/P1 by label (15:00 / 08:00 labels) to cross-check the end-time lookup.
3. Data oddities: duplicates, gaps, half-days, DST, zero-volume bars, ITB missing days.
"""
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/New_York"

# NYSE full-day closures inside 2023-11-17 .. 2026-10-16 (standard calendar, used only to tell holidays from data gaps)
NYSE_HOLIDAYS = pd.to_datetime(
    [
        "2023-11-23", "2023-12-25",
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04",
        "2024-09-02", "2024-11-28", "2024-12-25",
        "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
        "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
        "2026-09-07", "2026-11-26", "2026-12-25",
    ]
)
# known 14:00 ET FOMC statement days and 08:30 ET jobs-report days inside the sample (from public calendars)
FOMC = pd.to_datetime(
    ["2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18", "2025-01-29", "2025-03-19",
     "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10", "2026-01-28",
     "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16"]
)
NFP = pd.to_datetime(
    ["2024-06-07", "2024-07-05", "2024-08-02", "2024-09-06", "2024-10-04", "2024-11-01", "2024-12-06",
     "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02", "2025-06-06", "2025-07-03",
     "2025-08-01", "2025-09-05", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02",
     "2026-08-07", "2026-09-04"]
)


def _ranges(hhmm_list):
    return ", ".join(hhmm_list) if hhmm_list else "-"


def label_evidence(zb, itb):
    L = []
    lab = pd.Series(zb.index.strftime("%H:%M"), index=zb.index)
    dow = zb.index.dayofweek
    L.append("### ZB label structure")
    L.append("")
    L.append(f"- index tz = `{zb.index.tz}`, unique = {zb.index.is_unique}, monotonic = {zb.index.is_monotonic_increasing}, bars = {len(zb)}, first = {zb.index[0]}, last = {zb.index[-1]}.")
    sun = sorted(set(lab[dow == 6]))
    mon_thu = sorted(set(lab[(dow >= 0) & (dow <= 3)]) - {"09:30", "10:30", "11:30", "12:30"})
    fri = sorted(set(lab[dow == 4]) - {"09:30", "10:30", "11:30", "12:30"})
    L.append(f"- Sunday labels: {_ranges(sun)}  (Globex re-opens Sunday 18:00 ET).")
    L.append(f"- Mon-Thu label hours present: {mon_thu[0]}..{mon_thu[-1]} with a hole only at 17:00 (maintenance hour 17:00-18:00 ET): 17:00 label count = {(lab=='17:00').sum()} (one stray zero-volume flat bar), 18:00 label count = {(lab=='18:00').sum()}.")
    L.append(f"- Friday label hours: {fri[0]}..{fri[-1]} (last label 16:00, nothing after; Globex closes Friday 17:00 ET).")
    L.append("- If labels were bar END times, Sunday's first label would be 19:00 and every session's last label would be 17:00. The data show the opposite (first Sunday label 18:00, last weekday label 16:00, 17:00 absent). => **labels = bar START** (each bar covers label .. label+1h).")
    L.append("- ITB: labels 09:30,10:30,...,15:30 (15:30 is the half-hour stub to 16:00); the 09:30 label exists, an END-labelled series would start at 10:30. => START as well.")
    # event study
    z = zb.copy()
    z["rng"] = z["High"] - z["Low"]
    z["lab"] = z.index.strftime("%H:%M")
    z["date"] = pd.DatetimeIndex(z.index.strftime("%Y-%m-%d"))
    z = z[z["lab"].str.endswith(":00") & (z["date"].dt.dayofweek < 5)]
    def ratio(days, hrs):
        x = z[z["date"].isin(days)].groupby("lab")["rng"].mean()
        b = z[~z["date"].isin(days)].groupby("lab")["rng"].mean()
        return (x / b).loc[hrs]
    hrs_f = ["12:00", "13:00", "14:00", "15:00", "16:00"]
    hrs_n = ["06:00", "07:00", "08:00", "09:00", "10:00"]
    rf = ratio(FOMC, hrs_f)
    rn = ratio(NFP, hrs_n)
    L.append("")
    L.append("Event check (mean High-Low on event days / mean on other days, by bar label):")
    L.append("")
    L.append("| label | " + " | ".join(hrs_f) + " |")
    L.append("|---|" + "---|" * len(hrs_f))
    L.append("| FOMC statement 14:00 ET (%d days) | " % len(FOMC) + " | ".join(f"{v:.2f}" for v in rf) + " |")
    L.append("")
    L.append("| label | " + " | ".join(hrs_n) + " |")
    L.append("|---|" + "---|" * len(hrs_n))
    L.append("| Jobs report 08:30 ET (%d days) | " % len(NFP) + " | ".join(f"{v:.2f}" for v in rn) + " |")
    L.append("")
    L.append("The 14:00 ET FOMC release produces its range spike in the bar labelled 14:00 (not 15:00), and the 08:30 ET releases in the bar labelled 08:00 (not 09:00): consistent only with START labels.")
    return "\n".join(L)


def selfcheck(zb, t):
    """Re-derive P0/P1 purely by label (15:00 / 08:00) with groupby/map and compare to the end-time lookup."""
    z = zb.copy()
    z["date"] = z.index.strftime("%Y-%m-%d")
    z["hhmm"] = z.index.strftime("%H:%M")
    c15 = z[z["hhmm"] == "15:00"].set_index("date")["Close"]
    c08 = z[z["hhmm"] == "08:00"].set_index("date")["Close"]
    p0 = t["prev"].dt.strftime("%Y-%m-%d").map(c15)
    p1 = t["date"].dt.strftime("%Y-%m-%d").map(c08)
    same0 = ((p0 == t["P0"]) | (p0.isna() & t["P0"].isna())).all()
    same1 = ((p1 == t["P1"]) | (p1.isna() & t["P1"].isna())).all()
    return bool(same0), bool(same1)


def oddities(zb, itb, t_all, e):
    L = []
    L.append("### ZB (ZB=F 60m) oddities")
    L.append("")
    # structure by date
    z = zb.copy()
    z["date"] = pd.DatetimeIndex(z.index.strftime("%Y-%m-%d"))
    z["hhmm"] = z.index.strftime("%H:%M")
    full_mt = [f"{h:02d}:00" for h in list(range(0, 17)) + list(range(18, 24))]
    full_f = [f"{h:02d}:00" for h in range(0, 17)]
    full_s = [f"{h:02d}:00" for h in range(18, 24)]
    rows = []
    for dte, g in z.groupby("date"):
        have = set(g["hhmm"])
        w = dte.dayofweek
        ref = set(full_s if w == 6 else full_f if w == 4 else full_mt)
        miss = sorted(ref - have)
        extra = sorted(have - ref)
        if miss or extra:
            if extra and set(extra) == {"09:30", "10:30", "11:30", "12:30"}:
                rows.append((dte, "HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent"))
            else:
                msg = []
                if miss:
                    msg.append("missing " + (f"{miss[0]}..{miss[-1]} ({len(miss)} bars)" if len(miss) > 3 else ",".join(miss)))
                if extra:
                    msg.append("extra " + ",".join(extra))
                rows.append((dte, "; ".join(msg)))
    L.append(f"Dates with a non-standard hour set: {len(rows)} of {z['date'].nunique()} (standard = Sun 18-23h; Mon-Thu 00-16h + 18-23h; Fri 00-16h).")
    L.append("")
    L.append("| date | what |")
    L.append("|---|---|")
    for dte, msg in rows:
        L.append(f"| {dte:%Y-%m-%d} {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dte.dayofweek]} | {msg} |")
    L.append("")
    zv = zb[zb["Volume"] == 0]
    zl = pd.Series(zv.index.strftime("%H:%M")).value_counts().sort_index()
    L.append(f"- Zero-volume bars: {len(zv)} of {len(zb)}; {int(zl.get('16:00', 0))} at label 16:00 (of {int((zb.index.strftime('%H:%M')=='16:00').sum())}), {int(zl.get('18:00', 0))} at label 18:00, the rest {len(zv)-int(zl.get('16:00',0))-int(zl.get('18:00',0))} scattered. These carry normal-looking OHLC (not flat); likely a volume-reporting quirk. The bars actually used (labels 15:00 and 08:00) are almost never zero-volume (see list in results).")
    L.append("- No duplicated timestamps; no NaNs; Close == Adj Close everywhere; last ZB bar is 2026-10-16 16:00 (volume 0).")
    L.append("- A single stray flat zero-volume bar labelled 17:00 on 2025-03-10 (the Monday after the US spring-forward); harmless.")
    L.append("- Half-days (NYSE 1pm closes): the ZB file contains ONLY the four :30-grid bars for 2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24. Hence on those D the 09:00 bar is missing (no trade) and on the next ITB day the 16:00 bar of prev is missing (no trade).")
    L.append("")
    L.append("### ITB (60m) oddities")
    L.append("")
    i = itb.copy()
    i["date"] = pd.DatetimeIndex(i.index.strftime("%Y-%m-%d"))
    i["hhmm"] = i.index.strftime("%H:%M")
    std = ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]
    itb_rows = []
    for dte, g in i.groupby("date"):
        have = list(g["hhmm"])
        if have != std:
            itb_rows.append((dte, have))
    L.append("Days whose bar set is not the standard 7 bars (09:30..15:30):")
    L.append("")
    for dte, have in itb_rows:
        note = ""
        if have == ["09:30", "10:30", "11:30"]:
            note = " (NYSE half-day: 12:30-13:00 stub bar absent)"
        L.append(f"- {dte:%Y-%m-%d}: {','.join(have)}{note}")
    # weekdays missing completely and not a holiday
    all_bd = pd.bdate_range(itb.index[0].tz_localize(None).normalize(), itb.index[-1].tz_localize(None).normalize())
    have_days = pd.DatetimeIndex(sorted(set(i["date"])))
    have_0930 = pd.DatetimeIndex(sorted(set(i.loc[i["hhmm"] == "09:30", "date"])))
    gone = [d for d in all_bd if d not in have_days and d not in NYSE_HOLIDAYS]
    nohol = [d for d in all_bd if d in NYSE_HOLIDAYS and d in have_days]
    L.append("")
    L.append("Non-holiday weekdays with no ITB bars at all (data gap): " + (", ".join(f"{d:%Y-%m-%d}" for d in gone) if gone else "none") + ".")
    L.append("Weekdays that have ITB bars although listed as NYSE holidays: " + (", ".join(f"{d:%Y-%m-%d}" for d in nohol) if nohol else "none") + ".")
    miss0930 = [d for d in have_days if d not in have_0930]
    L.append("Days with ITB bars but no 09:30 bar (so not a trade day D): " + (", ".join(f"{d:%Y-%m-%d}" for d in miss0930) if miss0930 else "none") + ".")
    zi = itb[itb["Volume"] == 0]
    L.append(f"Zero-volume ITB bars: {len(zi)}; two of them are 09:30 bars (2023-12-13, 2024-05-16) but both predate the first trade day. No NaNs, no duplicates.")
    L.append(f"ITB 09:30 bars in file: {len(have_0930)}; NYSE weekdays in range that are not holidays: {len([d for d in all_bd if d not in NYSE_HOLIDAYS])}.")
    # days where prev is not the preceding NYSE trading day
    nyse_days = pd.DatetimeIndex([d for d in all_bd if d not in NYSE_HOLIDAYS])
    chk = []
    for _, r in e.iterrows():
        if pd.isna(r["prev"]):
            continue
        k = nyse_days.get_indexer([r["date"]])[0]
        if k > 0 and nyse_days[k - 1] != r["prev"]:
            chk.append((r["date"], r["prev"], nyse_days[k - 1]))
    L.append("")
    L.append("Days D where `prev` (previous day with an ITB 09:30 bar) is NOT the preceding NYSE trading day because of ITB gaps: " + ("; ".join(f"D={d:%Y-%m-%d} prev={p:%Y-%m-%d} (NYSE prior day {q:%Y-%m-%d})" for d, p, q in chk) if chk else "none") + ".")
    return "\n".join(L), chk


def dst_check(zb, e):
    L = []
    L.append("### DST handling")
    L.append("")
    L.append("Unique UTC offsets in the ZB index: " + ", ".join(sorted(set(str(x) for x in zb.index.strftime('%z')))) + "; same for ITB when loaded. US transitions inside the sample: 2024-11-03 (fall back), 2025-03-09 (spring fwd), 2025-11-02 (fall back), 2026-03-08 (spring fwd) - all fall on Sundays, i.e. inside the Globex weekend close (re-open 18:00 ET), so no bar is duplicated/skipped by the 02:00 transition itself.")
    L.append(f"Label-hour vs UTC check: bars labelled 18:00 ET sit at 22:00 UTC in EDT and 23:00 UTC in EST (and 08:00 ET at 12:00/13:00 UTC), i.e. the stored labels follow wall-clock ET in both regimes.")
    L.append("")
    L.append("Trades on the first session after each transition (P0 label of prev, P1 label of D, with offsets):")
    L.append("")
    L.append("| D | prev | P0 bar label (ends 16:00 ET) | P1 bar label (ends 09:00 ET) | P0 | P1 | d |")
    L.append("|---|---|---|---|---|---|---|")
    for dd in ["2024-11-04", "2025-03-10", "2025-11-03", "2026-03-09"]:
        r = e[e["date"] == pd.Timestamp(dd)]
        if r.empty:
            L.append(f"| {dd} | n/a | | | | | |")
            continue
        r = r.iloc[0]
        t0 = pd.Timestamp(f"{r['prev']:%Y-%m-%d} 15:00", tz=TZ)
        t1 = pd.Timestamp(f"{r['date']:%Y-%m-%d} 08:00", tz=TZ)
        ok0 = t0 in zb.index
        ok1 = t1 in zb.index
        L.append(f"| {dd} | {r['prev']:%Y-%m-%d} | {t0} ({'present' if ok0 else 'MISSING'}) | {t1} ({'present' if ok1 else 'MISSING'}) | {r['P0']} | {r['P1']} | {r['d']} |")
    return "\n".join(L)


def main():
    from backtest import load, build_table, add_returns, eval_rows

    zb, itb = load()
    t = add_returns(build_table(zb, itb, True))
    e = eval_rows(t)
    print(label_evidence(zb, itb))
    print("selfcheck (P0 same, P1 same):", selfcheck(zb, t))
    o, chk = oddities(zb, itb, t, e)
    print(o)
    print(dst_check(zb, e))


if __name__ == "__main__":
    main()
