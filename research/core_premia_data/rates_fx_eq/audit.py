"""Feasibility audit: synthetic-construction error, acquisition completeness, candidate universe.

Instrument-level comparisons only (synthetic vs a real investable proxy of the SAME instrument).
No signal, sort, strategy, control or portfolio return is formed. The AQR workbook is used for its
date axis and per-class non-null flags only (``aqr_tsmom_dates.parquet``).

Outputs -> reports/core_premia_20260925/rates_fx_eq/
  completeness.json, synthetic_error.csv, universe.csv, universe.json, carry_inputs.csv, summary.json

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.audit
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from research.core_premia_data.rates_fx_eq.common import ATTEMPTS, META, PROC, REPORT, RAW, SYN, utc_now, write_json
from research.core_premia_data.rates_fx_eq.synthetic import BOND_SPECS, EQUITY, COUNTRY_CCY

G10 = {"AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"}
G7_BOND = {"US", "DE", "JP", "UK", "CA", "FR", "IT"}
AQR_START = pd.Timestamp("1985-01-31")
DQ_START = pd.Timestamp("1982-01-01")
EVENTS: list = []
CURRENT = [""]


# ------------------------------------------------------------------ helpers
def monthly_excess(daily: pd.DataFrame, col="excess_ret") -> pd.Series:
    s = daily.set_index("date")[col].dropna()
    return (1 + s).groupby(s.index.to_period("M")).prod() - 1


def err_stats(ref: pd.Series, syn: pd.Series, ann: int) -> dict:
    d = pd.concat([ref.rename("ref"), syn.rename("syn")], axis=1).dropna()
    if len(d) < 12:
        return {"n": len(d)}
    diff = d.ref - d.syn
    sd_ref = d.ref.std() * np.sqrt(ann)
    te = diff.std() * np.sqrt(ann)
    beta = np.cov(d.ref, d.syn)[0, 1] / d.syn.var()
    return {"n": int(len(d)), "start": str(d.index.min()), "end": str(d.index.max()),
            "corr": round(float(d.ref.corr(d.syn)), 4), "beta_ref_on_syn": round(float(beta), 4),
            "te_ann": round(float(te), 5), "te_over_sigma_ref": round(float(te / sd_ref), 4),
            "mean_diff_ann": round(float(diff.mean() * ann), 5), "sigma_ref_ann": round(float(sd_ref), 5),
            "max_abs_diff": round(float(diff.abs().max()), 5)}


ROLL_MONTHS = {2, 3, 5, 6, 8, 9, 11, 12}  # quarterly-expiry month and the month before


def add(rows, component, market, synthetic, reference, freq, st, note=""):
    rows.append({"component": component, "market_id": market, "synthetic": synthetic, "reference": reference,
                 "freq": freq, **st, "note": note})


# ------------------------------------------------------------------ synthetic error
def synthetic_errors():
    b = pd.read_parquet(SYN / "bond_excess_daily.parquet")
    f = pd.read_parquet(SYN / "fx_excess_daily.parquet")
    e = pd.read_parquet(SYN / "equity_excess_daily.parquet")
    m = pd.read_parquet(PROC / "market_daily.parquet")
    rfp = pd.read_parquet(SYN / "short_rates_daily.parquet")
    rf = {c: g.set_index("date")["rf_pct"] for c, g in rfp.groupby("ccy")}
    mk = {t: g.set_index("date").sort_index() for t, g in m.groupby("ticker")}
    rows = []

    def proxy_excess(tick, ccy, use="adjclose"):
        d = mk[tick]
        r = d[use] / d[use].shift(1) - 1
        dt = d.index.to_series().diff().dt.days / 365
        cash = rf.get(ccy, pd.Series(dtype=float)).reindex(d.index)
        out = pd.DataFrame({"date": d.index, "excess_ret": (r - cash / 100 * dt).values, "ret": r.values}).iloc[1:]
        return out

    def bond_syn(mid):
        return b[b.market_id == mid][["date", "excess_ret"]]

    def avg_syn(mids):
        parts = [bond_syn(x).set_index("date")["excess_ret"] for x in mids]
        s = pd.concat(parts, axis=1).dropna().mean(axis=1)
        return s.reset_index().rename(columns={0: "excess_ret", "index": "date"})

    bond_checks = [
        ("BOND_US_2Y", ["BOND_US_2Y"], "SHY", "USD"), ("BOND_US_5Y", ["BOND_US_5Y"], "IEI", "USD"),
        ("BOND_US_5Y", ["BOND_US_5Y", "BOND_US_7Y"], "IEI", "USD"),
        ("BOND_US_10Y", ["BOND_US_10Y"], "IEF", "USD"), ("BOND_US_10Y", ["BOND_US_7Y", "BOND_US_10Y"], "IEF", "USD"),
        ("BOND_US_7Y", ["BOND_US_7Y"], "IEF", "USD"), ("BOND_US_20Y", ["BOND_US_20Y"], "TLH", "USD"),
        ("BOND_US_30Y", ["BOND_US_20Y", "BOND_US_30Y"], "TLT", "USD"), ("BOND_US_20Y", ["BOND_US_20Y"], "TLT", "USD"),
        ("BOND_UK_10Y", ["BOND_UK_10Y"], "IGLT.L", "GBP"), ("BOND_UK_ZC_10Y", ["BOND_UK_ZC_10Y"], "IGLT.L", "GBP"),
        ("BOND_DE_10Y", ["BOND_DE_5Y", "BOND_DE_10Y"], "EXHD.DE", "EUR"), ("BOND_DE_2Y", ["BOND_DE_2Y"], "EXHB.DE", "EUR"),
        ("BOND_DE_10Y", ["BOND_DE_10Y"], "IBGM.AS", "EUR"), ("BOND_EA_AAA_10Y", ["BOND_EA_AAA_10Y"], "IBGM.AS", "EUR"),
        ("BOND_FR_10Y", ["BOND_FR_10Y"], "IBGM.AS", "EUR"), ("BOND_IT_10Y", ["BOND_IT_10Y"], "IBGM.AS", "EUR"),
        ("BOND_JP_10Y", ["BOND_JP_10Y"], "2561.T", "JPY"), ("BOND_JP_7Y", ["BOND_JP_7Y"], "2510.T", "JPY"),
        ("BOND_CA_10Y", ["BOND_CA_10Y"], "XGB.TO", "CAD"), ("BOND_CA_30Y", ["BOND_CA_30Y"], "ZFL.TO", "CAD"),
        ("BOND_AU_10Y", ["BOND_AU_10Y"], "IGB.AX", "AUD"), ("BOND_CH_10Y", ["BOND_CH_10Y"], "CSBGC0.SW", "CHF"),
    ]
    for mid, syns, tick, ccy in bond_checks:
        if tick not in mk:
            continue
        syn = avg_syn(syns)
        ref = proxy_excess(tick, ccy)
        lbl = "+".join(s.replace("BOND_", "") for s in syns) + " synthetic (EW avg)" if len(syns) > 1 else syns[0] + " synthetic"
        add(rows, "bond", mid, lbl, f"{tick} ETF adj-close excess ({ccy} cash)", "monthly",
            err_stats(monthly_excess(ref), monthly_excess(syn), 12), "ETF has maturity band/expense ratio; synthetic no roll-down")
        add(rows, "bond", mid, lbl, f"{tick} ETF adj-close excess ({ccy} cash)", "daily",
            err_stats(ref.set_index("date")["excess_ret"], syn.set_index("date")["excess_ret"], 252), "")
    fut_checks = [("BOND_US_2Y", ["BOND_US_2Y"], "ZT=F"), ("BOND_US_5Y", ["BOND_US_5Y"], "ZF=F"),
                  ("BOND_US_7Y", ["BOND_US_7Y"], "ZN=F"), ("BOND_US_10Y", ["BOND_US_10Y"], "ZN=F"),
                  ("BOND_US_30Y", ["BOND_US_20Y", "BOND_US_30Y"], "ZB=F")]
    for mid, syns, tick in fut_checks:
        syn = monthly_excess(avg_syn(syns))
        fr = mk[tick]["close"]
        fm = fr.groupby(fr.index.to_period("M")).last().pct_change()
        add(rows, "bond", mid, "+".join(syns), f"{tick} continuous front future (all months)", "monthly",
            err_stats(fm, syn, 12), "Yahoo continuous future: unadjusted roll gaps; CTD duration differs")
        keep = [p for p in fm.index if p.month not in ROLL_MONTHS]
        add(rows, "bond", mid, "+".join(syns), f"{tick} continuous front future (non-roll months Jan/Apr/Jul/Oct)",
            "monthly", err_stats(fm.loc[keep], syn, 12), "roll months excluded")

    # FX vs CME futures and currency ETFs (H.10 synthetic)
    fxh = f[f.source == "fed_h10"]
    fut = {"EUR": "6E=F", "JPY": "6J=F", "GBP": "6B=F", "AUD": "6A=F", "CAD": "6C=F", "CHF": "6S=F",
           "NZD": "6N=F", "MXN": "6M=F"}
    etf = {"EUR": "FXE", "JPY": "FXY", "GBP": "FXB", "AUD": "FXA", "CAD": "FXC", "CHF": "FXF"}
    for ccy, tick in fut.items():
        syn = monthly_excess(fxh[fxh.ccy == ccy])
        fr = mk[tick]["close"]
        fm = fr.groupby(fr.index.to_period("M")).last().pct_change()
        if ccy == "MXN" and fm.abs().max() > 1:  # quoted per 1 MXN, orientation already USD per MXN
            pass
        add(rows, "fx", f"FX_{ccy}", "H.10 spot + OECD/official rate differential", f"{tick} CME continuous future (all months)",
            "monthly", err_stats(fm, syn, 12), "futures settle ~14:00-16:00 CT vs H.10 noon ET; roll gaps included")
        keep = [p for p in fm.index if p.month not in ROLL_MONTHS]
        add(rows, "fx", f"FX_{ccy}", "H.10 spot + OECD/official rate differential", f"{tick} (non-roll months)",
            "monthly", err_stats(fm.loc[keep], syn, 12), "roll months excluded")
        syn_spot = fxh[fxh.ccy == ccy].set_index("date")["spot_ret"]
        add(rows, "fx", f"FX_{ccy}", "H.10 spot only (no carry)", f"{tick} (non-roll months)", "monthly",
            err_stats(fm.loc[keep], ((1 + syn_spot).groupby(syn_spot.index.to_period("M")).prod() - 1), 12),
            "shows what the carry leg adds")
    for ccy, tick in etf.items():
        if tick not in mk:
            continue
        syn = monthly_excess(fxh[fxh.ccy == ccy])
        ref = monthly_excess(proxy_excess(tick, "USD"))
        add(rows, "fx", f"FX_{ccy}", "H.10 spot + rate differential", f"{tick} currency-trust ETF excess (USD cash)",
            "monthly", err_stats(ref, syn, 12), "trust earns deposit rate minus 0.40% fee; can be below policy rate")

    # FX vs LSE 1-week forward points (carry-input and return error)
    fwd = pd.read_parquet(PROC / "fx_fwd_points_daily.parquet")
    spot = pd.read_parquet(PROC / "fx_spot_daily.parquet")
    lse = spot[spot.source == "lse_vault_legacy_fx"]
    carry_rows = []
    for pair, g in fwd.groupby("pair"):
        base, quote = pair[:3], pair[3:]
        ccy = base if quote == "USD" else quote
        pip = 0.01 if "JPY" in pair else 0.0001
        s = lse[lse.series_id == f"lse_fx/{pair}"].set_index("date")["quote_as_published"]
        pts = g.set_index("date")["sw_fwd_points"]
        d = pd.concat([s.rename("S"), pts.rename("pts")], axis=1).dropna()
        prem = (d.pts * pip) / d.S / (7 / 360)
        implied = (-prem if quote == "USD" else prem) * 100  # i_ccy - i_usd, % p.a.
        ours = fxh[fxh.ccy == ccy].set_index("date")["carry_diff_pct"]
        cm = pd.concat([implied.rename("implied"), ours.rename("ours")], axis=1).dropna()
        mm = cm.groupby(cm.index.to_period("M")).mean()
        carry_rows.append({"ccy": ccy, "pair": pair, "n_months": len(mm), "start": str(mm.index.min()),
                           "end": str(mm.index.max()), "corr_monthly_level": round(float(mm.implied.corr(mm.ours)), 4),
                           "mean_diff_pct_pa": round(float((mm.ours - mm.implied).mean()), 4),
                           "mae_pct_pa": round(float((mm.ours - mm.implied).abs().mean()), 4),
                           "p95_abs_diff_pct_pa": round(float((mm.ours - mm.implied).abs().quantile(0.95)), 4)})
        # return error: same LSE spot for both legs isolates the carry-input error
        usd_per = s if quote == "USD" else 1 / s
        sr = usd_per.pct_change()
        dt = usd_per.index.to_series().diff().dt.days / 365
        fwd_ret = sr + implied.shift(1).reindex(sr.index) / 100 * dt
        syn_ret = sr + ours.reindex(sr.index).shift(0) / 100 * dt  # ours already lagged inside rf
        add(rows, "fx", f"FX_{ccy}", "LSE spot + OECD/official rate differential",
            f"LSE spot + 1w forward-point implied differential ({pair}_SW_FWD)", "monthly",
            err_stats(((1 + fwd_ret.dropna()).groupby(fwd_ret.dropna().index.to_period('M')).prod() - 1),
                      ((1 + syn_ret.dropna()).groupby(syn_ret.dropna().index.to_period('M')).prod() - 1), 12),
            "isolates carry-input error; forward points are 1-week tenor, not 1-month")
        h10 = monthly_excess(fxh[fxh.ccy == ccy])
        add(rows, "fx", f"FX_{ccy}", "H.10 spot + OECD/official rate differential",
            f"LSE spot + 1w forward-point implied differential ({pair}_SW_FWD)", "monthly",
            err_stats(((1 + fwd_ret.dropna()).groupby(fwd_ret.dropna().index.to_period('M')).prod() - 1), h10, 12),
            "total: fixing-time (noon NY vs UTC-day close) + carry-input error")

    # Equity
    fxm = {c: g.set_index("date")["spot_ret"] for c, g in fxh.groupby("ccy")}
    for mid, (px, tr, etf_t, ccy, fut_t) in EQUITY.items():
        em = e[e.market_id == f"EQ_{mid}"]
        syn_d = em[em.role == "price_index"]
        tr_d = em[em.role == "tr_index"]
        etf_d = em[em.role == "etf_usd"]
        fut_d = em[em.role == "future_cont_usd"]
        local = syn_d if len(syn_d) else tr_d
        lname = f"{px} price + ETF-TTM dividend yield - {ccy} cash" if len(syn_d) else f"{tr} total-return index - {ccy} cash"
        if len(syn_d) and len(tr_d):
            add(rows, "equity", f"EQ_{mid}", lname, f"{tr} total-return index - cash (local)", "monthly",
                err_stats(monthly_excess(tr_d), monthly_excess(syn_d), 12), "pure dividend-estimate error")
            add(rows, "equity", f"EQ_{mid}", lname, f"{tr} total-return index - cash (local)", "daily",
                err_stats(tr_d.set_index("date")["excess_ret"], syn_d.set_index("date")["excess_ret"], 252), "")
        if len(local) and len(etf_d):
            # USD synthetic: local total return x FX, minus USD cash (monthly)
            lt = local.set_index("date")
            # local TOTAL return (independent of the local cash rate, which is missing for HKD/SGD/TWD/MYR)
            ltot = lt["ret"] + (lt["dy_est"].fillna(0) * lt["dt"] if len(syn_d) else 0.0)
            if len(syn_d):
                ltot = ltot.where(lt["dy_est"].notna())
            lm = (1 + ltot.dropna()).groupby(ltot.dropna().index.to_period("M")).prod() - 1
            if ccy == "USD":
                fm = pd.Series(0.0, index=lm.index)
            elif ccy in fxm:
                fs = fxm[ccy].dropna()
                fm = (1 + fs).groupby(fs.index.to_period("M")).prod() - 1
            else:
                fm = None
            if fm is not None:
                usd_rf = rf["USD"]
                ur = usd_rf.reindex(pd.bdate_range(usd_rf.index.min(), usd_rf.index.max())).ffill()
                rfm = (ur / 100 / 261).groupby(ur.index.to_period("M")).sum()
                syn_usd = (1 + lm) * (1 + fm) - 1 - rfm
                add(rows, "equity", f"EQ_{mid}", lname + " , converted at H.10 FX (USD excess)",
                    f"{etf_t} ETF adj-close excess (USD cash)", "monthly",
                    err_stats(monthly_excess(etf_d), syn_usd.dropna(), 12),
                    "ETF tracks MSCI (not the local benchmark), fee, withholding tax, close-time mismatch")
            else:
                add(rows, "equity", f"EQ_{mid}", lname, f"{etf_t} ETF", "monthly", {"n": 0},
                    f"no H.10 FX series for {ccy}")
        if len(fut_d) and len(local):
            fr = mk[fut_t]["close"]
            fmth = fr.groupby(fr.index.to_period("M")).last().pct_change()
            ref_local = monthly_excess(local)
            add(rows, "equity", f"EQ_{mid}", lname, f"{fut_t} continuous future (all months)", "monthly",
                err_stats(fmth, ref_local, 12), "roll gaps included" + ("; NKD is a USD quanto" if fut_t == "NKD=F" else ""))
            keep = [p for p in fmth.index if p.month not in ROLL_MONTHS]
            add(rows, "equity", f"EQ_{mid}", lname, f"{fut_t} continuous future (non-roll months)", "monthly",
                err_stats(fmth.loc[keep], ref_local, 12), "roll months excluded")
    se = pd.DataFrame(rows)
    se.to_csv(REPORT / "synthetic_error.csv", index=False)
    pd.DataFrame(carry_rows).to_csv(REPORT / "carry_input_error_fx_forward_points.csv", index=False)
    return se, pd.DataFrame(carry_rows)


# ------------------------------------------------------------------ data-quality per series
def dq(levels: pd.Series, rets: pd.Series | None, outlier: float, level_is_yield=False) -> dict:
    full = levels.dropna().sort_index()
    if full.empty:
        return {}
    # quality statistics are measured from DQ_START (AQR 1985-01 minus the 3-year warm-up) onward
    s = full[full.index >= DQ_START]
    if rets is not None:
        rets = rets[rets.index >= DQ_START]
    if s.empty:
        s = full
    wd = pd.bdate_range(s.index.min(), s.index.max())
    obs_wd = s.index[s.index.dayofweek < 5]
    gaps = s.index.to_series().diff().dt.days.fillna(0)
    runs, cur = 0, 1
    vals = s.values
    for i in range(1, len(vals)):
        if vals[i] == vals[i - 1]:
            cur += 1
            if cur == 5:
                runs += 1
                EVENTS.append({"series": CURRENT[0], "type": "stale_run_ge5", "date": str(s.index[i - 4].date()),
                               "detail": f"value {vals[i]} unchanged from {s.index[i - 4].date()}"})
        else:
            cur = 1
    if level_is_yield:
        mv = s.diff().abs()
        bad = mv[mv > outlier]
    else:
        bad = rets[rets.abs() > outlier] if rets is not None else pd.Series(dtype=float)
    n_out = int(len(bad))
    for dte, v in bad.items():
        EVENTS.append({"series": CURRENT[0], "type": "outlier_move", "date": str(dte.date()), "detail": f"{v:.4f}"})
    for dte, gdays in gaps[gaps > 7].items():
        if dte >= s.index.min():
            EVENTS.append({"series": CURRENT[0], "type": "gap_gt7d", "date": str(dte.date()), "detail": f"{int(gdays)} days"})
    return {"first": str(full.index.min().date()), "last": str(full.index.max().date()), "n_obs": int(len(full)),
            "dq_window_start": str(s.index.min().date()),
            "weekday_coverage": round(len(obs_wd) / max(len(wd), 1), 4), "longest_gap_days": int(gaps.max()),
            "n_gaps_gt7d": int((gaps > 7).sum()), "stale_runs_ge5": runs, "n_outlier_moves": n_out,
            "dup_dates": int(full.index.duplicated().sum()), "weekend_obs": int((s.index.dayofweek >= 5).sum())}


def aqr_overlap(first: pd.Timestamp, last: pd.Timestamp, aqr: pd.DataFrame, cls: str, warm_first: pd.Timestamp | None):
    a = aqr[aqr[f"has_{cls}"]]
    months = a.month_end.dt.to_period("M")
    rng = (months >= pd.Period(first, "M")) & (months <= pd.Period(last, "M"))
    ov = int(rng.sum())
    elig = 0
    if warm_first is not None:
        elig = int(((months >= pd.Period(warm_first, "M")) & (months <= pd.Period(last, "M"))).sum())
    return ov, elig


def warmup_month(dates: pd.Series, n=756):
    d = pd.Series(sorted(pd.to_datetime(dates.dropna().unique())))
    if len(d) <= n:
        return None
    return d.iloc[n]  # the 757th obs date: first month-end with >=756 prior valid obs is this month


def adv_stats(m: pd.DataFrame, tick: str, from_month=None):
    d = m[m.ticker == tick].set_index("date").sort_index()
    if d.empty or d["volume"].isna().all():
        return {}
    dv = (d["close"] * d["volume"]).rolling(60, min_periods=60).median()
    mm = dv.groupby(dv.index.to_period("M")).last().dropna()
    if from_month is not None:
        mm = mm[mm.index >= from_month]
    if mm.empty:
        return {}
    return {"adv60_median_latest": float(round(mm.iloc[-1], 0)), "adv60_min_last120m": float(round(mm.iloc[-120:].min(), 0)),
            "months_adv_ge_5m": int((mm >= 5e6).sum()), "months_with_adv": int(len(mm)),
            "first_month_adv_ge_5m": str(mm[mm >= 5e6].index.min()) if (mm >= 5e6).any() else None,
            "currency": d["currency"].iloc[-1]}


# ------------------------------------------------------------------ universe
def universe(se: pd.DataFrame, carry: pd.DataFrame):
    aqr = pd.read_parquet(PROC / "aqr_tsmom_dates.parquet")
    b = pd.read_parquet(SYN / "bond_excess_daily.parquet")
    f = pd.read_parquet(SYN / "fx_excess_daily.parquet")
    e = pd.read_parquet(SYN / "equity_excess_daily.parquet")
    y = pd.read_parquet(PROC / "yields_daily.parquet")
    m = pd.read_parquet(PROC / "market_daily.parquet")
    rows = []

    def best_err(mid, freq="monthly"):
        s = se[(se.market_id == mid) & (se.freq == freq) & se.te_over_sigma_ref.notna()]
        if s.empty:
            return {}
        r = s.sort_values("te_over_sigma_ref").iloc[0]
        return {"best_ref": r["reference"], "err_corr": r["corr"], "err_te_ann": r["te_ann"],
                "err_te_over_sigma_ref": r["te_over_sigma_ref"], "err_months": r["n"], "err_mean_diff_ann": r["mean_diff_ann"]}

    # curve availability per country (daily, >=2 tenors) for bond carry inputs
    curve = {}
    for c, g in y[~y.source.eq("snb")].groupby("country"):
        ten = g.groupby("tenor_y").date.agg(["min", "max"])
        curve[c] = "; ".join(f"{t:g}y[{r['min'].date()}..{r['max'].date()}]" for t, r in ten.iterrows())

    bond_proxy = {"US": "IEF / ZN=F (CBOT)", "DE": "EXHD.DE (Xetra) / FGBL (Eurex, no free history)",
                  "JP": "2561.T / 2510.T (TSE); JGB futures (no free history acquired)", "UK": "IGLT.L (LSE)",
                  "CA": "XGB.TO / ZFL.TO (TSX)", "FR": "none free single-country (IBGM.AS EUR 7-10 multi-issuer)",
                  "IT": "none free single-country (IBGM.AS multi-issuer)", "AU": "IGB.AX", "CH": "CSBGC0.SW",
                  "SE": "none free", "NO": "none free", "NZ": "none free", "ES": "none free", "EA_AAA": "IBGM.AS",
                  "UK_ZC": "IGLT.L"}
    bond_etf_tick = {"US": "IEF", "DE": "EXHD.DE", "JP": "2561.T", "UK": "IGLT.L", "CA": "XGB.TO", "AU": "IGB.AX",
                     "CH": "CSBGC0.SW", "EA_AAA": "IBGM.AS", "FR": "IBGM.AS", "IT": "IBGM.AS", "UK_ZC": "IGLT.L"}
    for (ctry, T), (src, sid, kind) in BOND_SPECS.items():
        mid = f"BOND_{ctry}_{T}Y"
        g = b[b.market_id == mid]
        if g.empty:
            continue
        lv = g.set_index("date")["y"]
        CURRENT[0] = mid
        q = dq(lv * 100, None, 0.75 if ctry in G7_BOND or ctry in {"AU", "CH", "SE", "NO", "NZ", "ES"} else 1.5, True)
        w = warmup_month(g.date)
        ov, elig = aqr_overlap(g.date.min(), g.date.max(), aqr, "FI", w)
        tick = bond_etf_tick.get(ctry)
        adv = adv_stats(m, tick) if tick else {}
        legacy = src.startswith("lse_vault_legacy")
        c_base = ctry.split("_ZC")[0]
        pit = ("official daily publication (end-of-day, next morning at latest); no vintage history kept"
               if not legacy else "vendor benchmark yield (LSE vault), retrieval time/vintage not recorded")
        cond = {
            "c1_unique_market": "primary" if T == 10 and ctry != "UK_ZC" else "alias/other tenor of same market",
            "c2_pit_source": "PASS" if not legacy else "FAIL(vintage/retrieval unknown)",
            "c3_120m_aqr_after_warmup": "PASS" if elig >= 120 else f"FAIL({elig})",
            "c3_coverage_weekday": q.get("weekday_coverage"),
            "c4_no_unexplained_defects": "PASS" if (q.get("stale_runs_ge5", 0) == 0 and q.get("n_outlier_moves", 0) == 0
                                                    and q.get("n_gaps_gt7d", 0) == 0) else "REVIEW",
            "c5_g7_curve_with_proxy": "PASS" if (c_base in {"US", "DE", "JP", "UK", "CA"} and not legacy) else
                                      ("FAIL(not G7)" if c_base not in G7_BOND else "FAIL(vendor series/no single-country proxy)"),
        }
        defects = []
        if q.get("n_outlier_moves"):
            defects.append(f"{q['n_outlier_moves']} daily |dy|>{0.75 if c_base in G7_BOND else 1.5}pp")
        if q.get("stale_runs_ge5"):
            defects.append(f"{q['stale_runs_ge5']} stale runs>=5d")
        if q.get("n_gaps_gt7d"):
            defects.append(f"{q['n_gaps_gt7d']} gaps>7d (max {q['longest_gap_days']}d)")
        if g.rf_pct.isna().mean() > 0:
            defects.append(f"financing rate missing {g.rf_pct.isna().mean():.1%} of days")
        if src == "boe_iadb":
            defects.append("BoE fitted curve (not a traded bond)")
        if src == "bundesbank":
            defects.append("Svensson-fitted par yield (not a traded bond); daily only from 1997-08")
        rows.append({"class": "bond", "market_id": mid, "country": ctry, "tenor_y": T, "source": src, "series_id": sid,
                     "yield_kind": kind, "investable_proxy": bond_proxy.get(ctry, "none free"),
                     **q, "aqr_class": "FI", "aqr_overlap_months": ov, "first_warm_month_756d": str(w.date()) if w is not None else None,
                     "aqr_eligible_months_after_warmup": elig, "pit_status": pit, "curve_tenors_daily": curve.get(c_base, ""),
                     "carry_input": "slope 10y-3m + roll-down need >=2 tenors: " + ("yes" if curve.get(c_base, "").count("y[") >= 2 else "NO"),
                     **{f"proxy_{k}": v for k, v in adv.items()}, **best_err(mid), **cond, "defects": "; ".join(defects)})

    # FX
    for (src, ccy), g in f.groupby(["source", "ccy"]):
        mid = f"FX_{ccy}"
        lv = g.set_index("date")["S"]
        CURRENT[0] = f"{mid}/{src}"
        q = dq(lv, g.set_index("date")["spot_ret"], 0.15)
        w = warmup_month(g.date)
        ov, elig = aqr_overlap(g.date.min(), g.date.max(), aqr, "FX", w)
        carry_ok = g.carry_diff_pct.notna()
        cr = carry[carry.ccy == ccy]
        pit = {"fed_h10": "official H.10 noon NY buying rates, published weekly (Mondays) / daily DDP; revisions rare",
               "ecb": "ECB 14:15 CET reference rate; not revised",
               "lse_vault_legacy_fx": "vendor UTC-day close; retrieval/vintage not recorded"}[src]
        cond = {"c1_unique_market": "primary" if src == "fed_h10" else "alias source of same currency",
                "c2_pit_source": "PASS" if src != "lse_vault_legacy_fx" else "FAIL(vintage/retrieval unknown)",
                "c3_120m_aqr_after_warmup": "PASS" if elig >= 120 else f"FAIL({elig})",
                "c3_coverage_weekday": q.get("weekday_coverage"),
                "c4_no_unexplained_defects": "PASS" if (q.get("stale_runs_ge5", 0) == 0 and q.get("n_outlier_moves", 0) == 0) else "REVIEW",
                "c5_g10_spot": "PASS" if ccy in G10 else "FAIL(not G10)"}
        defects = []
        if q.get("stale_runs_ge5"):
            defects.append(f"{q['stale_runs_ge5']} stale runs>=5d (pegs/managed?)")
        if q.get("n_outlier_moves"):
            defects.append(f"{q['n_outlier_moves']} daily |ret|>15%")
        if (~carry_ok).mean() > 0:
            defects.append(f"carry differential missing {(~carry_ok).mean():.1%} of days")
        if ccy in {"VEB", "HKD", "SGD", "MYR", "TWD", "THB", "LKR"}:
            defects.append("no free short-rate series (OECD) -> no carry/excess return")
        rows.append({"class": "fx", "market_id": mid, "country": ccy, "source": src, "series_id": ",".join(sorted(g.get("ccy").unique())),
                     "investable_proxy": {"EUR": "6E=F / FXE", "JPY": "6J=F / FXY", "GBP": "6B=F / FXB", "AUD": "6A=F / FXA",
                                          "CAD": "6C=F / FXC", "CHF": "6S=F / FXF", "NZD": "6N=F", "MXN": "6M=F"}.get(ccy, "none free"),
                     **q, "aqr_class": "FX", "aqr_overlap_months": ov, "first_warm_month_756d": str(w.date()) if w is not None else None,
                     "aqr_eligible_months_after_warmup": elig, "pit_status": pit,
                     "carry_input": f"rate differential available {carry_ok.mean():.1%} of days; sources: " +
                                    ",".join(sorted(set(g.rf_ccy_source.dropna().str.split('_').str[:2].str.join('_')))),
                     "fwd_points_check": (f"corr {cr.corr_monthly_level.iloc[0]}, MAE {cr.mae_pct_pa.iloc[0]}pp, "
                                          f"{cr.n_months.iloc[0]}m") if len(cr) else "none",
                     **best_err(mid), **cond, "defects": "; ".join(defects)})

    # Equity
    for mid_s, (px, tr, etf_t, ccy, fut_t) in EQUITY.items():
        mid = f"EQ_{mid_s}"
        em = e[e.market_id == mid]
        for role, tick in (("price_index", px), ("tr_index", tr), ("etf_usd", etf_t)):
            g = em[em.role == role]
            if g.empty:
                continue
            CURRENT[0] = f"{mid}/{role}/{tick}"
            q = dq(g.set_index("date")["level"], g.set_index("date")["ret"], 0.25)
            w = warmup_month(g.date)
            ov, elig = aqr_overlap(g.date.min(), g.date.max(), aqr, "EQ", w)
            adv = adv_stats(m, etf_t) if (etf_t and role == "etf_usd") else {}
            dy_ok = g.dy_est.notna().mean() if role == "price_index" else None
            defects = []
            if role == "price_index":
                defects.append("price-only index; dividends estimated from ETF TTM distributions" +
                               (f" (available {dy_ok:.0%} of days)" if dy_ok is not None else ""))
                if not etf_t:
                    defects.append("no ETF -> no dividend estimate -> no total return")
            if role == "etf_usd":
                defects.append("USD-listed ETF: US close vs local close; MSCI index; fee; Yahoo adj-close rebased at each distribution")
            if q.get("n_outlier_moves"):
                defects.append(f"{q['n_outlier_moves']} daily |ret|>25%")
            if q.get("stale_runs_ge5"):
                defects.append(f"{q['stale_runs_ge5']} stale runs>=5d")
            if q.get("weekend_obs"):
                defects.append(f"{q['weekend_obs']} weekend-dated bars")
            cond = {"c1_unique_market": "primary" if role == ("etf_usd" if etf_t else ("tr_index" if tr else "price_index")) else "alias of same market",
                    "c2_pit_source": "PASS" if role != "price_index" or dy_ok else "FAIL(no dividend estimate)",
                    "c3_120m_aqr_after_warmup": "PASS" if elig >= 120 else f"FAIL({elig})",
                    "c3_coverage_weekday": q.get("weekday_coverage"),
                    "c4_no_unexplained_defects": "PASS" if (q.get("stale_runs_ge5", 0) == 0 and q.get("n_outlier_moves", 0) == 0 and not q.get("weekend_obs")) else "REVIEW",
                    "c5_etf_adv_ge_5m": ("PASS(last 120m)" if adv and adv.get("adv60_min_last120m", 0) >= 5e6 else
                                         ("FAIL" if adv else "n/a (not an ETF proxy)"))}
            rows.append({"class": "equity", "market_id": mid, "country": ccy, "source": "yahoo_chart", "series_id": tick,
                         "role": role, "investable_proxy": f"{etf_t or 'none'}" + (f" / {fut_t}" if fut_t else ""),
                         **q, "aqr_class": "EQ", "aqr_overlap_months": ov,
                         "first_warm_month_756d": str(w.date()) if w is not None else None,
                         "aqr_eligible_months_after_warmup": elig,
                         "pit_status": "exchange close (local tz); Yahoo adj-close not stored point-in-time (re-based)",
                         **{f"proxy_{k}": v for k, v in adv.items()}, **best_err(mid), **cond, "defects": "; ".join(defects)})

    u = pd.DataFrame(rows)
    return u


def lse_index_rows(aqr):
    from research.core_premia_data.rates_fx_eq.common import ROOT
    c = json.loads((ROOT / "data/lse_catalog_20260917.json").read_text())
    out = []
    for x in c:
        if x["dataset"] != "index":
            continue
        first, last = pd.Timestamp(x["first_tick"][:10]), pd.Timestamp(x["last_tick"][:10])
        ov, _ = aqr_overlap(first, last, aqr, "EQ", None)
        out.append({"class": "equity", "market_id": f"LSE_INDEX_{x['symbol']}", "country": x.get("country"),
                    "source": "lse_catalog_20260917 (metadata only)", "series_id": x["symbol"], "role": "lse_index_cfd_like",
                    "first": str(first.date()), "last": str(last.date()), "aqr_class": "EQ", "aqr_overlap_months": ov,
                    "aqr_eligible_months_after_warmup": 0, "c3_120m_aqr_after_warmup": "FAIL(history < 4y)",
                    "pit_status": "UTC-day bars (00:00-24:00 UTC), include extended hours; price-only",
                    "defects": "history starts 2023-2026; MCP pull not executed (terminal not running); price-only, no dividends",
                    "investable_proxy": "none free"})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ completeness
def completeness():
    att = [json.loads(l) for l in ATTEMPTS.read_text().splitlines()]
    by = defaultdict(list)
    for a in att:
        by[(a["source"], a["name"])].append(a)
    build = json.loads((META / "build_record.json").read_text())
    y = pd.read_parquet(PROC / "yields_daily.parquet")
    fx = pd.read_parquet(PROC / "fx_spot_daily.parquet")
    m = pd.read_parquet(PROC / "market_daily.parquet")
    o = pd.read_parquet(PROC / "oecd_monthly.parquet")
    endpoints = []
    for (src, name), atts in sorted(by.items()):
        ok = [a for a in atts if a["outcome"] == "ok"]
        endpoints.append({"source": src, "name": name, "url": (ok or atts)[-1].get("url"),
                          "attempts": len(atts), "failures_or_retries": sum(1 for a in atts if a["outcome"] != "ok"),
                          "final_status": "ok" if ok else atts[-1]["outcome"],
                          "retrieved_at_utc": ok[-1]["logged_at_utc"] if ok else None,
                          "bytes": ok[-1].get("bytes", ok[-1].get("chars")) if ok else 0,
                          "errors": sorted({str(a.get("error") or a.get("http_status")) for a in atts if a["outcome"] != "ok"})[:5]})
    # expected vs received by dataset
    exp = {
        "fed_h10": {"expected_instruments": 23, "received_instruments": int(fx[fx.source == "fed_h10"].ccy.nunique()),
                    "range": [str(fx[fx.source == "fed_h10"].date.min().date()), str(fx[fx.source == "fed_h10"].date.max().date())],
                    "notes": "H.10 package carries 23 currencies incl. discontinued VEB; pre-1999 euro-legacy currencies (DEM, FRF, ITL, NLG, BEF, ESP...) are NOT in the DDP package and FRED (which has them) is unreachable -> missing"},
        "fed_h15": {"expected_instruments": 11, "received_instruments": int(y[y.source == "fed_h15"].series_id.nunique())},
        "boe_iadb": {"expected_instruments": 9, "received_instruments": int(y[y.source == "boe_iadb"].series_id.nunique())},
        "bundesbank": {"expected_instruments": 6, "received_instruments": int(y[y.source == "bundesbank"].series_id.nunique()),
                       "notes": "daily par curve starts 1997-08 (earlier only monthly, not pulled)"},
        "mof_japan": {"expected_instruments": 15, "received_instruments": int(y[y.source == "mof_japan"].series_id.nunique())},
        "boc_valet": {"expected_instruments": 5, "received_instruments": int(y[y.source == "boc_valet"].series_id.nunique()),
                      "notes": "benchmark yields from 2001; 3M T-bill weekly"},
        "riksbank": {"expected_instruments": 5, "received_instruments": int(y[y.source == "riksbank"].series_id.nunique()),
                     "notes": "STIBOR 3M closed 2020-07 (kept)"},
        "norges_bank": {"expected_instruments": 5, "received_instruments": int(y[y.source == "norges_bank"].series_id.nunique()),
                        "notes": "generic rates API history starts 2019-01"},
        "snb": {"expected_instruments": 13, "received_instruments": int(y[y.source == "snb"].series_id.nunique()),
                "notes": "monthly only; cube last obs 2025-07 (stale), publishing date 2025-09-01"},
        "ecb": {"expected_instruments": 5, "received_instruments": 4, "notes": "EURIBOR 3M key returned no data; API intermittently unreachable"},
        "oecd_sdmx": {"expected_measures": 3, "received_measures": int(o.measure.nunique()),
                      "areas_IRLT": int(o[o.measure == "IRLT"].ref_area.nunique()),
                      "areas_IR3TIB": int(o[o.measure == "IR3TIB"].ref_area.nunique()),
                      "notes": "monthly AVERAGES (not end-of-month); latest vintage only, revisable; no ALFRED vintages (unreachable)"},
        "yahoo_chart": {"expected_instruments": int(len(json.loads((META / 'acquire_yahoo_results.json').read_text())['results'])),
                        "received_instruments": int(m.ticker.nunique())},
        "lse_mcp": {"expected_calls": 55, "calls_made": 54, "calls_with_data": 0,
                    "notes": "LSE Terminal app not running; every call returned 'not running/cannot be opened'. The script lacked an abort-on-status guard at run time (added afterwards); 54 of the 60-call budget were consumed with zero data. No retry was made."},
        "lse_vault_legacy": {"notes": "pre-existing local pulls imported read-only: data/bond_yields (29 series), data/multiasset/yields (12), data/lse/fx_carry/raw.pkl (9 pairs spot+SW_FWD 2015+). Vendor retrieval timestamps are not in an ingestion record."},
    }
    blocked = json.loads((META / "blocked_probe_results.json").read_text())["results"]
    mcp = json.loads((META / "acquire_lse_mcp_results.json").read_text())
    out = {"generated_at_utc": utc_now().isoformat(), "endpoints": endpoints, "expected_vs_received": exp,
           "blocked_or_unreachable": {**blocked, "notes": "FRED/ALFRED: TLS stream reset/timeout from this host (also outside sandbox). "
                                     "Stooq: JavaScript proof-of-work bot check, not bypassed. RBA: timeout. RBNZ: HTTP 403. "
                                     "ECB: timed out at first probe, answered later (data taken). MSCI: login-gated (ruled out earlier)."},
           "lse_mcp_call_log": {"calls_made": mcp["calls_made"], "errors": sum(1 for c in mcp["calls"] if c.get("is_error"))},
           "processed_tables": build["tables"], "build_notes": build["notes"],
           "conventions": {
               "utc_day_flag": "LSE vault fx spot (legacy) are UTC calendar-day bars incl. extended hours; LSE index series likewise (not pulled)",
               "timezones": "H.10 noon America/New_York; H.15 ~15:30 ET closing bid; BoE London close; Bundesbank Frankfurt EOD; MOF Tokyo close; ECB 14:15 CET; Yahoo exchange-local close",
               "revisions": "OECD monthly averages revisable, no vintages; H.10/H.15 final, rarely revised; Yahoo adjusted close retro-rebased; no ALFRED",
               "discontinued_kept": "US 20y CMT gap 1987-1993 (Treasury stopped 20y), BoE IUDVCDA (to 2018), Riksbank STIBOR (to 2020), H.10 VEB, SNB cube stale 2025-07",
               "roll_adjustment": "No contract-level futures anywhere; Yahoo continuous futures are unadjusted front-month -> roll gaps; used only as overlap checks"}}
    write_json(REPORT / "completeness.json", out)
    return out


def main():
    se, carry = synthetic_errors()
    u = universe(se, carry)
    aqr = pd.read_parquet(PROC / "aqr_tsmom_dates.parquet")
    u = pd.concat([u, lse_index_rows(aqr)], ignore_index=True)
    u.to_csv(REPORT / "universe.csv", index=False)
    ev = pd.DataFrame(EVENTS)
    ev.to_csv(REPORT / "dq_events.csv", index=False)
    # ETF proxies: defects dated before the ETF's first month with 60-session median ADV >= USD 5m fall
    # outside any month condition (v) could make eligible -> mechanically explained.
    if "proxy_first_month_adv_ge_5m" in u:
        for i, r in u.iterrows():
            if r.get("role") == "etf_usd" and r.get("c4_no_unexplained_defects") == "REVIEW" and isinstance(r.get("proxy_first_month_adv_ge_5m"), str):
                key = f"{r.market_id}/etf_usd/{r.series_id}"
                later = ev[(ev.series == key) & (ev.date >= str(pd.Period(r.proxy_first_month_adv_ge_5m, "M").start_time.date()))]
                if later.empty:
                    u.at[i, "c4_no_unexplained_defects"] = "PASS(all events precede ADV-eligible months)"
    u.to_csv(REPORT / "universe.csv", index=False)
    u.to_json(REPORT / "universe.json", orient="records", indent=1, date_format="iso")
    u.to_json(REPORT / "universe.json", orient="records", indent=1, date_format="iso")
    comp = completeness()
    # breadth summary
    summ = {"generated_at_utc": utc_now().isoformat(), "aqr_tsmom_range": [str(aqr.month_end.min().date()), str(aqr.month_end.max().date())]}
    for cls in ("bond", "fx", "equity"):
        c = u[(u["class"] == cls) & (u.c1_unique_market == "primary")]
        cond_cols = [k for k in c.columns if k.startswith("c") and k[1].isdigit() and k != "c3_coverage_weekday" and k != "c1_unique_market"]
        allpass = c[cond_cols].apply(lambda r: all(pd.isna(v) or str(v).startswith("PASS") or str(v).startswith("n/a") for v in r), axis=1) if len(c) else []
        summ[cls] = {"primary_candidates": int(len(c)),
                     "pass_all_mechanical_conditions_provisional": int(np.sum(allpass)) if len(c) else 0,
                     "pass_list": c[allpass]["market_id"].tolist() if len(c) else [],
                     "c3_120m_pass": int((c.c3_120m_aqr_after_warmup == "PASS").sum())}
    write_json(REPORT / "summary.json", summ)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
