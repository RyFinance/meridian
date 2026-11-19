"""Step 2-3: MSTR after-hours / pre-market entry, exit at next official open.

Usage: mstr_sim.py dev|val
MSTR price at 20:00 / 04:00 is not in the daily data, so the remainder return is proxied:
  proxy A: mstr_R = beta * btc_R          (beta from prior data only; no idiosyncratic noise)
  proxy B: mstr_R = actual_gap - beta * btc_E   (puts all idiosyncratic gap noise, incl. AH earnings, in R)
Costs (per trade, fraction of notional, $100k): entry half-spread 15 bp (AH/pre-mkt), exit 2 bp
(opening auction), commission $0.005/share each side on the traded (unsplit) price, short borrow 0.3%/yr
prorated over calendar days held. Baseline close->open uses real gap, 2 bp each side + commission.
"""
import sys
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/agent_b")
import numpy as np
import pandas as pd
from common import OUT, mstr, stats

MODE = sys.argv[1] if len(sys.argv) > 1 else "dev"
PER = {"dev": ("2020-08-12", "2022-12-31"), "val": ("2023-01-01", "2026-08-10")}[MODE]
ENTRY_HS, EXIT_HS, MOC_HS, BORROW = 15e-4, 2e-4, 2e-4, 0.003

P = pd.read_parquet(OUT + "/panel.parquet").set_index("date")
M = mstr()
D = P.join(M[["gap", "raw_px", "Open"]], how="inner")
D = D[D.index >= "2020-08-12"].copy()
D = D.dropna(subset=["gap", "off"])

# expanding prior-only gap beta: gap ~ a + b*btc_off, from 2020-08-12, min 20 obs
x, y = D.off.values, D.gap.values
beta = np.full(len(D), np.nan)
for i in range(20, len(D)):
    xs, ys = x[:i], y[:i]
    beta[i] = np.cov(xs, ys)[0, 1] / np.var(xs, ddof=1)
D["beta"] = beta
D = D[(D.index >= PER[0]) & (D.index <= PER[1])].dropna(subset=["beta"])
comm = 0.01 / D.raw_px  # round trip commission fraction ($0.005/share x2 / price)
days = D.gap_days.values


def leg(pos, R, entry_hs):
    """pos in {-1,0,1}; R = log return proxy; returns net simple return."""
    gross = pos * (np.exp(R) - 1)
    cost = np.abs(pos) * (entry_hs + EXIT_HS + comm)
    borrow = np.where(pos < 0, BORROW * days / 365, 0)
    return pd.Series(np.where(pos == 0, 0.0, gross - cost - borrow), index=D.index), \
        pd.Series(np.where(pos == 0, 0.0, gross), index=D.index)


rules = {}
for tag, e, r in [("20", "E20", "R20"), ("04", "E04", "R04")]:
    E = D[e].fillna(0)
    RA = D.beta * D[r]
    RB = D.gap - D.beta * D[e]
    for pname, R in [("A", RA), ("B", RB)]:
        R = R.fillna(0)
        rules[f"{tag}_longifEpos_{pname}"] = leg(np.where(E > 0, 1, 0), R, ENTRY_HS)
        rules[f"{tag}_signE_{pname}"] = leg(np.sign(E).astype(int), R, ENTRY_HS)
        rules[f"{tag}_alwayslong_{pname}"] = leg(np.ones(len(D), int), R, ENTRY_HS)
        rules[f"{tag}_fadeE_{pname}"] = leg(-np.sign(E).astype(int), R, ENTRY_HS)
# weekend Sunday 20:00 entry (24/5 overnight venues), long-only if Fri16->Sun20 BTC > 0, long overnights only
lw = (D.kind == "long").values
for pname, R in [("A", D.beta * D.Rsun), ("B", D.gap - D.beta * D.Esun)]:
    pos = np.where(lw & (D.Esun.fillna(0) > 0), 1, 0)
    rules[f"sun20_longifEpos_{pname}"] = leg(pos, R.fillna(0), ENTRY_HS)
# baseline: MOC buy at close, sell at open, every night; real gap
g = np.exp(D.gap) - 1
base_net = g - (MOC_HS + EXIT_HS + comm)
rules["base_close_to_open_real"] = (base_net, g)
rules["base_close_to_open_real_weeknights"] = (base_net.where(D.kind == "weeknight", 0), g.where(D.kind == "weeknight", 0))

lines = []
def out(s=""):
    print(s); lines.append(str(s))

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
out(f"MODE={MODE} period {D.index.min().date()}..{D.index.max().date()} nights={len(D)} "
    f"beta range {D.beta.min():.2f}..{D.beta.max():.2f}")
rows = []
for k, (net, gross) in rules.items():
    s = stats(net, 252)
    tr = gross[gross != 0]
    s["gross_bp"] = tr.mean() * 1e4
    s["cost_bp"] = s["gross_bp"] - s["mean_bp"]
    # breakeven entry half-spread holding exit/comm fixed
    s["be_entry_hs_bp"] = ENTRY_HS * 1e4 + s["mean_bp"] if "base" not in k else MOC_HS * 1e4 + s["mean_bp"]
    rows.append(dict(rule=k, **s))
T = pd.DataFrame(rows).set_index("rule")
out(T.round(2).to_string())

out("\nPer-year net return (% of notional, sum) for each rule:")
Y = pd.DataFrame({k: v[0].groupby(v[0].index.year).sum() * 100 for k, v in rules.items()})
out(Y.T.round(1).to_string())
T.to_csv(f"{OUT}/mstr_{MODE}.csv")
Y.to_csv(f"{OUT}/mstr_{MODE}_by_year.csv")
open(f"{OUT}/mstr_{MODE}.txt", "w").write("\n".join(lines))
