"""Attack 1b / 3: rebuild regular-session closes from LSE intraday bars, re-run M, closing-price realism.

LSE bars for TLT are regular-hours-only until 2026-05 (09:00-15:00 ET clock-aligned 1h bars; the
09:00 bar contains 09:30-10:00). Close = close of the bar starting (session close - 60 min), i.e. the
last continuous trade before the bell; it is NOT the closing-auction print.

  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.b_lse
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from research.audit_tsy.common import OUT, book, hold_mask, irx_rf, month_pos, sharpe, yf_raw
from research.forward import nyse

bars = pd.concat([pd.read_csv(OUT / "lse_TLT_1h_bars_dev.csv"), pd.read_csv(OUT / "lse_TLT_1h_bars_val.csv")])
bars["time"] = pd.to_datetime(bars["time"], utc=True)
bars = bars.drop_duplicates("time").sort_values("time")
bars["et"] = bars["time"].dt.tz_convert(nyse.ET)
bars["day"] = bars["et"].dt.date

rows = {}
for day, g in bars.groupby("day"):
    if not nyse.is_session(day):
        continue
    close_t = dt.datetime.combine(day, nyse.session_close_time(day), tzinfo=nyse.ET)
    last = g[(g["et"] >= close_t - dt.timedelta(minutes=60)) & (g["et"] < close_t)]
    after = g[g["et"] >= close_t].sort_values("et")
    rows[pd.Timestamp(day)] = {"lse_close": float(last["close"].iloc[-1]) if len(last) else np.nan,
                               "lse_first_after_open": float(after["open"].iloc[0]) if len(after) else np.nan,
                               "n_bars": len(g)}
lse = pd.DataFrame.from_dict(rows, orient="index").sort_index()
lse.to_csv(OUT / "lse_TLT_rth_closes.csv")

raw = yf_raw("TLT")
irx = yf_raw("IRX")["Close"]
res = {"lse_sessions": int(lse["lse_close"].notna().sum()),
       "lse_first": str(lse.index.min().date()), "lse_last": str(lse.index.max().date())}

j = lse.join(raw[["Close", "Open", "Dividends"]], how="inner")
j["diff_bp"] = (j["lse_close"] / j["Close"] - 1) * 1e4
mp = month_pos(raw.index).reindex(j.index)
j["from_end"] = mp["from_end"]
endpoints = j["from_end"].isin([0, 3])            # closes that define the window: 4th-to-last and last
res["close_diff_lse_lasttrade_vs_yf_official_bp"] = {
    "all": {"n": int(j["diff_bp"].notna().sum()), "mean": float(j["diff_bp"].mean()), "median": float(j["diff_bp"].median()),
            "mad": float(j["diff_bp"].abs().median()), "p99_abs": float(j["diff_bp"].abs().quantile(.99)),
            "n_gt_25bp": int((j["diff_bp"].abs() > 25).sum())},
    "last_session_of_month": {"mean": float(j.loc[j["from_end"] == 0, "diff_bp"].mean()),
                              "mad": float(j.loc[j["from_end"] == 0, "diff_bp"].abs().median())},
    "fourth_to_last_session": {"mean": float(j.loc[j["from_end"] == 3, "diff_bp"].mean()),
                               "mad": float(j.loc[j["from_end"] == 3, "diff_bp"].abs().median())},
    "other_sessions": {"mean": float(j.loc[~endpoints, "diff_bp"].mean())},
    "largest_abs": {str(k.date()): round(float(v), 1) for k, v in j["diff_bp"].abs().nlargest(8).items()},
}
# post-close auction print where after-hours bars exist (2026-05 onward)
aa = j.dropna(subset=["lse_first_after_open"])
if len(aa):
    res["first_after_hours_bar_open_vs_yf_close_bp"] = {"n": int(len(aa)),
        "mean": float(((aa["lse_first_after_open"] / aa["Close"] - 1) * 1e4).mean()),
        "mad": float(((aa["lse_first_after_open"] / aa["Close"] - 1) * 1e4).abs().median())}

# M on LSE last-trade closes (dividends on yfinance ex-dates) vs on official closes, same sample
def tr(c, d):
    return (c + d) / c.shift(1) - 1


spans = {"dev_2007_2014": ("2007-01-03", "2014-12-31"), "val_2015_2026": ("2015-01-02", "2026-08-31")}
for tag, (a, b) in spans.items():
    idx = raw.loc[a:b].index
    c_off = raw["Close"].reindex(idx)
    c_lse = lse["lse_close"].reindex(idx)
    miss = int(c_lse.isna().sum())
    c_lse_f = c_lse.fillna(c_off)                      # fill the few missing sessions with official
    d = raw["Dividends"].reindex(idx).fillna(0)
    rf = irx_rf(raw.index, irx).reindex(idx).fillna(0)
    e = hold_mask(idx)
    out = {"missing_lse_sessions_filled_with_official": miss}
    for name, c in (("official", c_off), ("lse_last_trade", c_lse_f)):
        r = tr(c, d).fillna(0); r.iloc[0] = 0
        for k, cst in (("gross", 0.0), ("base", 2e-4)):
            m, act = book(r, rf, e, cst)
            out[f"{name}_{k}"] = {"active_sharpe": sharpe(act), "active_ann": float(act.mean() * 252)}
        per = idx.to_period("M")
        out[f"{name}_window_bp"] = float((((1 + r).where(e, 1.0)).groupby(per).prod() - 1).mean() * 1e4)
    # 3. execution alternatives (official prices): enter next open after the decision close, exit at
    #    (a) last close, (b) next open after last close (ex-dividend open: add the dividend)
    o = raw["Open"].reindex(idx)
    mpi = month_pos(idx)
    per = idx.to_period("M")
    wins = []
    months = sorted(set(per))
    for p in months:
        s = idx[per == p]
        if len(s) < 5:
            continue
        d4, d3, dl = s[-4], s[-3], s[-1]
        pos_l = idx.get_loc(dl)
        nxt = idx[pos_l + 1] if pos_l + 1 < len(idx) else None
        cc = c_off
        # dividends paid inside (d3..dl] are received by all variants (ex-date inside the hold)
        div_in = float(d.loc[d3:dl].sum()) if True else 0.0
        div_in_cc = float(d.loc[s[-3]:dl].sum())
        close_close = (cc[dl] + div_in_cc) / cc[d4] - 1
        # enter at the d3 open (d3 ex-date dividend is then NOT received: ex-date open is already ex)
        div_after_open = float(d.loc[d3:dl].sum()) - (float(d[d3]) if d[d3] > 0 else 0.0)
        open_close = (cc[dl] + div_after_open) / o[d3] - 1
        if nxt is not None:
            div_nxt = float(d[nxt])
            open_open = (o[nxt] + div_nxt + div_after_open) / o[d3] - 1
            close_open = (o[nxt] + div_nxt + div_in_cc) / cc[d4] - 1
        else:
            open_open = close_open = np.nan
        wins.append({"month": str(p), "close_close": close_close, "open_close": open_close,
                     "open_open": open_open, "close_open": close_open})
    W = pd.DataFrame(wins).set_index("month")
    W.to_csv(OUT / f"b_execution_windows_{tag}.csv")
    out["execution_window_mean_bp"] = {k: float(W[k].mean() * 1e4) for k in W.columns}
    out["execution_window_monthly_tstat"] = {k: float(W[k].mean() / W[k].std() * np.sqrt(W[k].notna().sum())) for k in W.columns}
    # overnight component alone (last close -> next open), which close->open adds
    res[tag] = out

(OUT / "b_lse.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
