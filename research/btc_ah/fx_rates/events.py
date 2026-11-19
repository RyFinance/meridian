"""Treasury refunding-statement days and refunding-week auction days (Tue/Wed/Thu after the statement).
Statement dates 2026 (Feb 4, May 6, Aug 5) and Nov 5 2025 from Treasury/press sources; the other
2024-25 statement dates follow the Treasury pattern (Wednesday before the refunding auctions) and are approximate.
Overnight window is 16:00 -> 09:00 ET, which includes the 08:30 refunding statement. 10y/30y auctions (13:00 ET)
fall inside the session, after entry, so they are NOT in the signal; the test is whether overnight moves on
event days behave differently from ordinary days."""
import numpy as np, pandas as pd
from pathlib import Path
import analyze as A
H = Path(__file__).parent
STATEMENTS = ["2024-07-31", "2024-10-30", "2025-02-05", "2025-04-30", "2025-07-30", "2025-11-05",
              "2026-02-04", "2026-05-06", "2026-08-05"]
AUCTION = []
for s in STATEMENTS:
    t = pd.Timestamp(s)
    AUCTION += [(t + pd.Timedelta(days=d)).strftime("%Y-%m-%d") for d in (6, 7, 8)]
AUCTION = set(AUCTION) - {"2026-08-11", "2026-08-12", "2026-08-13"}  # after the sealed cutoff
STM = set(STATEMENTS)
EVENT_PAIRS = [("ZN", "IEF"), ("ZB", "TLT"), ("ZB", "TMF"), ("ZB", "TBT")]

def main():
    maps = {k: A.load(k) for k in set(list(A.SIGS.values()) + [t for _, t in A.PAIRS])}
    keys = [k for k in maps["FXE"] if k.endswith("09:30")]
    days = sorted({pd.Timestamp(k[:10]).strftime("%Y-%m-%d") for k in keys})
    out = []
    for sig, tgt in EVENT_PAIRS:
        df = A.add_resid(A.build(sig, tgt, maps, days))
        df["D"] = pd.to_datetime(df.D).dt.strftime("%Y-%m-%d")
        df["grp"] = np.where(df.D.isin(STM), "statement", np.where(df.D.isin(AUCTION), "auction_day", "other"))
        df["oc"] = np.log(df.cl / df.o)
        for g, d in df.groupby("grp"):
            x = d.rS.values
            # follow the overnight futures move: long if the signal rose, short if it fell, OC exit
            s = np.sign(x)
            net = s * (d.cl.values / d.o.values - 1) - 2 * A.COST
            st = A.stats(net)
            b, t = A.ols(x, d.G.values) if len(d) > 5 else (np.nan, np.nan)
            out.append(dict(pair=f"{sig}->{tgt}", group=g, n=len(d), mean_overnight_bp=10000 * x.mean(),
                            mean_abs_overnight_bp=10000 * np.abs(x).mean(), pre_open_beta=b,
                            follow_OC_net_bp=10000 * st["mean"], t=st["t"], win=st["win"],
                            oc_mean_bp=10000 * d.oc.mean()))
    res = pd.DataFrame(out)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(res.round(3).to_string(index=False))
    res.to_csv(H / "event_days.csv", index=False)
    ev = df[df.grp != "other"]
    print("\nevent-day sessions in sample (ZB->TLT rows):", sorted(ev.D.unique()))

if __name__ == "__main__":
    main()
