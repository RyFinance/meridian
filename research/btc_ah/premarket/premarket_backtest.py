"""BTC -> MSTR pre-market and after-hours gap test (btc_ah brief).

Writes only inside research/btc_ah/premarket/. Sealed holdout: nothing at or after 2026-08-11 ET is loaded.
Dev beta: regular-session overnight (prev 15:59 close -> 09:30 open vs BTC 15:59 -> 09:29), dev days <= 2022-06-30.
Extended-hours data exists only for 2026-04-29..2026-08-10 (mstr_stock_1m_lse.parquet), so the
extended-hours tests are check-only (no dev sample exists for them).
"""
import glob
import math
from collections import Counter

import numpy as np
import pandas as pd

ROOT = "/Users/rytty/CCP/quant_v7"
OUT = f"{ROOT}/research/btc_ah/premarket"
NY = "America/New_York"
CUT = pd.Timestamp("2026-08-11", tz=NY)          # sealed holdout cutoff (exclusive)
DEV_END = "2022-06-30"
EXT_START = "2026-04-29"
ENTRY_SLIP = 0.0015   # 15 bp per side, extended-hours fill
PRE_SLIP = 0.0015     # exit in pre-market, 15 bp
RTH_SLIP = 0.0003     # exit in regular session, 3 bp
MIN = pd.Timedelta(minutes=1)
PM_TIMES = ["07:00", "08:00", "09:00", "09:15", "09:25"]
PM_EXITS = ["09:30", "09:35", "09:45", "10:00"]
AH_TIMES = ["16:30", "17:30", "19:00"]
THRS = [0.005, 0.01, 0.02, 0.03]


def T(day, hhmm):
    return pd.Timestamp(f"{day} {hhmm}", tz=NY)


def load_btc():
    bt = pd.read_parquet(
        "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet",
        columns=["timestamp", "close"],
    )
    s = pd.Series(bt["close"].values, index=bt["timestamp"].dt.tz_convert(NY)).sort_index()
    return s[s.index < CUT]


def load_mstr():
    parts = []
    for f in sorted(glob.glob(f"{ROOT}/research/mstr_btc_0dte/stock_1m_dev/*.parquet")):
        d = pd.read_parquet(f)
        idx = pd.to_datetime(d["time"].str.replace("Z", ""), utc=True).dt.tz_convert(NY)
        parts.append(pd.DataFrame({"open": d.open.values, "high": d.high.values, "low": d.low.values,
                                   "close": d.close.values, "volume": d.volume.values}, index=idx))
    dev = pd.concat(parts)
    L = pd.read_parquet(f"{ROOT}/research/mstr_btc_0dte/mstr_stock_1m_lse.parquet")
    L.index = L["ts"].dt.tz_localize("UTC").dt.tz_convert(NY)
    L = L[["open", "high", "low", "close", "volume"]]
    M = pd.concat([dev, L]).sort_index()
    M = M[~M.index.duplicated()]
    return M[M.index < CUT]


bt = load_btc()
M = load_mstr()
Md = {t: (r[0], r[1], r[2], r[3], r[4]) for t, r in zip(M.index, M[["open", "high", "low", "close", "volume"]].itertuples(index=False, name=None))}
cal = pd.read_parquet(f"{ROOT}/research/mstr_btc_0dte/daily_panel.parquet").index.strftime("%Y-%m-%d").tolist()
cal = [d for d in cal if d <= "2026-08-10"]
cal_prev = {cal[i]: cal[i - 1] for i in range(1, len(cal))}
cal_next = {cal[i]: cal[i + 1] for i in range(len(cal) - 1)}
hh = M.index.strftime("%H:%M")
dte = M.index.strftime("%Y-%m-%d")
close1559 = dict(zip(dte[hh == "15:59"], M.close.values[hh == "15:59"]))
open0930 = dict(zip(dte[hh == "09:30"], M.open.values[hh == "09:30"]))
mdays = set(dte)


def ols_beta(lo, hi):
    xs, ys = [], []
    for D in cal:
        if not (lo <= D <= hi) or D not in open0930 or D not in mdays:
            continue
        P = cal_prev.get(D)
        if P is None or P not in close1559:
            continue
        b0, b1 = bt.get(T(P, "15:59")), bt.get(T(D, "09:29"))
        if b0 is None or b1 is None:
            continue
        xs.append(math.log(b1 / b0))
        ys.append(math.log(open0930[D] / close1559[P]))
    x, y = np.array(xs), np.array(ys)
    beta0 = float((x * y).sum() / (x * x).sum())
    corr = float(np.corrcoef(x, y)[0, 1])
    return beta0, corr, len(x)


beta_dev, corr_dev, n_dev = ols_beta("2020-08-01", DEV_END)
beta_chk, corr_chk, n_chk = ols_beta("2022-07-01", "2023-12-31")
BETAS = {"beta_dev": beta_dev, "beta_1": 1.0}


def last_print(ref):
    """Last bar with volume at or before ref, within 30 minutes."""
    for k in range(30):
        bar = Md.get(ref - k * MIN)
        if bar is not None and bar[4] > 0:
            return bar[3]
    return None


def trade_ret(d, entry, exit_open, pre_exit=False):
    h, l = entry[1], entry[2]
    xs = PRE_SLIP if pre_exit else RTH_SLIP
    if d == 1:
        return exit_open * (1 - xs) / (h * (1 + ENTRY_SLIP)) - 1
    return (l * (1 - ENTRY_SLIP)) / (exit_open * (1 + xs)) - 1


rows, skip = [], Counter()
ext_days = [D for D in cal if D >= EXT_START and D in mdays]

# Pre-market: decide at T, enter bar T, exit at RTH open bars.
for D in ext_days:
    P = cal_prev.get(D)
    if P is None or P not in close1559 or (P not in mdays):
        skip["no_prev_close"] += 1
        continue
    P0m, P0b = close1559[P], bt.get(T(P, "15:59"))
    if P0b is None:
        skip["no_btc_p0"] += 1
        continue
    for tt in PM_TIMES:
        ref = T(D, tt) - MIN
        pm = last_print(ref)
        if pm is None:
            skip["stale_no_print_30m"] += 1
            continue
        bb = bt.get(ref)
        if bb is None:
            skip["no_btc_T"] += 1
            continue
        entry = Md.get(T(D, tt))
        if entry is None or entry[4] <= 0:
            skip["no_entry_volume"] += 1
            continue
        mret, bret = math.log(pm / P0m), math.log(bb / P0b)
        for bname, beta in BETAS.items():
            gap = beta * bret - mret
            for thr in THRS:
                if abs(gap) <= thr:
                    continue
                d = 1 if gap > 0 else -1
                for ex in PM_EXITS:
                    eb = Md.get(T(D, ex))
                    if eb is None or eb[4] <= 0:
                        skip["no_exit_volume"] += 1
                        continue
                    rows.append(dict(window="pre", day=D, decide=tt, beta=bname, thr=thr, exit=ex, dir=d,
                                     gap=gap, ret=trade_ret(d, entry, eb[0]),
                                     flip=trade_ret(-d, entry, eb[0])))

# After-hours: decide at T on day D (vs 16:00 close of D), enter bar T, exit next session 08:00 (pre) or 09:30 open.
for D in ext_days:
    if D not in close1559:
        skip["ah_no_p0"] += 1
        continue
    N = cal_next.get(D)
    if N is None or N not in mdays:
        skip["ah_no_next"] += 1
        continue
    P0m, P0b = close1559[D], bt.get(T(D, "15:59"))
    if P0b is None:
        skip["ah_no_btc_p0"] += 1
        continue
    for tt in AH_TIMES:
        ref = T(D, tt) - MIN
        pm = last_print(ref)
        if pm is None:
            skip["ah_stale"] += 1
            continue
        bb = bt.get(ref)
        entry = Md.get(T(D, tt))
        if bb is None or entry is None or entry[4] <= 0:
            skip["ah_no_entry"] += 1
            continue
        mret, bret = math.log(pm / P0m), math.log(bb / P0b)
        for bname, beta in BETAS.items():
            gap = beta * bret - mret
            for thr in THRS:
                if abs(gap) <= thr:
                    continue
                d = 1 if gap > 0 else -1
                for ex, pre in (("08:00", True), ("09:30", False)):
                    eb = Md.get(T(N, ex))
                    if eb is None or eb[4] <= 0:
                        skip["ah_no_exit"] += 1
                        continue
                    rows.append(dict(window="ah", day=D, decide=tt, beta=bname, thr=thr, exit=f"N{ex}", dir=d,
                                     gap=gap, ret=trade_ret(d, entry, eb[0], pre_exit=pre),
                                     flip=trade_ret(-d, entry, eb[0], pre_exit=pre)))

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/premarket_trades.csv", index=False)


def tstats(r):
    r = np.asarray(r, dtype=float)
    n = len(r)
    if n < 3:
        return dict(n=n, win=np.nan, mean_bp=np.nan, t=np.nan, avg_win_bp=np.nan, avg_loss_bp=np.nan)
    sd = r.std(ddof=1)
    return dict(n=n, win=(r > 0).mean(), mean_bp=r.mean() * 1e4, t=r.mean() / (sd / math.sqrt(n)),
                avg_win_bp=r[r > 0].mean() * 1e4 if (r > 0).any() else np.nan,
                avg_loss_bp=r[r <= 0].mean() * 1e4 if (r <= 0).any() else np.nan)


summ = []
for (win, decide, beta, thr, ex), g in df.groupby(["window", "decide", "beta", "thr", "exit"]):
    s = tstats(g.ret)
    f = tstats(g.flip)
    summ.append(dict(window=win, decide=decide, beta=beta, thr=thr, exit=ex, **{k: s[k] for k in s},
                     flip_n=f["n"], flip_mean_bp=f["mean_bp"], flip_t=f["t"], flip_win=f["win"]))
S = pd.DataFrame(summ).sort_values(["window", "t"], ascending=[True, False])
S.to_csv(f"{OUT}/premarket_summary.csv", index=False)

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
print(f"beta_dev={beta_dev:.4f} (corr {corr_dev:.3f}, n={n_dev}, dev<=2022-06-30) | "
      f"beta_chk_rth={beta_chk:.4f} (corr {corr_chk:.3f}, n={n_chk}, 2022-07..2023-12)")
print("ext days (2026 window with prior close):", len(ext_days))
print("skips:", dict(skip))
print("trade rows:", len(df), df.groupby("window").size().to_dict())
print(S.round(4).to_string(index=False))
