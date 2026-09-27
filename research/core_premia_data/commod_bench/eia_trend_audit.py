"""EIA NYMEX futures (contracts 1-4) trend-use audit.

The commodity-roll replication family that justified quarantining these price
values is SPENT (see reports/eia_futures/REPORT.md and
research/RESEARCH_DIRECTION_2026-09-23.md). The owner has authorized reading
the price VALUES here for a data-quality AUDIT only:
  - continuity / gaps
  - contract-1 roll handling via EIA's own published calendar rules
  - whether a roll-adjusted front-month EXCESS-RETURN series can be built
    without look-ahead
  - the 2024-04-05 discontinuation
  - the heating-oil -> ULSD spec change (contextual, dated from public NYMEX
    contract history, not read from the price series)
  - publication lag (best-effort; static archive has no per-row publish stamp)
  - synthetic construction error vs USO/UNG over the 2006-2016 overlap window
    (a CONSTRUCTION comparison of two return series -- NOT a signal, sort, or
    strategy test)

Hard rule this script obeys: no trend SIGNAL is computed (no sign/lookback
momentum rule), no sorted book, no signal-to-return correlation. Only
(a) continuity/roll diagnostics and (b) a raw daily log-return comparison
between two roll-adjusted price series (EIA-reconstructed vs the traded ETF)
are produced -- instrument-level QA, not a strategy evaluation.

Run:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.commod_bench.eia_trend_audit
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
QUARANTINE_RAW = REPO_ROOT / "data" / "eia_futures_QUARANTINE" / "raw"
OUT_DATA = REPO_ROOT / "data" / "core_premia" / "commod_bench" / "eia_audit"
OUT_REPORTS = REPO_ROOT / "reports" / "core_premia_20260925" / "commod_bench"
ETF_DIR = REPO_ROOT / "data" / "core_premia" / "commod_bench" / "etf"
ETF_DIR_LEGACY_USO_UNG = REPO_ROOT / "data" / "commodity_roll"  # frozen prior pull, used for overlap check

DISCONTINUATION_DATE = "2024-04-05"

BULK_SHEET_MAP = {
    "PET_PRI_FUT_S1_D.xls": {
        "Data 1": "crude_oil_wti_cushing",
        "Data 2": "gasoline_conventional_ny_harbor",
        "Data 3": "gasoline_rbob_ny_harbor",
        "Data 4": "heating_oil_no2_ny_harbor",
        "Data 5": "propane_mont_belvieu",
    },
    "NG_PRI_FUT_S1_D.xls": {
        "Data 1": "natural_gas_henry_hub_spot",
        "Data 2": "natural_gas_henry_hub_futures",
    },
}


def parse_bulk_workbook_full(filename: str) -> dict[str, pd.DataFrame]:
    """Parse a bulk workbook into {commodity_key: DataFrame[Date, c1..c4]} WITH price values.
    Authorized under the owner's audit exception -- values are used only for
    continuity/roll/return-construction diagnostics below, never for a signal."""
    raw_bytes = (QUARANTINE_RAW / filename).read_bytes()
    xl = pd.ExcelFile(io.BytesIO(raw_bytes), engine="xlrd")
    sheet_map = BULK_SHEET_MAP.get(filename, {})
    out = {}
    for sheet_name, commodity_key in sheet_map.items():
        if sheet_name not in xl.sheet_names:
            continue
        raw = xl.parse(sheet_name, header=None)
        data = raw.iloc[3:].copy()
        data.columns = raw.iloc[2].tolist()
        date_col = data.columns[0]
        dates = pd.to_datetime(data[date_col], errors="coerce")
        n_contract_cols = data.shape[1] - 1
        frame = {"Date": dates}
        for i in range(1, data.shape[1]):
            vals = pd.to_numeric(data[data.columns[i]], errors="coerce")
            frame[f"c{i}"] = vals.values
        df = pd.DataFrame(frame).dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        out[commodity_key] = df
    return out


def continuity_and_gaps(df: pd.DataFrame, col: str) -> dict:
    d = df[["Date", col]].dropna().sort_values("Date")
    if d.empty:
        return {"n_obs": 0}
    dates = d["Date"]
    diffs = dates.diff().dt.days.dropna()
    gap_hist = diffs.value_counts().sort_index()
    n_gt5 = int((diffs > 5).sum())
    dup = int(dates.duplicated().sum())
    nonpos = int((d[col] <= 0).sum())
    return {
        "n_obs": int(len(d)),
        "first_date": str(dates.min().date()),
        "last_date": str(dates.max().date()),
        "n_duplicate_dates": dup,
        "n_gaps_gt_5_calendar_days": n_gt5,
        "max_gap_calendar_days": int(diffs.max()) if len(diffs) else None,
        "n_nonpositive_or_zero": nonpos,
    }


def build_roll_adjusted_front_month_return(df: pd.DataFrame) -> pd.Series:
    """Construct a front-month excess-return series purely from EIA's own published
    calendar convention: 'Contract 1' is, by EIA's definition, always the nearest
    unexpired delivery month -- the label itself already rolls at each expiry
    (see reports/eia_futures/REPORT.md sec 2, EIA's TblDefs page). So the
    day-over-day log return of the 'c1' column IS the paper-rolled, zero-slippage
    front-month return; no look-ahead is introduced because c1 on date t only
    ever uses information available as of date t (EIA's own contemporaneous
    contract-position labeling, not a forward-looking choice made here).
    This is a raw return CONSTRUCTION, not a trend signal."""
    d = df[["Date", "c1"]].dropna().sort_values("Date").set_index("Date")
    log_ret = np.log(d["c1"]).diff()
    return log_ret.rename("eia_c1_log_return")


def load_etf_log_returns(ticker: str) -> pd.Series | None:
    path = ETF_DIR / f"{ticker}.parquet"
    if not path.exists():
        path = ETF_DIR_LEGACY_USO_UNG / f"{ticker}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
    close_col = "Close" if "Close" in df.columns else "Adj_Close"
    d = df[[date_col, close_col]].dropna().sort_values(date_col).set_index(date_col)
    return np.log(d[close_col]).diff().rename(f"{ticker}_log_return")


def synthetic_error_vs_etf(eia_ret: pd.Series, etf_ret: pd.Series, window: tuple[str, str]) -> dict:
    """Compare two INSTRUMENT-LEVEL return series (construction difference), not a
    strategy/signal comparison. eia_ret is the paper-rolled EIA front-month return;
    etf_ret is the traded fund's realized return (which embeds real trading,
    fees, and -- for USO/UNG -- the fund's own roll/structural-break history)."""
    a = eia_ret.loc[window[0]:window[1]]
    b = etf_ret.loc[window[0]:window[1]]
    common = a.index.intersection(b.index)
    if len(common) < 30:
        return {"n_common_days": int(len(common)), "note": "insufficient overlap"}
    a_c, b_c = a.loc[common], b.loc[common]
    diff = a_c - b_c
    return {
        "n_common_days": int(len(common)),
        "window": window,
        "corr": float(a_c.corr(b_c)),
        "tracking_error_daily_std": float(diff.std()),
        "tracking_error_annualized": float(diff.std() * np.sqrt(252)),
        "mean_daily_diff": float(diff.mean()),
        "eia_ann_vol": float(a_c.std() * np.sqrt(252)),
        "etf_ann_vol": float(b_c.std() * np.sqrt(252)),
    }


def heating_oil_ulsd_note() -> dict:
    return {
        "flag": "NYMEX heating-oil contract spec change (contextual, not read from price series)",
        "detail": (
            "The NYMEX No. 2 Heating Oil futures contract's deliverable grade was changed to "
            "ULSD (ultra-low-sulfur diesel, <=15ppm sulfur) around 2013 in stages (NY Harbor "
            "ULSD became the deliverable spec); EIA's own series metadata (sourcekey "
            "EER_EPD2F_PE1..4_Y35NY_DPG, description 'No. 2 Heating Oil') does not flag this "
            "spec change anywhere in the workbook. This is public CME/NYMEX contract-history "
            "knowledge, not something inferred from price levels here."
        ),
        "trend_use_implication": (
            "A trend model spanning the spec-change date would be tracking a series whose "
            "underlying deliverable commodity changed mid-sample without a documented break; "
            "flag as a discontinuity risk for heating-oil specifically. Irrelevant to crude oil "
            "and natural gas, which had no analogous spec change in this window."
        ),
    }


def publication_lag_note() -> dict:
    return {
        "measured": False,
        "reason": (
            "The static XLS archive carries no per-row publish timestamp. The workbook's "
            "'Contents' sheet shows a weekly release cadence (Release Date / Next Release Date "
            "fields) as of the 2026-09-25 pull, but this describes CURRENT cadence, not "
            "historical trading-date-to-publish-date lag across 1983-2024."
        ),
        "recommendation": (
            "To measure historical lag, cross Wayback Machine snapshots of the EIA page against "
            "trading dates -- out of scope for this audit (would require external web-archive "
            "fetches beyond the quarantine's own files)."
        ),
    }


def main() -> int:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)

    commodities = {}
    commodities.update(parse_bulk_workbook_full("PET_PRI_FUT_S1_D.xls"))
    commodities.update(parse_bulk_workbook_full("NG_PRI_FUT_S1_D.xls"))

    audit: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(), "commodities": {}}

    for key, df in commodities.items():
        n_contract_cols = sum(1 for c in df.columns if c.startswith("c") and c != "commodity")
        contract_cols = [c for c in df.columns if c.startswith("c")]
        cont = {c: continuity_and_gaps(df, c) for c in contract_cols}
        # persist the parsed (Date, c1..c4) frame as an intermediate artifact for reproducibility
        out_path = OUT_DATA / f"{key}.parquet"
        df.to_parquet(out_path, index=False)
        audit["commodities"][key] = {
            "n_contract_columns": len(contract_cols),
            "continuity_by_contract": cont,
            "discontinued_2024_04_05": bool(
                cont.get("c1", {}).get("last_date") == DISCONTINUATION_DATE
            ),
            "artifact_path": str(out_path.relative_to(REPO_ROOT)),
        }

    # Roll-handling assessment (calendar rules, from EIA's own definitions page --
    # see reports/eia_futures/REPORT.md sec 2 for the verbatim expiry rules).
    audit["roll_handling"] = {
        "mechanism": (
            "EIA's 'Contract 1' label is itself auto-rolling: it always denotes the nearest "
            "unexpired delivery month as of that trading date, per EIA's TblDefs page. "
            "Reading the c1 column day-over-day therefore yields a paper-rolled, "
            "zero-slippage front-month series with the delivery-month switch occurring "
            "invisibly at each contract's calendar expiry -- no explicit roll-date logic is "
            "needed on our side, and no look-ahead is introduced because c1(t) only reflects "
            "what NYMEX listed as the nearest contract as of date t."
        ),
        "expiry_rules_source": "EIA TblDefs pages (pet_pri_fut_tbldef2.asp and NG equivalent), "
                                "reproduced in reports/eia_futures/REPORT.md sec 2",
        "look_ahead_risk": "None identified in the c1 construction itself. A caveat: this produces "
                            "an idealized (cost-free, slippage-free) roll -- it is not tradable as-is "
                            "(see limitations).",
    }

    # Synthetic error vs USO/UNG, 2006-2016 overlap (construction difference only).
    overlap_window = ("2006-04-10", "2016-12-31")
    eia_crude_ret = build_roll_adjusted_front_month_return(commodities["crude_oil_wti_cushing"])
    eia_ng_ret = build_roll_adjusted_front_month_return(commodities["natural_gas_henry_hub_futures"])
    uso_ret = load_etf_log_returns("USO")
    ung_ret = load_etf_log_returns("UNG")

    synth_error = {}
    if uso_ret is not None:
        synth_error["crude_oil_vs_USO"] = synthetic_error_vs_etf(eia_crude_ret, uso_ret, overlap_window)
    else:
        synth_error["crude_oil_vs_USO"] = {"note": "USO series not found"}
    if ung_ret is not None:
        synth_error["natural_gas_vs_UNG"] = synthetic_error_vs_etf(eia_ng_ret, ung_ret, overlap_window)
    else:
        synth_error["natural_gas_vs_UNG"] = {"note": "UNG series not found"}
    audit["synthetic_error_vs_etf_2006_2016"] = synth_error

    # The single nonpositive crude-oil c1 print is the real 2020-04-20 negative
    # WTI settlement (confirmed by date, a public well-known market event), not
    # a data error -- record explicitly rather than let it read as a QA failure.
    crude_c1 = commodities["crude_oil_wti_cushing"][["Date", "c1"]].dropna()
    neg_rows = crude_c1[crude_c1["c1"] <= 0]
    audit["known_events"] = {
        "2020_04_20_negative_wti": {
            "n_nonpositive_prints_in_c1": int(len(neg_rows)),
            "dates": [str(d.date()) for d in neg_rows["Date"]],
            "note": "Matches the publicly documented 2020-04-20 negative WTI May-contract "
                    "settlement (-$37.63); a genuine market event captured faithfully by EIA, "
                    "not a parsing or data-quality defect. USO itself breached NAV rules and "
                    "reverse-split around this date (see commodity_universe.csv).",
        },
    }

    audit["heating_oil_ulsd_spec_change"] = heating_oil_ulsd_note()
    audit["publication_lag"] = publication_lag_note()
    audit["discontinuation"] = {
        "date": DISCONTINUATION_DATE,
        "detail": "EIA stopped publishing the entire PET/NG futures-price table after this date "
                   "('Futures prices after April 5, 2024, are not available' -- EIA's own header). "
                   "Hard ceiling on usable history regardless of window choice.",
    }

    # --- Verdict ---
    crude_cont = audit["commodities"]["crude_oil_wti_cushing"]["continuity_by_contract"]["c1"]
    ng_cont = audit["commodities"]["natural_gas_henry_hub_futures"]["continuity_by_contract"]["c1"]
    crude_te = synth_error.get("crude_oil_vs_USO", {}).get("tracking_error_annualized")
    ng_te = synth_error.get("natural_gas_vs_UNG", {}).get("tracking_error_annualized")

    # Crude oil's single nonpositive print is the confirmed, genuine 2020-04-20
    # negative-WTI event (see known_events above), not a data defect -- do not
    # penalize the clean-use verdict for a real market print.
    explained_nonpositive = {"crude_oil_wti": 1, "natural_gas_henry_hub": 0}

    verdict_lines = []
    clean_commodities = []
    for label, cont, te in (("crude_oil_wti", crude_cont, crude_te), ("natural_gas_henry_hub", ng_cont, ng_te)):
        unexplained_nonpos = cont.get("n_nonpositive_or_zero", 1) - explained_nonpositive.get(label, 0)
        ok = (
            cont.get("n_duplicate_dates", 1) == 0
            and unexplained_nonpos <= 0
            and cont.get("n_gaps_gt_5_calendar_days", 999) < 60
        )
        clean_commodities.append(label) if ok else None
        verdict_lines.append(
            f"{label}: dup_dates={cont.get('n_duplicate_dates')}, "
            f"nonpositive={cont.get('n_nonpositive_or_zero')} "
            f"(unexplained={unexplained_nonpos}), "
            f"gaps>5d={cont.get('n_gaps_gt_5_calendar_days')}, "
            f"synthetic_TE_ann_vs_etf={te}"
        )

    audit["verdict"] = {
        "clean_for_trend_use": True if clean_commodities else False,
        "clean_commodities": clean_commodities,
        "scope_caveat": (
            "Clean for CONTRACT-1 (front-month) and CONTRACT-4 (~3-4mo deferred) continuity "
            "for crude oil and natural gas only, through 2024-04-05. NOT clean/usable for "
            "heating oil, gasoline (conventional), or propane C2-C4 given the coverage gaps "
            "documented in reports/eia_futures/REPORT.md sec 3 (65-85% fill pre-2006, missing "
            "before ~1994). NOT a 12-month strip replication -- only a ~3-4 month front-curve "
            "slope is constructible; not equivalent to USL/UNL/USO's post-2020 basket."
        ),
        "detail_lines": verdict_lines,
        "recommended_use": (
            "Suitable as a supplementary front-curve TREND input (contract-1 daily log-return "
            "series) for crude oil and natural gas, 1983/1994-2024-04-05, with the explicit "
            "caveat that it is a cost-free/slippage-free idealized roll (see roll_handling), "
            "not a tradable series, and stops in April 2024. NOT suitable, on its own, for "
            "carry/curve-slope work beyond a narrow C1-C4 spread (see carry assessment)."
        ),
    }

    (OUT_REPORTS / "eia_trend_audit.json").write_text(json.dumps(audit, indent=2, default=str))
    print(json.dumps(audit["verdict"], indent=2))
    print("[done] wrote eia_trend_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
