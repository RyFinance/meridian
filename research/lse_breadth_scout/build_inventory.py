"""LSE breadth scout: reproducible local-catalog analysis (no MCP calls, no returns).

Read-only. Reads the already-downloaded catalog snapshot
`data/lse_catalog_20260917.json` (22,966 rows; itself pulled by an earlier
research session, not by this script) and reproduces the breadth counts used
in `reports/lse_breadth_scout/inventory.json`. Nothing here computes a
signal-return relationship; this is coverage/count bookkeeping only.

Live-terminal checks (news, options_flow, get_economics region breadth,
macro_search hits, screener, api_get /api/lse/databank, etc.) are NOT
reproduced here because they require the live MCP session; their raw results
are logged verbatim in `reports/lse_breadth_scout/mcp_call_log.json`.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/lse_breadth_scout/build_inventory.py
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "lse_catalog_20260917.json"


def load_catalog():
    return json.loads(CATALOG.read_text())


def dataset_counts(rows):
    return dict(Counter(r["dataset"] for r in rows).most_common())


def stocks_breakdown(rows):
    stocks = [r for r in rows if r["dataset"] == "stocks"]
    country = Counter(r.get("country_name", "") for r in stocks)
    live = Counter(r["live"] for r in stocks)
    return {
        "n": len(stocks),
        "country_name_top15": country.most_common(15),
        "live_distribution": dict(live),
        "n_non_live": live.get(0, 0),
        "note": "country_name is issuer domicile from the upstream feed, not trading venue; "
                "spot-checked names (AU=AngloGold Ashanti plc, FTI=TechnipFMC plc, LIN=Linde plc) "
                "are US-exchange (NYSE/NASDAQ) listings of foreign-domiciled issuers, not foreign-exchange "
                "executions. No `exchange` field is exposed by search_instruments or screener for this dataset.",
    }


def crypto_breakdown(rows):
    crypto = [r for r in rows if r["dataset"] == "crypto"]
    live = Counter(r["live"] for r in crypto)
    return {
        "n": len(crypto),
        "symbols": sorted(r["symbol"] for r in crypto),
        "live_distribution": dict(live),
        "non_live_symbols": sorted(r["symbol"] for r in crypto if r["live"] == 0),
    }


def fx_breakdown(rows):
    fx = [r for r in rows if r["dataset"] == "fx"]
    fxd = [r for r in rows if r["dataset"] == "fx_derivatives"]
    return {
        "fx_spot_n": len(fx),
        "fx_spot_symbols": sorted(r["symbol"] for r in fx),
        "fx_derivatives_n": len(fxd),
        "fx_derivatives_symbols": sorted(set(r["symbol"] for r in fxd)),
        "fx_derivatives_note": "9 G10 pairs x {SW fwd points, 1M/2M/3M/6M/9M/1Y ATM implied vol} = 63. "
                                "No EM forward points, no cross-currency basis swaps.",
    }


def bonds_breakdown(rows):
    bonds = [r for r in rows if r["dataset"] == "bonds"]
    country_tenor = Counter()
    for r in bonds:
        m = re.match(r"^([A-Z]{2})(\d+[A-Z])$", r["symbol"])
        if m:
            country_tenor[m.group(1)] += 1
    sy = [r for r in rows if r["dataset"] == "sovereign_yields"]
    return {
        "bonds_n": len(bonds),
        "bonds_n_countries": len(country_tenor),
        "bonds_tenors_per_country": dict(sorted(country_tenor.items())),
        "sovereign_yields_n": len(sy),
        "sovereign_yields_symbols": sorted(set(r["symbol"] for r in sy)),
        "note": "bonds and sovereign_yields are disjoint symbol sets covering similar ground "
                "from different apparent sources; bonds has far more country breadth (34) than "
                "sovereign_yields (8 countries x ~10 tenors).",
    }


def credit_futures_index_etf_commodity(rows):
    out = {}
    for ds in ["credit_indices", "futures", "index", "etf", "commodity", "interest_rates",
               "currency_index", "volatility"]:
        sub = [r for r in rows if r["dataset"] == ds]
        out[ds] = {
            "n": len(sub),
            "first_tick_min": min((r["first_tick"][:10] for r in sub), default=None),
            "first_tick_max": max((r["first_tick"][:10] for r in sub), default=None),
            "symbols": sorted(r["symbol"] for r in sub) if len(sub) <= 30 else f"{len(sub)} symbols, see catalog",
        }
    return out


def main():
    rows = load_catalog()
    report = {
        "catalog_file": str(CATALOG.relative_to(ROOT)),
        "catalog_n_rows": len(rows),
        "dataset_counts": dataset_counts(rows),
        "stocks": stocks_breakdown(rows),
        "crypto": crypto_breakdown(rows),
        "fx": fx_breakdown(rows),
        "bonds_and_yields": bonds_breakdown(rows),
        "other_families": credit_futures_index_etf_commodity(rows),
    }
    out_path = ROOT / "reports" / "lse_breadth_scout" / "catalog_breadth.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
