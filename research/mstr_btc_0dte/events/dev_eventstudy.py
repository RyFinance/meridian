"""DEV event study (2020-08..2023-12 only): MSTR BTC-purchase 8-K announcement drift.
Entry = official close of the first session at/after the 8-K acceptance time (noon-ish ET; the only
real-time-observable stamp we have). Exits: next open, next close, +3 close, +5 close.
Raw = MSTR log return. Hedged = MSTR - beta*BTC (beta = 120d rolling, clipped .3-3, up to D-1).
Costs per side: MSTR close fill 1 bp, open fill 3 bp, commission $0.005/sh; BTC leg 5 bp/side; BTC carry 5%/yr.
This script must NOT read any 2024+ prices. Enforcement: asserts on event dates only <= 2023-12-31.
"""
from __future__ import annotations
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # research/mstr_btc_0dte
P = pd.read_parquet(ROOT / "premium/panel.parquet").sort_index()
EV = pd.read_parquet(ROOT / "events/events_btc.parquet")

SESS = P.index
def session_after(ts_et: pd.Timestamp, same_day_ok: bool) -> int:
    d = ts_et.tz_convert("America/New_York") if ts_et.tzinfo else ts_et
    day = d.normalize().tz_localize(None)
    idx = SESS.searchsorted(day, side="right" if not same_day_ok else "left")
    return idx


def beta_at(i: int, bw: int = 120) -> float:
    lm = np.log(P.mstr); lb = np.log(P.btc)
    r = pd.DataFrame({"m": lm.diff(), "b": lb.diff()}).iloc[max(0, i - bw):i + 1]
    v = r.b.var()
    if not np.isfinite(v) or v <= 0 or len(r) < 30:
        return np.nan
    return float(np.clip(r.m.cov(r.b) / v, 0.3, 3.0))


def mstr_cost(entry_kind: str, exit_kind: str, px: float) -> float:
    slip = {"close": 1.0, "open": 3.0}
    c = slip[entry_kind] + slip[exit_kind]
    c += 1e4 * 0.005 / px  # commission per side, in bp
    c += 0.3  # SEC/TAF-ish on the sell side, bp
    return c


def run(events: pd.DataFrame, stress: float = 1.0):
    rows = []
    for _, e in events.iterrows():
        acc = pd.Timestamp(e["et"])
        same = acc.hour < 16 or (acc.hour == 15 and acc.minute < 55)
        i = session_after(acc, same_day_ok=same)
        if i >= len(SESS) - 6:
            continue
        bta = beta_at(i - 1)
        if not np.isfinite(bta):
            continue
        m0, b0 = P.mstr.iloc[i], P.btc.iloc[i]
        for hz, ek, xk, xm, xb in [
            ("to_open1", "close", "open", P.mstr_open.iloc[i + 1], P.btc_open.iloc[i + 1]),
            ("to_close1", "close", "close", P.mstr.iloc[i + 1], P.btc.iloc[i + 1]),
            ("to_close3", "close", "close", P.mstr.iloc[i + 3], P.btc.iloc[i + 3]),
            ("to_close5", "close", "close", P.mstr.iloc[i + 5], P.btc.iloc[i + 5]),
        ]:
            if not (np.isfinite(xm) and np.isfinite(xb)):
                continue
            days = (SESS[i + (1 if hz == "to_open1" else int(hz[-1]))] - SESS[i]).days
            r_m = np.log(xm / m0); r_b = np.log(xb / b0)
            gross = r_m; hedge = r_m - bta * r_b
            cm = mstr_cost("close", ek, m0) * stress
            cb = (2 * 5.0 + 1e4 * 0.05 * days / 365) * stress  # BTC leg slip+carry, bp
            # costs on MSTR only for the raw trade; MSTR+BTC for the hedged
            net_raw = gross - cm * 1e-4
            net_hedge = hedge - (cm + cb) * 1e-4
            rows.append(dict(entry=SESS[i], horizon=hz, beta=bta, gross=gross, hedge=hedge,
                             net_raw=net_raw, net_hedge=net_hedge, cm=cm, cb=cb))
    return pd.DataFrame(rows)


def stats(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) < 3:
        return f"n={len(x)}"
    t = x.mean() / x.std() * np.sqrt(len(x))
    return f"n={len(x):3d} mean={x.mean()*1e4:+6.1f}bp win={np.mean(x > 0):.2f} t={t:+5.2f} sum={x.sum()*100:+.1f}%"


def main():
    ev = EV[EV.kind == "purchase"].copy()
    ev = ev[ev.et <= "2023-12-31 23:59"]
    assert ev.et.max() <= pd.Timestamp("2023-12-31 23:59", tz="UTC"), "dev window violated"
    t = run(ev)
    print("events used (dev):", len(ev), "| rows:", len(t))
    print("event dates:", [str(d.date()) for d in ev.filingDate])
    print()
    for hz in ["to_open1", "to_close1", "to_close3", "to_close5"]:
        h = t[t.horizon == hz]
        print(f"[{hz:9s}] raw gross  : {stats(h.gross)}")
        print(f"[{hz:9s}] raw net    : {stats(h.net_raw)}")
        print(f"[{hz:9s}] hedge gross: {stats(h.hedge)}")
        print(f"[{hz:9s}] hedge net  : {stats(h.net_hedge)}")
        print()
    # baseline: all sessions, same windows
    base = []
    for i in range(60, len(SESS) - 6):
        if SESS[i] > pd.Timestamp("2023-12-31"):
            continue
        r_o = np.log(P.mstr_open.iloc[i + 1] / P.mstr.iloc[i])
        r_c1 = np.log(P.mstr.iloc[i + 1] / P.mstr.iloc[i])
        r_c3 = np.log(P.mstr.iloc[i + 3] / P.mstr.iloc[i])
        r_c5 = np.log(P.mstr.iloc[i + 5] / P.mstr.iloc[i])
        base.append(dict(o=r_o, c1=r_c1, c3=r_c3, c5=r_c5))
    B = pd.DataFrame(base)
    print("baseline (all dev sessions, MSTR close-anchored):")
    for c in B.columns:
        print(f"  {c}: {stats(B[c])}")
    # stress view for the two most likely freezes
    ts = run(ev, stress=2.0)
    for hz in ["to_open1", "to_close1", "to_close3", "to_close5"]:
        h = ts[ts.horizon == hz]
        print(f"[stress2x {hz:9s}] raw net: {stats(h.net_raw)} | hedge net: {stats(h.net_hedge)}")
    t.to_csv(ROOT / "events/dev_eventstudy_trades.csv", index=False)
    B.to_csv(ROOT / "events/dev_eventstudy_baseline.csv", index=False)


if __name__ == "__main__":
    main()
