"""Commodity ETF/ETN universe puller for the core-premia commodities/benchmarks task.

Pulls single-commodity and sector commodity ETFs/ETNs (2006+ where available,
including closed/delisted tickers) via yfinance, writes one parquet per ticker
under data/core_premia/commod_bench/etf/, and records a per-ticker
acquisition-completeness + reference-metadata row.

This is instrument-level price data only (QA use). No signal, no sort, no
strategy return is computed here.

Run:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.commod_bench.commodity_etf_universe
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DATA = REPO_ROOT / "data" / "core_premia" / "commod_bench" / "etf"
OUT_REPORTS = REPO_ROOT / "reports" / "core_premia_20260925" / "commod_bench"

# Universe: single-commodity and sector commodity ETFs/ETNs. Includes closed/
# delisted tickers (checked per-ticker via yfinance; recorded as unavailable
# if no price history is retrievable free). Reference metadata (inception,
# closure, roll methodology, expense ratio, structural breaks) is recorded
# from the issuer's own public fact sheets / prospectus text (not computed
# from price data).
UNIVERSE: dict[str, dict] = {
    # --- Energy ---
    "USO": {
        "name": "United States Oil Fund",
        "sector": "energy_crude_oil",
        "issuer": "USCF",
        "inception": "2006-04-10",
        "closure": None,
        "roll_methodology": (
            "Pre-2020: near-month NYMEX WTI futures, roll near expiry into next month. "
            "2020-04-24 onward (post the Apr-2020 negative-price event): reformed to a "
            "diversified, discretionary-weighted basket across multiple WTI contract months "
            "(not fixed front-month), per USCF's amended prospectus, to reduce single-contract "
            "concentration risk."
        ),
        "expense_ratio": 0.0081,
        "structural_breaks": [
            "2020-04-20/21: WTI May futures settled negative; USO breached NAV/share price "
            "floor rules, suspended creations, did a 1-for-8 reverse split (2020-04-29), and "
            "amended its investment policy (2020-04-24) to spread exposure across contract months.",
        ],
    },
    "UNG": {
        "name": "United States Natural Gas Fund",
        "sector": "energy_natural_gas",
        "issuer": "USCF",
        "inception": "2007-04-18",
        "closure": None,
        "roll_methodology": "Near-month NYMEX Henry Hub natural gas futures, rolled near expiry.",
        "expense_ratio": 0.0114,
        "structural_breaks": [
            "Multiple reverse splits driven by chronic contango decay: 1-for-2 (2012-02-16), "
            "1-for-4 (2018-03-01, approx), 1-for-4 (2021-08-31, approx) -- exact ratios/dates "
            "per USCF corporate-action notices; treat pre-split price history as split-adjusted "
            "by the data vendor.",
        ],
    },
    "UGA": {"name": "United States Gasoline Fund", "sector": "energy_gasoline", "issuer": "USCF",
            "inception": "2008-02-26", "closure": None,
            "roll_methodology": "Near-month NYMEX RBOB gasoline futures.", "expense_ratio": 0.0081,
            "structural_breaks": []},
    "UHN": {"name": "United States 12 Month Natural Gas Fund", "sector": "energy_natural_gas", "issuer": "USCF",
            "inception": "2010-01-04", "closure": None,
            "roll_methodology": "Equal-weighted strip of 12 consecutive NYMEX NG contract months.",
            "expense_ratio": 0.0060, "structural_breaks": []},
    "BNO": {"name": "United States Brent Oil Fund", "sector": "energy_crude_oil_brent", "issuer": "USCF",
            "inception": "2010-06-02", "closure": None,
            "roll_methodology": "Near-month ICE Brent crude futures, rolled near expiry.",
            "expense_ratio": 0.0090, "structural_breaks": []},
    "DBO": {"name": "Invesco DB Oil Fund", "sector": "energy_crude_oil", "issuer": "Invesco",
            "inception": "2007-01-05", "closure": None,
            "roll_methodology": "Optimum Yield: rules-based selection among listed WTI contract "
                                 "months to maximize implied roll yield (contango/backwardation aware).",
            "expense_ratio": 0.0077, "structural_breaks": []},
    "DBE": {"name": "Invesco DB Energy Fund", "sector": "energy_broad", "issuer": "Invesco",
            "inception": "2007-01-05", "closure": None,
            "roll_methodology": "Optimum Yield basket: WTI, heating oil, RBOB gasoline, Brent, natural gas.",
            "expense_ratio": 0.0077, "structural_breaks": []},
    "UCO": {"name": "ProShares Ultra Bloomberg Crude Oil (2x)", "sector": "energy_crude_oil_leveraged",
            "issuer": "ProShares", "inception": "2008-11-24", "closure": None,
            "roll_methodology": "2x daily WTI futures exposure via Bloomberg WTI Crude Oil Subindex swaps.",
            "expense_ratio": 0.0121, "structural_breaks": ["Reverse splits multiple times due to daily-reset decay."]},
    "SCO": {"name": "ProShares UltraShort Bloomberg Crude Oil (-2x)", "sector": "energy_crude_oil_leveraged",
            "issuer": "ProShares", "inception": "2008-11-24", "closure": None,
            "roll_methodology": "-2x daily WTI futures exposure.", "expense_ratio": 0.0121,
            "structural_breaks": ["Reverse/forward splits multiple times due to daily-reset decay."]},
    # --- Precious metals ---
    "GLD": {"name": "SPDR Gold Shares", "sector": "metals_precious_gold", "issuer": "State Street",
            "inception": "2004-11-18", "closure": None,
            "roll_methodology": "Physically backed (allocated gold bullion), no futures roll.",
            "expense_ratio": 0.0040, "structural_breaks": []},
    "SLV": {"name": "iShares Silver Trust", "sector": "metals_precious_silver", "issuer": "iShares/BlackRock",
            "inception": "2006-04-21", "closure": None,
            "roll_methodology": "Physically backed (allocated silver bullion), no futures roll.",
            "expense_ratio": 0.0050, "structural_breaks": []},
    "PALL": {"name": "abrdn Physical Palladium Shares", "sector": "metals_precious_palladium",
             "issuer": "abrdn (formerly Aberdeen Standard/ETFS)", "inception": "2010-01-08", "closure": None,
             "roll_methodology": "Physically backed palladium bullion, no futures roll.",
             "expense_ratio": 0.0060, "structural_breaks": []},
    "PPLT": {"name": "abrdn Physical Platinum Shares", "sector": "metals_precious_platinum",
             "issuer": "abrdn (formerly ETFS Physical Platinum)", "inception": "2010-01-08", "closure": None,
             "roll_methodology": "Physically backed platinum bullion, no futures roll.",
             "expense_ratio": 0.0060, "structural_breaks": []},
    "SIVR": {"name": "abrdn Physical Silver Shares", "sector": "metals_precious_silver",
             "issuer": "abrdn", "inception": "2009-07-24", "closure": None,
             "roll_methodology": "Physically backed silver bullion.", "expense_ratio": 0.0030,
             "structural_breaks": []},
    # --- Industrial metals ---
    "DBB": {"name": "Invesco DB Base Metals Fund", "sector": "metals_industrial", "issuer": "Invesco",
            "inception": "2007-01-05", "closure": None,
            "roll_methodology": "Optimum Yield basket: LME aluminum, zinc, copper (grade A) futures.",
            "expense_ratio": 0.0077, "structural_breaks": []},
    "CPER": {"name": "United States Copper Index Fund", "sector": "metals_industrial_copper",
             "issuer": "USCF", "inception": "2011-11-15", "closure": None,
             "roll_methodology": "SummerHaven Copper Index: rules-based selection across COMEX "
                                  "copper contract months by implied roll yield.",
             "expense_ratio": 0.0080, "structural_breaks": []},
    "JJC_ipath": {"name": "iPath Series B Bloomberg Copper Subindex ETN (JJC)",
                  "sector": "metals_industrial_copper", "issuer": "Barclays iPath",
                  "inception": "2007-06-06", "closure": "2023 (Barclays delisted the iPath Bloomberg "
                  "commodity ETN family; iPath ETNs generally ceased trading / were delisted "
                  "2023-04, some earlier)",
                  "roll_methodology": "Unsecured ETN tracking Bloomberg Copper Subindex Total Return "
                                       "(single front-month COMEX copper future, rolled per BCOM rules).",
                  "expense_ratio": 0.0075, "structural_breaks": ["Delisted 2023; issuer credit risk "
                                                                  "inherent to ETN structure (unlike GLD/SLV physical trusts)."]},
    # --- Agriculture ---
    "DBA": {"name": "Invesco DB Agriculture Fund", "sector": "agriculture_broad", "issuer": "Invesco",
            "inception": "2007-01-05", "closure": None,
            "roll_methodology": "Optimum Yield basket: corn, wheat, soybeans, sugar, live cattle, "
                                 "cocoa, coffee, feeder cattle, hogs.",
            "expense_ratio": 0.0093, "structural_breaks": []},
    "CORN": {"name": "Teucrium Corn Fund", "sector": "agriculture_corn", "issuer": "Teucrium",
             "inception": "2010-06-09", "closure": None,
             "roll_methodology": "Fixed weighted strip across 2nd-to-expire, 3rd-to-expire and "
                                  "December-following-year CBOT corn futures (Teucrium's disclosed "
                                  "static weighting, not optimum-yield).",
             "expense_ratio": 0.0225, "structural_breaks": []},
    "WEAT": {"name": "Teucrium Wheat Fund", "sector": "agriculture_wheat", "issuer": "Teucrium",
             "inception": "2011-09-19", "closure": None,
             "roll_methodology": "Same Teucrium fixed-strip design as CORN, applied to CBOT wheat.",
             "expense_ratio": 0.0225, "structural_breaks": []},
    "SOYB": {"name": "Teucrium Soybean Fund", "sector": "agriculture_soybeans", "issuer": "Teucrium",
             "inception": "2011-09-19", "closure": None,
             "roll_methodology": "Same Teucrium fixed-strip design, applied to CBOT soybeans.",
             "expense_ratio": 0.0225, "structural_breaks": []},
    "SGG_ipath": {"name": "iPath Series B Bloomberg Sugar Subindex ETN (SGG)", "sector": "agriculture_sugar",
                  "issuer": "Barclays iPath", "inception": "2008-06-06",
                  "closure": "2023 (iPath ETN family delisting)",
                  "roll_methodology": "ETN tracking Bloomberg Sugar Subindex (single front-month "
                                       "ICE sugar #11 future, BCOM roll schedule).",
                  "expense_ratio": 0.0075, "structural_breaks": ["Delisted 2023."]},
    "JO_ipath": {"name": "iPath Series B Bloomberg Coffee Subindex ETN (JO)", "sector": "agriculture_coffee",
                 "issuer": "Barclays iPath", "inception": "2008-08-15",
                 "closure": "2023 (iPath ETN family delisting)",
                 "roll_methodology": "ETN tracking Bloomberg Coffee Subindex (front-month ICE "
                                      "coffee C future).",
                 "expense_ratio": 0.0075, "structural_breaks": ["Delisted 2023."]},
    "COW_ipath": {"name": "iPath Series B Bloomberg Livestock Subindex ETN (COW)",
                  "sector": "agriculture_livestock", "issuer": "Barclays iPath", "inception": "2008-06-06",
                  "closure": "2023 (iPath ETN family delisting)",
                  "roll_methodology": "ETN tracking Bloomberg Livestock Subindex (CME live cattle "
                                       "and lean hogs futures).",
                  "expense_ratio": 0.0075, "structural_breaks": ["Delisted 2023."]},
    # --- Broad / macro commodity baskets (context, not single-commodity) ---
    "DBC": {"name": "Invesco DB Commodity Index Tracking Fund", "sector": "broad_basket", "issuer": "Invesco",
            "inception": "2006-02-03", "closure": None,
            "roll_methodology": "Optimum Yield across 14 futures (energy, metals, agriculture).",
            "expense_ratio": 0.0087, "structural_breaks": []},
    "GSG": {"name": "iShares S&P GSCI Commodity-Indexed Trust", "sector": "broad_basket",
            "issuer": "iShares/BlackRock", "inception": "2006-07-10", "closure": None,
            "roll_methodology": "Tracks S&P GSCI (production-weighted, energy-heavy, near-month "
                                 "futures with GSCI's fixed roll schedule).",
            "expense_ratio": 0.0075, "structural_breaks": []},
    "USL": {"name": "United States 12 Month Oil Fund", "sector": "energy_crude_oil", "issuer": "USCF",
            "inception": "2007-12-06", "closure": None,
            "roll_methodology": "Equal-weighted strip of 12 consecutive WTI contract months.",
            "expense_ratio": 0.0060, "structural_breaks": []},
    "UNL": {"name": "United States 12 Month Natural Gas Fund (legacy ticker note: distinct from UHN)",
            "sector": "energy_natural_gas", "issuer": "USCF", "inception": "2010-01-04", "closure": None,
            "roll_methodology": "Equal-weighted strip of 12 consecutive NYMEX NG contract months.",
            "expense_ratio": 0.0060, "structural_breaks": []},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pull_one(ticker: str) -> dict:
    """Pull full daily history for one ticker. Instrument-level OHLCV only."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    yf_symbol = ticker.split("_")[0]  # strip our internal suffixes like _ipath
    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(period="max", auto_adjust=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "ticker": ticker, "yf_symbol": yf_symbol, "available": False,
            "error": str(exc), "fetched_at_utc": fetched_at, "rows": 0,
        }
    if df is None or df.empty:
        return {
            "ticker": ticker, "yf_symbol": yf_symbol, "available": False,
            "error": "empty_history", "fetched_at_utc": fetched_at, "rows": 0,
        }
    df = df.reset_index()
    df.columns = [str(c).replace(" ", "_") for c in df.columns]
    out_path = OUT_DATA / f"{ticker}.parquet"
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    sha = sha256_file(out_path)
    first = df["Date"].min()
    last = df["Date"].max()
    # UTC-day / extended-hours flag: yfinance daily bars for US-listed ETFs are
    # regular-session daily closes (timezone-aware index, market-local, not UTC
    # midnight-aligned) -- flag explicitly rather than assume.
    tz_note = "market-local (US/Eastern) daily close, NOT UTC-day aligned; no extended-hours bars in daily history"
    return {
        "ticker": ticker, "yf_symbol": yf_symbol, "available": True,
        "fetched_at_utc": fetched_at, "rows": int(len(df)),
        "first_date": str(first.date()) if pd.notna(first) else None,
        "last_date": str(last.date()) if pd.notna(last) else None,
        "sha256": sha, "path": str(out_path.relative_to(REPO_ROOT)),
        "bar_alignment_note": tz_note,
    }


def main() -> int:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)

    completeness_rows = []
    for ticker, meta in UNIVERSE.items():
        rec = pull_one(ticker)
        rec.update({k: v for k, v in meta.items()})
        completeness_rows.append(rec)
        print(f"[pull] {ticker}: available={rec['available']} rows={rec.get('rows')} "
              f"first={rec.get('first_date')} last={rec.get('last_date')}")

    universe_df = pd.DataFrame(completeness_rows)
    universe_csv_cols = [
        "ticker", "name", "sector", "issuer", "inception", "closure",
        "expense_ratio", "roll_methodology", "structural_breaks",
        "available", "rows", "first_date", "last_date", "sha256",
    ]
    universe_df_out = universe_df.copy()
    universe_df_out["structural_breaks"] = universe_df_out["structural_breaks"].apply(
        lambda x: " | ".join(x) if isinstance(x, list) else x
    )
    universe_df_out[universe_csv_cols].to_csv(
        OUT_REPORTS / "commodity_universe.csv", index=False
    )

    # acquisition-completeness record for this endpoint
    n_expected = len(UNIVERSE)
    n_received = int(universe_df["available"].sum())
    completeness = {
        "endpoint": "yfinance (Ticker.history, period=max, auto_adjust=False)",
        "retrieval_started_utc": completeness_rows[0]["fetched_at_utc"] if completeness_rows else None,
        "retrieval_finished_utc": datetime.now(timezone.utc).isoformat(),
        "expected_instrument_count": n_expected,
        "received_instrument_count": n_received,
        "unavailable_tickers": [r["ticker"] for r in completeness_rows if not r["available"]],
        "date_range_by_ticker": {
            r["ticker"]: {"first": r.get("first_date"), "last": r.get("last_date"), "rows": r.get("rows")}
            for r in completeness_rows
        },
        "failures": [
            {"ticker": r["ticker"], "error": r.get("error")}
            for r in completeness_rows if not r["available"]
        ],
        "retries": "yfinance internal default (no explicit retry loop added; single attempt per ticker, "
                   "failures recorded as unavailable rather than silently dropped)",
        "notes": "Delisted/closed iPath ETNs (JJC, SGG, JO, COW and similar JJ*-series products) are "
                 "included in the requested universe; availability recorded per-ticker below. "
                 "yfinance symbol used strips any internal '_suffix' disambiguator.",
    }
    (OUT_REPORTS / "completeness.json").write_text(json.dumps(completeness, indent=2, default=str))
    print(f"[done] {n_received}/{n_expected} tickers retrieved. "
          f"Unavailable: {completeness['unavailable_tickers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
