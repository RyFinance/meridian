"""Universe / ticker-history sources that are free, account-less and legitimate.

1. Wayback Machine snapshots of SEC company_tickers.json (CIK<->ticker map, point-in-time only as of
   each snapshot) -- SEC only started publishing this file ~2018.
2. Wayback snapshots of Nasdaq Trader symbol directories nasdaqlisted.txt / otherlisted.txt
   (symbol + security name, point-in-time as of each snapshot).
3. Tiingo's public supported_tickers.zip (documentation file, no key): ticker, exchange, asset type,
   startDate, endDate -- includes delisted tickers but NO CIK / name.
The Wayback CDX endpoint was 503/timing out from this sandbox, so snapshots are located with the
`archive.org/wayback/available` API (closest snapshot to a target timestamp) and fetched raw (id_).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.sources
"""
from __future__ import annotations

import io
import json
import zipfile

import pandas as pd

from research.survivor_equity_pilot.common import DATA_DIR, REPORT_DIR, fetch

SEC_CT = "https://www.sec.gov/files/company_tickers.json"
NASDAQ_LISTED = "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED = "http://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
TIINGO = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"


def closest_snapshot(url: str, ts: str) -> dict | None:
    api = f"http://archive.org/wayback/available?url={url}&timestamp={ts}"
    st, body, _ = fetch(api, "wayback_api", store=False)
    if st != 200 or not body:
        return None
    snap = json.loads(body).get("archived_snapshots", {}).get("closest")
    return snap if snap and snap.get("available") else None


def raw_snapshot(snap_url: str) -> str:
    # insert id_ after the timestamp to get the unmodified archived body
    parts = snap_url.split("/")
    i = parts.index("web") + 1
    parts[i] = parts[i] + "id_"
    return "/".join(parts)


def get_snapshots(url: str, targets: list[str], subdir: str) -> list[dict]:
    got, seen = [], set()
    for t in targets:
        snap = closest_snapshot(url, t)
        if not snap:
            got.append({"target": t, "status": "no_snapshot"})
            continue
        ts = snap["timestamp"]
        if ts in seen:
            got.append({"target": t, "status": "duplicate_of", "timestamp": ts})
            continue
        seen.add(ts)
        raw = raw_snapshot(snap["url"])
        fname = f"{ts}_{url.rsplit('/', 1)[-1]}"
        p = DATA_DIR / subdir / fname
        if p.exists() and p.stat().st_size > 1000:
            got.append({"target": t, "timestamp": ts, "file": str(p), "status": "cached", "url": raw})
            continue
        st, body, rel = fetch(raw, subdir, fname, timeout=90)
        got.append({"target": t, "timestamp": ts, "file": str(DATA_DIR / subdir / fname) if rel else None,
                    "status": st, "url": raw, "bytes": len(body or b"")})
    return got


def load_company_tickers(files: list[dict]) -> pd.DataFrame:
    rows = []
    for f in files:
        if not f.get("file"):
            continue
        try:
            d = json.loads(open(f["file"], "rb").read())
        except Exception:  # noqa: BLE001
            continue
        for v in d.values():
            rows.append({"snapshot": f["timestamp"][:8], "cik": int(v["cik_str"]), "ticker": v["ticker"],
                         "title": v["title"]})
    return pd.DataFrame(rows)


def load_symdir(files: list[dict], kind: str) -> pd.DataFrame:
    rows = []
    for f in files:
        if not f.get("file"):
            continue
        txt = open(f["file"], "rb").read().decode("latin-1")
        lines = [ln for ln in txt.splitlines() if "|" in ln]
        if not lines or not (lines[0].startswith("Symbol") or lines[0].startswith("ACT Symbol")):
            continue
        hdr = lines[0].split("|")
        for ln in lines[1:]:
            if ln.startswith("File Creation Time"):
                continue
            parts = ln.split("|")
            rec = dict(zip(hdr, parts))
            sym = rec.get("Symbol") or rec.get("ACT Symbol")
            rows.append({"snapshot": f["timestamp"][:8], "kind": kind, "symbol": sym,
                         "name": rec.get("Security Name", ""), "exchange": rec.get("Exchange", "Q"),
                         "etf": rec.get("ETF", ""), "test": rec.get("Test Issue", "")})
    return pd.DataFrame(rows)


def load_tiingo() -> pd.DataFrame:
    p = DATA_DIR / "tiingo" / "supported_tickers.zip"
    if not p.exists():
        fetch(TIINGO, "tiingo", "supported_tickers.zip", timeout=90)
    z = zipfile.ZipFile(p)
    df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), dtype=str)
    return df


def main() -> None:
    ct_targets = [f"{y}0701" for y in range(2016, 2027)] + [f"{y}1231" for y in range(2017, 2026)]
    sym_targets = [f"{y}0701" for y in range(2006, 2027)]
    out = {
        "company_tickers": get_snapshots(SEC_CT, sorted(ct_targets), "wayback_company_tickers"),
        "nasdaqlisted": get_snapshots(NASDAQ_LISTED, sym_targets, "wayback_symdir"),
        "otherlisted": get_snapshots(OTHER_LISTED, sym_targets, "wayback_symdir"),
    }
    (DATA_DIR / "snapshot_index.json").write_text(json.dumps(out, indent=1))
    ct = load_company_tickers(out["company_tickers"])
    ct.to_parquet(DATA_DIR / "company_tickers_history.parquet")
    sd = pd.concat([load_symdir(out["nasdaqlisted"], "nasdaqlisted"),
                    load_symdir(out["otherlisted"], "otherlisted")])
    sd.to_parquet(DATA_DIR / "symdir_history.parquet")
    ti = load_tiingo()
    summary = {
        "company_tickers_snapshots": sorted(ct["snapshot"].unique().tolist()) if len(ct) else [],
        "company_tickers_rows_per_snapshot": ct.groupby("snapshot").size().to_dict() if len(ct) else {},
        "company_tickers_distinct_cik": int(ct["cik"].nunique()) if len(ct) else 0,
        "symdir_snapshots": sd.groupby(["kind", "snapshot"]).size().reset_index().values.tolist(),
        "tiingo_rows": len(ti), "tiingo_columns": list(ti.columns),
    }
    (REPORT_DIR / "universe_sources_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
