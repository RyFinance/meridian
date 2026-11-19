import pandas as pd, numpy as np
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent))
from analyze import stats, DEV_END_I, OPEC_MON
O = Path(__file__).parent
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 40)
TR = pd.read_parquet(O / "trades_intraday.parquet")
fol = TR[TR.kind == "follow"]; flp = TR[TR.kind == "flip"]
def row(name, df):
    s = stats(df); py = s.pop("per_year", {})
    return dict(sel=name, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}, per_year=py)
TOP = [("E_RES_k1.0", "FRO"), ("X_FH_k0.5", "FANG"), ("X_FH_k0.5", "OXY")]
out = []
for rule, ins in TOP:
    g = fol[(fol.rule == rule) & (fol.inst == ins)]; f = flp[(flp.rule == rule) & (flp.inst == ins)]
    for part, msk in [("dev", "dev"), ("check", "~dev")]:
        gg = g[g.dev] if part == "dev" else g[~g.dev]; ff = f[f.dev] if part == "dev" else f[~f.dev]
        out.append(row(f"{rule} {ins} {part} FOLLOW", gg)); out.append(row(f"{rule} {ins} {part} FLIP", ff))
# pooled: all instruments, each rule, follow vs flip, full-period & dev/check (equal weight per trade)
for rule in ["X_FH_k0.0", "X_OC_k0.0", "E_RES_k0.0", "X_FH_k1.0", "X_OC_k1.0", "E_RES_k1.0"]:
    g = fol[fol.rule == rule]; f = flp[flp.rule == rule]
    for part in ["dev", "check"]:
        gg = g[g.dev] if part == "dev" else g[~g.dev]; ff = f[f.dev] if part == "dev" else f[~f.dev]
        out.append(row(f"POOLED {rule} {part} FOLLOW", gg)); out.append(row(f"POOLED {rule} {part} FLIP", ff))
# event subsets for the x-follow OC k=0 pooled energy-equity set (one trade per instrument per day)
sub = {"weekend (Fri->Mon)": fol[(fol.rule == "X_OC_k0.0") & fol.weekend],
       "weekend |oil|>3%": fol[(fol.rule == "X_OC_k0.0") & fol.weekend & (fol.x.abs() > 0.03)],
       "OPEC+ Mondays (memory dates)": fol[(fol.rule == "X_OC_k0.0") & fol.date.isin(pd.to_datetime(OPEC_MON))],
       "weekend |oil|>3% FLIP": flp[(flp.rule == "X_OC_k0.0") & flp.weekend & (flp.x.abs() > 0.03)]}
for k, v in sub.items():
    out.append(row(f"EVENT {k} (all dates, X_OC pooled)", v))
# per-year table, pooled X_FH_k0 and E_RES_k0 follow vs flip
for rule in ["X_FH_k0.0", "X_OC_k0.0", "E_RES_k0.0"]:
    g = fol[fol.rule == rule]
    print(rule, "per-year mean bp (n):", {y: (round(v[0],1), v[1]) for y, v in stats(g)["per_year"].items()} if len(g) else None)
    print(rule, "FLIP per-year:", {y: (round(v[0],1), v[1]) for y, v in stats(flp[flp.rule==rule])["per_year"].items()})
R = pd.DataFrame(out)
print(R[["sel","n","win","mean_bp","t","avg_win_bp","avg_loss_bp"]].round(2).to_string())
for _, r in R.iterrows():
    print(r["sel"], r["per_year"])
# gap beta and gap-x correlation by instrument (dev)
dev = TR[(TR.kind=="follow") & (TR.rule=="X_FH_k0.0") & TR.dev]
gb = dev.groupby("inst").agg(gapbeta=("gapbeta","first"), n=("gap","size"))
print(gb.round(3).to_string())
