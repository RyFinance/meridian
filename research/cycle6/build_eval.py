"""Cycle-6 evaluation layer (FREEZE+SPEC agent, 2026-09-26).

Instrument-level data transforms ONLY: reformat the data pass outputs (data/cycle6/{rates,equity}) and the frozen
external benchmark files into the long panel format the engine reads (research/cycle6/engine/io.py:
columns ``date, market_id, value``). No signal-conditioned, strategy, control or portfolio return is computed here.

Outputs (data/cycle6/eval/):
  candidate_list.csv             engine membership file (class, market_id, qa_status, ...); PASS rows only
  membership_monthly.parquet     month x (class, market_id): in-window flag and valid daily-return count
  panels/daily_excess_{EQ,FI10,FI_UST,FX,CM}.parquet   daily excess returns (decimal), PASS rows, [first,last]
  signals/*.parquet              monthly signal inputs keyed by market_id (decimal units)
  series/*.parquet               benchmark / reference series (long, market_id = series name)
  eval_build_record.json         conventions, input hashes, code hash, per-file provenance

Truncation rule (ADDENDUM-1 item 1): every instrument-keyed row is kept only for dates in
[candidates.first_date, candidates.last_date] (monthly rows: by their observation date). Country CPI and
US-rate series are macro series, not instruments, and are not truncated.

Run: python -m research.cycle6.build_eval
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
D6 = REPO / "data" / "cycle6"
OUT = D6 / "eval"
CPB = REPO / "data" / "core_premia"
BENCH = CPB / "commod_bench" / "benchmarks"
BENCH_MANIFEST = REPO / "reports" / "core_premia_20260925" / "commod_bench" / "benchmarks_manifest.json"
ACQ_SPEC = CPB / "rates_fx_eq" / "snapshot_spec_core_premia_rates_fx_eq_acq_v1.json"
LOGICAL_AS_OF = "2026-09-26"

FX_CPI_COUNTRY = {"FX_AUD": "AU", "FX_CAD": "CA", "FX_CHF": "CH", "FX_EUR": "DE", "FX_GBP": "UK",
                  "FX_JPY": "JP", "FX_NOK": "NO", "FX_NZD": "NZ", "FX_SEK": "SE"}
AQR_TSMOM_COLS = ["TSMOM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX", "TSMOM^CM"]
AQR_VME_COLS = ["MOMLS_VME_EQ", "MOMLS_VME_FX", "MOMLS_VME_FI", "MOMLS_VME_COM",
                "VALLS_VME_EQ", "VALLS_VME_FX", "VALLS_VME_FI", "VALLS_VME_COM"]
AQR_CENTURY_COLS = ["Equity indices Carry", "Fixed income Carry", "Currencies Carry", "Commodities Carry",
                    "Equity indices Defensive"]


# ------------------------------------------------------------------------------------------------ helpers
def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def iso(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%dT00:00:00+00:00")


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            for kk, vv in _walk(v):
                yield (str(k) + "/" + kk if kk else str(k)), vv
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)
    else:
        yield "", o


def max_retrieval(path: Path, exclude=("build_started_utc", "built_at_utc", "written_utc")) -> str:
    """Latest retrieval/fetch timestamp recorded under ``endpoints`` of a completeness record."""
    d = json.loads(path.read_text())
    best = None
    for k, v in _walk(d.get("endpoints", {})):
        leaf = k.split("/")[-1] if k else ""
        if any(e in k for e in exclude):
            continue
        if not isinstance(v, str) or not re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", v):
            continue
        if not re.search(r"retriev|fetch", k) and not re.search(r"retriev|fetch", leaf):
            continue
        t = pd.Timestamp(v)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        best = t if best is None or t > best else best
    return best.isoformat()


def long_frame(df: pd.DataFrame, date_col: str, id_col: str, val_col: str) -> pd.DataFrame:
    x = df[[date_col, id_col, val_col]].rename(columns={date_col: "date", id_col: "market_id", val_col: "value"})
    x = x.dropna(subset=["value"])
    x["date"] = pd.to_datetime(x["date"])
    x["market_id"] = x["market_id"].astype(str)
    x["value"] = x["value"].astype(float)
    x = x.sort_values(["market_id", "date"]).reset_index(drop=True)
    if x.duplicated(["date", "market_id"]).any():
        raise ValueError("duplicate (date, market_id)")
    return x


def truncate(df: pd.DataFrame, cands: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    w = cands.drop_duplicates("market_id").set_index("market_id")[["first_date", "last_date"]]
    m = df.merge(w, left_on="market_id", right_index=True, how="inner")
    keep = (m[date_col] >= pd.to_datetime(m["first_date"])) & (m[date_col] <= pd.to_datetime(m["last_date"]))
    return m.loc[keep, df.columns]


# ------------------------------------------------------------------------------------------------ candidates
def build_candidates() -> pd.DataFrame:
    r = pd.read_csv(D6 / "rates" / "candidates.csv")
    e = pd.read_csv(D6 / "equity" / "candidates.csv")
    r["source_file"] = "data/cycle6/rates/candidates.csv"
    e["source_file"] = "data/cycle6/equity/candidates.csv"
    u = pd.concat([r, e], ignore_index=True)
    u = u[u["qa_status"].astype(str).str.upper() == "PASS"].copy()
    u["source_class"] = u["class"]
    u["tenor"] = u["tenor"]
    rows = []
    for _, row in u.iterrows():
        mid = row["market_id"]
        if row["source_class"] == "FI":
            ten = int(row["tenor"])
            if ten == 10:
                rows.append({**row, "class": "FI", "use_note": "FI 10y per country (ADDENDUM-1 item 5)"})
            if mid.startswith("FI_US_") and ten in (2, 5, 10, 30):
                rows.append({**row, "class": "FI_UST", "use_note": "US maturity bucket for BAB-FI (ADDENDUM-1 item 5)"})
            if ten != 10 and not mid.startswith("FI_US_"):
                rows.append({**row, "class": "FI_OTHER",
                             "use_note": "PASS, not in any cycle-6 component universe (ADDENDUM-1 item 5)"})
        else:
            rows.append({**row, "use_note": ""})
    c = pd.DataFrame(rows)
    c["alias_of"] = ""
    cols = ["class", "market_id", "qa_status", "source_class", "tenor", "economic_market", "construction", "source",
            "first_date", "last_date", "n_months", "alias_of", "use_note", "source_file"]
    c = c[cols].sort_values(["class", "market_id"]).reset_index(drop=True)
    return c


# ------------------------------------------------------------------------------------------------ panels
def daily_panels(c: pd.DataFrame) -> dict:
    eq = pd.read_parquet(D6 / "equity" / "equity_excess_daily.parquet")
    fi = pd.read_parquet(D6 / "rates" / "bond_excess_daily.parquet")
    fx = pd.read_parquet(D6 / "rates" / "fx_excess_daily.parquet")
    cm = pd.read_parquet(D6 / "rates" / "commodity_excess_daily.parquet")
    out = {}
    for name, src, cls in (("EQ", eq, "EQ"), ("FI10", fi, "FI"), ("FI_UST", fi, "FI_UST"), ("FX", fx, "FX"),
                           ("CM", cm, "CM")):
        ids = c.loc[c["class"] == cls, "market_id"].unique()
        x = src[src["market_id"].isin(ids)]
        x = long_frame(x, "date", "market_id", "excess_ret")
        x = truncate(x, c[c["class"] == cls])
        missing = sorted(set(ids) - set(x["market_id"]))
        if missing:
            raise ValueError(f"{name}: no data for {missing}")
        out[name] = x
    return out


def pit_cpi_monthly(cpi: pd.DataFrame, country: str, months: pd.DatetimeIndex) -> pd.Series:
    """At each month-end t: CPI level of the latest reference month whose available_date <= t."""
    s = cpi[cpi["country"] == country].sort_values(["available_date", "month"])
    s = s.drop_duplicates("available_date", keep="last")
    avail = s.set_index("available_date")["value"]
    ref = s.set_index("available_date")["month"]
    # latest reference month among releases available by t (releases are monotone in reference month)
    idx = avail.index.searchsorted(months, side="right") - 1
    vals = np.where(idx >= 0, avail.to_numpy()[np.clip(idx, 0, None)], np.nan)
    if not ref.is_monotonic_increasing:
        raise ValueError(f"CPI {country}: reference months not monotone in available_date")
    return pd.Series(vals, index=months, name=country)


def signal_panels(c: pd.DataFrame) -> dict:
    out = {}
    fxc = pd.read_parquet(D6 / "rates" / "fx_carry_inputs_monthly.parquet")
    fxc = fxc[fxc["market_id"].isin(c.loc[c["class"] == "FX", "market_id"])].copy()
    fxt = truncate(fxc, c[c["class"] == "FX"], date_col="obs_date")
    # FX carry input: foreign 3m rate (decimal) as known at the month-end observation
    fr = fxt[["obs_date", "market_id", "rf_ccy_pct"]].copy()
    fr["v"] = fr["rf_ccy_pct"] / 100.0
    out["signals/fx_foreign_rate_monthly.parquet"] = long_frame(fr, "obs_date", "market_id", "v")
    # FX spot (USD per unit of foreign currency) at month-end
    out["signals/fx_spot_monthly.parquet"] = long_frame(fxt, "obs_date", "market_id", "spot_usd_per_ccy")
    # US 3m rate (decimal): one value per month (row with the latest observation date in the month)
    us = fxc.sort_values("obs_date").groupby(fxc["month"].dt.to_period("M")).tail(1)
    us = us.assign(market_id="USD_RF_3M", v=us["rf_usd_pct"] / 100.0)
    out["series/usd_rate_3m_monthly.parquet"] = long_frame(us, "obs_date", "market_id", "v")

    # CPI point-in-time monthly (available_date <= month-end); FX-keyed foreign CPI and US CPI
    cpi = pd.read_parquet(D6 / "equity" / "cpi_monthly_pit.parquet")
    months = pd.date_range("1955-01-31", "2026-09-30", freq="ME")
    frames = []
    spot_w = out["signals/fx_spot_monthly.parquet"].groupby("market_id")["date"].agg(["min", "max"])
    for mid, ctry in FX_CPI_COUNTRY.items():
        s = pit_cpi_monthly(cpi, ctry, months)
        lo, hi = spot_w.loc[mid, "min"], spot_w.loc[mid, "max"]
        s = s[(s.index >= lo - pd.offsets.MonthEnd(0)) & (s.index <= hi + pd.offsets.MonthEnd(0))]
        frames.append(pd.DataFrame({"date": s.index, "market_id": mid, "value": s.to_numpy()}))
    out["signals/fx_cpi_pit_monthly.parquet"] = long_frame(pd.concat(frames), "date", "market_id", "value")
    su = pit_cpi_monthly(cpi, "US", months)
    out["series/cpi_us_pit_monthly.parquet"] = long_frame(
        pd.DataFrame({"date": su.index, "market_id": "US_CPI", "value": su.to_numpy()}), "date", "market_id", "value")

    # FI 10y: month-end yield (decimal) from the construction's own yield column; KMVP carry incl. roll-down
    fi = pd.read_parquet(D6 / "rates" / "bond_excess_daily.parquet")
    ids10 = c.loc[c["class"] == "FI", "market_id"].unique()
    y = fi[fi["market_id"].isin(ids10)].dropna(subset=["y"])
    y = truncate(y[["date", "market_id", "y"]], c[c["class"] == "FI"])
    y = y.sort_values("date").groupby([y["market_id"], y["date"].dt.to_period("M")]).tail(1)
    out["signals/fi10_yield_monthly.parquet"] = long_frame(y, "date", "market_id", "y")
    bc = pd.read_parquet(D6 / "rates" / "bond_carry_inputs_monthly.parquet")
    bc = bc[bc["market_id"].isin(ids10)].copy()
    bc = truncate(bc, c[c["class"] == "FI"], date_col="obs_date")
    bc["v"] = bc["carry_pct_pa"] / 100.0
    out["signals/fi10_carry_monthly.parquet"] = long_frame(bc, "obs_date", "market_id", "v")
    return out


# ------------------------------------------------------------------------------------------------ external series
def _aqr_sheet(fname: str, sheet: str, header_row: int, cols: list[str]) -> pd.DataFrame:
    df = pd.read_excel(BENCH / fname, sheet_name=sheet, header=header_row - 1)
    dcol = df.columns[0]
    df = df.rename(columns={dcol: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    df = df.dropna(subset=["date"])
    missing = [k for k in cols if k not in df.columns]
    if missing:
        raise ValueError(f"{fname}: columns absent {missing}")
    frames = []
    for k in cols:
        v = pd.to_numeric(df[k], errors="coerce")
        frames.append(pd.DataFrame({"date": df["date"], "market_id": k, "value": v}))
    return long_frame(pd.concat(frames), "date", "market_id", "value")


def kf_mkt_rf() -> pd.DataFrame:
    with zipfile.ZipFile(BENCH / "ff_research_data_factors.zip") as z:
        txt = z.read(z.namelist()[0]).decode("latin-1")
    rows = []
    started = False
    for line in txt.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5 and re.fullmatch(r"\d{6}", parts[0]):
            started = True
            rows.append((parts[0], float(parts[1])))
        elif started and rows and not re.fullmatch(r"\d{6}", parts[0] or "x"):
            break  # end of the monthly block (annual block follows)
    df = pd.DataFrame(rows, columns=["ym", "v"])
    df["date"] = pd.to_datetime(df["ym"], format="%Y%m") + pd.offsets.MonthEnd(0)
    df["market_id"] = "KF_US_MKT_RF"
    df["v"] = df["v"] / 100.0
    return long_frame(df, "date", "market_id", "v")


def core_etfs() -> dict:
    m = pd.read_parquet(CPB / "rates_fx_eq" / "processed" / "market_daily.parquet", columns=["date", "ticker",
                                                                                              "adjclose"])
    rf = pd.read_parquet(D6 / "rates" / "short_rates_daily.parquet")
    rf = rf[rf["ccy"] == "USD"].set_index("date")["rf_pct"].sort_index()
    tr, ex = [], []
    for tk in ("SPY", "IEF"):
        s = m[m["ticker"] == tk].set_index("date")["adjclose"].sort_index()
        r = s.pct_change().dropna()
        dt = pd.Series(r.index, index=r.index).diff().dt.days.fillna(1) / 365.0
        rfa = rf.reindex(r.index)
        if rfa.isna().any():
            raise ValueError(f"{tk}: USD short rate missing on {int(rfa.isna().sum())} days")
        e = r - rfa / 100.0 * dt
        tr.append(pd.DataFrame({"date": r.index, "market_id": tk, "value": r.to_numpy()}))
        ex.append(pd.DataFrame({"date": e.index, "market_id": tk, "value": e.to_numpy()}))
    y = pd.read_parquet(CPB / "rates_fx_eq" / "processed" / "yields_daily.parquet")
    tb = y[y["series_id"] == "RIFLGFCM03_N.B"][["date", "value_pct"]].copy()
    tb["market_id"] = "TB3M"
    tb["v"] = tb["value_pct"] / 100.0
    return {"series/core_etf_total_return_daily.parquet": long_frame(pd.concat(tr), "date", "market_id", "value"),
            "series/core_etf_excess_daily.parquet": long_frame(pd.concat(ex), "date", "market_id", "value"),
            "series/tbill_3m_daily.parquet": long_frame(tb, "date", "market_id", "v")}


def bab_benchmarks(panels: dict) -> pd.DataFrame:
    """ADDENDUM-1 item 10: equal-weighted daily average of the eligible (PASS, in-window) instruments."""
    frames = []
    for name, key in (("BAB_BENCH_EQ_EW", "EQ"), ("BAB_BENCH_FI_UST_EW", "FI_UST")):
        w = panels[key].pivot(index="date", columns="market_id", values="value")
        s = w.mean(axis=1, skipna=True).dropna()
        frames.append(pd.DataFrame({"date": s.index, "market_id": name, "value": s.to_numpy()}))
    return long_frame(pd.concat(frames), "date", "market_id", "value")


def membership_monthly(c: pd.DataFrame, panels: dict) -> pd.DataFrame:
    key = {"EQ": "EQ", "FI": "FI10", "FI_UST": "FI_UST", "FX": "FX", "CM": "CM"}
    rows = []
    for cls, pk in key.items():
        p = panels[pk]
        cnt = p.groupby(["market_id", p["date"].dt.to_period("M")]).size()
        for _, r in c[c["class"] == cls].iterrows():
            f, l = pd.Period(r["first_date"], "M"), pd.Period(r["last_date"], "M")
            for m in pd.period_range(f, l, freq="M"):
                rows.append({"month": m.to_timestamp(how="end").normalize(), "class": cls,
                             "market_id": r["market_id"], "in_window": True,
                             "n_valid_days": int(cnt.get((r["market_id"], m), 0))})
    return pd.DataFrame(rows).sort_values(["class", "market_id", "month"]).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ main
def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panels").mkdir(exist_ok=True)
    (OUT / "signals").mkdir(exist_ok=True)
    (OUT / "series").mkdir(exist_ok=True)
    c = build_candidates()
    panels = daily_panels(c)
    files = {f"panels/daily_excess_{k}.parquet": v for k, v in panels.items()}
    files.update(signal_panels(c))
    files["series/aqr_tsmom_monthly.parquet"] = _aqr_sheet("aqr_tsmom_factors_monthly.xlsx", "TSMOM Factors", 18,
                                                           AQR_TSMOM_COLS)
    files["series/aqr_vme_monthly.parquet"] = _aqr_sheet("aqr_value_momentum_everywhere_monthly.xlsx",
                                                         "VME Factors", 22, AQR_VME_COLS)
    files["series/aqr_century_monthly.parquet"] = _aqr_sheet("aqr_century_factor_premia_monthly.xlsx",
                                                             "Century of Factor Premia", 19, AQR_CENTURY_COLS)
    files["series/kf_us_mkt_rf_monthly.parquet"] = kf_mkt_rf()
    files.update(core_etfs())
    files["series/bab_benchmarks_daily.parquet"] = bab_benchmarks(panels)
    memb = membership_monthly(c, panels)

    for rel, df in files.items():
        df.to_parquet(OUT / rel, index=False)
    c.to_csv(OUT / "candidate_list.csv", index=False)
    memb.to_parquet(OUT / "membership_monthly.parquet", index=False)

    # ---- provenance ----
    rates_rt = max_retrieval(D6 / "rates" / "completeness.json")
    eq_rt = max_retrieval(D6 / "equity" / "completeness.json")
    bm = {e["filename"]: e for e in json.loads(BENCH_MANIFEST.read_text())["entries"]}
    for fn, e in bm.items():
        if sha_file(BENCH / fn) != e["sha256"]:
            raise ValueError(f"benchmark bytes differ from ingestion record: {fn}")
    acq = json.loads(ACQ_SPEC.read_text())["metadata"]

    def acq_rt(sym):
        ks = [k for k, v in acq.items() if v.get("symbol") == sym and k.startswith("raw/")]
        return max(acq[k]["retrieved_at"] for k in ks), [acq[k]["source_identifier"] for k in ks]

    spy_rt, spy_id = acq_rt("SPY")
    ief_rt, ief_id = acq_rt("IEF")
    h15_rt, h15_id = acq_rt("h15_cmt_daily_all")
    later = lambda *ts: max(pd.Timestamp(t).tz_convert("UTC") if pd.Timestamp(t).tzinfo else  # noqa: E731
                            pd.Timestamp(t).tz_localize("UTC") for t in ts).isoformat()
    prov = {
        "panels/daily_excess_EQ.parquet": ("cycle6 equity data pass (equity_excess_daily)",
                                           "data/cycle6/equity/equity_excess_daily.parquet; completeness.json endpoints",
                                           eq_rt),
        "panels/daily_excess_FI10.parquet": ("cycle6 rates data pass (bond_excess_daily), 10y rows",
                                             "data/cycle6/rates/bond_excess_daily.parquet; completeness.json endpoints",
                                             rates_rt),
        "panels/daily_excess_FI_UST.parquet": ("cycle6 rates data pass (bond_excess_daily), US 2/5/10/30y",
                                               "data/cycle6/rates/bond_excess_daily.parquet; fed_h15 CMT", rates_rt),
        "panels/daily_excess_FX.parquet": ("cycle6 rates data pass (fx_excess_daily)",
                                           "data/cycle6/rates/fx_excess_daily.parquet; fed_h10 + short rates", rates_rt),
        "panels/daily_excess_CM.parquet": ("cycle6 rates data pass (commodity_excess_daily)",
                                           "data/cycle6/rates/commodity_excess_daily.parquet; EIA + yfinance ETFs",
                                           rates_rt),
        "signals/fx_foreign_rate_monthly.parquet": ("cycle6 rates data pass (fx_carry_inputs_monthly.rf_ccy_pct)",
                                                    "data/cycle6/rates/fx_carry_inputs_monthly.parquet", rates_rt),
        "signals/fx_spot_monthly.parquet": ("cycle6 rates data pass (fx_carry_inputs_monthly.spot_usd_per_ccy)",
                                            "data/cycle6/rates/fx_carry_inputs_monthly.parquet; fed_h10", rates_rt),
        "series/usd_rate_3m_monthly.parquet": ("cycle6 rates data pass (fx_carry_inputs_monthly.rf_usd_pct)",
                                               "data/cycle6/rates/fx_carry_inputs_monthly.parquet", rates_rt),
        "signals/fx_cpi_pit_monthly.parquet": ("cycle6 equity data pass (cpi_monthly_pit), PIT by available_date",
                                               "data/cycle6/equity/cpi_monthly_pit.parquet (OECD SDMX/LSE)", eq_rt),
        "series/cpi_us_pit_monthly.parquet": ("cycle6 equity data pass (cpi_monthly_pit) US, PIT by available_date",
                                              "data/cycle6/equity/cpi_monthly_pit.parquet (OECD SDMX)", eq_rt),
        "signals/fi10_yield_monthly.parquet": ("cycle6 rates data pass (bond_excess_daily.y) month-end",
                                               "data/cycle6/rates/bond_excess_daily.parquet", rates_rt),
        "signals/fi10_carry_monthly.parquet": ("cycle6 rates data pass (bond_carry_inputs_monthly.carry_pct_pa)",
                                               "data/cycle6/rates/bond_carry_inputs_monthly.parquet", rates_rt),
        "series/aqr_tsmom_monthly.parquet": ("AQR", bm["aqr_tsmom_factors_monthly.xlsx"]["url"],
                                             bm["aqr_tsmom_factors_monthly.xlsx"]["fetch_time_utc"]),
        "series/aqr_vme_monthly.parquet": ("AQR", bm["aqr_value_momentum_everywhere_monthly.xlsx"]["url"],
                                           bm["aqr_value_momentum_everywhere_monthly.xlsx"]["fetch_time_utc"]),
        "series/aqr_century_monthly.parquet": ("AQR", bm["aqr_century_factor_premia_monthly.xlsx"]["url"],
                                               bm["aqr_century_factor_premia_monthly.xlsx"]["fetch_time_utc"]),
        "series/kf_us_mkt_rf_monthly.parquet": ("Kenneth French data library", bm["ff_research_data_factors.zip"]["url"],
                                                bm["ff_research_data_factors.zip"]["fetch_time_utc"]),
        "series/core_etf_total_return_daily.parquet": ("yahoo_chart adjclose (core_premia acq v1 snapshot)",
                                                       "; ".join(spy_id + ief_id), later(spy_rt, ief_rt)),
        "series/core_etf_excess_daily.parquet": ("yahoo_chart adjclose minus USD 3m (cycle6 short_rates_daily)",
                                                 "; ".join(spy_id + ief_id), later(spy_rt, ief_rt, rates_rt)),
        "series/tbill_3m_daily.parquet": ("fed_h15 3-month CMT RIFLGFCM03_N.B (core_premia acq v1 processed)",
                                          "; ".join(h15_id), h15_rt),
        "series/bab_benchmarks_daily.parquet": ("equal-weight average of PASS in-window instruments (ADDENDUM-1 i.10)",
                                                "derived from panels/daily_excess_EQ and daily_excess_FI_UST",
                                                later(eq_rt, rates_rt)),
    }
    meta = {}
    for rel, df in files.items():
        src, ident, rt = prov[rel]
        meta[rel] = {"source": src, "source_identifier": ident, "retrieved_at": rt, "logical_as_of": LOGICAL_AS_OF,
                     "symbol": ",".join(sorted(df["market_id"].unique())), "first_timestamp": iso(df["date"].min()),
                     "last_timestamp": iso(df["date"].max()), "row_count": int(len(df)), "temporal": True}
    meta["candidate_list.csv"] = {"source": "union of cycle6 rates+equity candidates.csv, PASS only (ADDENDUM-1 i.4)",
                                  "source_identifier": "data/cycle6/rates/candidates.csv; data/cycle6/equity/candidates.csv",
                                  "retrieved_at": later(rates_rt, eq_rt), "logical_as_of": LOGICAL_AS_OF,
                                  "symbol": "cycle6_candidate_list", "first_timestamp": None, "last_timestamp": None,
                                  "row_count": int(len(c)), "temporal": False}
    meta["membership_monthly.parquet"] = {"source": "derived: candidate windows x daily panels",
                                          "source_identifier": "candidate_list.csv; panels/*", "retrieved_at":
                                          later(rates_rt, eq_rt), "logical_as_of": LOGICAL_AS_OF,
                                          "symbol": "cycle6_membership_monthly",
                                          "first_timestamp": iso(memb["month"].min()),
                                          "last_timestamp": iso(memb["month"].max()), "row_count": int(len(memb)),
                                          "temporal": True}
    inputs = [D6 / "rates" / "candidates.csv", D6 / "equity" / "candidates.csv",
              D6 / "rates" / "completeness.json", D6 / "equity" / "completeness.json",
              D6 / "equity" / "equity_excess_daily.parquet", D6 / "equity" / "cpi_monthly_pit.parquet",
              D6 / "rates" / "bond_excess_daily.parquet", D6 / "rates" / "fx_excess_daily.parquet",
              D6 / "rates" / "commodity_excess_daily.parquet", D6 / "rates" / "fx_carry_inputs_monthly.parquet",
              D6 / "rates" / "bond_carry_inputs_monthly.parquet", D6 / "rates" / "short_rates_daily.parquet",
              CPB / "rates_fx_eq" / "processed" / "market_daily.parquet",
              CPB / "rates_fx_eq" / "processed" / "yields_daily.parquet", BENCH_MANIFEST, ACQ_SPEC,
              *[BENCH / f for f in ("aqr_tsmom_factors_monthly.xlsx", "aqr_value_momentum_everywhere_monthly.xlsx",
                                    "aqr_century_factor_premia_monthly.xlsx", "ff_research_data_factors.zip")]]
    record = {
        "written_by": "cycle-6 FREEZE+SPEC agent", "logical_as_of": LOGICAL_AS_OF,
        "no_returns_computed": "instrument-level transforms only; no signal-conditioned/strategy/control/portfolio return",
        "code": {"research/cycle6/build_eval.py": sha_file(Path(__file__))},
        "inputs_sha256": {str(p.relative_to(REPO)): sha_file(p) for p in inputs},
        "conventions": {
            "long_format": "date, market_id, value (engine io.py)",
            "units": "returns, yields, rates, carry: decimals; CPI: index level; spot: USD per unit foreign currency",
            "truncation": "instrument rows kept only within candidates first_date..last_date (monthly rows by obs date)",
            "engine_classes": "EQ, FI (10y per country), FI_UST (US 2/5/10/30y; FI_US_10Y listed in FI and FI_UST), FX, CM; "
                              "FI_OTHER = PASS non-10y non-US buckets not used by any component",
            "fx_cpi": "month-end t value = CPI of the latest release with available_date <= t (data pass lag rule "
                      "default_2m; latest vintage, not first release); FX_EUR uses DE CPI (no euro-area CPI in pass)",
            "usd_rate": "rf_usd_pct of the FX-carry input row with the latest observation date in the month",
            "fi10_yield": "last valid daily construction yield (bond_excess_daily.y) in the month",
            "fi10_carry": "carry_pct_pa/100 = (y - rf + roll-down) as defined by the rates data pass",
            "core_etf_excess": "adjclose simple return - USD 3m (cycle6 short_rates_daily, lagged 1 obs) x calendar days/365",
            "tbill": "H.15 3m CMT, unlagged, decimal (book lags it one month itself)",
            "kf": "F-F_Research_Data_Factors monthly block, Mkt-RF /100, dated month-end",
            "aqr": "sheet header rows TSMOM 18, VME 22, Century 19; values reformatted only (not inspected/compared)",
            "bab_bench": "equal-weight mean over instruments with a return that day (EQ panel; FI_UST panel)",
        },
        "provenance": meta,
    }
    (OUT / "eval_build_record.json").write_text(json.dumps(record, indent=1, sort_keys=True))
    return record


if __name__ == "__main__":
    rec = main()
    for k, v in sorted(rec["provenance"].items()):
        print(f"{k:48s} rows={v['row_count']:>8} {v['first_timestamp']} .. {v['last_timestamp']}")
