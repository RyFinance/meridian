#!/usr/bin/env python
"""
Blind re-implementation of the ZB overnight -> ITB first-hour backtest, written only from the spec.

Run:  cd /Users/rytty/CCP/quant_v7 && .venv/bin/python research/zb_itb/verify/blind/backtest.py

Rule (one trade per day D that has an ITB 09:30 bar):
  prev = previous date that has an ITB 09:30 bar
  P0   = Close of the ZB 60m bar that ENDS at 16:00 ET on prev
  P1   = Close of the ZB 60m bar that ENDS at 09:00 ET on D
  d    = sign(ln(P1/P0));  trade ITB from Open to Close of the 09:30-10:30 bar on D
  gross = d*ln(exit/entry);  net = gross - 0.0004

Bar-label convention (verified in label_check.py): timestamps mark bar START for both files, so
  "bar that ends at 16:00 ET"  == bar labelled 15:00 ET
  "bar that ends at 09:00 ET"  == bar labelled 08:00 ET
Everything is done on tz-aware America/New_York wall-clock times (no manual UTC offsets).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/New_York"
BASE = Path("/Users/rytty/CCP/quant_v7/research/zb_itb/verify")
ZB_PATH = BASE / "yf_cache" / "ZB_F_60m.parquet"
ITB_PATH = BASE / "yf_cache" / "ITB_60m.parquet"
OUT = BASE / "blind"
COST = 0.0004  # 2 bp per side, round trip = 4 bp, in log-return units

SPLIT_A_END = pd.Timestamp("2026-08-10")
SPLIT_B_START = pd.Timestamp("2026-08-11")
SPLIT_B_END = pd.Timestamp("2026-10-16")


# --------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------
def load():
    zb = pd.read_parquet(ZB_PATH).sort_index()
    itb = pd.read_parquet(ITB_PATH).sort_index()
    for name, df in (("ZB", zb), ("ITB", itb)):
        if df.index.tz is None:
            raise SystemExit(f"{name}: index is tz-naive, cannot proceed")
        df.index = df.index.tz_convert(TZ)
        assert df.index.is_unique, f"{name}: duplicated timestamps"
        assert df.index.is_monotonic_increasing
    return zb, itb


# --------------------------------------------------------------------------------------
# signal construction
# --------------------------------------------------------------------------------------
def build_table(zb, itb, label_is_start=True, p0_end_hhmm="16:00", p1_end_hhmm="09:00"):
    """One row per ITB trading day D (has a 09:30 bar), with P0/P1 (NaN if the exact bar is missing)."""
    # ZB: key every bar by the wall-clock time at which it ENDS
    if label_is_start:
        end = zb.index + pd.Timedelta(hours=1)  # absolute-time addition on tz-aware index
    else:
        end = zb.index
    close_by_end = pd.Series(zb["Close"].to_numpy(dtype=float), index=end)
    vol_by_end = pd.Series(zb["Volume"].to_numpy(dtype=float), index=end)
    assert close_by_end.index.is_unique

    # ITB 09:30 bar of each day
    m = (itb.index.hour == 9) & (itb.index.minute == 30)
    b = itb.loc[m, ["Open", "Close", "Volume"]].copy()
    b.index = pd.DatetimeIndex(b.index.strftime("%Y-%m-%d"))  # naive date of the bar (ET)
    assert b.index.is_unique
    days = list(b.index)

    rows = []
    for i, D in enumerate(days):
        prev = days[i - 1] if i > 0 else pd.NaT
        p0 = p1 = np.nan
        v0 = v1 = np.nan
        if prev is not pd.NaT:
            t0 = pd.Timestamp(f"{prev:%Y-%m-%d} {p0_end_hhmm}", tz=TZ)
            t1 = pd.Timestamp(f"{D:%Y-%m-%d} {p1_end_hhmm}", tz=TZ)
            if t0 in close_by_end.index:
                p0, v0 = close_by_end[t0], vol_by_end[t0]
            if t1 in close_by_end.index:
                p1, v1 = close_by_end[t1], vol_by_end[t1]
        rows.append(
            dict(
                date=D,
                prev=prev,
                P0=p0,
                P1=p1,
                P0_vol=v0,
                P1_vol=v1,
                entry=float(b.loc[D, "Open"]),
                exit=float(b.loc[D, "Close"]),
            )
        )
    t = pd.DataFrame(rows)
    return t


def add_returns(t):
    t = t.copy()
    ok = t["P0"].notna() & t["P1"].notna()
    lr = np.log(t["P1"] / t["P0"])
    d = np.sign(lr)
    t["d"] = np.where(ok, d, np.nan)
    gross = t["d"] * np.log(t["exit"] / t["entry"])
    t["gross"] = gross
    t["net"] = np.where(t["d"].notna() & (t["d"] != 0), gross - COST, np.where(t["d"] == 0, 0.0, np.nan))
    return t


def eval_rows(t):
    """Rows from the first day where all inputs exist."""
    ok = t["P0"].notna() & t["P1"].notna()
    first = t.index[ok][0]
    return t.loc[first:].copy()


# --------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------
def max_drawdown(net_series, include_initial=True):
    eq = np.exp(np.cumsum(np.asarray(net_series, dtype=float)))
    if include_initial:
        eq = np.concatenate([[1.0], eq])
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1.0).min())


def stats_block(sub, mode, span_days):
    """
    sub: eval rows (all days D in the window, incl. no-signal days) with d/gross/net columns.
    mode: 'ls' (long/short, trade whenever d != 0) or 'lo' (long only: only d == +1).
    Per-trade stats are over the days that actually trade.  'daily' stats put 0 on every other day.
    """
    sub = sub.copy()
    no_sig = int((sub["d"].isna()).sum())
    flat = int((sub["d"] == 0).sum())
    if mode == "ls":
        trade = sub["d"].isin([-1.0, 1.0])
    else:
        trade = sub["d"] == 1.0
    gross = sub.loc[trade, "gross"].to_numpy()
    net = sub.loc[trade, "net"].to_numpy()
    n = len(net)
    out = {}
    out["n_trades"] = n
    out["n_days_in_window"] = len(sub)
    out["no_signal_days"] = no_sig
    out["flat_d0_days"] = flat
    out["n_short"] = int((sub["d"] == -1.0).sum()) if mode == "ls" else 0
    out["n_long"] = int((sub["d"] == 1.0).sum())
    out["mean_gross_bp"] = gross.mean() * 1e4
    out["mean_net_bp"] = net.mean() * 1e4
    sd = net.std(ddof=1)
    out["sd_net_bp"] = sd * 1e4
    out["t_net"] = net.mean() / sd * np.sqrt(n)
    out["win_rate_net"] = float((net > 0).mean())
    # compounded equity, annualised over calendar days / 365.25
    total_log = float(np.sum(net))
    out["total_net_log"] = total_log
    out["end_equity"] = float(np.exp(total_log))
    years = span_days / 365.25
    out["years"] = years
    out["ann_ret"] = float(np.exp(total_log) ** (1.0 / years) - 1.0)
    out["max_dd"] = max_drawdown(net, include_initial=True)
    out["max_dd_noinit"] = max_drawdown(net, include_initial=False)
    # Sharpe on per-trade series (literal) and on zero-filled daily series
    out["sharpe_trade_series"] = net.mean() / sd * np.sqrt(252)
    daily = np.where(trade, sub["net"].fillna(0.0), 0.0)
    out["sharpe_daily_zero_filled"] = daily.mean() / daily.std(ddof=1) * np.sqrt(252)
    out["mean_net_bp_daily_zero_filled"] = daily.mean() * 1e4
    gd = np.where(trade, sub["gross"].fillna(0.0), 0.0)
    out["mean_gross_bp_daily_zero_filled"] = gd.mean() * 1e4
    out["t_net_daily_zero_filled"] = daily.mean() / daily.std(ddof=1) * np.sqrt(len(daily))
    out["win_rate_net_over_all_days"] = float((daily > 0).mean())
    return out


def span_days_of(sub):
    return (sub["date"].iloc[-1] - sub["date"].iloc[0]).days


def split_windows(e):
    A = e[e["date"] <= SPLIT_A_END]
    B = e[(e["date"] >= SPLIT_B_START) & (e["date"] <= SPLIT_B_END)]
    return {"FULL": e, "<=2026-08-10": A, "2026-08-11..2026-10-16": B}


# --------------------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------------------
def fmt_stats_table(title, res):
    keys = [
        ("n_trades", "n trades", "{:d}"),
        ("n_long", "  of which long (d=+1)", "{:d}"),
        ("n_short", "  of which short (d=-1)", "{:d}"),
        ("no_signal_days", "no-signal days (missing P0/P1 bar)", "{:d}"),
        ("flat_d0_days", "flat days (P1==P0, d=0, no trade)", "{:d}"),
        ("n_days_in_window", "ITB trading days D in window", "{:d}"),
        ("mean_gross_bp", "mean gross (bp/trade)", "{:.3f}"),
        ("mean_net_bp", "mean net (bp/trade)", "{:.3f}"),
        ("sd_net_bp", "sd net (bp/trade, ddof=1)", "{:.2f}"),
        ("t_net", "t-stat net (mean/sd*sqrt(n))", "{:.3f}"),
        ("win_rate_net", "win rate net (net>0, per trade)", "{:.4f}"),
        ("end_equity", "end equity exp(sum net), start=1", "{:.4f}"),
        ("years", "years (calendar days/365.25)", "{:.4f}"),
        ("ann_ret", "annualised compounded return (net)", "{:.4%}"),
        ("max_dd", "max drawdown of compounded net equity", "{:.4%}"),
        ("sharpe_trade_series", "Sharpe net, ann. sqrt(252), per-trade series", "{:.3f}"),
        ("sharpe_daily_zero_filled", "Sharpe net, ann. sqrt(252), daily series (0 on non-trade days)", "{:.3f}"),
        ("mean_net_bp_daily_zero_filled", "mean net (bp/day, zero-filled)", "{:.3f}"),
        ("mean_gross_bp_daily_zero_filled", "mean gross (bp/day, zero-filled)", "{:.3f}"),
        ("t_net_daily_zero_filled", "t-stat net on zero-filled daily series", "{:.3f}"),
    ]
    names = list(res.keys())
    lines = [f"### {title}", "", "| metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k, label, f in keys:
        cells = []
        for nme in names:
            v = res[nme][k]
            cells.append(f.format(int(v)) if f == "{:d}" else f.format(v))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    zb, itb = load()

    # ---------------- primary run: labels are bar START ----------------
    t_all = add_returns(build_table(zb, itb, label_is_start=True))
    e = eval_rows(t_all)
    first_valid = e["date"].iloc[0]
    last_day = e["date"].iloc[-1]
    pre_days = t_all[t_all["date"] < first_valid]
    n_pre = len(pre_days)
    n_pre_prezb = int((pre_days["date"] < zb.index[0].tz_localize(None).normalize()).sum())

    # trades file: rows where we actually trade
    trades = e[e["d"].isin([-1.0, 1.0])][["date", "P0", "P1", "d", "entry", "exit", "gross", "net"]].copy()
    trades["date"] = trades["date"].dt.strftime("%Y-%m-%d")
    trades["d"] = trades["d"].astype(int)
    trades.to_csv(OUT / "trades.csv", index=False, float_format="%.10g")

    # no-signal days file
    ns = e[e["d"].isna()].copy()
    def reason(r):
        parts = []
        if np.isnan(r["P0"]):
            parts.append("P0 bar (ZB ending 16:00 ET on prev=%s) missing" % r["prev"].strftime("%Y-%m-%d"))
        if np.isnan(r["P1"]):
            parts.append("P1 bar (ZB ending 09:00 ET on D) missing")
        return "; ".join(parts)
    ns["reason"] = ns.apply(reason, axis=1)
    ns["date"] = ns["date"].dt.strftime("%Y-%m-%d")
    ns["prev"] = ns["prev"].dt.strftime("%Y-%m-%d")
    ns[["date", "prev", "reason"]].to_csv(OUT / "no_signal_days.csv", index=False)
    flat_days = e[e["d"] == 0.0]

    # ---------------- stats ----------------
    wins = split_windows(e)
    res_ls, res_lo = {}, {}
    for k, sub in wins.items():
        sd_days = span_days_of(sub)
        res_ls[k] = stats_block(sub, "ls", sd_days)
        res_lo[k] = stats_block(sub, "lo", sd_days)
    # alt annualisation (+1 day) for reference
    alt_ann = {}
    for k, sub in wins.items():
        yrs = (span_days_of(sub) + 1) / 365.25
        alt_ann[k] = (res_ls[k]["end_equity"] ** (1 / yrs) - 1, res_lo[k]["end_equity"] ** (1 / yrs) - 1)

    # sensitivity: if labels were END (P0=bar labelled 16:00, P1=bar labelled 09:00)
    t_alt = add_returns(build_table(zb, itb, label_is_start=False))
    e_alt = eval_rows(t_alt)
    alt_res = stats_block(e_alt, "ls", span_days_of(e_alt))

    # sensitivity: prev = previous NYSE day even if its ITB 09:30 bar is absent (only 2026-02-02 differs)
    # (computed explicitly below)
    # ---- odd-case: 2026-02-03
    odd = t_all[t_all["date"] == pd.Timestamp("2026-02-03")]

    # long-only trade table stats are in res_lo; also store per-year/half summaries
    e2 = e.copy()
    e2["year"] = e2["date"].dt.year
    yr = (
        e2[e2["d"].isin([-1.0, 1.0])]
        .groupby("year")
        .agg(n=("net", "size"), mean_gross_bp=("gross", lambda x: x.mean() * 1e4), mean_net_bp=("net", lambda x: x.mean() * 1e4))
    )

    # zero-volume P0/P1 bars among trades
    tr_rows = e[e["d"].isin([-1.0, 1.0])]
    zero_p0 = int((tr_rows["P0_vol"] == 0).sum())
    zero_p1 = int((tr_rows["P1_vol"] == 0).sum())
    zero_p0_dates = tr_rows.loc[tr_rows["P0_vol"] == 0, "date"].dt.strftime("%Y-%m-%d").tolist()
    zero_p1_dates = tr_rows.loc[tr_rows["P1_vol"] == 0, "date"].dt.strftime("%Y-%m-%d").tolist()

    # ---------------- write RESULTS.md ----------------
    L = []
    L.append("# ZB overnight -> ITB first-hour: blind re-implementation\n")
    L.append("Inputs: `ZB_F_60m.parquet` and `ITB_60m.parquet` only. Script: `backtest.py` (labels verified by `label_check.py`).\n")
    L.append("## Conventions used\n")
    L.append("- Both parquet indexes are tz-aware `America/New_York` (checked; `tz_convert` is a no-op). All time matching is wall-clock ET via tz-aware Timestamps, so DST is handled by pandas, not by hand.")
    L.append("- **Bar timestamps mark the START of each bar** (both ZB and ITB). Evidence in the 'Label convention' section. So the 'ZB bar that ENDS at 16:00 ET' is the bar labelled 15:00, and the 'bar that ENDS at 09:00 ET' is the bar labelled 08:00.")
    L.append("- prev = previous date (in the sorted list of dates that have an ITB 09:30 bar). D ranges over all dates that have an ITB 09:30 bar from the first D where P0, P1, entry and exit all exist (%s). ITB days before that (%d, all before the ZB file starts) are not counted." % (first_valid.strftime("%Y-%m-%d"), n_pre))
    L.append("- d = sign(ln(P1/P0)); d=0 only if P1==P0 exactly (no trade, no cost). net = gross - 0.0004 on each trade. sd uses ddof=1.")
    L.append("- Annualised return = end_equity^(1/years)-1 with end_equity=exp(sum(net)) and years = (last date - first date of the window in calendar days)/365.25 (window = first/last ITB trading day D in the window, whether or not that day trades). Max drawdown includes the starting equity of 1.0 as the first peak.")
    L.append("- Sharpe = mean/sd*sqrt(252). Primary Sharpe uses the per-trade net series (one trade per day, no-signal days omitted). The zero-filled daily-series Sharpe is shown alongside. For long-only, non-long days earn 0 in the daily series.")
    L.append("")
    L.append("## Long/short strategy (d = +1 long ITB, d = -1 short ITB)\n")
    L.append(fmt_stats_table("Long/short", res_ls))
    L.append("Alternative annualisation (years = (last-first+1 days)/365.25): " + "; ".join(f"{k}: {v[0]:.4%}" for k, v in alt_ann.items()))
    L.append("")
    L.append("max drawdown excluding the initial 1.0 as a peak: " + "; ".join(f"{k}: {res_ls[k]['max_dd_noinit']:.4%}" for k in res_ls))
    L.append("")
    L.append("## Long-only version (only d = +1 trades; every other day earns 0)\n")
    L.append(fmt_stats_table("Long-only", res_lo))
    L.append("Alternative annualisation (years = (last-first+1 days)/365.25): " + "; ".join(f"{k}: {v[1]:.4%}" for k, v in alt_ann.items()))
    L.append("")
    L.append("max drawdown excluding the initial 1.0 as a peak: " + "; ".join(f"{k}: {res_lo[k]['max_dd_noinit']:.4%}" for k in res_lo))
    L.append("")
    L.append("## Calendar-year breakdown (long/short trades)\n")
    L.append(yr.round(3).to_markdown() if hasattr(yr, "to_markdown") else yr.round(3).to_string())
    L.append("")
    L.append("## No-signal days (no trade because a required ZB bar does not exist exactly)\n")
    L.append(f"Total from {first_valid:%Y-%m-%d} on: {len(ns)} (list also in `no_signal_days.csv`).\n")
    L.append("| date D | prev | reason |")
    L.append("|---|---|---|")
    for _, r in ns.iterrows():
        L.append(f"| {r['date']} | {r['prev']} | {r['reason']} |")
    L.append("")
    if len(flat_days):
        L.append(f"Flat days (P1==P0 exactly, d=0, no trade): {len(flat_days)} -> " + ", ".join(flat_days["date"].dt.strftime("%Y-%m-%d")))
    else:
        L.append("Flat days (P1==P0 exactly, d=0): none.")
    L.append("")
    L.append(f"Zero-volume bars used as P0: {zero_p0} {zero_p0_dates}; as P1: {zero_p1} {zero_p1_dates} (kept: the bar exists and has a price).")
    L.append("")
    L.append("## Sensitivity: if the labels were (wrongly) read as bar END")
    L.append(
        "P0 := bar labelled 16:00, P1 := bar labelled 09:00. Full sample: n=%d, mean gross %.3f bp, mean net %.3f bp, t=%.3f, win %.4f, ann %.2f%%. "
        "(Shown only so a mismatch against another implementation can be diagnosed; it is NOT the answer.)"
        % (alt_res["n_trades"], alt_res["mean_gross_bp"], alt_res["mean_net_bp"], alt_res["t_net"], alt_res["win_rate_net"], alt_res["ann_ret"] * 100)
    )
    L.append("")
    import label_check as lc
    c0, c1 = lc.selfcheck(zb, t_all)
    L.append("## Label convention evidence\n")
    L.append(lc.label_evidence(zb, itb))
    L.append("")
    L.append(f"Self-check: P0/P1 re-derived purely by label (15:00 / 08:00) match the end-time lookup for every day: P0 {c0}, P1 {c1}.")
    L.append("")
    L.append("## Data oddities\n")
    odd_md, _chk = lc.oddities(zb, itb, t_all, e)
    L.append(odd_md)
    L.append("")
    L.append(lc.dst_check(zb, e))
    L.append("")
    L.append("Note on 2026-02-03 and 2026-07-15: `prev` skips ITB-missing days (2026-02-02 has no 09:30 bar; 2026-07-13/14 absent), so P0 is taken on 2026-01-30 / 2026-07-10 where ZB has no 15:00 bar -> no trade. Reading `prev` as the prior NYSE day instead would add at most these two trades.")
    (OUT / "RESULTS.md").write_text("\n".join(L))
    print("\n".join(L))
    print("trades rows:", len(trades), "first", trades['date'].iloc[0], "last", trades['date'].iloc[-1])
    print("odd 2026-02-03 row:\n", odd.to_string())


if __name__ == "__main__":
    main()
