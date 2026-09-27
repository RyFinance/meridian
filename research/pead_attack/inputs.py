"""Frozen inputs for the PEAD attack, rebuilt from the same pinned files the config-sweep replay used.

Everything here reuses the replay's own code (live_backtest/historical_providers.py,
live_backtest/run_historical_replay.py, bot/signal_pipeline.build_feature_row) with the same in-process
monkeypatches the replay harness installs -- nothing under bot/ or live_backtest/ is modified, and no
file outside reports/pead_attack/ is written. The production model is read with joblib.load directly
(never fit_or_load, whose cache-miss branch would write to bot/state/model/).

Outputs (reports/pead_attack/inputs/):
  events.parquet    every event the replay's watcher could surface in the window (row order = the
                    replay's own iteration order), with the production features, raw ensemble
                    probability and calibrated probability (NaN where build_feature_row returns None),
                    plus the same event re-scored with a point-in-time dollar-volume rank (diagnostic D1).
  closes_fill.parquet  last close <= date (historical_close_price semantics) on the replay calendar
  calendar.parquet  replay dates, circuit-breaker tier, T-bill rf, Mkt-RF and FF5+UMD factors
  manifest.json     sha256 of every source file used, window, Kelly payoff ratio

Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.inputs
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import bot.signal_pipeline as signal_pipeline_module
import live_backtest.historical_providers as hp
from bot.earnings_watcher import ReportedEarnings, load_validated_universe
from live_backtest.run_historical_replay import compute_replay_window, get_trading_dates
from research.options_signals.signals import french_daily

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "pead_attack" / "inputs"
RAW = ROOT / "data" / "raw"
FACTORS = ROOT / "reports" / "momentum_verification_20260919" / "factor_inputs.csv"
LOOKBACK_CALENDAR_DAYS = 3  # bot/run_cycle.EARNINGS_LOOKBACK_DAYS
PIT_DV_WINDOW = 63           # same window reports/run_pead_expanded_pipeline.py used for the static rank


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_model():
    return joblib.load(signal_pipeline_module.MODEL_PATH)


def install_scoring_patches() -> None:
    """The two data patches live_backtest.run_historical_replay.install_historical_monkeypatches applies
    to the scoring path (and nothing else -- no state/alert paths are touched because nothing here
    alerts or writes)."""
    signal_pipeline_module.fetch_ticker_earnings_live = lambda t: hp.historical_earnings_history_for_sue(
        t, _SCORING_AS_OF["date"])
    signal_pipeline_module._trailing_return = hp.historical_trailing_return


_SCORING_AS_OF: dict = {"date": None}


def window_events(start: pd.Timestamp, end: pd.Timestamp, universe: list[str]) -> pd.DataFrame:
    df = hp._signal_history().copy()
    df["row_order"] = np.arange(len(df))
    m = (df["date"] >= start - pd.Timedelta(days=LOOKBACK_CALENDAR_DAYS)) & (df["date"] <= end) & df["ticker"].isin(universe)
    return df.loc[m].reset_index(drop=True)


def pit_dollar_volume_rank(universe: list[str]) -> pd.DataFrame:
    """Point-in-time analogue of the static dollar_volume_rank: mean close*volume over the 63 sessions
    strictly before each date, ranked descending across the universe names with data (pandas default
    'average' ties, as in earnings/features.py and bot/signal_pipeline.py)."""
    dv = {}
    for t in universe:
        p = RAW / f"{t}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "close", "volume"])
        d["timestamp"] = pd.to_datetime(d["timestamp"]).dt.normalize()
        d = d.drop_duplicates("timestamp").set_index("timestamp").sort_index()
        dv[t] = d["close"] * d["volume"]
    panel = pd.DataFrame(dv).sort_index()
    mean = panel.rolling(PIT_DV_WINDOW, min_periods=20).mean().shift(1)
    return mean.rank(axis=1, ascending=False)


def score_events(ev: pd.DataFrame, pipeline, pit_rank: pd.DataFrame | None) -> pd.DataFrame:
    install_scoring_patches()
    feats, raw, cal, pit_raw, pit_cal = [], [], [], [], []
    for r in ev.itertuples(index=False):
        _SCORING_AS_OF["date"] = r.date
        event = ReportedEarnings(ticker=r.ticker, earnings_date=r.earnings_date_raw, eps_estimate=r.eps_estimate,
                                 eps_actual=r.eps_actual, surprise_pct=r.surprise_pct, days_since=0)
        row = signal_pipeline_module.build_feature_row(event)
        if row is None:
            feats.append(None); raw.append(np.nan); cal.append(np.nan); pit_raw.append(np.nan); pit_cal.append(np.nan)
            continue
        p = pipeline.ensemble.predict_proba(row)
        feats.append(row.iloc[0].to_dict())
        raw.append(float(p[0])); cal.append(float(pipeline.calibrator.transform(p)[0]))
        if pit_rank is not None:
            key = pd.Timestamp(r.earnings_date_raw).normalize()
            loc = pit_rank.index.searchsorted(key, side="right") - 1  # row at or before the announcement day
            rk = pit_rank.iloc[loc].get(r.ticker, np.nan) if loc >= 0 else np.nan
            if np.isfinite(rk):
                row2 = row.copy()
                row2["dollar_volume_rank"] = float(rk)
                p2 = pipeline.ensemble.predict_proba(row2)
                pit_raw.append(float(p2[0])); pit_cal.append(float(pipeline.calibrator.transform(p2)[0]))
            else:
                pit_raw.append(np.nan); pit_cal.append(np.nan)
    out = ev.copy()
    fdf = pd.DataFrame([f if f is not None else {} for f in feats], index=out.index)
    for c in fdf.columns:
        out[f"feat_{c}"] = fdf[c]
    out["raw_proba"] = raw
    out["calibrated_proba"] = cal
    out["pit_raw_proba"] = pit_raw
    out["pit_calibrated_proba"] = pit_cal
    out["sue"] = out.get("feat_signal")
    out["scorable"] = np.isfinite(out["calibrated_proba"])
    return out


def fill_closes(tickers: list[str], cal: pd.DatetimeIndex) -> pd.DataFrame:
    """historical_close_price semantics: the last cached close on or before each replay date."""
    cols = {}
    for t in tickers:
        panel = hp._load_price_panel(t)
        s = panel.set_index("timestamp")["close"]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        cols[t] = s.reindex(s.index.union(cal)).ffill().reindex(cal)
    return pd.DataFrame(cols, index=cal)


def factor_frame(cal: pd.DatetimeIndex) -> pd.DataFrame:
    ff = french_daily()
    rf = ff["rf"].reindex(cal.union(ff.index)).ffill().reindex(cal)  # exactly research/pead_audit/mtm_audit.py
    f = pd.read_csv(FACTORS, parse_dates=["date"]).set_index("date")
    f = f.rename(columns={"Mkt-RF": "ff_mkt_rf", "SMB": "smb", "HML": "hml", "RMW": "rmw", "CMA": "cma",
                          "RF": "ff_rf", "Mom": "umd"})
    out = pd.DataFrame({"rf": rf, "mkt_rf": ff["mkt_rf"].reindex(cal)}, index=cal)
    return out.join(f.reindex(cal))


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    start, end = compute_replay_window()
    dates = pd.DatetimeIndex(get_trading_dates(start, end))
    tiers = [hp.historical_breaker_tier(d)[0] for d in dates]
    universe = load_validated_universe()
    pipeline = load_model()
    if hasattr(pipeline.ensemble.members.get("random_forest"), "n_jobs"):
        pipeline.ensemble.members["random_forest"].n_jobs = 2  # prediction is n_jobs-invariant; be gentle on CPU
    ev = window_events(start, end, universe)
    pit = pit_dollar_volume_rank(universe)
    scored = score_events(ev, pipeline, pit)
    scored.to_parquet(OUT / "events.parquet", index=False)
    closes = fill_closes(sorted(set(scored["ticker"])), dates)
    closes.to_parquet(OUT / "closes_fill.parquet")
    calf = factor_frame(dates)
    calf["tier"] = tiers
    calf.to_parquet(OUT / "calendar.parquet")
    sources = ["data/pead_signal_expanded.parquet", "data/earnings_sue_expanded.parquet",
               "data/pead_labeled_features_expanded.parquet", "reports/universe_ranking.csv",
               "reports/circuit_breaker_daily_production.csv", "data/expanded_universe_all_tickers.txt",
               "bot/state/model/pead_model_expanded.joblib",
               "reports/momentum_verification_20260919/factor_inputs.csv"]
    manifest = {
        "window": [str(start.date()), str(end.date())], "n_dates": len(dates), "n_events": int(len(scored)),
        "n_scorable": int(scored["scorable"].sum()), "payoff_b": float(pipeline.payoff.b),
        "calibrator": pipeline.calibrator.method, "ensemble_weights": pipeline.ensemble.weights,
        "source_sha256": {s: sha256(ROOT / s) for s in sources},
        "raw_price_sha256": {t: sha256(RAW / f"{t}.parquet") for t in sorted(set(scored["ticker"]))},
        "output_sha256": {p.name: sha256(p) for p in sorted(OUT.glob("*.parquet"))},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == "__main__":
    m = main()
    print({k: v for k, v in m.items() if k not in ("raw_price_sha256", "source_sha256", "output_sha256")})
