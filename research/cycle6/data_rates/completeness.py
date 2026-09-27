"""Write data/cycle6/rates/completeness.json (per endpoint: API/URL, retrieval UTC, expected vs received, failures,
conventions). Reads only ingest records (never filesystem mtimes)."""
from __future__ import annotations

import json

import pandas as pd

from research.cycle6.data_rates.common import COMM, META, OLD, OUT, RAW, utc_now, write_json


def main():
    disc = json.loads((META / "lse_discover.json").read_text())
    pull = json.loads((META / "lse_pull.json").read_text())
    run1 = json.loads((META / "lse_pull_run1_aborted.json").read_text())
    D = json.loads((RAW / "lse_series_combined.json").read_text())
    per = {}
    for c in pull["calls"]:
        k = f"{c['dataset']}/{c['symbol']}"
        r = per.setdefault(k, {"calls": 0, "errors": 0, "truncated_split": 0, "first_fetch_utc": None, "last_fetch_utc": None})
        r["calls"] += 1
        r["errors"] += int(bool(c.get("err")))
        r["truncated_split"] += int(bool(c.get("truncated")))
        f = c.get("fetched_at_utc")
        if f:
            r["first_fetch_utc"] = min(filter(None, [r["first_fetch_utc"], f]))
            r["last_fetch_utc"] = max(filter(None, [r["last_fetch_utc"], f]))
    for k, v in D.items():
        rows = v["rows"]
        per.setdefault(k, {}).update({"catalog_first": v["meta"]["first"], "catalog_last": v["meta"]["last"],
                                      "catalog_frequency": v["meta"].get("frequency"), "name": v["meta"].get("name"),
                                      "received_rows": len(rows),
                                      "received_first": rows[0]["date"] if rows else None,
                                      "received_last": rows[-1]["date"] if rows else None,
                                      "complete_vs_catalog": bool(rows) and rows[0]["date"] == v["meta"]["first"]
                                      and rows[-1]["date"] == v["meta"]["last"]})
    old_off = json.loads((OLD / "meta" / "acquire_official_results.json").read_text())
    old_ecb = json.loads((OLD / "meta" / "acquire_ecb_results.json").read_text())
    reused = {k: {x: v.get(x) for x in ("url", "fetched_at_utc", "ok", "sha256", "raw_path")}
              for k, v in {**old_off["results"], **old_ecb["results"]}.items()
              if k.split("/")[0] in ("fed_h15", "h15", "fed_h10", "h10", "boe", "boe_iadb", "bundesbank", "mof", "mof_japan",
                                     "boc", "boc_valet", "riksbank", "norges_bank", "norges", "ecb", "snb", "oecd")}
    y = pd.read_parquet(OLD / "processed" / "yields_daily.parquet")
    offr = {f"{s}/{i}": {"first": str(g.date.min().date()), "last": str(g.date.max().date()), "rows": len(g)}
            for (s, i), g in y.groupby(["source", "series_id"]) if not s.startswith("lse_vault")}
    comm_c = json.loads((ROOT_REPORT / "completeness.json").read_text()) if ROOT_REPORT.exists() else {}
    br = json.loads((META / "build_record.json").read_text())
    out = {
        "written_utc": utc_now().isoformat(),
        "scope": "cycle-6 DATA agent: rates + FX + commodities (research only; no signals/strategy returns)",
        "endpoints": {
            "lse_terminal_mcp.macro_search": {
                "api": "LSE Terminal stdio MCP via research.lse_mcp_client (read-only whitelist), tool macro_search",
                "retrieval_utc": disc["run_at_utc"], "calls": len(disc["calls"]),
                "failures": sum(bool(c.get("err")) for c in disc["calls"]),
                "arguments": "query in {yield, rate, bill, interbank} x country in 19 codes, limit 300",
                "series_found": len(disc["series"]),
                "raw": "data/cycle6/rates/raw/lse_mcp_catalog/", "note": "first attempt inside the OS sandbox saw "
                "'terminal not running' (localhost blocked); rerun outside the sandbox succeeded; no call failed"},
            "lse_terminal_mcp.macro_series": {
                "api": "LSE Terminal MCP tool macro_series (dataset bonds|economics), 4-year windows, recursive halving "
                       "when the reply carries the '... truncated' marker (~60,000 chars)",
                "retrieval_utc": pull["run_at_utc"], "calls": pull["n_calls"],
                "failures": sum(bool(c.get("err")) for c in pull["calls"]),
                "consecutive_failure_guard": "stop after 3; not triggered in the final run",
                "earlier_run": {"file": "meta/lse_pull_run1_aborted.json", "note": pull.get("previous_run_note"),
                                "calls": len(run1.get("calls", []))},
                "expected": "every daily 'bonds' series of the target countries with catalog first date < 2020-01-01 "
                            "+ 22 short-rate 'economics' series",
                "not_pulled_short_history": pull["not_pulled_short_history"],
                "per_series": per, "raw": "data/cycle6/rates/raw/lse_mcp_series/ + raw/lse_series_combined.json"},
            "official_reused_from_core_premia_acq_v1": {
                "note": "not re-downloaded; bytes frozen in snapshot core_premia_rates_fx_eq_acq_v1 (manifest "
                        "8b5e6205cf5f...); processed table data/core_premia/rates_fx_eq/processed/yields_daily.parquet",
                "fetch_records": reused, "series_ranges": offr},
            "fed_h10_fx": {"source": "data/core_premia/rates_fx_eq/processed/fx_spot_daily.parquet (source fed_h10)",
                           "expected": "9 G10 vs USD", "received": 9,
                           "convention": "USD per unit of currency, noon NY buying rate"},
            "oecd_monthly_short_rates": {"source": "data/core_premia/rates_fx_eq/processed/oecd_monthly.parquet",
                                         "convention": "IR3TIB > IRSTCI, monthly AVERAGE, usable from the 1st day of the "
                                                       "following month"},
            "commodity_etfs": {"source": "data/core_premia/commod_bench/etf/*.parquet (yfinance, auto_adjust=False; "
                                         "Adj_Close used)", "retrieval": comm_c.get("retrieval_started_utc"),
                               "expected": 12, "received": 12, "not_candidates": br["not_candidate_cm"]},
            "eia_nymex_c1_c4": {"source": "data/core_premia/commod_bench/eia_audit/{crude_oil_wti_cushing,"
                                          "natural_gas_henry_hub_futures}.parquet (EIA PET_PRI_FUT_S1_D / NG_PRI_FUT_S1_D)",
                                "last_date": "2024-04-05 (EIA discontinued)", "qa": br["cm_eia_qa"],
                                "convention": "director roll correction: first trading day after expiry return = "
                                              "C1_t/C2_{t-1}-1; CL expiry = 3 bd before the 25th (preceding bd if the "
                                              "25th is not one), NG expiry = 3 bd before the 1st of the delivery month; "
                                              "business days = the series' own trading dates; days with price <= 0 "
                                              "(WTI 2020-04-20/21) have undefined return (NaN)"},
        },
        "conventions": {
            "bond_excess": "r = y_{t-1}dt - D_{t-1}dy + 0.5 C_{t-1}dy^2 - rf_{t-1}dt, dt = calendar days/365, D,C of a "
                           "par bond with coupon y_{t-1} (annual coupon DE/FR/IT/ES/CH/SE/NO, semiannual otherwise); "
                           "same code as research/core_premia_data/rates_fx_eq/synthetic.py; no roll-down in the return",
            "bond_carry_inputs": "month-end (last obs in month): yield, local short rate (as known that day), slope = y "
                                 "- rf, roll-down = D x (y_T - y_n)/(T - n) with n the next shorter curve tenor >= 1y "
                                 "(own source preferred; else the 0.25y local short rate), carry = y - rf + roll-down, "
                                 "all % p.a.",
            "short_rates": "official daily (lag 1 obs, ffill <= 10 bd) > LSE daily (JPY JP3M bill, AUD BBSW, CHF CH3M, "
                           "NZD interbank, NOK interbank; lag 1 obs) > OECD monthly (prev month). EUR members use EUR "
                           "(ECB AAA 3M from 2004, OECD EA before)",
            "fx_excess": "S_t/S_{t-1} - 1 + (rf_ccy - rf_usd)_{t-1} dt",
            "commodity_excess": "ETF adjusted-close return - USD 3M (H.15) x dt; EIA futures return is already excess",
            "history_start_rule": "after the last unexplained gap > 10 bd and after the last flat run >= 10 bd (strict "
                                  "full-history status recorded in candidates notes)",
            "qa": "FRAMEWORK §3 (a)-(d); proxies pre-declared in build.py PROXY_FI / PROXY_FX; TE on monthly compounded "
                  "excess returns over months where the synthetic is defined on every row",
        },
        "vendor_vs_official_yield_check": br["vendor_vs_official"],
        "fi_official_rejected": br["fi_official_rejected"],
        "row_counts": br["rows"],
    }
    write_json(OUT / "completeness.json", out)


ROOT_REPORT = OUT.parents[1].parent / "reports" / "core_premia_20260925" / "commod_bench"

if __name__ == "__main__":
    main()
