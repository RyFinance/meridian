"""Write a research.data_snapshot spec for the rates/FX/equity-index acquisition and freeze it.

This is an ACQUISITION snapshot (dataset_version ``core_premia_rates_fx_eq_acq_v1``), not the
registered evaluation snapshot: no market has been selected. The "membership" artifact is the
candidate-availability panel (every candidate x month-end: has data / has 756-day warm-up), which
the owner's mechanical selection must be applied to later under a NEW dataset version.

Metadata rules (DATA_SNAPSHOT_POLICY.md): retrieval time comes from the ingest records
(collectors manifest ``fetched_at_utc``; for derived tables the build record time; for the
pre-existing LSE-vault files the time of this package's read-only import, because their vendor
retrieval time was never recorded -- disclosed as a defect). Never filesystem mtime.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.snapshot
"""
from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from research.core_premia_data.rates_fx_eq.common import DATA, META, PROC, RAW, REPORT, ROOT, STORE, SYN, utc_now, write_json

VERSION = "core_premia_rates_fx_eq_acq_v1"
AS_OF = "2026-09-26"


def iso(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.isoformat()


def membership():
    aqr = pd.read_parquet(PROC / "aqr_tsmom_dates.parquet")
    months = pd.period_range("1960-01", "2026-09", freq="M")
    rows = []
    for fname, key, idcol in (("bond_excess_daily.parquet", "excess_ret", "market_id"),
                              ("fx_excess_daily.parquet", "excess_ret", "market_id"),
                              ("equity_excess_daily.parquet", "excess_ret", "market_id")):
        d = pd.read_parquet(SYN / fname)
        tag = "source" if "source" in d else ("role" if "role" in d else None)
        for (mid, sub), g in d.groupby([idcol, tag] if tag else [idcol, idcol]):
            dates = g.loc[g[key].notna(), "date"].sort_values()
            if dates.empty:
                continue
            per = dates.dt.to_period("M")
            cnt = per.value_counts().sort_index()
            cum = cnt.cumsum()
            mm = pd.DataFrame({"n_days": cnt, "cum_days": cum})
            mm["market_id"], mm["variant"] = mid, sub
            rows.append(mm.reset_index(names="month"))
    m = pd.concat(rows, ignore_index=True)
    m["warm_756"] = (m["cum_days"] - m["n_days"]) >= 756
    m["month"] = m["month"].astype(str)
    a = set(aqr.month_end.dt.to_period("M").astype(str))
    m["aqr_month"] = m["month"].isin(a)
    m.to_parquet(META / "candidate_availability_monthly.parquet", index=False)
    return m


def bounds_for_raw(source: str, name: str, y, fx, o, mk, aqr):
    def yb(mask):
        g = y[mask]
        return (g.date.min(), g.date.max(), int(len(g))) if len(g) else (None, None, 0)
    if source == "fed_h15":
        return yb(y.source == "fed_h15")
    if source == "boe_iadb":
        return yb((y.source == "boe_iadb") & (y.series_id == name))
    if source == "bundesbank":
        return yb((y.source == "bundesbank") & y.series_id.str.contains(name.split("_")[-1]))
    if source == "mof_japan":
        g = y[y.source == "mof_japan"]
        g = g[g.date < "2026-09-01"] if name == "jgbcme_all" else g[g.date >= "2026-09-01"]
        return (g.date.min(), g.date.max(), int(len(g)))
    if source in ("boc_valet", "riksbank"):
        return yb((y.source == source) & (y.series_id == name))
    if source == "norges_bank":
        return yb((y.source == source) & (y.series_id == name.replace("GOVT_GENERIC_RATES_B_", "GOVT_GENERIC_RATES.B.").replace("_TBIL", ".TBIL").replace("_GBON", ".GBON")))
    if source == "snb":
        return yb(y.source == "snb")
    if source == "ecb":
        if name.startswith("YC"):
            return yb((y.source == "ecb") & (y.series_id == name))
        g = fx[fx.source == "ecb"]
        return (g.date.min(), g.date.max(), int(len(g)))
    if source == "fed_h10":
        a, b = name.split("_")[-2:]
        g = fx[(fx.source == "fed_h10") & (fx.date >= f"{a}-01-01") & (fx.date <= f"{b}-12-31")]
        return (g.date.min(), g.date.max(), int(len(g)))
    if source == "oecd_sdmx":
        g = o[o.measure == name.split("_")[-1]]
        return (g.month.min(), g.month.max(), int(len(g)))
    if source == "yahoo_chart":
        g = mk.get(name)
        return (g.date.min(), g.date.max(), int(len(g))) if g is not None else (None, None, 0)
    if source == "aqr" and name == "TSMOM_factors_monthly":
        return (aqr.month_end.min(), aqr.month_end.max(), int(len(aqr)))
    return (None, None, 0)


def date_bounds(path):
    try:
        d = pd.read_parquet(path)
    except Exception:  # noqa: BLE001
        return None, None, None
    for c in ("date", "month_end", "month"):
        if c in d:
            s = pd.to_datetime(d[c].astype(str), errors="coerce")
            return s.min(), s.max(), int(len(d))
    return None, None, int(len(d))


def build_spec():
    from research.core_premia_data.rates_fx_eq.acquire_yahoo import safe
    y = pd.read_parquet(PROC / "yields_daily.parquet")
    fx = pd.read_parquet(PROC / "fx_spot_daily.parquet")
    o = pd.read_parquet(PROC / "oecd_monthly.parquet")
    mkt = pd.read_parquet(PROC / "market_daily.parquet")
    mk = {safe(t): g for t, g in mkt.groupby("ticker")}
    aqr = pd.read_parquet(PROC / "aqr_tsmom_dates.parquet")
    build = json.loads((META / "build_record.json").read_text())
    import_time = build["built_at_utc"]
    now = utc_now().isoformat()
    meta = {}

    # raw scope
    man = {}
    for mf in RAW.glob("*/manifest.jsonl"):
        for line in mf.read_text().splitlines():
            r = json.loads(line)
            man[r["path"]] = r
    for p in sorted(RAW.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(RAW).as_posix()
        key = f"raw/{rel}"
        r = man.get(rel)
        if r is None:  # manifests and attempt log
            meta[key] = {"source": "ingest log", "source_identifier": None, "retrieved_at": now, "logical_as_of": AS_OF,
                         "symbol": rel, "first_timestamp": None, "last_timestamp": None,
                         "row_count": sum(1 for _ in p.open()), "temporal": False}
            continue
        f, l, n = bounds_for_raw(r["source"], r["name"], y, fx, o, mk, aqr)
        temporal = f is not None
        meta[key] = {"source": r["source"], "source_identifier": r.get("url") or json.dumps(r.get("arguments")),
                     "retrieved_at": r["fetched_at_utc"], "logical_as_of": AS_OF, "symbol": r["name"],
                     "first_timestamp": iso(f), "last_timestamp": iso(l), "row_count": int(n), "temporal": temporal}
    # derived scopes
    for scope, root in (("processed", PROC), ("synthetic", SYN), ("meta", META)):
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            f, l, n = date_bounds(p) if p.suffix == ".parquet" else (None, None, None)
            meta[f"{scope}/{rel}"] = {"source": f"core_premia_data.rates_fx_eq.{scope}", "source_identifier": None,
                                      "retrieved_at": import_time, "logical_as_of": AS_OF, "symbol": rel,
                                      "first_timestamp": iso(f), "last_timestamp": iso(l),
                                      "row_count": int(n) if n is not None else sum(1 for _ in p.open("rb")),
                                      "temporal": f is not None}
    # legacy LSE-vault inputs (read-only; vendor retrieval time unrecorded)
    legacy = [("legacy_bond_yields", ROOT / "data/bond_yields", ["*.parquet", "manifest.json"]),
              ("legacy_multiasset_yields", ROOT / "data/multiasset/yields", ["*.parquet"]),
              ("legacy_fx_carry", ROOT / "data/lse/fx_carry", ["raw.pkl"])]
    for scope, root, inc in legacy:
        for pat in inc:
            for p in sorted(root.glob(pat)):
                rel = p.relative_to(root).as_posix()
                f, l, n = date_bounds(p) if p.suffix == ".parquet" else (None, None, None)
                if p.name == "raw.pkl":
                    f, l, n = pd.Timestamp("2014-12-01"), pd.Timestamp("2026-09-17"), 27
                meta[f"{scope}/{rel}"] = {"source": "LSE vault (pre-existing local pull; vendor retrieval time not recorded)",
                                          "source_identifier": "https://api.londonstrategicedge.com/vault",
                                          "retrieved_at": import_time, "logical_as_of": AS_OF,
                                          "symbol": p.stem, "first_timestamp": iso(f), "last_timestamp": iso(l),
                                          "row_count": int(n) if n is not None else 1, "temporal": f is not None}
    spec = {
        "dataset_version": VERSION,
        "scopes": [{"name": "raw", "root": str(RAW), "include": ["**/*"]},
                   {"name": "processed", "root": str(PROC), "include": ["**/*"]},
                   {"name": "synthetic", "root": str(SYN), "include": ["**/*"]},
                   {"name": "meta", "root": str(META), "include": ["**/*"]},
                   {"name": "legacy_bond_yields", "root": str(ROOT / "data/bond_yields"), "include": ["*.parquet", "manifest.json"]},
                   {"name": "legacy_multiasset_yields", "root": str(ROOT / "data/multiasset/yields"), "include": ["*.parquet"]},
                   {"name": "legacy_fx_carry", "root": str(ROOT / "data/lse/fx_carry"), "include": ["raw.pkl"]}],
        "metadata": meta,
        "universe": {
            "membership_artifact": "meta/candidate_availability_monthly.parquet",
            "exclusions": "none applied: acquisition snapshot, selection not yet made (see reports/core_premia_20260925/rates_fx_eq/universe.csv condition columns)",
            "symbol_mappings": "research/core_premia_data/rates_fx_eq/synthetic.py EQUITY/BOND_SPECS/CCY tables; yahoo ticker -> raw name via acquire_yahoo.safe()",
            "delistings": ["US 20y CMT suspended 1987-01..1993-09 (Treasury)", "BoE IUDVCDA ends 2018-06-29",
                           "Riksbank STIBOR 3M ends 2020-07-03", "H.10 Venezuelan bolivar (VEB) kept", "SNB rendoblim cube last obs 2025-07",
                           "pre-1999 euro legacy currencies: not acquired (no reachable free source)"],
            "mapping_artifacts": [], "delisting_artifacts": []},
        "intermediate_artifacts": ["processed/yields_daily.parquet", "processed/fx_spot_daily.parquet",
                                   "processed/oecd_monthly.parquet", "processed/market_daily.parquet",
                                   "synthetic/bond_excess_daily.parquet", "synthetic/fx_excess_daily.parquet",
                                   "synthetic/equity_excess_daily.parquet", "synthetic/short_rates_daily.parquet"],
    }
    return spec


def main():
    membership()
    spec = build_spec()
    spec_path = DATA / f"snapshot_spec_{VERSION}.json"
    spec_path.write_text(json.dumps(spec, indent=1, sort_keys=True) + "\n")
    res = subprocess.run([sys.executable, "-m", "research.data_snapshot", "--store", str(STORE), "freeze", str(spec_path)],
                         capture_output=True, text=True, cwd=ROOT)
    out = {"dataset_version": VERSION, "store": str(STORE), "spec": str(spec_path.relative_to(ROOT)),
           "returncode": res.returncode, "manifest_sha256": res.stdout.strip(), "stderr": res.stderr[-2000:],
           "frozen_at_utc": utc_now().isoformat(), "n_files": len(spec["metadata"])}
    write_json(REPORT / "snapshot_freeze.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
