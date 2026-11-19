import sys; sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/pairs")
import numpy as np, pandas as pd, pairs_gap as P
D = P.D; CUT = P.CUT
def load60(t):
    df = pd.read_parquet(f"{D}/{t}_60m.parquet")
    df = df[df.index < CUT + pd.Timedelta(days=1)]           # strictly <= 2026-08-10
    df = df[df.index < pd.Timestamp("2026-08-11")]
    b = df[df.index.time == pd.Timestamp("10:30").time()]    # second regular-hours bar (10:30 ET)
    return pd.Series(b["open"].values, index=b.index.normalize())
MAP = {"COIN": "COIN", "MSTR": "MSTR"}
e10 = {t: load60(t).reindex(P.G) for t in MAP}
ib10 = load60("IBIT").reindex(P.G)
def sens_trades(name, h, X, sign):
    u = P.UNIVERSE[name]
    tb = P.build_trades(name, u, h, ) if False else None
    gs = u["gap"]; beta = P.rolling_beta(gs, P.ref_gap); resid = gs - beta * P.ref_gap
    o_s = u["o"]; c_s = u["c"]
    ex = P.exit_stock(pd.DataFrame({"o": o_s, "c": c_s}), h)
    R = ex / e10[name] - 1                                  # entry at 10:30 bar, not the 09:30 print
    ref_ex = P.ref_exit(h)
    Rref = ref_ex / ib10 - 1                                # IBIT 10:30 entry (IBIT-era only)
    days = P.exit_days(h)
    tb = pd.DataFrame(dict(resid=resid, beta=beta, R=R, Rref=Rref, days=days))
    tb = tb.dropna(); tb = tb[(tb.beta > 0) & (tb.resid.abs() > X)]
    pos = (-np.sign(tb.resid)) if sign == -1 else np.sign(tb.resid)
    pnl = pos * (tb.R - tb.beta * tb.Rref)
    cost = 6.0 * (1 + tb.beta) / 1e4
    out = pd.DataFrame(dict(pnl=pnl, cost=cost, beta=tb.beta, days=tb.days,
                            short_stock=(pos < 0).astype(float), short_etf=(pos > 0).astype(float) * tb.beta))
    return out
rows = []
cases = [("COIN", "C3", 0.02), ("MSTR", "O1", 0.03), ("COIN", "O1", 0.03)]
for name, h, X in cases:
    for sign in (-1, +1):
        tr = sens_trades(name, h, X, sign)
        chk = tr[tr.index > P.DEV_END]
        for fee in P.STOCK_SHORT_FEE:
            net = P.net_series(chk, fee)
            st = P.stats(net)
            rows.append(dict(case=f"{name}|{h}|X{X:.2f}", side="REV" if sign == -1 else "FLIP", stock_borrow=fee,
                             n=st["n"], win=round(st["win"], 2), mean_bp=round(st["mean_bp"], 1), t=round(st["t"], 2),
                             avg_win=round(st["avg_win_bp"], 0), avg_loss=round(st["avg_loss_bp"], 0)))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print("CHECK ONLY, entry at 10:30 bar (60m data, 2024-08..2026-08-10)")
print(out.to_string(index=False))
print("first 60m entry date:", e10["COIN"].dropna().index.min(), " last:", e10["COIN"].dropna().index.max())
