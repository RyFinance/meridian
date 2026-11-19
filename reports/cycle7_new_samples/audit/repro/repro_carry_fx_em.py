"""Independent reproduction of CARRY-FX on FX-EM from spec text only (no builder engine/runner code used).

Spec: research/cycle6/specs/CARRY-FX.md (sha 4b154993...). Sample: research/cycle7/samples/CARRY-FX__FX-EM.md.
Conventions chosen from the spec text (documented where the spec is silent):
  - signal month t: the foreign-rate row dated in calendar month t; US rate = the USD_RF_3M row dated in month t.
  - carry = (i* - i)/(1 + i); ranking is invariant to the common 1/(1+i) factor.
  - eligible at t iff both rates exist at t; defined iff N_t >= 4.
  - w = z (rank - (N+1)/2), average ranks for ties, z so that longs sum +1, shorts -1.
  - net return labelled month t+1: per instrument, compound daily excess returns strictly after its first session of
    month t+1 through its first session of month t+2 (or through its last available session if none exists).
    A held instrument with no return in the period contributes 0 and is counted unpriced.
  - cost = 3bp * sum|w_new - w_drift|, w_drift = w_old*(1+R_i) [DRIFT='raw'] or w_old*(1+R_i)/(1+R_p) ['norm'].
  - control = mean over 100 random-rank books, signal iid U(0,1) on the same eligible set,
    rng = np.random.default_rng(20260926), draws book-major then month-major.
"""
from __future__ import annotations
import json, sys, hashlib
import numpy as np, pandas as pd

ROOT = "/Users/rytty/CCP/quant_v7"
VIEW = f"{ROOT}/data/cycle7/snapshot_store/versions/cycle7_fx_em_v1/view/eval"
OUT = f"{ROOT}/reports/cycle7_new_samples/audit/repro"
INSTR = ["FX_ARS","FX_BRL","FX_CLP","FX_COP","FX_CZK","FX_DKK","FX_HUF","FX_IDR","FX_ILS","FX_INR","FX_ISK",
         "FX_KRW","FX_MXN","FX_MYR","FX_PEN","FX_PHP","FX_PLN","FX_RUB","FX_SGD","FX_THB","FX_TRY","FX_ZAR"]
BP = 3e-4
MIN_N = 4


def load():
    cand = pd.read_csv(f"{VIEW}/candidate_list.csv")
    cand = cand[(cand["class"] == "FX") & (cand.qa_status == "PASS") & cand.market_id.isin(INSTR)]
    assert sorted(cand.market_id) == INSTR
    win = {r.market_id: (pd.Timestamp(r.first_date), pd.Timestamp(r.last_date)) for r in cand.itertuples()}
    d = pd.read_parquet(f"{VIEW}/panels/daily_excess_FX.parquet")
    d = d[d.market_id.isin(INSTR)]
    d = d[[win[m][0] <= t <= win[m][1] for m, t in zip(d.market_id, d.date)]]
    daily = d.pivot(index="date", columns="market_id", values="value").reindex(columns=INSTR).sort_index()
    f = pd.read_parquet(f"{VIEW}/signals/fx_foreign_rate_monthly.parquet")
    f = f[f.market_id.isin(INSTR)]
    f = f[[win[m][0] <= t <= win[m][1] for m, t in zip(f.market_id, f.date)]]
    f["m"] = f.date.dt.to_period("M")
    fr = f.pivot(index="m", columns="market_id", values="value").reindex(columns=INSTR)
    u = pd.read_parquet(f"{VIEW}/series/usd_rate_3m_monthly.parquet")
    u = u[u.market_id == "USD_RF_3M"].sort_values("date")
    u["m"] = u.date.dt.to_period("M")
    us = u.groupby("m").value.last()
    return daily, fr, us


def signal(fr, us):
    months = fr.index.union(us.index).sort_values()
    fr = fr.reindex(months)
    usv = us.reindex(months)
    carry = (fr.sub(usv, axis=0)).div(1.0 + usv, axis=0)
    return carry  # NaN where not eligible


def rank_weights(sig_row: np.ndarray) -> np.ndarray:
    w = np.zeros_like(sig_row)
    ok = ~np.isnan(sig_row)
    n = ok.sum()
    if n < MIN_N:
        return w
    r = pd.Series(sig_row[ok]).rank(method="average").to_numpy()
    c = r - (n + 1) / 2.0
    s = np.abs(c).sum()
    if s == 0:
        return w
    w[ok] = c * (2.0 / s)
    return w


def hold_returns(daily: pd.DataFrame, months):
    """R[label month m] per instrument: compound excess returns after first session of m through first session of m+1."""
    idx = daily.index
    per = idx.to_period("M")
    out = {}
    arr = daily.to_numpy()
    lg = np.log1p(arr)
    for j, c in enumerate(daily.columns):
        col = arr[:, j]
        have = ~np.isnan(col)
        dts = idx[have]
        lv = lg[have, j]
        cs = np.concatenate([[0.0], np.cumsum(lv)])  # cs[k] = sum of first k obs
        pm = dts.to_period("M")
        # position of first session in each month
        first_pos = pd.Series(np.arange(len(dts)), index=pm).groupby(level=0).first()
        res = {}
        for m in months:
            if m not in first_pos.index:
                res[m] = np.nan
                continue
            a = first_pos[m]
            nxt = first_pos[first_pos.index > m]
            if len(nxt) and nxt.index[0] == m + 1:
                b = nxt.iloc[0]
            else:  # no session in m+1: hold through the last available session before the next priced month
                b = nxt.iloc[0] - 1 if len(nxt) else len(dts) - 1
            if b <= a:
                res[m] = np.nan
                continue
            res[m] = np.expm1(cs[b + 1] - cs[a + 1])
        out[c] = res
    return pd.DataFrame(out).reindex(index=months, columns=daily.columns)


def gross_returns(daily, months):
    lg = np.log1p(daily)
    per = daily.index.to_period("M")
    s = lg.groupby(per).sum(min_count=1)
    return np.expm1(s).reindex(months)


def book(W: np.ndarray, R: np.ndarray, drift: str):
    """W[t]: weights for label month t (already lagged); R[t]: holding returns. Returns ret, rbc, cost, turnover, unpriced."""
    T, K = W.shape
    Rz = np.where(np.isnan(R), 0.0, R)
    prev_drift = np.zeros(K)
    rbc = np.zeros(T); cost = np.zeros(T); to = np.zeros(T); unp = np.zeros(T, int); nheld = np.zeros(T, int)
    for t in range(T):
        w = W[t]
        to[t] = np.abs(w - prev_drift).sum()
        cost[t] = BP * to[t]
        rbc[t] = (w * Rz[t]).sum()
        held = w != 0
        nheld[t] = held.sum(); unp[t] = (held & np.isnan(R[t])).sum()
        wd = w * (1.0 + Rz[t])
        if drift == "norm":
            wd = wd / (1.0 + rbc[t])
        prev_drift = wd
    return rbc - cost, rbc, cost, to, unp, nheld


def hold_returns_carry_day1(daily, months):
    """POST-HOC alternative (adopted after reading builder panel.py): an instrument with no session in month m
    still earns its first-session return of m+1 in period m (days 2..end of m plus day 1 of m+1)."""
    R = hold_returns(daily, months)
    idx = daily.index
    for c in daily.columns:
        s = daily[c].dropna()
        pm = s.index.to_period("M")
        have = set(pm)
        for m in months:
            if m not in have and (m + 1) in have:
                R.loc[m, c] = s[pm == (m + 1)].iloc[0]
    return R


def run(drift="raw", seed=20260926, n_books=100, daily=None, fr=None, us=None, draw_order="book_month",
        day1=False):
    if daily is None:
        daily, fr, us = load()
    carry = signal(fr, us)
    sig_months = carry.index
    S = carry.to_numpy()
    Wsig = np.vstack([rank_weights(S[i]) for i in range(len(S))])
    defined = (~np.isnan(S)).sum(1) >= MIN_N
    first_sig = sig_months[np.argmax(defined)]
    # label months: signal month + 1, from first defined signal to last defined signal
    last_data = daily.index.max().to_period("M")  # window ends at the last month with any daily data
    lab = pd.period_range(first_sig + 1, min(sig_months[defined][-1] + 1, last_data), freq="M")
    sig_idx = {m: i for i, m in enumerate(sig_months)}
    W = np.vstack([Wsig[sig_idx[m - 1]] if (m - 1) in sig_idx else np.zeros(len(INSTR)) for m in lab])
    R = (hold_returns_carry_day1 if day1 else hold_returns)(daily, lab).to_numpy()
    G = gross_returns(daily, lab).to_numpy()
    net, rbc, cost, to, unp, nheld = book(W, R, drift)
    gross = (W * np.where(np.isnan(G), 0, G)).sum(1)
    # control
    rng = np.random.default_rng(seed)
    elig = ~np.isnan(S)
    # "builder" draw order (POST-HOC, from engine controls.py): book b uses default_rng([seed, b]) and draws a full
    # (panel months 1973-03..last daily month) x (sorted universe) uniform matrix, masked to the eligible set.
    full_months = pd.period_range(daily.index.min().to_period("M"), daily.index.max().to_period("M"), freq="M")
    ctrl = np.zeros(len(lab))
    lab_def = np.array([((m - 1) in sig_idx) and defined[sig_idx[m - 1]] for m in lab])
    for b in range(n_books):
        if draw_order == "builder":
            U = pd.DataFrame(np.random.default_rng([int(seed), b]).random((len(full_months), len(INSTR))),
                             index=full_months)
        Wc = np.zeros_like(W)
        for k, m in enumerate(lab):
            if not lab_def[k]:
                continue
            e = elig[sig_idx[m - 1]]
            z = np.full(len(INSTR), np.nan)
            if draw_order == "builder":
                z[e] = U.loc[m - 1].to_numpy()[e]
            else:
                z[e] = rng.random(e.sum())
            Wc[k] = rank_weights(z)
        ctrl += book(Wc, R, drift)[0]
    ctrl /= n_books
    df = pd.DataFrame({"month": lab.astype(str), "net": net, "ret_before_cost": rbc, "cost": cost, "turnover": to,
                       "n_held": nheld, "unpriced": unp, "gross": gross, "control": ctrl, "active": net - ctrl,
                       "defined": lab_def})
    return df, W, lab


if __name__ == "__main__":
    drift = sys.argv[1] if len(sys.argv) > 1 else "raw"
    mode = sys.argv[2] if len(sys.argv) > 2 else "independent"   # or "aligned" (builder seeding + day-1 rule)
    kw = dict(draw_order="builder", day1=True) if mode == "aligned" else {}
    df, W, lab = run(drift, **kw)
    tag = drift if mode == "independent" else f"{drift}_aligned"
    df.to_csv(f"{OUT}/repro_series_{tag}.csv", index=False)
    pd.DataFrame(W, index=lab.astype(str), columns=INSTR).to_csv(f"{OUT}/repro_weights_{tag}.csv")
    print(df.head(), len(df), df.defined.all())
