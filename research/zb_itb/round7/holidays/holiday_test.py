"""Round 7: are post-holiday sessions structurally different for the ZB-gap -> homebuilder rule?
Proxy panel: research/zb_itb/verify/long_history_panel.parquet (gap = sign of TLT open vs prior close,
b930_1030 = equal-weight builder basket 09:30 open -> 10:30). Cost 6 bp round trip.
NYSE holidays hardcoded (pandas_market_calendars not installed)."""
import datetime as dt
import numpy as np, pandas as pd
from scipy import stats

PANEL = "/Users/rytty/CCP/quant_v7/research/zb_itb/verify/long_history_panel.parquet"
D = dt.timedelta

def easter(y):
    a = y % 19; b = y // 100; c = y % 100; d = b // 4; e = b % 4; f = (b + 8) // 25
    g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30; i = c // 4; k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31; da = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(y, mo, da)

def nth_wd(y, m, wd, n):
    first = dt.date(y, m, 1); return first + D((wd - first.weekday()) % 7 + 7 * (n - 1))

def last_wd(y, m, wd):
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1) - D(1)
    return nxt - D((nxt.weekday() - wd) % 7)

def obs(d):
    if d.weekday() == 5: return d - D(1)   # Saturday -> Friday
    if d.weekday() == 6: return d + D(1)   # Sunday -> Monday
    return d

def nyse_holidays(y):
    h = {}
    ny = dt.date(y, 1, 1)
    if ny.weekday() == 5: pass            # NYSE does not close Friday Dec 31 for a Saturday New Year
    else: h[obs(ny) if ny.weekday() != 6 else ny + D(1)] = "NewYear"
    h[nth_wd(y, 1, 0, 3)] = "MLK"
    h[nth_wd(y, 2, 0, 3)] = "Presidents"
    h[easter(y) - D(2)] = "GoodFriday"
    h[last_wd(y, 5, 0)] = "Memorial"
    if y >= 2022: h[obs(dt.date(y, 6, 19))] = "Juneteenth"
    h[obs(dt.date(y, 7, 4))] = "July4"
    h[nth_wd(y, 9, 0, 1)] = "Labor"
    h[nth_wd(y, 11, 3, 4)] = "Thanksgiving"
    h[obs(dt.date(y, 12, 25))] = "Christmas"
    return h

HOL = {}
for y in range(2009, 2027): HOL.update(nyse_holidays(y))
# unscheduled closures (national mourning / Sandy)
for d, n in [(dt.date(2012, 10, 29), "Sandy"), (dt.date(2012, 10, 30), "Sandy"),
             (dt.date(2018, 12, 5), "BushFuneral"), (dt.date(2025, 1, 9), "CarterMourning")]:
    HOL[d] = n

panel = pd.read_parquet(PANEL)
days = [pd.Timestamp(x).date() for x in panel.index]
dset = set(days)

def is_session(d): return d.weekday() < 5 and d not in HOL

# early closes: day after Thanksgiving (certain); Christmas Eve and July 3 when trading weekdays (approximate)
EARLY_CORE = set(); EARLY_EXT = set()
for y in range(2010, 2027):
    tg = nth_wd(y, 11, 3, 4); EARLY_CORE.add(tg + D(1))
    for d in [dt.date(y, 12, 24), dt.date(y, 7, 3)]:
        if is_session(d): EARLY_EXT.add(d)
EARLY_EXT |= EARLY_CORE

# classify each panel day
rows = []; missing = []
for i, d in enumerate(days):
    if i == 0: continue
    p = days[i - 1]
    between = []; x = p + D(1)
    while x < d:
        if x.weekday() < 5: between.append(x)
        x += D(1)
    hol_between = [x for x in between if x in HOL]
    nonhol_between = [x for x in between if x not in HOL]
    if nonhol_between: missing.append((p, d))
    cls = None
    if hol_between and not nonhol_between:
        wds = {x.weekday() for x in hol_between}
        if 0 in wds: cls = "post_Mon_hol"
        elif 4 in wds: cls = "post_Fri_hol"
        else: cls = "post_midweek_hol"
    rows.append(dict(day=d, prev=p, cls=cls,
                     hol_name=(HOL[hol_between[0]] if hol_between else ""),
                     mon_normal=(d.weekday() == 0 and not between),
                     early_prev=(p in EARLY_EXT), early_prev_core=(p in EARLY_CORE),
                     early_prev_strict=(p in EARLY_CORE and not between)))
C = pd.DataFrame(rows).set_index("day")
C["gap"] = panel.gap.reindex(C.index).values
C["b"] = panel.b930_1030.reindex(C.index).values
C = C.dropna(subset=["gap", "b"])
C = C[C.gap != 0]
C["pnl"] = C.gap * C.b - 0.0006
C["hit"] = (C.gap * C.b > 0).astype(float)
C["year"] = [d.year for d in C.index]
C["post"] = C.cls.fillna("").str.startswith("post")

print(f"panel sessions {len(panel)}  classified {len(C)}  missing-session flags {len(missing)}")
print("holidays detected in panel window (weekday, 2010-2026):")
hl = sorted([(d, n) for d, n in HOL.items() if d.weekday() < 5 and 2010 <= d.year <= 2026 and d.year and d in set(days) | {d}])
print("  count of weekday holidays 2010-2026:", sum(1 for d in HOL if d.weekday() < 5 and 2010 <= d.year <= 2026))
print("  post-holiday sessions in panel:", int(C.post.sum()), dict(C.cls.value_counts()))
print("  early-close next-session (core, no holiday between) in panel:",
      int((C.early_prev_strict).sum()), " | ext:", int((C.early_prev & C.cls.isna()).sum()))

def stat(x):
    x = pd.Series(x).dropna()
    n = len(x)
    if n < 2: return f"n {n}"
    m = x.mean(); s = x.std(ddof=1)
    return f"n {n:3d} mean {m*1e4:+7.1f}bp t {m/s*np.sqrt(n):+5.2f} hit {(x>0).mean():.2f}"

def compare(name, mask, data):
    g = data.loc[mask, "pnl"]; o = data.loc[~mask, "pnl"]
    if len(g) < 3: print(f"  {name:38s} n={len(g)} too few"); return
    tt = stats.ttest_ind(g, o, equal_var=False)
    hit = data.loc[mask, "hit"].mean(); hitc = data.loc[~mask, "hit"].mean()
    print(f"  {name:38s} {stat(g)} | others {stat(o)} | diff {(g.mean()-o.mean())*1e4:+7.1f}bp Welch t {tt.statistic:+5.2f} p {tt.pvalue:.3f} | sign-agree grp {hit:.2f} vs {hitc:.2f}")

PERIODS = [("2010-19", "2010", "2019"), ("2020-23", "2020", "2023"), ("2024-26", "2024", "2026"), ("ALL", "2010", "2026")]
subs = {"post_Mon_hol": "post_Mon_hol", "post_Fri_hol": "post_Fri_hol", "post_midweek_hol": "post_midweek_hol"}

for pname, a, b in PERIODS:
    X = C[(C.year >= int(a)) & (C.year <= int(b))]
    print(f"\n===== {pname}  (sessions {len(X)})")
    print("  ALL sessions                          ", stat(X.pnl))
    compare("POST-HOLIDAY (any) vs others", X.post, X)
    for k in subs:
        compare(f"  {k}", X.cls == k, X)
    compare("POST-HOLIDAY vs non-post-holiday", X.post, X[~X.post].reindex(X.index).fillna(False).astype(bool) if False else X)  # placeholder replaced below
    nonpost = X[~X.post]
    g = X.loc[X.post, "pnl"]; o = nonpost.pnl
    if len(g) >= 3:
        tt = stats.ttest_ind(g, o, equal_var=False)
        print(f"  {'post vs NON-post sessions':38s} {stat(g)} | non-post {stat(o)} | diff {(g.mean()-o.mean())*1e4:+7.1f}bp Welch t {tt.statistic:+5.2f} p {tt.pvalue:.3f}")
    compare("MONDAY after normal weekend", X.mon_normal, X)
    compare("DAY AFTER early close (core)", X.early_prev_strict, X)
    compare("DAY AFTER early close (ext, incl. Xmas Eve/Jul 3)", X.early_prev & X.cls.isna(), X)
    compare("DAY AFTER early close vs non-post", X.early_prev_strict, X[~X.post].assign(**{}).reindex(X.index).dropna(subset=["pnl"]) if False else X)

print("\n===== post-holiday sessions list (ALL)")
pl = C[C.post][["prev", "hol_name", "cls", "gap", "b", "pnl"]].copy()
pl["pnl_bp"] = (pl.pnl * 1e4).round(1); pl["b_bp"] = (pl.b * 1e4).round(1)
print(pl[["prev", "hol_name", "cls", "gap", "b_bp", "pnl_bp"]].to_string())
