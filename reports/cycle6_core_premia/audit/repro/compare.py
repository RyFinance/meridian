"""Compare independent repro series with builder outputs (net.csv / gross.csv / book sleeves.csv CORE)."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import BUILDER, OUT  # noqa: E402

CUTOFF = {"TSMOM-FI": "2011-01", "TSMOM-CM": "2011-01", "XSMOM-FX": "2009-04", "VAL-FX": "2009-04",
          "CARRY-FX": "2013-09", "SEAS-FX": "2019-02", "CORE": "2019-02",
          "VAL-FX__cpi_geomean": "2009-04", "SEAS-FX__floor_excl_zero": "2019-02"}
TOL = 1e-6


def stats(x):
    x = x.dropna()
    if len(x) < 2:
        return (np.nan,) * 3
    m, s = x.mean() * 12, x.std(ddof=1) * np.sqrt(12)
    return m, s, m / s if s > 0 else np.nan


def builder_series(sid, kind):
    if sid == "CORE":
        if kind != "net":
            return None
        b = pd.read_csv(BUILDER / "book/sleeves.csv")[["month", "CORE"]].dropna()
        return b.set_index("month")["CORE"]
    f = BUILDER / "components" / sid.split("__")[0] / f"{kind}.csv"
    return pd.read_csv(f).set_index("month")["ret"]


def compare(sid, kind):
    r = pd.read_csv(OUT / f"repro_{sid}.csv").set_index("month")[f"{kind}_ret"].dropna()
    b = builder_series(sid, kind)
    if b is None:
        return None, None
    both = pd.concat([r.rename("repro"), b.rename("builder")], axis=1)
    ov = both.dropna()
    diff = ov.repro - ov.builder
    rows = []
    for win, sub in (("full", ov), ("post", ov[ov.index >= CUTOFF[sid]])):
        rm, rs, rsh = stats(sub.repro)
        bm, bs, bsh = stats(sub.builder)
        d = sub.repro - sub.builder
        rows.append({"id": sid, "series": kind, "window": win, "n_repro_only": int(both.builder.isna().sum()),
                     "n_builder_only": int(both.repro.isna().sum()), "n_overlap": len(sub),
                     "first": sub.index.min(), "last": sub.index.max(),
                     "corr": sub.repro.corr(sub.builder), "mean_abs_diff": d.abs().mean(), "max_abs_diff": d.abs().max(),
                     "n_diff_gt_1e-6": int((d.abs() > TOL).sum()),
                     "repro_mean_ann": rm, "repro_vol_ann": rs, "repro_sharpe": rsh,
                     "builder_mean_ann": bm, "builder_vol_ann": bs, "builder_sharpe": bsh})
    flagged = diff[diff.abs() > TOL]
    only = both[both.isna().any(axis=1)]
    return rows, (flagged, only)


if __name__ == "__main__":
    allrows, detail = [], {}
    for sid in CUTOFF:
        for kind in ("net", "gross"):
            rows, det = compare(sid, kind)
            if rows:
                allrows += rows
                detail[(sid, kind)] = det
    df = pd.DataFrame(allrows)
    df.to_csv(OUT / "compare_summary.csv", index=False)
    pd.set_option("display.width", 250)
    print(df[["id", "series", "window", "n_overlap", "n_repro_only", "n_builder_only", "corr", "mean_abs_diff",
              "max_abs_diff", "n_diff_gt_1e-6", "repro_sharpe", "builder_sharpe"]].to_string())
    rows = []
    for (sid, kind), (fl, only) in detail.items():
        for m, v in fl.items():
            rows.append({"id": sid, "series": kind, "month": m, "diff": v})
        for m, r in only.iterrows():
            rows.append({"id": sid, "series": kind, "month": m, "diff": np.nan,
                         "note": "repro only" if pd.isna(r.builder) else "builder only"})
    pd.DataFrame(rows).to_csv(OUT / "flagged_months.csv", index=False)
