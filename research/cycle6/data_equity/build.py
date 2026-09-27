"""Cycle-6 equity data pass: levels, per-market excess returns, instrument QA, CPI (PIT), valuation.

DATA WORK ONLY. Hard rule honoured: no signal is computed, nothing is sorted on a signal, no
strategy/control/portfolio return exists here. Returns computed are instrument-level only
(one construction per economic market, and its QA error against the market's real traded proxy).

Construction per market is chosen mechanically by FRAMEWORK §3 priority, fixed in MARKETS below
BEFORE any return was computed (availability only, never returns):
  T1 local total-return index - local cash
  T2 local price index + declared dividend estimate - local cash
     dividend estimate dy = trailing-365-day distributions of the mapped USD country ETF / ETF close,
     only after 12 months of ETF history, known at t-1 (the declared estimate of the prior pass)
  T3 USD country ETF total return (adjusted close) - USD cash (declared unhedged deviation)
A tier is used iff all its inputs exist for the market (level, local cash, dy source). Price index
choice where several exist: the longest history (earliest first date); alternates listed in notes.
Local cash = prior pass short_rate() method (official daily lagged 1 obs, else OECD prev-month avg),
extended here with national OECD rates for euro-legacy members before 1999-01-01 (EUR after).
Cash drag: excess_t = ret_t [+ dy_{t-1} dt] - rf_{t-1} dt, dt = calendar days / 365.

Instrument QA (FRAMEWORK §3), status PASS/FAIL:
 (a) construction error vs real traded proxy (the market's USD country ETF): monthly
     TE/sigma_proxy with the synthetic converted to USD by Fed H.10 month-end spot:
       syn_usd = (1+R_local_total)(1+R_fx) - 1 ;  proxy = R_etf_adj ; both minus the same USD cash.
     FAIL if > 0.60 on >= 36 overlapping months. Not applicable to T3 (the construction IS the ETF)
     or where no ETF/H.10 FX exists (recorded).
 (b) gap > 10 business days between consecutive valid excess-return dates inside the span: FAIL.
 (c) run of >= 10 consecutive identical level closes: FAIL.
 (d) point-in-time: all inputs are lagged (dy, cash at t-1); index/ETF closes are final. PASS.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle6.data_equity.build
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import research.core_premia_data.rates_fx_eq.synthetic as syn
from research.cycle6.data_equity.common import META, OUT, PRIOR, RAW, latest, utc_now, write_json

PRIOR_MANIFEST = "8b5e6205cf5fe8084914913e7d278103c302887d0bf3a44aa6c063452ff67e28"

# ---------------------------------------------------------------- declared market table (before returns)
# market_id: (economic market, ccy, TR index or None, [price index candidates], ETF (dy source / T3 / proxy))
MARKETS = {
    "EQ_US": ("United States", "USD", "^SP500TR", ["^GSPC"], "SPY"),
    "EQ_CA": ("Canada", "CAD", None, ["^GSPTSE"], "EWC"),
    "EQ_UK": ("United Kingdom", "GBP", None, ["^FTSE", "^FTAS", "^FTLC"], "EWU"),
    "EQ_DE": ("Germany", "EUR", "^GDAXI", [], "EWG"),
    "EQ_FR": ("France", "EUR", None, ["^FCHI"], "EWQ"),
    "EQ_IT": ("Italy", "EUR", None, ["FTSEMIB.MI"], "EWI"),
    "EQ_ES": ("Spain", "EUR", None, ["^IBEX"], "EWP"),
    "EQ_NL": ("Netherlands", "EUR", None, ["^AEX"], "EWN"),
    "EQ_BE": ("Belgium", "EUR", None, ["^BFX"], "EWK"),
    "EQ_AT": ("Austria", "EUR", None, ["^ATX"], "EWO"),
    "EQ_FI": ("Finland", "EUR", None, ["^OMXH25"], "EFNL"),
    "EQ_IE": ("Ireland", "EUR", None, ["^ISEQ"], "EIRL"),
    "EQ_PT": ("Portugal", "EUR", None, ["PSI20.LS"], None),
    "EQ_CH": ("Switzerland", "CHF", "^SSHI", ["^SSMI"], "EWL"),
    "EQ_SE": ("Sweden", "SEK", None, ["^OMX", "^OMXSPI"], "EWD"),
    "EQ_NO": ("Norway", "NOK", "OSEBX.OL", [], "ENOR"),
    "EQ_DK": ("Denmark", "DKK", None, ["^OMXC25"], "EDEN"),
    "EQ_JP": ("Japan", "JPY", None, ["^N225"], "EWJ"),
    "EQ_AU": ("Australia", "AUD", None, ["^AORD", "^AXJO"], "EWA"),
    "EQ_NZ": ("New Zealand", "NZD", "^NZ50", [], "ENZL"),  # S&P/NZX 50 headline = gross index (with imputation)
    "EQ_HK": ("Hong Kong", "HKD", None, ["^HSI"], "EWH"),
    "EQ_SG": ("Singapore", "SGD", None, ["^STI"], "EWS"),
    "EQ_IL": ("Israel", "ILS", None, ["^TA125.TA"], "EIS"),
    "EQ_KR": ("South Korea", "KRW", None, ["^KS11", "^KS200"], "EWY"),
    "EQ_TW": ("Taiwan", "TWD", None, ["^TWII"], "EWT"),
    "EQ_IN": ("India", "INR", None, ["^BSESN", "^NSEI"], "INDA"),
    "EQ_CN": ("China", "CNY", None, ["000001.SS", "000300.SS"], "FXI"),
    "EQ_BR": ("Brazil", "BRL", "^BVSP", [], "EWZ"),  # Ibovespa = gross total-return methodology
    "EQ_MX": ("Mexico", "MXN", None, ["^MXX"], "EWW"),
    "EQ_ZA": ("South Africa", "ZAR", None, ["^J203.JO", "^J200.JO"], "EZA"),
    "EQ_MY": ("Malaysia", "MYR", None, ["^KLSE"], "EWM"),
    "EQ_TH": ("Thailand", "THB", None, ["^SET.BK"], "THD"),
    "EQ_ID": ("Indonesia", "IDR", None, ["^JKSE"], "EIDO"),
    "EQ_TR": ("Turkey", "TRY", None, ["XU100.IS"], "TUR"),
    "EQ_PL": ("Poland", "PLN", None, [], "EPOL"),
    "EQ_CL": ("Chile", "CLP", None, [], "ECH"),
}
EURO_LEGACY = {"EQ_DE": "DEM", "EQ_FR": "FRF", "EQ_IT": "ITL", "EQ_ES": "ESP", "EQ_NL": "NLG", "EQ_BE": "BEF",
               "EQ_AT": "ATS", "EQ_FI": "FIM", "EQ_IE": "IEP", "EQ_PT": "PTE"}
LEGACY_AREA = {"FRF": "FRA", "ITL": "ITA", "ESP": "ESP", "NLG": "NLD", "BEF": "BEL", "ATS": "AUT", "FIM": "FIN",
               "IEP": "IRL", "PTE": "PRT"}
EURO_START = pd.Timestamp("1999-01-01")
# LSE CFD symbol -> Yahoo index it quotes (informational source-agreement check only)
LSE_MAP = {"SPX500/USD": "^GSPC", "DE30/EUR": "^GDAXI", "UK100/GBP": "^FTSE", "FR40/EUR": "^FCHI",
           "IT40/EUR": "FTSEMIB.MI", "ES35/EUR": "^IBEX", "NL30/EUR": "^AEX", "CH20/CHF": "^SSMI",
           "HK33/HKD": "^HSI", "JP225/USD": "^N225", "AU200/AUD": "^AXJO", "UK250/GBP": "^FTMC",
           "NAS100/USD": "^NDX", "US30/USD": "^DJI", "US2000/USD": "^RUT", "EU50/EUR": "^STOXX50E",
           "CN50/USD": None}
TE_MAX, MIN_OVERLAP, GAP_MAX, STALE_MIN = 0.60, 36, 10, 10


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------- inputs
def yahoo_new():
    from research.cycle6.data_equity.acquire_web import YAHOO_ETF, YAHOO_NEW
    rows, divs, rec = [], [], {}
    for t, kind in {**YAHOO_NEW, **YAHOO_ETF}.items():
        hit = latest("yahoo_chart", t.replace("^", "IDX_").replace(".", "_"))
        if hit is None:
            rec[t] = {"ok": False}
            continue
        p, m = hit
        r = json.loads(p.read_text())["chart"]["result"][0]
        tz = r["meta"].get("exchangeTimezoneName", "UTC")
        ts = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(tz)
        q = r["indicators"]["quote"][0]
        adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        d = pd.DataFrame({"date": ts.tz_localize(None).normalize(), "close": q.get("close"),
                          "adjclose": adj if adj is not None else q.get("close")})
        nd = int(d.duplicated("date").sum())
        d = d.dropna(subset=["close"]).drop_duplicates("date", keep="last")
        d["ticker"], d["kind"], d["currency"] = t, kind, r["meta"].get("currency")
        rows.append(d)
        for ev in (r.get("events", {}).get("dividends") or {}).values():
            divs.append({"ticker": t, "date": pd.Timestamp(ev["date"], unit="s", tz="UTC").tz_convert(tz)
                         .tz_localize(None).normalize(), "amount": ev["amount"]})
        rec[t] = {"ok": True, "url": m.get("url"), "fetched_at_utc": m["fetched_at_utc"], "sha256": m["sha256"],
                  "path": m["path"], "rows": len(d), "dup_dates_dropped": nd, "kind": kind,
                  "first": str(d.date.min().date()), "last": str(d.date.max().date())}
    return pd.concat(rows, ignore_index=True), pd.DataFrame(divs), rec


def lse_levels():
    res = json.loads((META / "acquire_lse_results.json").read_text())
    rows, rec = [], {}
    for name, r in res["candles"].items():
        if not r["ok"]:
            continue
        c = json.loads((RAW / r["path"]).read_bytes())
        sym = c["symbol"]
        d = pd.DataFrame(c["candles"], columns=["t", "open", "high", "low", "close", "volume"])
        d["date"] = pd.to_datetime(d.t, unit="s", utc=True).dt.tz_localize(None).dt.normalize()
        d["ticker"] = sym
        rows.append(d[["date", "close", "ticker"]])
        rec.setdefault(sym, []).append({"url": r["url"], "fetched_at_utc": r["fetched_at_utc"], "path": r["path"],
                                        "rows": len(d)})
    df = pd.concat(rows, ignore_index=True).drop_duplicates(["ticker", "date"], keep="last")
    return df, rec


def short_rates(index):
    y, fx, o, m, dv = syn.load()
    for ccy, area in LEGACY_AREA.items():
        syn.CCY[ccy] = (area, [])
    rf = {}
    for c in set(v[1] for v in MARKETS.values()) | set(EURO_LEGACY.values()) | {"USD"}:
        rf[c] = syn.short_rate(c, y, o, index) if c in syn.CCY else pd.DataFrame(
            {"rf_pct": np.nan, "rf_source": None}, index=index)
    return rf, fx


# ---------------------------------------------------------------- helpers
def month_end_last(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s.groupby(s.index.to_period("M")).last()


def gaps_and_stale(level: pd.Series, valid_dates: pd.DatetimeIndex):
    out = {"gaps": [], "stale_runs": []}
    vd = np.array(valid_dates.values, dtype="datetime64[D]")
    if len(vd) > 1:
        bd = np.busday_count(vd[:-1], vd[1:]) - 1
        for i in np.where(bd > GAP_MAX)[0]:
            out["gaps"].append({"from": str(vd[i]), "to": str(vd[i + 1]), "missing_bdays": int(bd[i])})
    lv = level.dropna()
    same = lv.eq(lv.shift(1))
    run_id = (~same).cumsum()
    runs = lv.groupby(run_id).agg(["size"]).join(lv.index.to_series().groupby(run_id.values).agg(["first", "last"]))
    for _, r in runs[runs["size"] >= STALE_MIN].iterrows():
        out["stale_runs"].append({"from": str(r["first"].date()), "to": str(r["last"].date()), "n_obs": int(r["size"])})
    return out


def run():
    started = utc_now().isoformat()
    m_old = pd.read_parquet(PRIOR / "processed" / "market_daily.parquet")[["date", "close", "adjclose", "ticker", "kind", "currency"]]
    d_old = pd.read_parquet(PRIOR / "processed" / "dividends.parquet")
    m_new, d_new, yrec = yahoo_new()
    mk = pd.concat([m_old.assign(source="yahoo_chart(prior snapshot core_premia_rates_fx_eq_acq_v1)"),
                    m_new.assign(source="yahoo_chart(cycle6)")], ignore_index=True)
    dv = pd.concat([d_old, d_new], ignore_index=True)
    lse, lrec = lse_levels()
    series = {t: g.set_index("date").sort_index() for t, g in mk.groupby("ticker")}
    divs = {t: g.set_index("date")["amount"].sort_index() for t, g in dv.groupby("ticker")}

    idx = pd.bdate_range("1960-01-01", "2026-09-30")
    rf, fx = short_rates(idx)
    h10 = {c: g.set_index("date")["usd_per_ccy"].sort_index() for c, g in fx[fx.source == "fed_h10"].groupby("ccy")}

    lev_rows, ex_rows, cands, qa_detail, val_rows = [], [], [], {}, []
    for mid, (name, ccy, tr, pxs, etf) in MARKETS.items():
        # local cash (euro legacy national before 1999)
        cash = rf.get(ccy, pd.DataFrame({"rf_pct": np.nan, "rf_source": None}, index=idx)).copy()
        if mid in EURO_LEGACY:
            leg = rf[EURO_LEGACY[mid]]
            pre = idx < EURO_START
            cash.loc[pre, ["rf_pct", "rf_source"]] = leg.loc[pre, ["rf_pct", "rf_source"]].values
            cash.loc[~pre & cash.rf_pct.isna(), "rf_source"] = None
        has_cash = cash.rf_pct.notna().any()
        # dividend estimate from ETF
        dy = None
        if etf and etf in series:
            e = series[etf]
            ttm = divs.get(etf, pd.Series(dtype=float)).reindex(e.index).fillna(0.0).rolling("365D").sum()
            dy_raw = (ttm / e["close"]).where(e.index >= e.index[0] + pd.Timedelta(days=365))
            dy = dy_raw.shift(1)
            me = month_end_last(dy_raw)
            for per, v in me.items():
                val_rows.append({"market_id": mid, "country": name, "month": per.to_timestamp(how="end").normalize(),
                                 "metric": "etf_ttm_dividend_yield", "value": float(v), "source_ticker": etf,
                                 "available_date": dy_raw.dropna()[dy_raw.dropna().index.to_period("M") == per].index.max()})
        avail_px = [p for p in pxs if p in series]
        notes = []
        if tr and tr in series and has_cash:
            tier, tick, construction = 1, tr, "local_TR_minus_local_cash"
        elif avail_px and has_cash and dy is not None:
            tick = min(avail_px, key=lambda p: series[p].index.min())
            tier, construction = 2, "local_price_plus_div_est_minus_local_cash"
            alts = [p for p in avail_px if p != tick]
            if alts:
                notes.append(f"price index chosen by longest history; alternates {alts}")
        elif etf and etf in series:
            tier, tick, construction = 3, etf, "usd_etf_tr_minus_usd_cash"
            why = []
            if not has_cash:
                why.append(f"no local cash rate for {ccy}")
            if not avail_px and not tr:
                why.append("no local index level")
            if avail_px and dy is None:
                why.append("no dividend estimate")
            notes.append("T3 because " + "; ".join(why))
        else:
            cands.append({"class": "EQ", "market_id": mid, "economic_market": name, "construction": "none",
                          "source": "", "first_date": "", "last_date": "", "n_months": 0, "qa_status": "FAIL",
                          "qa_reasons": "no feasible construction (no TR index, no dividend estimate, no country ETF)",
                          "notes": f"price index {avail_px} exists but no dividend source/ETF"})
            continue
        d = series[tick]
        col = "adjclose" if tier == 3 else "close"
        df = pd.DataFrame({"level": d[col]})
        df["ret"] = df.level / df.level.shift(1) - 1
        df["dt"] = df.index.to_series().diff().dt.days / 365.0
        c = (rf["USD"] if tier == 3 else cash).reindex(df.index)
        df["rf_pct"], df["rf_source"] = c.rf_pct.values, c.rf_source.values
        df["dy_est"] = dy.reindex(df.index).ffill(limit=5) if (tier == 2) else np.nan
        df["excess_ret"] = df.ret + (df.dy_est.fillna(0) * df.dt if tier == 2 else 0) - df.rf_pct / 100 * df.dt
        if tier == 2:
            df.loc[df.dy_est.isna(), "excess_ret"] = np.nan
        df = df.iloc[1:]
        valid = df.excess_ret.notna()
        span = df[valid]
        first, last = span.index.min(), span.index.max()
        df = df.loc[first:last]
        df["market_id"], df["ticker"], df["construction"], df["tier"] = mid, tick, construction, tier
        df["ccy"] = "USD" if tier == 3 else ccy
        df["source"] = d["source"].iloc[-1]
        ex_rows.append(df.reset_index(names="date"))

        # ---- QA
        reasons, info = [], {}
        gs = gaps_and_stale(d[col].loc[first:last], df.index[df.excess_ret.notna()])
        if gs["gaps"]:
            reasons.append(f"(b) {len(gs['gaps'])} gap(s) >{GAP_MAX} bdays, max {max(g['missing_bdays'] for g in gs['gaps'])}")
        if gs["stale_runs"]:
            reasons.append(f"(c) {len(gs['stale_runs'])} stale run(s) >= {STALE_MIN}")
        info.update(gs)
        if tier in (1, 2) and etf and etf in series and (ccy == "USD" or ccy in h10):
            tot = (df.ret + (df.dy_est * df.dt if tier == 2 else 0)).dropna()
            L = (1 + tot).cumprod()
            Rl = month_end_last(L).pct_change()
            Rfx = month_end_last(h10[ccy]).pct_change() if ccy != "USD" else Rl * 0
            e = series[etf]["adjclose"]
            Re = month_end_last(e).pct_change()
            u = rf["USD"].reindex(e.index)
            cu = (u.rf_pct / 100 * e.index.to_series().diff().dt.days / 365).fillna(0)
            Cu = cu.groupby(cu.index.to_period("M")).sum()
            j = pd.concat({"syn": (1 + Rl) * (1 + Rfx) - 1, "etf": Re, "cu": Cu}, axis=1).dropna()
            j = j.iloc[1:]  # drop partial first overlap month
            n = len(j)
            if n >= MIN_OVERLAP:
                pe = j.etf - j.cu
                te = float((j.syn - j.etf).std() / pe.std())
                rho = float(np.corrcoef(j.syn, j.etf)[0, 1])
                info["proxy"] = {"ticker": etf, "months": n, "te_over_sigma": round(te, 4), "corr": round(rho, 4),
                                 "first_month": str(j.index.min()), "last_month": str(j.index.max())}
                if te > TE_MAX:
                    reasons.append(f"(a) TE/sigma vs {etf} = {te:.2f} > {TE_MAX} on {n} months")
            else:
                info["proxy"] = {"ticker": etf, "months": n, "note": "< 36 overlapping months; (a) not applicable"}
        elif tier in (1, 2):
            info["proxy"] = {"note": f"no ETF proxy or no H.10 FX for {ccy}; (a) not applicable"}
        else:
            info["proxy"] = {"note": "construction is the traded ETF itself; (a) not applicable"}
        # informational LSE CFD agreement
        for lsym, ytick in LSE_MAP.items():
            if ytick == tick or (ytick in pxs and tick == ytick):
                ls = lse[lse.ticker == lsym].set_index("date")["close"]
                a = pd.concat({"y": month_end_last(d["close"]).pct_change(), "l": month_end_last(ls).pct_change()},
                              axis=1).dropna()
                if len(a) >= 12:
                    info["lse_cfd_agreement"] = {"symbol": lsym, "months": len(a),
                                                 "corr_monthly": round(float(a.corr().iloc[0, 1]), 4),
                                                 "te_monthly": round(float((a.y - a.l).std()), 5)}
        rfsrc = df.rf_source.dropna().unique().tolist()
        if tier == 2:
            notes.append(f"dividend estimate from {etf} TTM distributions (USD ETF, MSCI index, net of withholding)")
        if "proxy" in info and "te_over_sigma" in info["proxy"]:
            notes.append(f"proxy {etf}: TE/sigma {info['proxy']['te_over_sigma']}, corr {info['proxy']['corr']}, "
                         f"{info['proxy']['months']} m")
        elif "proxy" in info:
            notes.append(info["proxy"]["note"])
        if "lse_cfd_agreement" in info:
            la = info["lse_cfd_agreement"]
            notes.append(f"LSE {la['symbol']} monthly corr {la['corr_monthly']} ({la['months']} m)")
        nmiss = int(df.excess_ret.isna().sum())
        if nmiss:
            notes.append(f"{nmiss} in-span days without excess (cash/dy missing)")
        info["rf_sources"] = rfsrc
        qa_detail[mid] = info
        per = df.excess_ret.dropna().index.to_period("M")
        cands.append({"class": "EQ", "market_id": mid, "economic_market": name, "construction": construction,
                      "source": f"{tick} ({df['source'].iloc[0]}); cash {'USD' if tier == 3 else ccy}",
                      "first_date": str(first.date()), "last_date": str(last.date()),
                      "n_months": int(per.nunique()),
                      "qa_status": "FAIL" if reasons else "PASS", "qa_reasons": "; ".join(reasons),
                      "notes": " | ".join(notes)})

    ex = pd.concat(ex_rows, ignore_index=True)
    ex.to_parquet(OUT / "equity_excess_daily.parquet", index=False)
    pd.DataFrame(cands).to_csv(OUT / "candidates.csv", index=False)

    # levels: every equity-relevant ticker used or considered
    used = set()
    for mid, (_, _, tr, pxs, etf) in MARKETS.items():
        used |= {tr, etf, *pxs}
    lv = mk[mk.ticker.isin(used)].copy()
    lv["kind"] = lv["kind"].fillna("")
    lse2 = lse.assign(adjclose=np.nan, kind="lse_cfd_index_price", currency=lse.ticker.str.split("/").str[1],
                      source="lse_engine(/api/candles, provider=lse, 1d UTC bars)")
    levels = pd.concat([lv, lse2], ignore_index=True)[["date", "ticker", "kind", "currency", "close", "adjclose", "source"]]
    levels.to_parquet(OUT / "equity_levels_daily.parquet", index=False)

    val = pd.DataFrame(val_rows)
    val.to_parquet(OUT / "valuation_monthly.parquet", index=False)

    cpi, cpi_rec = build_cpi()
    cpi.to_parquet(OUT / "cpi_monthly_pit.parquet", index=False)

    write_json(META / "qa_detail.json", qa_detail)
    comp = {
        "built_at_utc": utc_now().isoformat(), "build_started_utc": started,
        "code": {str(p.relative_to(OUT.parents[2])): _sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "rules": {"TE_MAX": TE_MAX, "MIN_OVERLAP_MONTHS": MIN_OVERLAP, "GAP_MAX_BDAYS": GAP_MAX, "STALE_MIN": STALE_MIN},
        "endpoints": {
            "yahoo_chart_prior_snapshot": {
                "note": "tickers reused from frozen acquisition snapshot core_premia_rates_fx_eq_acq_v1 "
                        "(processed/market_daily.parquet, dividends.parquet); retrieval UTC in that snapshot's metadata",
                "manifest_sha256": PRIOR_MANIFEST},
            "yahoo_chart_cycle6": {"api": "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1=-2208988800"
                                          "&interval=1d&events=div|split&includeAdjustedClose=true",
                                   "expected": len(yrec), "received": sum(v["ok"] for v in yrec.values()),
                                   "failures": [k for k, v in yrec.items() if not v["ok"]], "per_ticker": yrec,
                                   "conventions": "exchange-local daily closes; adjclose re-based retroactively at "
                                                  "each distribution (returns PIT, stored levels not)"},
            "lse_engine_candles": {"api": "http://127.0.0.1:7799/api/candles (GET, read-only; same engine the LSE "
                                          "MCP get_history wraps)", "expected": len(LSE_MAP),
                                   "received": len(lrec), "failures": [s for s in LSE_MAP if s not in lrec],
                                   "per_symbol": lrec,
                                   "conventions": "CFD/cash index PRICE levels, UTC-day bars, max 5000 bars per call "
                                                  "(paged); used only for levels + informational agreement; no "
                                                  "vendor publication timestamps",
                                   "access_note": "MCP stdio bridge could not launch from the command sandbox "
                                                  "(3 consecutive 'open -b' failures); MCP tools terminal_status/"
                                                  "search_instruments/get_history worked in-session; data pulled via "
                                                  "the engine's GET routes"},
            **cpi_rec,
        },
        "short_rates": "prior pass syn.short_rate(); euro-legacy national OECD IR3TIB/IRSTCI prev-month averages "
                       "before 1999-01-01 (DEM, FRF, ITL, ESP, NLG, BEF, ATS, FIM, IEP, PTE); EUR after",
        "fx_for_qa": "Fed H.10 (prior snapshot processed/fx_spot_daily.parquet, source fed_h10)",
        "outputs": {p.name: {"rows": len(pd.read_parquet(p)) if p.suffix == ".parquet" else None, "sha256": _sha(p)}
                    for p in sorted(OUT.glob("*.parquet")) + [OUT / "candidates.csv"]},
    }
    write_json(OUT / "completeness.json", comp)
    print(pd.DataFrame(cands)[["market_id", "construction", "first_date", "n_months", "qa_status", "qa_reasons"]].to_string())


# ---------------------------------------------------------------- CPI
ISO3 = {"USA": "US", "CAN": "CA", "GBR": "UK", "DEU": "DE", "FRA": "FR", "ITA": "IT", "ESP": "ES", "NLD": "NL",
        "BEL": "BE", "AUT": "AT", "FIN": "FI", "IRL": "IE", "PRT": "PT", "CHE": "CH", "SWE": "SE", "NOR": "NO",
        "DNK": "DK", "JPN": "JP", "AUS": "AU", "NZL": "NZ", "ISR": "IL", "KOR": "KR", "IND": "IN", "CHN": "CN",
        "BRA": "BR", "MEX": "MX", "ZAF": "ZA", "IDN": "ID", "TUR": "TR", "POL": "PL", "CHL": "CL", "GRC": "GR",
        "HUN": "HU", "CZE": "CZ", "ISL": "IS", "COL": "CO", "RUS": "RU", "SAU": "SA", "ARG": "AR"}
DEFAULT_LAG_MONTHS = 2


def build_cpi():
    """One source per country, rule fixed before looking at values:
    OECD DF_PRICES_ALL CPI index (N, total, NSA); frequency with the earliest start (tie -> monthly);
    else LSE macro series. Quarterly values are placed on the quarter's last month.
    available_date = last calendar day of reference month + DEFAULT_LAG_MONTHS months (conservative;
    release dates before 2015 unknown), extended to the max observed LSE-calendar release lag if longer.
    Values are latest vintage (no real-time vintages available keylessly)."""
    src = json.loads((META / "acquire_web_results.json").read_text())["oecd_cpi"]
    frames = []
    for f in ("M", "Q"):
        r = src[f]
        o = pd.read_csv(RAW / r["path"], usecols=["REF_AREA", "FREQ", "TIME_PERIOD", "OBS_VALUE"])
        if f == "Q":
            per = pd.PeriodIndex(o.TIME_PERIOD.str.replace("-Q", "Q"), freq="Q")
            o["month"] = per.asfreq("M", how="end").to_timestamp(how="end").normalize()
        else:
            o["month"] = pd.PeriodIndex(o.TIME_PERIOD, freq="M").to_timestamp(how="end").normalize()
        frames.append(o.assign(freq=f))
    o = pd.concat(frames)
    o = o[o.REF_AREA.isin(ISO3)].dropna(subset=["OBS_VALUE"])
    o["country"] = o.REF_AREA.map(ISO3)
    pick, rows = {}, []
    for c, g in o.groupby("country"):
        starts = g.groupby("freq").month.min()
        f = "M" if ("M" in starts and starts["M"] <= starts.get("Q", starts["M"])) else starts.idxmin()
        gg = g[g.freq == f].sort_values("month")
        pick[c] = f"oecd_{f}"
        rows.append(pd.DataFrame({"country": c, "month": gg.month.values, "value": gg.OBS_VALUE.values,
                                  "freq": f, "source": f"oecd_sdmx DF_PRICES_ALL CPI IX _T N ({f})"}))
    lres = json.loads((META / "acquire_lse_results.json").read_text())
    lse_used, chained = {}, {}
    for c, r in lres["cpi"].items():
        if not r["ok"]:
            continue
        d = pd.DataFrame(json.loads((RAW / r["path"]).read_bytes()))
        d["month"] = pd.to_datetime(d.date).dt.to_period("M").dt.to_timestamp(how="end").dt.normalize()
        d["value"] = d.value.astype(float)
        if c in pick:
            # declared extension rule: OECD monthly series that end before the LSE series are extended by
            # ratio-chaining the LSE index (value = OECD_last * LSE_t / LSE_at_OECD_last); monthly only.
            if pick[c] != "oecd_M":
                continue
            k = [i for i, x in enumerate(rows) if x.country.iloc[0] == c][0]
            base = rows[k]
            last_m = base.month.max()
            ls = d.set_index("month").value
            ls = ls[~ls.index.duplicated(keep="last")]
            if last_m not in ls.index or ls.index.max() <= last_m:
                continue
            ext = ls[ls.index > last_m] / ls[last_m] * base.set_index("month").value[last_m]
            rows[k] = pd.concat([base, pd.DataFrame({"country": c, "month": ext.index, "value": ext.values, "freq": "M",
                                                     "source": f"chained lse_engine macro {d.symbol.iloc[0]} after "
                                                               f"{last_m.date()}"})], ignore_index=True)
            chained[c] = {"oecd_last": str(last_m.date()), "extended_to": str(ext.index.max().date()),
                          "n_months": len(ext), "lse_url": r["url"]}
            continue
        pick[c] = "lse"
        lse_used[c] = r["url"]
        rows.append(pd.DataFrame({"country": c, "month": d.month.values, "value": d.value.astype(float).values,
                                  "freq": "M", "source": f"lse_engine macro {d.symbol.iloc[0]}"}))
    cpi = pd.concat(rows, ignore_index=True)
    # observed release lags (LSE calendar, 2015+), informational + extends lag if longer than default
    cal = pd.DataFrame(json.loads((RAW / lres["calendar"]["CPI_released"]["path"]).read_bytes()))
    mon = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
    cal = cal[cal.period_hint.isin(mon) & ~cal.event.str.contains("mid-month|Flash|Prel|Tokyo|Saxony|Bavaria|Hesse|"
                                                                   "Baden|Westphalia|Brandenburg", case=False)]
    rd = pd.to_datetime(cal.date)
    pm = cal.period_hint.map(mon)
    yr = rd.dt.year - (pm > rd.dt.month).astype(int)
    ref_end = pd.to_datetime(dict(year=yr, month=pm, day=1)) + pd.offsets.MonthEnd(0)
    cal = cal.assign(lag_days=(rd - ref_end).dt.days, country=cal.region_code.replace({"GB": "UK"}))
    lag = cal[cal.lag_days.between(0, 200)].groupby("country").lag_days.agg(["max", "median", "count"])
    base = cpi.month + pd.offsets.MonthEnd(DEFAULT_LAG_MONTHS)
    ext = cpi.country.map(lag["max"]).fillna(0).astype(int)
    alt = cpi.month + pd.to_timedelta(ext + 1, unit="D")
    cpi["available_date"] = np.where(alt > base, alt, base)
    cpi["available_date"] = pd.to_datetime(cpi.available_date)
    cpi["lag_rule"] = np.where(alt > base, "observed_max_release_lag+1d", f"default_{DEFAULT_LAG_MONTHS}m")
    cpi["vintage"] = "latest (revised); not first release"
    rec = {"oecd_cpi": {"api": src["M"]["url"] + " ; " + src["Q"]["url"], "fetched_at_utc":
                        {f: src[f]["fetched_at_utc"] for f in src}, "countries_chosen": {c: p for c, p in pick.items()
                                                                                         if p.startswith("oecd")},
                        "conventions": "index 2015=100, NSA, national methodology; latest vintage"},
           "lse_cpi": {"api": "http://127.0.0.1:7799/api/macro/series (GET)", "expected": len(lres["cpi"]),
                       "received": sum(v["ok"] for v in lres["cpi"].values()), "used_for": lse_used,
                       "chained_extensions_of_oecd": chained,
                       "conventions": "LSE macro catalog CPI 'points', latest vintage, used only where OECD lacks the country"},
           "lse_calendar_release_lags": {"api": lres["calendar"]["CPI_released"]["url"],
                                         "fetched_at_utc": lres["calendar"]["CPI_released"]["fetched_at_utc"],
                                         "observed_lag_days": lag.reset_index().to_dict("records")}}
    return cpi, rec


if __name__ == "__main__":
    run()
