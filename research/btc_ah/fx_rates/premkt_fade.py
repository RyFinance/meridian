"""Extra family B (post-grid, counted separately): fade the residual at the 09:00 pre-market price and
exit at the 09:30 open. Entry at the 09:00 print (close of 08:00 bar, treated as the next tradable price after the
decision bar). Costs: 15 bp per side (extended hours, per BRIEF). 24 variants = 12 pairs x k in {0, 1.0}."""
import numpy as np, pandas as pd
from pathlib import Path
import analyze as A
H = Path(__file__).parent
COST_PM = 0.0015
def main():
    maps = {k: A.load(k) for k in set(list(A.SIGS.values()) + [t for _, t in A.PAIRS])}
    keys = [k for k in maps["FXE"] if k.endswith("09:30")]
    days = sorted({pd.Timestamp(k[:10]).strftime("%Y-%m-%d") for k in keys})
    rows = []
    for sig, tgt in A.PAIRS:
        Sm, Tm = maps[A.SIGS[sig]], maps[tgt]
        df = A.add_resid(A.build(sig, tgt, maps, days))
        df["D"] = pd.to_datetime(df.D).dt.date
        # entry price = pre-open 09:00 print: e09 = o * exp(-gap)
        df["e09"] = df.o * np.exp(-df.gap)
        for k in [0.0, 1.0]:
            for sgn, fam in [(-1, "fade"), (1, "follow")]:
                d = df.dropna(subset=["z"]); d = d[np.abs(d.z) >= k] if k > 0 else d
                d = d[d.R != 0]
                dirn = sgn * np.sign(d.R.values)
                net = dirn * (d.o.values / d.e09.values - 1) - 2 * COST_PM
                rows.append(dict(variant=f"PM {sig}->{tgt}|{fam}|k{k}", D=d.D.values, net=net))
    out = []
    for r in rows:
        x = pd.DataFrame({"D": r["D"], "net": r["net"]})
        for lab, m in [("dev", x.D < A.SPLIT), ("check", x.D >= A.SPLIT)]:
            s = A.stats(x.net[m])
            out.append(dict(variant=r["variant"], sample=lab, **s))
    res = pd.DataFrame(out)
    dev = res[res["sample"] == "dev"].set_index("variant")
    chk = res[res["sample"] == "check"].set_index("variant")
    print(f"family B variants: {len(dev)}")
    print("dev variants with t>2:", int((dev.t > 2).sum()), " max dev t:", round(dev.t.max(), 2))
    top = dev[dev.n >= 50].sort_values("t", ascending=False).head(3).index
    print(pd.concat([dev.loc[top, ["n", "win", "mean", "t"]].add_prefix("dev_"),
                     chk.loc[top, ["n", "win", "mean", "t"]].add_prefix("chk_")], axis=1).round(4).to_string())
    print("\nfamily B mean dev net over all 24:", round(dev["mean"].mean(), 5))
    # gross reversion size for context
    d = A.add_resid(A.build("ZB", "TLT", maps, days))
    print("ZB->TLT |R| median (bp):", round(10000 * d.R.abs().median(), 1), " sigma_R median (bp):", round(10000 * d.sigR.median(), 1))

if __name__ == "__main__":
    main()
