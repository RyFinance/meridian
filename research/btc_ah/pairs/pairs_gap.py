# Market-neutral open-gap pair test: stock vs tradable BTC ETF (BITO pre-2024-01-12, IBIT after).
import numpy as np, pandas as pd, sys, json
D = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/pairs"
CUT = pd.Timestamp("2026-08-10")          # sealed holdout: nothing after this is loaded
START = pd.Timestamp("2021-10-20")        # BITO inception = first tradable hedge
DEV_END = pd.Timestamp("2024-06-30")
IBIT_USE = pd.Timestamp("2024-01-12")     # first day IBIT is used as hedge (its first gap needs a prior close)
BETA_WIN = 120
COST_BP_PER_EXEC = 3.0
REF_BORROW = 0.0025                       # assumed borrow on the ETF leg when shorted
STOCK_SHORT_FEE = [0.0, 0.05, 0.20]       # annual borrow on the short stock leg (sensitivity)
MINERS = ["RIOT", "CLSK", "HUT", "WULF", "IREN", "CIFR", "BTBT"]
THRESH = [0.01, 0.02, 0.03, 0.05]
HORIZ = ["C0", "O1", "C3"]

def load(t):
    df = pd.read_parquet(f"{D}/{t}_1d.parquet")
    df = df[(df.index <= CUT) & (df.index >= START)].sort_index()
    f = df["adj close"] / df["close"]
    return pd.DataFrame({"o": df["open"] * f, "c": df["adj close"]}).dropna()

G = load("BITO").index                       # common calendar (BITO trades every US session)
def on_G(d): return d.reindex(G)
bito, ibit = on_G(load("BITO")), on_G(load("IBIT"))
use_I = pd.Series(G >= IBIT_USE, index=G)
ref_o = bito.o.where(~use_I, ibit.o)          # entry price of the instrument used that day
gap_b = bito.o / bito.c.shift(1) - 1
gap_i = ibit.o / ibit.c.shift(1) - 1
ref_gap = gap_b.where(~use_I, gap_i)
def ref_at(k, kind):                          # exit price k rows ahead of the same instrument
    if kind == "c": return bito.c.shift(-k).where(~use_I, ibit.c.shift(-k))
    return bito.o.shift(-1).where(~use_I, ibit.o.shift(-1))

def exit_stock(d, h):
    if h == "C0": return d.c
    if h == "O1": return d.o.shift(-1)
    return d.c.shift(-3)
def ref_exit(h):
    if h == "C0": return ref_at(0, "c")
    if h == "O1": return ref_at(1, "o")
    return ref_at(3, "c")
def exit_days(h):
    g = pd.Series(G, index=G)
    if h == "C0": return pd.Series(0.0, index=G)
    if h == "O1": return (g.shift(-1) - g).dt.days.astype(float)
    return (g.shift(-3) - g).dt.days.astype(float)

# stocks
def stock_series(t):
    s = on_G(load(t)); return s.o, s.c
def gap_of(o, c): return o / c.shift(1) - 1
UNIVERSE = {}
for t in ["MSTR", "COIN", "MARA"]:
    o, c = stock_series(t); UNIVERSE[t] = dict(o=o, c=c, gap=gap_of(o, c), leg="single")
# miner basket: equal-weight, each name's own open->exit return; needs >=3 valid names
mo, mc, mg, mret = {}, {}, {}, {}
for t in MINERS:
    o, c = stock_series(t); mo[t], mc[t], mg[t] = o, c, gap_of(o, c)
gap_bsk = pd.DataFrame(mg).mean(axis=1, skipna=True).where(pd.DataFrame(mg).notna().sum(axis=1) >= 3)
UNIVERSE["MINERS"] = dict(gap=gap_bsk, leg="basket", names=MINERS, mo=mo, mc=mc)

def rolling_beta(gs, gr):
    cov = gs.rolling(BETA_WIN, min_periods=60).cov(gr)
    var = gr.rolling(BETA_WIN, min_periods=60).var()
    return (cov / var).shift(1)                 # window ends at t-1: past days only

def build_trades(name, u, h):
    """Return per-day arrays for stock leg and ETF leg, for a given exit horizon."""
    gs = u["gap"]
    beta = rolling_beta(gs, ref_gap)
    resid = gs - beta * ref_gap
    # exit-date-aligned stock return
    if u["leg"] == "single":
        o, c = u["o"], u["c"]
        R = exit_stock(pd.DataFrame({"o": o, "c": c}), h) / o - 1
    else:
        Rs = []
        for t in u["names"]:
            ex = exit_stock(pd.DataFrame({"o": u["mo"][t], "c": u["mc"][t]}), h)
            Rs.append(ex / u["mo"][t] - 1)
        Rdf = pd.DataFrame(Rs).T
        R = Rdf.mean(axis=1, skipna=True).where(Rdf.notna().sum(axis=1) >= 3)
        # basket entry-open is basket-level; per-name exits are equal-weight averaged
    Rref = ref_exit(h) / ref_o - 1
    days = exit_days(h)
    return pd.DataFrame(dict(resid=resid, beta=beta, R=R, Rref=Rref, days=days, gs=gs))

def trades(name, u, h, X, sign):
    """sign=-1 reversion (short rich, buy cheap); +1 flip/momentum control."""
    tb = build_trades(name, u, h)
    tb = tb.dropna(subset=["resid", "beta", "R", "Rref"])
    tb = tb[(tb.beta > 0) & (tb.resid.abs() > X)]
    # position: reversion = against sign of residual
    # reversion (sign=-1): stock rich (resid>0) -> short stock; flip control (sign=+1): the opposite
    pos = (-np.sign(tb.resid)) if sign == -1 else (np.sign(tb.resid))   # +1 long stock/short ETF, -1 short stock/long ETF
    pos = pos.astype(float)
    pnl = pos * (tb.R - tb.beta * tb.Rref)                 # per $1 stock-leg notional
    cost = 6.0 * (1 + tb.beta) / 1e4                       # 4 executions x 3bp, legs weighted by notional
    borrow_stock_short = (pos < 0).astype(float)           # stock leg short
    borrow_etf_short = (pos > 0).astype(float) * tb.beta
    out = pd.DataFrame(dict(pnl=pnl, cost=cost, beta=tb.beta, days=tb.days,
                            short_stock=borrow_stock_short, short_etf=borrow_etf_short))
    return out

def stats(x, label=""):
    x = x.dropna()
    n = len(x)
    if n < 2: return dict(n=n)
    m = x.mean(); sd = x.std(ddof=1); t = m / (sd / np.sqrt(n)) if sd > 0 else np.nan
    w = x[x > 0]; l = x[x <= 0]
    return dict(n=n, win=(x > 0).mean(), mean_bp=m * 1e4, t=t,
                avg_win_bp=w.mean() * 1e4 if len(w) else np.nan,
                avg_loss_bp=l.mean() * 1e4 if len(l) else np.nan)

def net_series(tr, fee=0.0):
    borrow = fee * tr.days / 365.0 * tr.short_stock + REF_BORROW * tr.days / 365.0 * tr.short_etf
    return tr.pnl - tr.cost - borrow

def per_year(net):
    g = net.groupby(net.index.year).agg(["count", "mean"])
    return {int(y): (int(r["count"]), round(r["mean"] * 1e4, 1)) for y, r in g.iterrows()}

if __name__ == "__main__":
    rows = []; store = {}
    for name, u in UNIVERSE.items():
        for h in HORIZ:
            for X in THRESH:
                for sign in (-1, +1):
                    tr = trades(name, u, h, X, sign)
                    net = net_series(tr)
                    dev = net[net.index <= DEV_END]; chk = net[net.index > DEV_END]
                    key = f"{name}|{h}|X{X:.2f}|{'REV' if sign==-1 else 'FLIP'}"
                    rec = dict(variant=key, ctrl=(sign == +1))
                    for tag, s in (("dev", dev), ("chk", chk)):
                        st = stats(s)
                        for k, v in st.items(): rec[f"{tag}_{k}"] = v
                    rec["dev_gross_bp"] = (tr.pnl[tr.index <= DEV_END]).mean() * 1e4 if (tr.index <= DEV_END).any() else np.nan
                    rec["chk_gross_bp"] = (tr.pnl[tr.index > DEV_END]).mean() * 1e4 if (tr.index > DEV_END).any() else np.nan
                    rec["cost_bp"] = (tr.cost).mean() * 1e4
                    rec["years_all"] = json.dumps(per_year(net))
                    rows.append(rec); store[key] = net
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/variants.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(df[["variant", "dev_n", "dev_mean_bp", "dev_t", "chk_n", "chk_mean_bp", "chk_t", "cost_bp"]].round(2).to_string())
