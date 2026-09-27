"""Sample the XBRL "frames" API (data.sec.gov/api/xbrl/frames/...), which returns every
filer's reported value for one concept/period in a single JSON response -- a live,
reachable cross-section that complements the (also successfully downloaded) bulk Financial
Statement Data Sets ZIP profiled in profile_bulk_samples.py.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.sample_xbrl_frames
"""
from __future__ import annotations

import json

from research.edgar_scout.common import DATA_DIR, Manifest, get

FRAMES = {
    "Assets_CY2023Q4I": "https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2023Q4I.json",
    "CommonStockSharesOutstanding_CY2023Q4I": "https://data.sec.gov/api/xbrl/frames/us-gaap/CommonStockSharesOutstanding/shares/CY2023Q4I.json",
    "NetIncomeLoss_CY2023Q4": "https://data.sec.gov/api/xbrl/frames/us-gaap/NetIncomeLoss/USD/CY2023Q4.json",
    "PaymentsOfDividendsCommonStock_CY2023": "https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsOfDividendsCommonStock/USD/CY2023.json",
}


def main() -> None:
    manifest = Manifest()
    out = {}
    for key, url in FRAMES.items():
        resp = get(url)
        if resp.status_code == 200:
            d = resp.json()
            data = d.get("data", [])
            ciks = {row["cik"] for row in data}
            out[key] = {
                "n_rows": len(data),
                "n_distinct_cik": len(ciks),
                "taxonomy": d.get("taxonomy"), "tag": d.get("tag"), "unit": d.get("uom"),
                "pts": d.get("pts"),
                "sample_row": data[0] if data else None,
            }
            manifest.record_bytes(f"xbrl_frames/{key}.json", url, resp.content, 200)
        else:
            out[key] = {"error": resp.status_code}
            manifest.record_refusal(f"xbrl_frames/{key}", url, resp.status_code, resp.text)
        print(key, {k: v for k, v in out[key].items() if k != "sample_row"})
    (DATA_DIR / "xbrl_frames_sample.json").write_text(json.dumps(out, indent=1, default=str))
    manifest.write(DATA_DIR / "xbrl_frames" / "manifest.json")


if __name__ == "__main__":
    main()
