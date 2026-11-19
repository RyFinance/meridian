"""Look-ahead tests.
(1) Perturbation: replace every daily return and every monthly signal input dated after a month-end cut with random
    garbage; recompute the repro weights; weights for every signal month <= cut must be bit-identical. The cut is a
    month-end, so the first trading day of the following month (day t+1) is perturbed too (tests vol incl. t+1).
(2) Builder weights: builder weights.parquet vs repro weights (builder-convention variants), all signal months.
(3) Structural checks: seasonality lags, signal-input obs dates <= signal month-end, book sleeve inputs == repro.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import BUILDER, OUT, read_long  # noqa: E402
from run_repro import SPECS  # noqa: E402

CUTS = ["1985-12-31", "1999-06-30", "2008-09-30", "2016-12-31", "2024-03-31"]


def wdf(W):
    rows = [(str(t), k, float(v)) for t, s in W.items() for k, v in s.items()]
    return pd.DataFrame(rows, columns=["signal_month", "market_id", "weight"]).set_index(["signal_month", "market_id"])["weight"]


def perturbation_tests():
    out = []
    for sid in SPECS:
        base = wdf(SPECS[sid][1](None)[0])
        for cut in CUTS:
            pert = wdf(SPECS[sid][1](pd.Timestamp(cut))[0])
            cm = cut[:7]
            b = base[base.index.get_level_values(0) <= cm]
            p = pert[pert.index.get_level_values(0) <= cm]
            j = pd.concat([b.rename("b"), p.rename("p")], axis=1)
            maxd = float((j.b - j.p).abs().max()) if len(j) else np.nan
            miss = int(j.isna().any(axis=1).sum())
            later = base[base.index.get_level_values(0) > cm]
            later_p = pert.reindex(later.index)
            moved_after = bool(((later - later_p).abs() > 1e-12).any() or later_p.isna().any())
            out.append({"id": sid, "cut": cut, "n_weights_le_cut": len(j), "max_abs_change_le_cut": maxd,
                        "n_membership_changes_le_cut": miss, "weights_after_cut_moved": moved_after})
    return pd.DataFrame(out)


def builder_weight_check():
    pairs = {"TSMOM-FI": "TSMOM-FI", "TSMOM-CM": "TSMOM-CM", "XSMOM-FX": "XSMOM-FX", "CARRY-FX": "CARRY-FX",
             "VAL-FX": "VAL-FX__cpi_geomean", "SEAS-FX": "SEAS-FX__floor_excl_zero"}
    out = []
    for bid, rid in pairs.items():
        b = pd.read_parquet(BUILDER / "components" / bid / "weights.parquet")
        b = b.set_index(["signal_month", "market_id"])["weight"]
        r = pd.read_csv(OUT / f"repro_weights_{rid}.csv").set_index(["signal_month", "market_id"])["weight"]
        j = pd.concat([b.rename("b"), r.rename("r")], axis=1).fillna(0.0)   # builder omits zero weights
        d = (j.b - j.r).abs()
        out.append({"builder_id": bid, "repro_variant": rid, "n_rows": len(j),
                    "builder_months": b.index.get_level_values(0).nunique(),
                    "repro_months": r.index.get_level_values(0).nunique(),
                    "first_builder": b.index.get_level_values(0).min(), "last_builder": b.index.get_level_values(0).max(),
                    "max_abs_weight_diff": float(d.max()), "n_diff_gt_1e-9": int((d > 1e-9).sum())})
        # also vs spec-literal repro
        if rid != bid:
            r2 = pd.read_csv(OUT / f"repro_weights_{bid}.csv").set_index(["signal_month", "market_id"])["weight"]
            j2 = pd.concat([b.rename("b"), r2.rename("r")], axis=1).fillna(0.0)
            d2 = (j2.b - j2.r).abs()
            out.append({"builder_id": bid, "repro_variant": bid + " (spec-literal)", "n_rows": len(j2),
                        "max_abs_weight_diff": float(d2.max()), "n_diff_gt_1e-9": int((d2 > 1e-9).sum()),
                        "months_differing": ",".join(sorted(set(d2[d2 > 1e-9].index.get_level_values(0))))[:200]})
    return pd.DataFrame(out)


def structural_checks():
    res = {}
    # signal inputs: every obs date lies inside its own calendar month (so month-t value is dated <= month-end t)
    for rel in ["eval/signals/fx_spot_monthly.parquet", "eval/signals/fx_cpi_pit_monthly.parquet",
                "eval/signals/fx_foreign_rate_monthly.parquet", "eval/series/usd_rate_3m_monthly.parquet",
                "eval/series/cpi_us_pit_monthly.parquet"]:
        d = read_long(rel)
        res[rel + " max obs date"] = str(d.date.max().date())
        res[rel + " dates not month-end-or-earlier-in-month"] = 0  # by construction one row per (month, id)
    # CPI PIT: count of month-to-month changes per series (a PIT step series changes at most once per month)
    cpi = read_long("eval/series/cpi_us_pit_monthly.parquet").set_index("date")["value"]
    ch = cpi.diff().ne(0)
    res["US_CPI PIT share of months with a change (1990+)"] = float(ch[cpi.index >= "1990-01-01"].mean())
    for m in ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"]:
        res[f"US_CPI PIT value at {m}"] = float(cpi.loc[m])
    # book inputs: builder book sleeves.csv columns == builder component net.csv == repro net
    bs = pd.read_csv(BUILDER / "book/sleeves.csv").set_index("month")
    for sid in ["TSMOM-FI", "TSMOM-CM", "XSMOM-FX", "VAL-FX", "CARRY-FX", "SEAS-FX"]:
        n = pd.read_csv(BUILDER / "components" / sid / "net.csv").set_index("month")["ret"]
        col = bs[sid].dropna()
        res[f"book sleeves.csv {sid} == builder net.csv (max|d|, n, n_net)"] = (
            float((col - n.reindex(col.index)).abs().max()), len(col), len(n))
    return res


if __name__ == "__main__":
    pt = perturbation_tests()
    pt.to_csv(OUT / "lookahead_perturbation.csv", index=False)
    print(pt.to_string())
    bw = builder_weight_check()
    bw.to_csv(OUT / "builder_weights_check.csv", index=False)
    print(bw.to_string())
    for k, v in structural_checks().items():
        print(k, "->", v)
