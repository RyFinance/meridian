"""Registered, development-only evaluation of two preregistered JKP themes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.amendment4 import calib


OUT = Path("reports/sol_beyond_menu/wave2")
PREREG = {
    "wave2_jkp_accruals": ("PREREG_WAVE2_ACCRUALS.md", "1c8ae4d26ac59796ca5197a534fa0bfa8acbf13ca09337830f9c6325a34e414e", "accruals"),
    "wave2_jkp_debt_issuance": ("PREREG_WAVE2_DEBT_ISSUANCE.md", "765dc17f37a5a77f6254b51749526a9ba7bb0dc0015529f59a9593e76741e03d", "debt_issuance"),
}
START, DEV_END = "1988-01", "2015-12"
EXPECTED = 336


def read_development(view: Path, theme: str) -> pd.DataFrame:
    path = view / "raw/[world]_[all_themes]_[monthly]_[vw_cap].zip"
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.endswith(".csv")]
        if len(members) != 1:
            raise ValueError("exactly one JKP CSV archive member required")
        reader = csv.DictReader(io.TextIOWrapper(z.open(members[0]), encoding="utf-8-sig"))
        records = []
        for row in reader:
            if row["name"] != theme:
                continue
            month = row["date"][:7]
            if month > DEV_END:  # discard locked holdout before parsing its numeric return
                continue
            if month < START:
                continue
            records.append((month, float(row["ret"])))
    months = pd.period_range(START, DEV_END, freq="M")
    if len(records) != EXPECTED or len(set(m for m, _ in records)) != EXPECTED:
        raise ValueError(f"{theme}: missing/duplicated development months")
    series = pd.Series({pd.Period(month): ret for month, ret in records}).reindex(months)
    if series.isna().any() or not np.isfinite(series.to_numpy()).all():
        raise ValueError(f"{theme}: missing/nonfinite development return")
    frame = pd.DataFrame(index=months.to_timestamp("M"))
    frame.index.name = "date"
    frame["gross_factor"] = series.to_numpy()
    frame["active_net"] = frame.gross_factor - .004
    frame["active_stress"] = frame.gross_factor - .010
    return frame


def summarize(frame: pd.DataFrame, experiment: str) -> dict:
    x = frame.active_net.to_numpy()
    inference = calib.calibrated_pvalues(x[None, :], overlap=1, B=159,
                                         seed=20260927 + list(PREREG).index(experiment),
                                         full=True, bandwidth_fraction=.20,
                                         crash=(.2 / 12, -6.0))
    L = int(inference["L"])
    lrv = float(calib.obm_lrv(x, L + 1) if L > 16 else calib.nw_lrv(x, L))
    var = float(x.var())
    D = max(1.0, lrv / var) if var > 0 else math.inf
    yearly = frame.active_net.groupby(frame.index.year).sum()
    total = float(yearly.sum())
    concentration = float(yearly.max() / total) if total > 0 else None
    stress = float(frame.active_stress.mean())
    p = float(inference["p"][0])
    threshold = .05 / len(PREREG)
    return {"experiment": experiment, "status": "DEVELOPMENT_ONLY", "n_months": len(x),
            "first": str(frame.index.min().date()), "last": str(frame.index.max().date()),
            "mean_annualized": float(x.mean() * 12),
            "active_sharpe": float(x.mean() / x.std(ddof=1) * math.sqrt(12)),
            "calibrated_p": p, "a4_t": float(inference["t"][0]),
            "a4_ar_order": int(inference["ar_order"][0]), "a4_bandwidth": L,
            "effective_n": float(len(x) / D), "variance_inflation_D": D,
            "stress_mean_annualized": stress * 12,
            "max_year_share_of_total_pnl": concentration,
            "largest_year": int(yearly.idxmax()),
            "positive_threshold": threshold,
            "positive": bool(p < threshold and stress > 0 and concentration is not None and concentration <= .40),
            "holdout": "2016-01 through 2025-12 locked; not read numerically"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=tuple(PREREG), required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("QUANT_DATA_MANIFEST_SHA256"):
        raise RuntimeError("registered snapshot runner required")
    filename, expected_hash, theme = PREREG[args.experiment]
    if hashlib.sha256((Path(__file__).parent / filename).read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError("preregistration hash changed")
    if args.membership != args.snapshot_root / "raw/universe.json":
        raise RuntimeError("unexpected universe artifact")
    universe = json.loads(args.membership.read_text())
    if universe["dataset_version"] != os.environ["QUANT_DATASET_VERSION"] or theme not in universe["candidate_themes"]:
        raise RuntimeError("frozen universe mismatch")
    frame = read_development(args.snapshot_root, theme)
    result = summarize(frame, args.experiment)
    result["manifest_sha256"] = os.environ["QUANT_DATA_MANIFEST_SHA256"]
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / f"{args.experiment}_dev.csv", float_format="%.12g")
    (OUT / f"{args.experiment}_result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
