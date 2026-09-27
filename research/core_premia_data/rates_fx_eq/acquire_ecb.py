"""ECB data API ingest (keyless SDMX CSV). The ECB API timed out at the first probes of the
2026-09-26 session and answered at a later probe; this module was run then.
EURIBOR 3M (FM dataset) returned no rows for the tried keys and is recorded as a failure.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.acquire_ecb
"""
from __future__ import annotations

from research.core_premia_data.rates_fx_eq.common import META, fetch, utc_now, write_json

API = "https://data-api.ecb.europa.eu/service/data/"
SERIES = {
    "FM_EURIBOR3M_D": "FM/D.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
    "EXR_USD_EUR_D": "EXR/D.USD.EUR.SP00.A",
    "YC_AAA_SR_3M": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M",   # euro-area AAA govt spot curve, 2004+
    "YC_AAA_SR_2Y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    "YC_AAA_SR_10Y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
}


def run() -> dict:
    res = {}
    for name, key in SERIES.items():
        url = API + key + "?format=csvdata"
        r = fetch("ecb", name, url, ext="csv", timeout=180,
                  validate=lambda b: (b.count(b"\n") > 100, "few lines"))
        res[name] = {"ok": r is not None, "url": url, "raw_path": r["path"] if r else None,
                     "sha256": r["sha256"] if r else None, "bytes": r["bytes"] if r else 0,
                     "fetched_at_utc": r["fetched_at_utc"] if r else None}
    write_json(META / "acquire_ecb_results.json", {"run_at_utc": utc_now().isoformat(), "results": res})
    return res


if __name__ == "__main__":
    print({k: v["ok"] for k, v in run().items()})
