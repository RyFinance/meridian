"""Public market-structure/positioning/crypto data scout (Workload B, cycle 4).

Builds data/public_scout/MANIFEST.json: for every small sample file fetched during this scout,
records the exact source URL, the fetch time (UTC), the file size and its sha256. The files
themselves were fetched with `curl -A "quant_v7-research/1.0"`, politely (<=3 req/s, one host at
a time), during the session on 2026-09-24 evening (UTC). This script does not re-fetch anything;
it only re-hashes what is already on disk and pairs it with the URL used to fetch it (recorded
by hand below, since curl was invoked directly rather than through a single Python fetcher).

Run:
    cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.public_scout.build_manifest
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/public_scout"

# fetch time recorded for the whole batch (single scouting session)
FETCH_TIME_UTC = "2026-09-25T05:04:00Z"  # to ~05:16Z; see individual curl timestamps in session log
USER_AGENT = "quant_v7-research/1.0"

# relative path (under data/public_scout/) -> source URL
SOURCES: dict[str, str] = {
    # FINRA Reg SHO daily short-sale volume (consolidated NMS + 3 per-venue files)
    "finra_regsho/CNMSshvol20260922.txt": "https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260922.txt",
    "finra_regsho/CNMSshvol20260923.txt": "https://cdn.finra.org/equity/regsho/daily/CNMSshvol20260923.txt",
    "finra_regsho/FNSQshvol20260923.txt": "https://cdn.finra.org/equity/regsho/daily/FNSQshvol20260923.txt",
    "finra_regsho/FNYXshvol20260923.txt": "https://cdn.finra.org/equity/regsho/daily/FNYXshvol20260923.txt",
    "finra_regsho/FORFshvol20260923.txt": "https://cdn.finra.org/equity/regsho/daily/FORFshvol20260923.txt",
    # FINRA bi-monthly consolidated short interest (exchange + OTC unified in this bulk file)
    "finra_short_interest/shrt20210715.csv": "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20210715.csv",
    "finra_short_interest/shrt20260831.csv": "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260831.csv",
    # CFTC Commitments of Traders, annual history ZIPs (legacy, disaggregated, TFF, CIT/supplemental)
    "cftc_cot/deacot1986.zip": "https://www.cftc.gov/files/dea/history/deacot1986.zip",
    "cftc_cot/deacot2024.zip": "https://www.cftc.gov/files/dea/history/deacot2024.zip",
    "cftc_cot/fut_disagg_txt_2010.zip": "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2010.zip",
    "cftc_cot/fut_disagg_txt_2024.zip": "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2024.zip",
    "cftc_cot/fut_fin_txt_2010.zip": "https://www.cftc.gov/files/dea/history/fut_fin_txt_2010.zip",
    "cftc_cot/fut_fin_txt_2024.zip": "https://www.cftc.gov/files/dea/history/fut_fin_txt_2024.zip",
    "cftc_cot/dea_cit_txt_2006.zip": "https://www.cftc.gov/files/dea/history/dea_cit_txt_2006.zip",
    "cftc_cot/dea_cit_txt_2024.zip": "https://www.cftc.gov/files/dea/history/dea_cit_txt_2024.zip",
    # Binance USD-M perpetual futures public data (data.binance.vision), incl. two delisted tokens
    "binance/BTCUSDT-fundingRate-2020-01.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2020-01.zip",
    "binance/BTCUSDT-metrics-2024-01-15.zip": "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2024-01-15.zip",
    "binance/BTCUSDT-premIdx-2024-01.zip": "https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/BTCUSDT/1d/BTCUSDT-1d-2024-01.zip",
    "binance/BTCUSDT-spot-klines-2017-08.zip": "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2017-08.zip",
    "binance/LUNAUSDT-fundingRate-2022-01.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/LUNAUSDT/LUNAUSDT-fundingRate-2022-01.zip",
    "binance/LUNAUSDT-fundingRate-2022-04.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/LUNAUSDT/LUNAUSDT-fundingRate-2022-04.zip",
    "binance/LUNAUSDT-fundingRate-2022-05.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/LUNAUSDT/LUNAUSDT-fundingRate-2022-05.zip",
    "binance/FTTUSDT-fundingRate-2022-10.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/FTTUSDT/FTTUSDT-fundingRate-2022-10.zip",
    "binance/FTTUSDT-fundingRate-2022-11.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/FTTUSDT/FTTUSDT-fundingRate-2022-11.zip",
    "binance/FTTUSDT-fundingRate-2022-12.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/FTTUSDT/FTTUSDT-fundingRate-2022-12.zip",
    "binance/SRMUSDT-fundingRate-2022-01.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/SRMUSDT/SRMUSDT-fundingRate-2022-01.zip",
    "binance/SRMUSDT-fundingRate-2022-10.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/SRMUSDT/SRMUSDT-fundingRate-2022-10.zip",
    "binance/SRMUSDT-fundingRate-2022-11.zip": "https://data.binance.vision/data/futures/um/monthly/fundingRate/SRMUSDT/SRMUSDT-fundingRate-2022-11.zip",
    # TreasuryDirect auction results (rich fields: bid-to-cover, tail, indirect/direct, primary dealer)
    "treasury_auctions/notes_1985_sample.json": "https://www.treasurydirect.gov/TA_WS/securities/search?format=json&startDate=1985-01-01&endDate=1985-12-31&type=Note",
    "treasury_auctions/notes_2024_sample.json": "https://www.treasurydirect.gov/TA_WS/securities/search?format=json&startDate=2024-01-01&endDate=2024-12-31&type=Note",
    # Wikipedia pageviews (keyless, daily, from 2015-07-01)
    "wikipedia/Apple_Inc_daily_201507.json": "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/Apple_Inc./daily/2015070100/2015073100",
    # FRED (keyless CSV download; note GDP series id hung/timed out repeatedly, DGS10 worked)
    "fred/DGS10_sample.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> dict:
    entries = []
    missing = []
    for rel, url in sorted(SOURCES.items()):
        p = DATA / rel
        if not p.exists():
            missing.append(rel)
            continue
        entries.append({
            "path": rel,
            "url": url,
            "fetch_time_utc": FETCH_TIME_UTC,
            "user_agent": USER_AGENT,
            "size_bytes": p.stat().st_size,
            "sha256": sha256_of(p),
        })
    on_disk = {str(p.relative_to(DATA)) for p in DATA.rglob("*") if p.is_file() and p.name != "MANIFEST.json"}
    unrecorded = sorted(on_disk - set(SOURCES))
    return {"entries": entries, "missing_on_disk": missing, "unrecorded_files": unrecorded}


def main() -> None:
    result = build()
    out = DATA / "MANIFEST.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out} with {len(result['entries'])} entries")
    if result["missing_on_disk"]:
        print("WARNING missing on disk:", result["missing_on_disk"])
    if result["unrecorded_files"]:
        print("WARNING files on disk without a recorded URL:", result["unrecorded_files"])


if __name__ == "__main__":
    main()
