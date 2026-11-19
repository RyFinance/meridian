# BTC macro-release spillover study. Sealed: nothing after 2026-08-10 is loaded.
import glob, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
ROOT = "/Users/rytty/CCP/quant_v7/research"
OUT = f"{ROOT}/btc_ah/macro"
CUT = pd.Timestamp("2026-08-10 23:59:59")          # naive ET wall time upper bound
DEV_END = pd.Timestamp("2022-06-30")
RT_STOCK = 2 * 3e-4                                  # 3 bp per side, regular hours
RT_BTC = 2 * 5e-4                                    # 5 bp per side

def to_et_naive(ts_utc):
    return ts_utc.dt.tz_convert(ET).dt.tz_localize(None)

# ---------- BTC 1m ----------
b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
b = b[b.timestamp < pd.Timestamp("2026-08-11", tz="UTC")]
bidx = to_et_naive(b.timestamp)
bo = pd.Series(b.open.values, index=bidx); bo = bo[~bo.index.duplicated()].sort_index()
bc = pd.Series(b.close.values, index=bidx); bc = bc[~bc.index.duplicated()].sort_index()

# ---------- MSTR 1m dev (regular + ext; use regular-hour bars only) ----------
fr = [pd.read_parquet(f) for f in sorted(glob.glob(f"{ROOT}/mstr_btc_0dte/stock_1m_dev/*.parquet"))]
s = pd.concat(fr)
sidx = to_et_naive(pd.to_datetime(s.time.str.replace("Z", ""), utc=True))
s = pd.DataFrame({"o": s.open.values, "c": s.close.values}, index=sidx)
s = s[~s.index.duplicated()].sort_index()
s = s[(s.index.time >= pd.Timestamp("09:30").time()) & (s.index.time < pd.Timestamp("16:00").time())]
m1 = {"o": s.o, "c": s.c}

# ---------- MSTR/peers 60m (yfinance, check only) ----------
def load60(t):
    d = pd.read_parquet(f"{OUT}/cache/{t}_60m.parquet")
    idx = d.ts.dt.tz_localize(None) if d.ts.dt.tz is not None else d.ts
    idx = pd.to_datetime(idx)
    d = pd.DataFrame({"o": d.Open.values, "c": d.Close.values}, index=idx)
    d = d[d.index <= CUT]
    return {"o": d.o, "c": d.c}

# ---------- Calendars ----------
CPI_H = ["2020-01-14 2020-02-13 2020-03-11 2020-04-10 2020-05-12 2020-06-10 2020-07-14 2020-08-12 2020-09-11 2020-10-13 2020-11-12 2020-12-10",
         "2021-01-13 2021-02-10 2021-03-10 2021-04-13 2021-05-12 2021-06-10 2021-07-13 2021-08-11 2021-09-14 2021-10-13 2021-11-10 2021-12-10",
         "2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10 2022-07-13 2022-08-10 2022-09-13 2022-10-13 2022-11-10 2022-12-13",
         "2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13 2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12",
         "2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11",
         "2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18"]
NFP_H = ["2020-01-10 2020-02-07 2020-03-06 2020-04-03 2020-05-08 2020-06-05 2020-07-02 2020-08-07 2020-09-04 2020-10-02 2020-11-06 2020-12-04",
         "2021-01-08 2021-02-05 2021-03-05 2021-04-02 2021-05-07 2021-06-04 2021-07-02 2021-08-06 2021-09-03 2021-10-08 2021-11-05 2021-12-03",
         "2022-01-07 2022-02-04 2022-03-04 2022-04-01 2022-05-06 2022-06-03 2022-07-08 2022-08-05 2022-09-02 2022-10-07 2022-11-04 2022-12-02",
         "2023-01-06 2023-02-03 2023-03-10 2023-04-07 2023-05-05 2023-06-02 2023-07-07 2023-08-04 2023-09-01 2023-10-06 2023-11-03 2023-12-08",
         "2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06",
         "2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16"]
FOMC_H = ["2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16",
          "2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15",
          "2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14",
          "2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13",
          "2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18",
          "2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10",
          "2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29"]
cal = pd.read_csv("/Users/rytty/CCP/polymarket_arb/state/cache/economic_calendar.csv", low_memory=False)
cal = cal[cal.region_code == "US"]
def from_cal(name):
    d = pd.to_datetime(cal[cal.event == name].date)
    return pd.DatetimeIndex(d[(d >= "2026-01-01") & (d <= "2026-08-10")])
cpi = pd.DatetimeIndex(pd.to_datetime(" ".join(CPI_H).split())).append(from_cal("CPI"))
nfp = pd.DatetimeIndex(pd.to_datetime(" ".join(NFP_H).split())).append(from_cal("Non Farm Payrolls"))
fomc = pd.DatetimeIndex(pd.to_datetime(" ".join(FOMC_H).split()))
cpi = cpi[cpi <= CUT].normalize().unique(); nfp = nfp[nfp <= CUT].normalize().unique(); fomc = fomc[fomc <= CUT].normalize().unique()
print("events: CPI", len(cpi), "NFP", len(nfp), "FOMC", len(fomc))

# ---------- Universe: weekdays 2020-08-12..2026-08-10 ----------
days = pd.bdate_range("2020-08-12", "2026-08-10")
def T(hm, shift=False):
    base = days + pd.offsets.BDay(1) if shift else days
    return [d + pd.Timedelta(hours=hm[0], minutes=hm[1]) for d in base]
def g(series, hm, shift=False):
    return series.reindex(pd.DatetimeIndex(T(hm, shift))).to_numpy()

def build(o, c, close_hm):
    """Price panel on the weekday universe. o=open series, c=close series."""
    r = pd.DataFrame(index=days)
    r["eM"] = g(o, (9, 30)); r["x1000"] = g(o, (10, 0)); r["x1030"] = g(o, (10, 30)); r["x1200"] = g(o, (12, 0))
    r["eF"] = g(o, (14, 30))
    r["xc"] = g(c, close_hm); r["xn"] = g(c, close_hm, shift=True)
    return r

# BTC move (fractions), uses BTC only
btc = pd.DataFrame(index=days)
btc["mA"] = g(bo, (9, 25)) / g(bo, (8, 30)) - 1
btc["mF"] = g(bo, (14, 30)) / g(bo, (14, 0)) - 1
btc["ev_cpi"] = days.isin(cpi); btc["ev_nfp"] = days.isin(nfp); btc["ev_fomc"] = days.isin(fomc)
btc["nonev"] = ~(btc.ev_cpi | btc.ev_nfp | btc.ev_fomc)
EVM = {"CPI": btc.ev_cpi, "NFP": btc.ev_nfp, "CPI+NFP": btc.ev_cpi | btc.ev_nfp}

INSTR = {
    "BTC":    dict(rec=build(bo, bc, (15, 59)), rt=RT_BTC, exM=["x1000", "x1030", "x1200", "xc"], exF=["xc", "xn"], dev=True),
    "MSTR1m": dict(rec=build(m1["o"], m1["c"], (15, 59)), rt=RT_STOCK, exM=["x1000", "x1030", "x1200", "xc"], exF=["xc", "xn"], dev=True),
}
for t in ["MSTR", "COIN", "MARA", "RIOT", "CLSK"]:
    d = load60(t)
    rec = build(d["o"], d["c"], (15, 30))
    rec["x1000"] = np.nan; rec["x1200"] = np.nan   # 60m bars cannot give 10:00 / 12:00 exits
    INSTR[f"{t}60m"] = dict(rec=rec, rt=RT_STOCK, exM=["x1030", "xc"], exF=["xc", "xn"], dev=False)

def split(idx, part):
    return idx <= DEV_END if part == "dev" else idx > DEV_END

def stats(x):
    n = len(x)
    if n < 3:
        return dict(n=n, win=np.nan, mean=np.nan, t=np.nan, aw=np.nan, al=np.nan)
    sd = x.std(ddof=1)
    return dict(n=n, win=(x > 0).mean(), mean=x.mean() * 1e4,
                t=x.mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan,
                aw=x[x > 0].mean() * 1e4 if (x > 0).any() else np.nan,
                al=x[x <= 0].mean() * 1e4 if (x <= 0).any() else np.nan)

def net_series(rec, btcmove, w, evm, dirn, th, ex, rt):
    e = rec.eM if w == "M" else rec.eF
    m = btcmove.mA if w == "M" else btcmove.mF
    x = rec[ex]
    m = m.reindex(rec.index); evm = evm.reindex(rec.index).fillna(False).astype(bool)
    ok = m.notna() & e.notna() & x.notna() & (m.abs() * 1e4 >= th) & (m != 0)
    sgn = np.sign(m) * (1 if dirn == "with" else -1)
    net = sgn * (x / e - 1) - rt
    return net[ok & evm], net[ok & btcmove.nonev.reindex(rec.index).fillna(False).astype(bool)]

rows = []
for iname, cfg in INSTR.items():
    rec = cfg["rec"]
    for w, evsets in [("M", ["CPI", "NFP", "CPI+NFP"]), ("F", ["FOMC"])]:
        exits = cfg["exM"] if w == "M" else cfg["exF"]
        for evname in evsets:
            evm = EVM[evname] if w == "M" else btc.ev_fomc
            for th in [0, 20, 50]:
                for ex in exits:
                    for dirn in ["with", "against"]:
                        ev, ct = net_series(rec, btc, w, evm, dirn, th, ex, cfg["rt"])
                        ev_flip, _ = net_series(rec, btc, w, evm, "against" if dirn == "with" else "with", th, ex, cfg["rt"])
                        for part in (["dev", "check"] if cfg["dev"] else ["check"]):
                            x = ev[split(ev.index, part)]; c = ct[split(ct.index, part)]
                            f = ev_flip[split(ev_flip.index, part)]
                            st = stats(x)
                            cs = stats(c)
                            yrs = x.groupby(x.index.year).mean().mul(1e4).round(0).astype(int).to_dict() if len(x) else {}
                            rows.append(dict(instr=iname, window=("morning 08:30" if w == "M" else "FOMC 14:00"),
                                             events=evname, dir=dirn, th_bp=th, exit=ex, split=part,
                                             **st, flip_mean=f.mean() * 1e4 if len(f) else np.nan,
                                             ctrl_n=cs["n"], ctrl_mean=cs["mean"], ctrl_t=cs["t"], years=str(yrs)))
R = pd.DataFrame(rows)
R.to_csv(f"{OUT}/all_variants.csv", index=False)
n_variants = len(R[(R.split == "dev") | (R.split == "check")].groupby(["instr", "window", "events", "dir", "th_bp", "exit"]))
print("variant specs enumerated:", n_variants, " rows:", len(R))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
R["mean"] = R["mean"].round(1)
R.to_pickle(f"{OUT}/R.pkl")
