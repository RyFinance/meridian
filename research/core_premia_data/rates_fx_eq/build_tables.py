"""Parse frozen raw bytes into tidy, source-labelled tables (no returns here).

Outputs (data/core_premia/rates_fx_eq/processed/):
  yields_daily.parquet      country, tenor_y, kind, source, series_id, date, value_pct, obs_tz, publication
  fx_spot_daily.parquet     ccy, source, series_id, date, usd_per_ccy, quote_as_published, obs_tz
  fx_fwd_points_daily.parquet  pair, date, sw_fwd_points (LSE 1-week forward swap points; legacy pull)
  oecd_monthly.parquet      ref_area, measure, month, value_pct, obs_status, methodology  (monthly AVERAGES)
  market_daily.parquet      ticker, kind, date (exchange-local), open, high, low, close, adjclose, volume, currency, exchange_tz
  dividends.parquet         ticker, date, amount
  aqr_tsmom_dates.parquet   month_end, has_TSMOM, has_EQ, has_FI, has_FX, has_CM  (dates and non-null flags ONLY)
  build_record.json         per-table input raw paths + sha256 + row/date bounds, duplicates removed, parse notes

Pre-existing LSE-vault pulls (data/bond_yields, data/multiasset/yields, data/lse/fx_carry/raw.pkl)
are imported read-only; their vendor retrieval time is NOT in an ingestion record, which is carried
as a point-in-time/provenance defect (``source`` prefixed ``lse_vault_legacy``).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.build_tables
"""
from __future__ import annotations

import io
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from research.core_premia_data.rates_fx_eq.common import META, PROC, RAW, ROOT, latest_raw, utc_now, write_json

REC: dict = {"built_at_utc": None, "tables": {}, "inputs": {}, "notes": []}


def _inp(source, name):
    got = latest_raw(source, name)
    if got is None:
        REC["notes"].append(f"missing raw {source}/{name}")
        return None, None
    p, rec = got
    REC["inputs"][f"{source}/{name}"] = {"path": str(p.relative_to(ROOT)), "sha256": rec["sha256"],
                                        "fetched_at_utc": rec["fetched_at_utc"], "url": rec.get("url")}
    return p, rec


# ----------------------------------------------------------------------------- yields
def _y(rows, country, tenor, kind, source, sid, dates, vals, tz, pub):
    df = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce"),
                       "value_pct": pd.to_numeric(pd.Series(vals), errors="coerce").values})
    df = df.dropna()
    df["country"], df["tenor_y"], df["kind"], df["source"], df["series_id"] = country, float(tenor), kind, source, sid
    df["obs_tz"], df["publication"] = tz, pub
    rows.append(df)


def yields() -> pd.DataFrame:
    rows = []
    # Fed H.15 CMT
    p, _ = _inp("fed_h15", "h15_cmt_daily_all")
    raw = pd.read_csv(p, skiprows=5, na_values=["ND", ""])
    raw = raw.rename(columns={raw.columns[0]: "date"})
    ten = {"RIFLGFCM01_N.B": 1 / 12, "RIFLGFCM03_N.B": 0.25, "RIFLGFCM06_N.B": 0.5, "RIFLGFCY01_N.B": 1,
           "RIFLGFCY02_N.B": 2, "RIFLGFCY03_N.B": 3, "RIFLGFCY05_N.B": 5, "RIFLGFCY07_N.B": 7,
           "RIFLGFCY10_N.B": 10, "RIFLGFCY20_N.B": 20, "RIFLGFCY30_N.B": 30}
    for c, t in ten.items():
        _y(rows, "US", t, "cmt_par_bey", "fed_h15", c, raw["date"], raw[c], "America/New_York",
           "H.15 daily, next business day ~16:15 ET; CMT from closing bid (~15:30 ET)")
    # BoE
    from research.core_premia_data.rates_fx_eq.acquire_official import BOE_CODES
    for code, (label, t, kind) in BOE_CODES.items():
        p, _ = _inp("boe_iadb", code)
        if p is None:
            continue
        d = pd.read_csv(p)
        _y(rows, "UK", t, kind, "boe_iadb", code, pd.to_datetime(d["DATE"], format="%d %b %Y"), d[code],
           "Europe/London", "BoE IADB, fitted curves published next business day ~12:00 London")
    # Bundesbank par yields
    for t in (1, 2, 5, 10, 20, 30):
        p, _ = _inp("bundesbank", f"BBSIS_ZAR_R{t:02d}XX")
        if p is None:
            continue
        txt = p.read_text(encoding="utf-8-sig").splitlines()
        body = [l.split(";") for l in txt if l[:4].isdigit() and l[4] == "-"]
        _y(rows, "DE", t, "par_annual", "bundesbank", f"BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R{t:02d}XX.R.A.A._Z._Z.A",
           [b[0] for b in body], [b[1].replace(",", ".") if b[1] != "." else None for b in body], "Europe/Berlin",
           "Bundesbank Svensson-derived par yields, end-of-day Frankfurt, published next business day")
    # MOF Japan
    parts = []
    for n in ("jgbcme_all", "jgbcme_current_month"):
        p, _ = _inp("mof_japan", n)
        if p is not None:
            parts.append(pd.read_csv(p, skiprows=1, na_values=["-"], encoding="latin-1"))
    mof = pd.concat(parts).drop_duplicates("Date", keep="last")
    for c in mof.columns[1:]:
        t = float(c.rstrip("Y"))
        _y(rows, "JP", t, "par_semiannual", "mof_japan", f"JGB_{c}", pd.to_datetime(mof["Date"], format="%Y/%m/%d", errors="coerce"),
           mof[c], "Asia/Tokyo", "MOF Japan JGB interest rates (Japan Securities Dealers Assoc. closing reference), same day")
    # Bank of Canada
    from research.core_premia_data.rates_fx_eq.acquire_official import BOC_SERIES
    for sid, t in BOC_SERIES.items():
        p, _ = _inp("boc_valet", sid)
        if p is None:
            continue
        obs = json.loads(p.read_text())["observations"]
        kind = "tbill_weekly" if sid.startswith("V") else ("benchmark_long_gt10y" if "LONG" in sid else "benchmark")
        _y(rows, "CA", t, kind, "boc_valet", sid, [o["d"] for o in obs], [o.get(sid, {}).get("v") for o in obs],
           "America/Toronto", "Bank of Canada Valet, benchmark mid yields at close, published same/next day")
    # Riksbank
    from research.core_premia_data.rates_fx_eq.acquire_official import RIKS_SERIES
    for sid, t in RIKS_SERIES.items():
        p, _ = _inp("riksbank", sid)
        if p is None:
            continue
        obs = json.loads(p.read_text())
        kind = "stibor_discontinued_2020" if "STIBOR" in sid else ("tbill" if "TB" in sid else "benchmark")
        _y(rows, "SE", t, kind, "riksbank", sid, [o["date"] for o in obs], [o["value"] for o in obs],
           "Europe/Stockholm", "Riksbank SWEA, daily fixing/closing, published same day")
    # Norges Bank
    from research.core_premia_data.rates_fx_eq.acquire_official import NORGES_SERIES
    for (tenor, inst), t in NORGES_SERIES.items():
        p, _ = _inp("norges_bank", f"GOVT_GENERIC_RATES_B_{tenor}_{inst}")
        if p is None:
            continue
        d = pd.read_csv(p, sep=";")
        _y(rows, "NO", t, "generic_" + inst.lower(), "norges_bank", f"GOVT_GENERIC_RATES.B.{tenor}.{inst}",
           d["TIME_PERIOD"], d["OBS_VALUE"], "Europe/Oslo", "Norges Bank generic rates, same day")
    # ECB AAA euro-area spot curve
    for t, n in ((0.25, "YC_AAA_SR_3M"), (2, "YC_AAA_SR_2Y"), (10, "YC_AAA_SR_10Y")):
        p, _ = _inp("ecb", n)
        if p is None:
            continue
        d = pd.read_csv(p, usecols=["TIME_PERIOD", "OBS_VALUE"])
        _y(rows, "EA_AAA", t, "zero_svensson", "ecb", n, d["TIME_PERIOD"], d["OBS_VALUE"], "Europe/Frankfurt",
           "ECB AAA euro-area govt spot curve, published next business day ~12:00 CET")
    # SNB monthly (kept in yields table flagged monthly)
    p, _ = _inp("snb", "rendoblim")
    txt = p.read_text(encoding="utf-8-sig").splitlines()
    body = [l.replace('"', "").split(";") for l in txt if l.startswith('"19') or l.startswith('"20')]
    snb = pd.DataFrame(body, columns=["month", "tenor", "value"])
    for tn, g in snb.groupby("tenor"):
        _y(rows, "CH", float(tn.rstrip("J")), "monthly_confed_yield", "snb", f"rendoblim/{tn}",
           pd.to_datetime(g["month"]) + pd.offsets.MonthEnd(0), g["value"], "Europe/Zurich",
           "SNB rendoblim MONTHLY; cube stale (last obs 2025-07, publishing date 2025-09-01)")
    # Legacy LSE vault pulls (read-only imports)
    for folder, tag in ((ROOT / "data/bond_yields", "lse_vault_legacy_bonds_full"),
                        (ROOT / "data/multiasset/yields", "lse_vault_legacy_bonds_1995window")):
        for f in sorted(folder.glob("*.parquet")):
            d = pd.read_parquet(f)
            sym = f.stem
            ctry = {"UK": "UK"}.get(sym[:2], sym[:2])
            ten_s = sym[2:]
            t = float(ten_s[:-1]) / (12 if ten_s.endswith("M") else 1)
            col = "value" if "value" in d else d.columns[-1]
            dcol = "date" if "date" in d else d.columns[0]
            _y(rows, ctry, t, "benchmark_vendor", tag, f"bonds/{sym}", d[dcol], d[col], "UTC-day?",
               "LSE vault 'bonds' dataset; vendor retrieval time not in an ingestion record")
            REC["inputs"][f"{tag}/{sym}"] = {"path": str(f.relative_to(ROOT)), "sha256": _sha(f),
                                            "fetched_at_utc": None, "url": "LSE vault /series (pre-existing pull)"}
    y = pd.concat(rows, ignore_index=True)
    before = len(y)
    y = y.drop_duplicates(["source", "series_id", "date"], keep="last")
    REC["notes"].append(f"yields: dropped {before - len(y)} exact duplicate (source,series,date) rows")
    return y


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- FX
def fx() -> tuple[pd.DataFrame, pd.DataFrame]:
    from research.core_premia_data.rates_fx_eq.acquire_official import H10_CHUNKS
    parts = []
    for a, b in H10_CHUNKS:
        p, _ = _inp("fed_h10", f"h10_daily_{a}_{b}")
        lines = p.read_text().splitlines()
        cur = next(l for l in lines if l.startswith('"Currency:"')).replace('"', "").split(",")[1:]
        ids = next(l for l in lines if l.startswith('"Time Period"')).replace('"', "").split(",")[1:]
        d = pd.read_csv(p, skiprows=6, header=None, na_values=["ND", ""])
        d.columns = ["date"] + ids
        m = d.melt("date", var_name="series_id", value_name="quote").dropna()
        m["ccy"] = m["series_id"].map(dict(zip(ids, cur)))
        parts.append(m)
    h = pd.concat(parts).drop_duplicates(["series_id", "date"])
    h["usd_per_ccy"] = np.where(h["series_id"].str.startswith("RXI$US"), h["quote"], 1.0 / h["quote"])
    h["source"], h["obs_tz"] = "fed_h10", "America/New_York (noon buying rates, NY)"
    out = [h.rename(columns={"quote": "quote_as_published"})]
    p, _ = _inp("ecb", "EXR_USD_EUR_D")
    e = pd.read_csv(p, usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
    out.append(pd.DataFrame({"date": e["TIME_PERIOD"], "series_id": "EXR.D.USD.EUR.SP00.A", "ccy": "EUR",
                             "quote_as_published": e["OBS_VALUE"], "usd_per_ccy": e["OBS_VALUE"], "source": "ecb",
                             "obs_tz": "Europe/Frankfurt (14:15 CET reference rate)"}))
    pk = ROOT / "data/lse/fx_carry/raw.pkl"
    raw = pickle.load(open(pk, "rb"))
    REC["inputs"]["lse_vault_legacy_fx_carry/raw.pkl"] = {"path": str(pk.relative_to(ROOT)), "sha256": _sha(pk),
                                                         "fetched_at_utc": None, "url": "LSE vault fx + fx_derivatives (2026-09-18 pull per research/fx_carry_vol/PLAN.md)"}
    fwd = []
    for (pair, what), v in raw.items():
        if what == "spot":
            base, quote = pair[:3], pair[3:]
            ccy = base if quote == "USD" else quote
            usd_per = v["close"] if quote == "USD" else 1.0 / v["close"]
            out.append(pd.DataFrame({"date": v["ts"], "series_id": f"lse_fx/{pair}", "ccy": ccy,
                                     "quote_as_published": v["close"], "usd_per_ccy": usd_per.values,
                                     "source": "lse_vault_legacy_fx", "obs_tz": "UTC-day bar close (00:00-24:00 UTC)"}))
        elif what == "SW_FWD":
            fwd.append(pd.DataFrame({"pair": pair, "date": v["date"], "sw_fwd_points": v["value"]}))
    s = pd.concat(out, ignore_index=True)
    s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None).dt.normalize()
    s = s.drop_duplicates(["source", "series_id", "date"], keep="last")
    f = pd.concat(fwd, ignore_index=True)
    f["date"] = pd.to_datetime(f["date"])
    return s, f


# ----------------------------------------------------------------------------- OECD
def oecd() -> pd.DataFrame:
    parts = []
    for m in ("IRLT", "IR3TIB", "IRSTCI"):
        p, _ = _inp("oecd_sdmx", f"DF_FINMARK_{m}")
        d = pd.read_csv(p, usecols=["REF_AREA", "MEASURE", "METHODOLOGY", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS"],
                        low_memory=False)
        parts.append(d)
    d = pd.concat(parts)
    d = d.rename(columns={"REF_AREA": "ref_area", "MEASURE": "measure", "METHODOLOGY": "methodology",
                          "TIME_PERIOD": "month", "OBS_VALUE": "value_pct", "OBS_STATUS": "obs_status"})
    d = d[d["month"].astype(str).str.len() == 7].dropna(subset=["value_pct"])
    d["month"] = pd.to_datetime(d["month"]) + pd.offsets.MonthEnd(0)
    dup = d.duplicated(["ref_area", "measure", "methodology", "month"]).sum()
    REC["notes"].append(f"oecd: {dup} duplicate (area,measure,methodology,month) rows dropped")
    return d.drop_duplicates(["ref_area", "measure", "methodology", "month"], keep="last")


# ----------------------------------------------------------------------------- Yahoo
def market() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from research.core_premia_data.rates_fx_eq.acquire_yahoo import TICKERS, safe
    rows, divs, metas = [], [], []
    for kind, ticks in TICKERS.items():
        for t in ticks:
            p, _ = _inp("yahoo_chart", safe(t))
            if p is None:
                continue
            r = json.loads(p.read_text())["chart"]["result"][0]
            meta = r["meta"]
            tz = meta.get("exchangeTimezoneName", "UTC")
            ts = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(tz)
            q = r["indicators"]["quote"][0]
            adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
            d = pd.DataFrame({"date": ts.tz_localize(None).normalize(), "open": q.get("open"), "high": q.get("high"),
                              "low": q.get("low"), "close": q.get("close"), "volume": q.get("volume"),
                              "adjclose": adj if adj is not None else q.get("close")})
            d["ticker"], d["kind"], d["currency"], d["exchange_tz"] = t, kind, meta.get("currency"), tz
            nd = d.duplicated("date").sum()
            d = d.dropna(subset=["close"]).drop_duplicates("date", keep="last")
            rows.append(d)
            for ev in (r.get("events", {}).get("dividends") or {}).values():
                divs.append({"ticker": t, "date": pd.Timestamp(ev["date"], unit="s", tz="UTC").tz_convert(tz).tz_localize(None).normalize(),
                             "amount": ev["amount"]})
            metas.append({"ticker": t, "kind": kind, "currency": meta.get("currency"), "exchange": meta.get("exchangeName"),
                          "exchange_tz": tz, "instrument_type": meta.get("instrumentType"),
                          "name": meta.get("longName") or meta.get("shortName"),
                          "first_trade_date": meta.get("firstTradeDate"), "dup_dates_dropped": int(nd)})
    return pd.concat(rows, ignore_index=True), pd.DataFrame(divs), pd.DataFrame(metas)


# ----------------------------------------------------------------------------- AQR (dates only)
def aqr_dates() -> pd.DataFrame:
    p, _ = _inp("aqr", "TSMOM_factors_monthly")
    d = pd.read_excel(p, sheet_name="TSMOM Factors", header=None)
    hdr = next(i for i in range(len(d)) if str(d.iloc[i, 1]).strip() == "TSMOM")
    cols = [str(c) for c in d.iloc[hdr, :]]
    body = d.iloc[hdr + 1:, :]
    out = pd.DataFrame({"month_end": pd.to_datetime(body.iloc[:, 0], errors="coerce")})
    for j, c in enumerate(cols):
        if c.startswith("TSMOM"):
            key = "has_" + (c.split("^")[1] if "^" in c else "TSMOM")
            out[key] = pd.to_numeric(body.iloc[:, j], errors="coerce").notna().values  # presence flag only
    return out.dropna(subset=["month_end"]).reset_index(drop=True)


def _bounds(df, dcol="date"):
    return {"rows": int(len(df)), "first": str(pd.to_datetime(df[dcol]).min().date()) if len(df) else None,
            "last": str(pd.to_datetime(df[dcol]).max().date()) if len(df) else None}


def main():
    REC["built_at_utc"] = utc_now().isoformat()
    y = yields()
    y.to_parquet(PROC / "yields_daily.parquet", index=False)
    REC["tables"]["yields_daily"] = _bounds(y)
    s, f = fx()
    s.to_parquet(PROC / "fx_spot_daily.parquet", index=False)
    f.to_parquet(PROC / "fx_fwd_points_daily.parquet", index=False)
    REC["tables"]["fx_spot_daily"] = _bounds(s)
    REC["tables"]["fx_fwd_points_daily"] = _bounds(f)
    o = oecd()
    o.to_parquet(PROC / "oecd_monthly.parquet", index=False)
    REC["tables"]["oecd_monthly"] = _bounds(o, "month")
    m, dv, meta = market()
    m.to_parquet(PROC / "market_daily.parquet", index=False)
    dv.to_parquet(PROC / "dividends.parquet", index=False)
    meta.to_parquet(PROC / "market_meta.parquet", index=False)
    REC["tables"]["market_daily"] = _bounds(m)
    REC["tables"]["dividends"] = _bounds(dv)
    a = aqr_dates()
    a.to_parquet(PROC / "aqr_tsmom_dates.parquet", index=False)
    REC["tables"]["aqr_tsmom_dates"] = _bounds(a, "month_end")
    write_json(META / "build_record.json", REC)
    print(json.dumps(REC["tables"], indent=1))
    print(REC["notes"])


if __name__ == "__main__":
    main()
