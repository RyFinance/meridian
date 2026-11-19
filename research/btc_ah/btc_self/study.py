"""BTC-only after-hours study (agent btc_self).

Sealed holdout: every row with timestamp >= 2026-08-11 00:00 UTC is dropped
immediately after loading. Dev = trade dates 2018-01-01..2022-06-30,
check = 2022-07-01..2026-08-10.

Timing convention:
  signal price at time T  = close of the last bar labelled <= T-1min (info strictly before T)
  fill price at time T    = open of the first bar labelled >= T (next bar)
Costs (round trip): spot 10 bp (5 bp/side); IBIT proxy 6 bp (3 bp/side) only when
entry and exit are both regular hours (09:30-16:00 ET).
"""
import json
from datetime import datetime, timedelta, timezone, date as Date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import stats as sps

SRC = "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/btc_self"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
CUT = pd.Timestamp("2026-08-11", tz="UTC")  # exclusive: keep dates <= 2026-08-10
DEV_END = Date(2022, 6, 30)
START = Date(2018, 1, 1)
TOL = 300  # seconds of tolerance for sparse minute bars
COST_SPOT = 0.0010  # round trip
COST_IBIT = 0.0006  # round trip, RTH only

# ---------- load and seal ----------
df = pd.read_parquet(SRC, columns=["timestamp", "open", "high", "low", "close"])
df = df[df["timestamp"] < CUT]
df = df.sort_values("timestamp").drop_duplicates("timestamp")
ts = df["timestamp"].values.astype("datetime64[s]").astype(np.int64)
OP = df["open"].values
HI = df["high"].values
LO = df["low"].values
CL = df["close"].values
N = len(ts)
print("bars kept:", N, "first", df.timestamp.iloc[0], "last", df.timestamp.iloc[-1])

# NYSE full-day holidays (hardcoded; early closes ignored)
HOL = {
    Date(2018,1,1), Date(2018,1,15), Date(2018,2,19), Date(2018,3,30), Date(2018,5,28),
    Date(2018,7,4), Date(2018,9,3), Date(2018,11,22), Date(2018,12,5), Date(2018,12,25),
    Date(2019,1,1), Date(2019,1,21), Date(2019,2,18), Date(2019,4,19), Date(2019,5,27),
    Date(2019,7,4), Date(2019,9,2), Date(2019,11,28), Date(2019,12,25),
    Date(2020,1,1), Date(2020,1,20), Date(2020,2,17), Date(2020,4,10), Date(2020,5,25),
    Date(2020,7,3), Date(2020,9,7), Date(2020,11,26), Date(2020,12,25),
    Date(2021,1,1), Date(2021,1,18), Date(2021,2,15), Date(2021,4,2), Date(2021,5,31),
    Date(2021,7,5), Date(2021,9,6), Date(2021,11,25), Date(2021,12,24),
    Date(2022,1,17), Date(2022,2,21), Date(2022,4,15), Date(2022,5,30), Date(2022,6,20),
    Date(2022,7,4), Date(2022,9,5), Date(2022,11,24), Date(2022,12,26),
    Date(2023,1,2), Date(2023,1,16), Date(2023,2,20), Date(2023,4,7), Date(2023,5,29),
    Date(2023,6,19), Date(2023,7,4), Date(2023,9,4), Date(2023,11,23), Date(2023,12,25),
    Date(2024,1,1), Date(2024,1,15), Date(2024,2,19), Date(2024,3,29), Date(2024,5,27),
    Date(2024,6,19), Date(2024,7,4), Date(2024,9,2), Date(2024,11,28), Date(2024,12,25),
    Date(2025,1,1), Date(2025,1,9), Date(2025,1,20), Date(2025,2,17), Date(2025,4,18),
    Date(2025,5,26), Date(2025,6,19), Date(2025,7,4), Date(2025,9,1), Date(2025,11,27),
    Date(2025,12,25),
    Date(2026,1,1), Date(2026,1,19), Date(2026,2,16), Date(2026,4,3), Date(2026,5,25),
    Date(2026,6,19), Date(2026,7,3), Date(2026,9,7), Date(2026,11,26), Date(2026,12,25),
}
days = []
d = Date(2017, 8, 1)
while d <= Date(2026, 8, 10):
    if d.weekday() < 5 and d not in HOL:
        days.append(d)
    d += timedelta(days=1)


def ep(d, hh, mm):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp()


def fill_open(t):
    t = np.asarray(t, float)
    idx = np.searchsorted(ts, t, side="left")
    ic = np.minimum(idx, N - 1)
    ok = (idx < N) & ((ts[ic] - t) <= TOL)
    return OP[ic], ok, idx


def sig_close(t):
    t = np.asarray(t, float)
    idx = np.searchsorted(ts, t - 60, side="right") - 1
    ic = np.maximum(idx, 0)
    ok = (idx >= 0) & ((t - 60 - ts[ic]) <= TOL)
    return CL[ic], ok


rows = []
for i, d in enumerate(days):
    if d < START or i == 0:
        continue
    p = days[i - 1]
    t16 = ep(p, 16, 0)
    base = datetime.fromtimestamp(ep(d, 16, 0), tz=UTC)
    hand = {}
    for k in (0, 3, 8):
        cand = datetime(base.year, base.month, base.day, k, tzinfo=UTC)
        if cand <= base:
            cand += timedelta(days=1)
        hand[k] = cand.timestamp()
    rows.append(dict(
        d=d, p=p, t_p1600=t16, t0930=ep(d, 9, 30), t1030=ep(d, 10, 30),
        t1200=ep(d, 12, 0), t1600=ep(d, 16, 0),
        t_next0930=ep(days[i + 1], 9, 30) if i + 1 < len(days) else np.nan,
        h0=hand[0], h3=hand[3], h8=hand[8],
        is_mon=d.weekday() == 0, p_fri=p.weekday() == 4,
    ))
R = pd.DataFrame(rows)
R["year"] = [x.year for x in R["d"]]
R["dev"] = [x <= DEV_END for x in R["d"]]
print("trade days", len(R), "dev", R.dev.sum(), "check", (~R.dev).sum())


def summarize(gross, cost, dates_mask_dev, dates_year):
    """gross, cost arrays for one split; returns stats dict."""
    gross = np.asarray(gross, float)
    n = len(gross)
    if n < 5:
        return dict(n=n)
    net = gross - cost
    sd = net.std(ddof=1)
    t = net.mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan
    p = 2 * (1 - sps.t.cdf(abs(t), n - 1)) if np.isfinite(t) else np.nan
    return dict(
        n=n,
        win=float((net > 0).mean()),
        mean_net=float(net.mean()),
        t=float(t),
        p=float(p),
        avg_win=float(net[net > 0].mean()) if (net > 0).any() else np.nan,
        avg_loss=float(net[net <= 0].mean()) if (net <= 0).any() else np.nan,
        mirror_mean_net=float((-gross - cost).mean()),
        gross_mean=float(gross.mean()),
    )


def year_means(gross, cost, years):
    s = pd.DataFrame({"y": years, "net": np.asarray(gross) - cost})
    return {int(k): round(float(v), 5) for k, v in s.groupby("y")["net"].mean().items()}


results = []  # one record per variant, both splits
trade_store = {}  # variant name -> dict(dev=..., check=...) arrays for top rules


def record(family, name, params, gross, cost, years, dev_mask, drift_gross_dev, drift_gross_chk, rth):
    rth = np.asarray(rth, bool)
    """gross/cost/years/dev_mask are aligned arrays for the variant's trades.
    drift_* = unconditional long gross over all valid days in that split."""
    rec = dict(family=family, name=name, **params)
    for split, m in (("dev", dev_mask), ("chk", ~dev_mask)):
        g = gross[m]
        c = cost[m]
        st = summarize(g, c, None, None)
        for k, v in st.items():
            rec[f"{split}_{k}"] = v
        if len(g) >= 5:
            ci = np.where(rth[m], COST_IBIT, c) if rth is not None else c
            rec[f"{split}_ibit_mean_net"] = float((g - ci).mean())
            rec[f"{split}_years"] = year_means(g, c, years[m])
        rec[f"{split}_drift_gross"] = float(drift_gross_dev if split == "dev" else drift_gross_chk)
    results.append(rec)
    trade_store[name] = dict(gross=gross, cost=cost, years=years, dev=dev_mask, rth=rth)


def quant_thr(absvals, dev_mask, qs):
    dv = absvals[dev_mask & np.isfinite(absvals)]
    return {q: (0.0 if q == 0 else float(np.quantile(dv, q))) for q in qs}


# ======================================================================
# H1: overnight move (prev 16:00 ET -> 09:30 ET) vs RTH continuation
# ======================================================================
pxp, okp = sig_close(R.t_p1600.values)
pxo, oko = sig_close(R.t0930.values)
Ov = pxo / pxp - 1
valid_o = okp & oko & np.isfinite(Ov)
ent, oke, _ = fill_open(R.t0930.values)
ex = {}
for hz, col in ((60, "t1030"), (150, "t1200"), (390, "t1600")):
    px_, okx, _ = fill_open(R[col].values)
    ex[hz] = (px_, okx)

absO = np.abs(Ov)
QS = [0, 0.5, 0.75, 0.9]
thr_h1 = quant_thr(absO, R.dev.values & valid_o, QS)
dev_mask_h1 = R.dev.values
years = R.year.values
H1_COUNT = 0
for hz, (px_, okx) in ex.items():
    base_ok = valid_o & oke & okx
    dr_dev = np.nanmean(px_[base_ok & dev_mask_h1] / ent[base_ok & dev_mask_h1] - 1)
    dr_chk = np.nanmean(px_[base_ok & ~dev_mask_h1] / ent[base_ok & ~dev_mask_h1] - 1)
    for mode in ("down", "up", "both"):
        for q in QS:
            thr = thr_h1[q]
            if mode == "down":
                sel = Ov <= -thr
            elif mode == "up":
                sel = Ov >= thr
            else:
                sel = absO >= thr
            for action in ("cont", "rev"):
                H1_COUNT += 1
                m = base_ok & sel & (Ov != 0 if q == 0 else True)
                sgn = np.sign(Ov) * (1 if action == "cont" else -1)
                gross = (sgn * (px_ / ent - 1))[m]
                cost = np.full(gross.shape, COST_SPOT)
                name = f"H1|hz{hz}|{mode}|q{q}|{action}"
                record("H1", name, dict(horizon_min=hz, mode=mode, q=q, action=action, cost_tier="spot/ibit(RTH)"),
                       gross, cost, years[m], dev_mask_h1[m],
                       dr_dev, dr_chk, np.ones(gross.shape, bool))
                trade_store[name]["dates"] = R.d.values[m]
                trade_store[name]["ibit_gross"] = gross
print("H1 variants:", H1_COUNT)

# ======================================================================
# H2: weekend gap (Fri 16:00 ET -> Mon 09:30 ET). Fade-to-fill vs continuation.
# ======================================================================
gap_rows = []
for j in range(len(R)):
    r = R.iloc[j]
    if not (r.is_mon and r.p_fri):
        continue
    ref_px, okr = sig_close([r.t_p1600])
    ref = float(ref_px[0])
    pre, okpre = sig_close([r.t0930])
    if not (okr[0] and okpre[0]):
        continue
    g = float(pre[0] / ref - 1)
    ia = np.searchsorted(ts, r.t_p1600, side="left")
    ib = np.searchsorted(ts, r.t0930, side="left")
    if g > 0:
        prefilled = bool(LO[ia:ib].size and LO[ia:ib].min() <= ref)
    elif g < 0:
        prefilled = bool(HI[ia:ib].size and HI[ia:ib].max() >= ref)
    else:
        prefilled = True
    e_px, oke2, i0 = fill_open([r.t0930])
    if not oke2[0]:
        continue
    i0 = int(i0[0])
    iA = int(np.searchsorted(ts, r.t1600, side="left"))
    iB = int(np.searchsorted(ts, r.t_next0930, side="left")) if np.isfinite(r.t_next0930) else -1
    if iB < 0 or iB >= N or iA >= N:
        continue
    # RTH fill and 24h-to-next-open fill, for gap-fill stats (after entry only)
    if g > 0:
        fill_rth = bool(LO[i0:iA].min() <= ref) if iA > i0 else False
        fill_24 = bool(LO[i0:iB].min() <= ref) if iB > i0 else False
    else:
        fill_rth = bool(HI[i0:iA].max() >= ref) if iA > i0 else False
        fill_24 = bool(HI[i0:iB].max() >= ref) if iB > i0 else False
    gap_rows.append(dict(d=r.d, year=r.year, dev=bool(r.dev), g=g, ref=ref, entry=float(e_px[0]),
                         i0=i0, iA=iA, iB=iB, prefilled=prefilled, fill_rth=fill_rth, fill_24=fill_24,
                         tA=r.t1600, tB=r.t_next0930))
G = pd.DataFrame(gap_rows)
G["absg"] = G.g.abs()
print("Mondays with usable weekend gap:", len(G))

gs = []
for split, m in (("dev", G.dev), ("chk", ~G.dev)):
    sub = G[m]
    gs.append(dict(split=split, mondays=len(sub), crossed_ref_overnight_share=float(sub.prefilled.mean()),
                   p_fill_rth=float(sub.fill_rth.mean()) if len(sub) else np.nan,
                   p_fill_24h=float(sub.fill_24.mean()) if len(sub) else np.nan,
                   median_absgap_pct=float(sub.absg.median() * 100)))
GAP_STATS = gs
print("weekend gap-fill stats:", json.dumps(gs, indent=1))

# quantile thresholds for |gap| on dev, non-prefilled Mondays
G2 = G.copy()  # fills are measured only after the 09:30 entry; the overnight crossing is not a filter
thr_g = {}
for q in [0, 0.5, 0.75]:
    thr_g[q] = 0.0 if q == 0 else float(np.quantile(G2.absg[G2.dev], q))

def sim_path(i0, iex, entry, dirn, stop, tgt):
    """Walk bars i0..iex-1. Stop first if both hit in one bar. Returns exit price, or None if neither."""
    lo = LO[i0:iex]
    hi = HI[i0:iex]
    op = OP[i0:iex]
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
        if dirn > 0:
            return min(stop, o)
        return max(stop, o)
    o = op[jt]
    if dirn > 0:
        return max(tgt, o)
    return min(tgt, o)


H2_COUNT = 0
for side in ("fade", "cont"):
    for qg, gthr in thr_g.items():
        for s in (0.5, 1.0, 2.0, None):
            for exitw in ("mon1600", "tue0930"):
                H2_COUNT += 1
                grs, costs, yrs, devs, dts, rth_flags = [], [], [], [], [], []
                for _, r in G2.iterrows():
                    if r.absg < gthr or r.absg == 0:
                        continue
                    dirn = (-1 if r.g > 0 else 1) if side == "fade" else (1 if r.g > 0 else -1)
                    stop = None if s is None else r.entry * (1 - dirn * s * r.absg)
                    tgt = r.ref if side == "fade" else None
                    iex = r.iA if exitw == "mon1600" else r.iB
                    xp = sim_path(r.i0, iex, r.entry, dirn, stop, tgt)
                    if xp is None:
                        xp = OP[iex]  # time exit at next-bar open
                    gross = dirn * (xp / r.entry - 1)
                    grs.append(gross)
                    costs.append(COST_SPOT)
                    rth_flags.append(exitw == "mon1600")
                    yrs.append(r.year)
                    devs.append(bool(r.dev))
                    dts.append(r.d)
                if len(grs) == 0:
                    continue
                grs = np.array(grs)
                costs = np.array(costs)
                devs = np.array(devs)
                yrs = np.array(yrs)
                drift_dev = float(np.mean(
                    [OP[int(r.iB)] / OP[int(r.i0)] - 1 for _, r in G2[G2.dev].iterrows()])) if exitw == "tue0930" else np.nan
                drift_chk = float(np.mean(
                    [OP[int(r.iB)] / OP[int(r.i0)] - 1 for _, r in G2[~G2.dev].iterrows()])) if exitw == "tue0930" else np.nan
                name = f"H2|{side}|gap>={qg}|stop{s}|exit{exitw}"
                record("H2", name, dict(side=side, gap_q=qg, stop_mult=(s if s is not None else "none"),
                                        exit=exitw, cost_tier="spot/ibit(Mon RTH exit)"),
                       grs, costs, yrs, devs, drift_dev, drift_chk, np.array(rth_flags))
                trade_store[name]["dates"] = np.array(dts)
print("H2 variants:", H2_COUNT)

# ======================================================================
# H4: session handoffs (00:00, 03:00, 08:00 UTC) after the US 16:00 ET -> handoff move
# ======================================================================
H4_COUNT = 0
hand_thr = {}
for k in (0, 3, 8):
    H = R[f"h{k}"].values
    pxH, okH = sig_close(H)
    pxC, okC = sig_close(R.t1600.values)
    prior = pxH / pxC - 1
    okk = okH & okC & np.isfinite(prior)
    Hent, okE, _ = fill_open(H)
    exits = {}
    for hz in (60, 180):
        pxX, okX, _ = fill_open(H + hz * 60)
        exits[hz] = (pxX, okX)
    hand_thr[k] = {q: (0.0 if q == 0 else float(np.quantile(np.abs(prior)[okk & R.dev.values], q))) for q in QS}
    for hz, (pxX, okX) in exits.items():
        base_ok = okk & okE & okX
        dr_dev = np.nanmean(pxX[base_ok & R.dev.values] / Hent[base_ok & R.dev.values] - 1)
        dr_chk = np.nanmean(pxX[base_ok & ~R.dev.values] / Hent[base_ok & ~R.dev.values] - 1)
        for mode in ("down", "up", "both"):
            for q in QS:
                thr = hand_thr[k][q]
                if mode == "down":
                    sel = prior <= -thr
                elif mode == "up":
                    sel = prior >= thr
                else:
                    sel = np.abs(prior) >= thr
                for action in ("cont", "rev"):
                    H4_COUNT += 1
                    m = base_ok & sel
                    sgn = np.sign(prior) * (1 if action == "cont" else -1)
                    gross = (sgn * (pxX / Hent - 1))[m]
                    cost = np.full(gross.shape, COST_SPOT)
                    name = f"H4|h{k}utc|hz{hz}|{mode}|q{q}|{action}"
                    record("H4", name, dict(handoff_utc=k, horizon_min=hz, mode=mode, q=q, action=action,
                                            cost_tier="spot"),
                           gross, cost, years[m], R.dev.values[m], dr_dev, dr_chk, np.zeros(gross.shape, bool))
                    trade_store[name]["dates"] = R.d.values[m]
print("H4 variants:", H4_COUNT)

RES = pd.DataFrame(results)
RES.to_pickle(f"{OUT}/variants.pkl")
TOTAL = len(RES)
print("TOTAL variants:", TOTAL, "(H1", H1_COUNT, "H2", H2_COUNT, "H4", H4_COUNT, ")")
pd.Series(thr_h1).to_json(f"{OUT}/thr_h1.json")
json.dump(dict(gap=GAP_STATS, thr_g={str(k): v for k, v in thr_g.items()},
               hand_thr={str(k): {str(q): v for q, v in d_.items()} for k, d_ in hand_thr.items()},
               thr_h1={str(q): v for q, v in thr_h1.items()}), open(f"{OUT}/thresholds_and_gap.json", "w"), indent=1)
G.to_pickle(f"{OUT}/weekend_gaps.pkl")
import pickle
with open(f"{OUT}/trade_store.pkl", "wb") as fh:
    pickle.dump(trade_store, fh)
print("saved")
