"""Leakage audit of the production PEAD ML filter (PLAN.md section 8, L1-L6). Descriptive numbers only.

Nothing under bot/ or live_backtest/ is written: the refit check (L3) re-runs fit_or_load's body in memory
(never fit_or_load itself, whose cache-miss branch writes bot/state/model/).

Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.leakage   (writes reports/pead_attack/leakage.json)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from research.pead_attack.common import OUT, ROOT, Inputs
from research.pead_attack.engine import simulate

RAW = ROOT / "data" / "raw"
MEMBERSHIP = ROOT / "reports" / "momentum_verification_20260919" / "reconstructed_membership.parquet"


def l1_static_rank(inp: Inputs, real_trades: pd.DataFrame) -> dict:
    out = {}
    rank_train = pd.read_csv(ROOT / "reports/expanded_universe_liquidity_ranking.csv")
    rank_serve = pd.read_csv(ROOT / "reports/universe_ranking.csv")
    # vintage: the training rank is the mean close*volume of each ticker's last 63 cached sessions (2026)
    vint = {}
    for t in ["A", "AAPL", "NVDA", "PLTR", "SNDK"]:
        d = pd.read_parquet(RAW / f"{t}.parquet").sort_values("timestamp")
        d = d[d["timestamp"] <= "2026-08-17"].tail(63)
        vint[t] = {"rank_file_value": float(rank_train.set_index("ticker").loc[t, "avg_dollar_volume"]),
                   "mean_close_x_volume_last63_to_2026_08_17": float((d["close"] * d["volume"]).mean()),
                   "window": [str(d["timestamp"].min().date()), str(d["timestamp"].max().date())]}
    out["training_rank_vintage_check"] = vint
    feats = pd.read_parquet(ROOT / "data/pead_labeled_features_expanded.parquet")
    rk = rank_train.assign(r=rank_train["avg_dollar_volume"].rank(ascending=False)).set_index("ticker")["r"]
    out["training_feature_equals_2026_rank"] = bool(np.allclose(feats["dollar_volume_rank"], feats["ticker"].map(rk)))
    out["serving_vs_training_rank_spearman"] = float(spearmanr(
        rank_serve.set_index("ticker")["avg_dollar_volume"].reindex(rk.index), -rk).correlation)
    ev = inp.events[inp.stream.ev_scorable].copy()
    # realised raw return from the entry close (effective date) to 20 sessions later, for description only
    px = inp.closes_fill
    i = inp.dates.get_indexer(pd.to_datetime(ev["date"]))
    ok = (i >= 0) & (i + 20 < len(inp.dates))
    ev = ev[ok]
    i = i[ok]
    j = np.array([inp.col[t] for t in ev["ticker"]])
    ev["fwd20"] = px.to_numpy()[i + 20, j] / px.to_numpy()[i, j] - 1
    ev["fwd20_signed"] = np.sign(ev["sue"]) * ev["fwd20"]
    rs = ev["feat_dollar_volume_rank"]
    out["window_scorable_events"] = int(len(ev))
    out["spearman_static_rank_vs_calibrated_proba"] = float(spearmanr(rs, ev["calibrated_proba"]).correlation)
    out["spearman_static_rank_vs_fwd20_raw"] = float(spearmanr(rs, ev["fwd20"]).correlation)
    out["spearman_static_rank_vs_fwd20_signed"] = float(spearmanr(rs, ev["fwd20_signed"]).correlation)
    pit_rank = _pit_rank_at(ev)
    out["spearman_static_vs_pit_rank"] = float(spearmanr(rs, pit_rank, nan_policy="omit").correlation)
    improve = pit_rank - rs  # > 0: the name's 2026 rank is better than its rank at the event (it grew)
    out["spearman_rank_improvement_vs_fwd20_raw"] = float(spearmanr(improve, ev["fwd20"], nan_policy="omit").correlation)
    q = pd.qcut(improve.rank(method="first"), 5, labels=False)
    out["fwd20_raw_by_rank_improvement_quintile_bps"] = (ev.groupby(q)["fwd20"].mean() * 1e4).round(1).to_dict()
    b = inp.b
    kelly_pass = lambda p: (p - (1 - p) / b) > 0
    pit = ev["pit_calibrated_proba"]
    out["pit_rescore"] = {"mean_abs_proba_change": float((pit - ev["calibrated_proba"]).abs().mean()),
                          "kelly_pass_share_static": float(kelly_pass(ev["calibrated_proba"]).mean()),
                          "kelly_pass_share_pit": float(kelly_pass(pit).mean()),
                          "kelly_pass_flip_share": float((kelly_pass(pit) != kelly_pass(ev["calibrated_proba"])).mean())}
    # pre-earnings return features: training (residual, window ENDS ON the effective date, so it includes the
    # reaction day) vs serving (raw, strictly before the announcement day)
    tr = feats.set_index(["date", "ticker"])
    key = list(zip(pd.to_datetime(ev["date"]), ev["ticker"]))
    t5 = tr["pre_earnings_return_5d"].reindex(key).to_numpy()
    out["pre_return_5d_train_vs_serve"] = {
        "n_matched": int(np.isfinite(t5).sum()),
        "pearson": float(pd.Series(t5).corr(pd.Series(ev["feat_pre_earnings_return_5d"].to_numpy()))),
        "train_feature_std": float(np.nanstd(t5)), "serve_feature_std": float(ev["feat_pre_earnings_return_5d"].std())}
    resid = pd.read_parquet(ROOT / "data/residual_returns_wide_expanded.parquet").sort_index()
    ii, jj = resid.index.get_indexer(feats["date"]), resid.columns.get_indexer(feats["ticker"])
    roll = resid.rolling(5).sum().to_numpy()
    out["training_5d_feature_includes_effective_day"] = bool(np.allclose(feats["pre_earnings_return_5d"], roll[ii, jj], equal_nan=True))
    # effective-date alignment and timestamps
    hrs = pd.to_datetime(inp.events["earnings_date_raw"]).dt.hour
    out["announcement_hour_counts_window"] = hrs.value_counts().sort_index().to_dict()
    tev = inp.events.iloc[real_trades["event"].to_numpy()]
    th = pd.to_datetime(tev["earnings_date_raw"]).dt.hour.to_numpy()
    sus = th < 5
    out["real_trades_with_announcement_before_05h"] = {
        "n": int(sus.sum()), "pnl": float(real_trades["realized_pnl"].to_numpy()[sus].sum()),
        "total_pnl": float(real_trades["realized_pnl"].sum())}
    ed = pd.to_datetime(inp.events["earnings_date_raw"])
    out["entry_never_before_announcement_day"] = bool((pd.to_datetime(inp.events["date"]) >= ed.dt.normalize()).all())
    return out


def _pit_rank_at(ev: pd.DataFrame) -> pd.Series:
    from research.pead_attack.inputs import pit_dollar_volume_rank
    from bot.earnings_watcher import load_validated_universe
    pr = pit_dollar_volume_rank(load_validated_universe())
    vals = []
    for t, d in zip(ev["ticker"], pd.to_datetime(ev["earnings_date_raw"]).dt.normalize()):
        loc = pr.index.searchsorted(d, side="right") - 1
        vals.append(pr.iloc[loc].get(t, np.nan) if loc >= 0 else np.nan)
    return pd.Series(vals, index=ev.index)


def l2_l3_partitions() -> dict:
    from ml.validation import split_time_disjoint_panel
    df = pd.read_parquet(ROOT / "data/pead_labeled_features_expanded.parquet")
    parts, partitions = split_time_disjoint_panel(df, holding_period=20, min_rows_per_partition=100)
    cal = pd.read_parquet(ROOT / "data/residual_returns_wide_expanded.parquet", columns=["AAPL"]).index.sort_values()
    out = {"partitions": {p.name: {"start": p.start, "end": p.end, "n_rows": p.n_rows} for p in partitions}}
    for name in ["train", "validation"]:
        last = pd.Timestamp(parts[name]["date"].max())
        k = cal.get_loc(last)
        out[f"{name}_last_label_end"] = str(cal[k + 20].date())
    nxt = {"train": "validation", "validation": "holdout_a"}
    out["label_overlap"] = {n: bool(pd.Timestamp(out[f"{n}_last_label_end"]) >= pd.Timestamp(out["partitions"][m]["start"]))
                            for n, m in nxt.items()}
    return out


def l3_refit_matches_cache(inp: Inputs) -> dict:
    """Re-run bot.signal_pipeline.fit_or_load's body in memory and compare with the cached model on the window
    events. Identical scores prove the cached model saw only train (fit, payoff) and validation (weights, calibrator)."""
    import ml.ensemble as ens
    from earnings.features import PEAD_FEATURE_COLUMNS
    from ml.calibration import select_and_fit_calibrator
    from ml.validation import split_time_disjoint_panel
    from risk.kelly import estimate_payoff_ratio
    orig = ens.build_ensemble_members

    def gentle():
        m = orig()
        m["random_forest"].set_params(n_jobs=2)
        return m
    ens.build_ensemble_members = gentle
    try:
        df = pd.read_parquet(ROOT / "data/pead_labeled_features_expanded.parquet")
        parts, _ = split_time_disjoint_panel(df, holding_period=20, min_rows_per_partition=100)
        ensemble = ens.fit_weighted_ensemble(parts, PEAD_FEATURE_COLUMNS, "label_cost_adjusted")
        calibrator = select_and_fit_calibrator(ensemble, parts["validation"], "label_cost_adjusted")
        payoff = estimate_payoff_ratio(parts["train"], "label_cost_adjusted")
    finally:
        ens.build_ensemble_members = orig
    ev = inp.events[inp.stream.ev_scorable]
    X = ev[[f"feat_{c}" for c in PEAD_FEATURE_COLUMNS]].copy()
    X.columns = PEAD_FEATURE_COLUMNS
    refit = calibrator.transform(ensemble.predict_proba(X))
    cached = ev["calibrated_proba"].to_numpy()
    return {"refit_payoff_b": float(payoff.b), "cached_payoff_b": inp.b,
            "refit_weights": ensemble.weights, "calibrator_method": calibrator.method,
            "max_abs_diff_calibrated_proba": float(np.max(np.abs(refit - cached))),
            "share_identical_to_1e-9": float(np.mean(np.abs(refit - cached) < 1e-9)),
            "validation_dates": [str(parts["validation"]["date"].min().date()), str(parts["validation"]["date"].max().date())]}


def l4_survivorship(inp: Inputs, real_trades: pd.DataFrame) -> dict:
    mem = pd.read_parquet(MEMBERSHIP)
    mem.index = pd.to_datetime(mem.index)
    from bot.earnings_watcher import load_validated_universe
    uni = set(load_validated_universe())
    w = mem.loc[inp.dates[0]:inp.dates[-1]]
    ever = set(w.columns[w.any()])
    out = {"window_index_members_ever": len(ever), "members_missing_from_universe": len(ever - uni),
           "missing_examples": sorted(ever - uni)[:25], "membership_last_date": str(mem.index.max().date())}
    m = mem.reindex(inp.dates, method="ffill")
    tr = real_trades.copy()
    tr["member_on_entry"] = [bool(m.iloc[i].get(t, False)) for i, t in zip(tr["entry_i"], tr["ticker"])]
    nm = tr[~tr["member_on_entry"]]
    out["real_trades_not_index_member_on_entry"] = {
        "n": int(len(nm)), "share": float(len(nm) / len(tr)), "pnl": float(nm["realized_pnl"].sum()),
        "total_pnl": float(tr["realized_pnl"].sum()), "tickers": sorted(nm["ticker"].unique())[:40]}
    first = {}
    for t in sorted(set(inp.events["ticker"])):
        d = pd.read_parquet(RAW / f"{t}.parquet", columns=["timestamp"])
        first[t] = pd.Timestamp(d["timestamp"].min())
    out["universe_names_with_prices_starting_after_2015_03"] = int(sum(v > pd.Timestamp("2015-03-31") for v in first.values()))
    return out


def l6_replay_window(inp: Inputs) -> dict:
    ev = inp.events
    uns = ev[~ev["scorable"]]
    from live_backtest.historical_providers import _load_price_panel

    def enough(t, as_of, days):
        p = _load_price_panel(t)
        h = p[(p["timestamp"] >= as_of - pd.Timedelta(days=days)) & (p["timestamp"] < as_of)]
        return len(h) > 20
    reason_price = [not enough(t, pd.Timestamp(d).normalize(), 30) for t, d in zip(uns["ticker"], uns["earnings_date_raw"])]
    ok45 = [enough(t, pd.Timestamp(d).normalize(), 45) for t, d in zip(uns["ticker"], uns["earnings_date_raw"])]
    return {"visible_events": int(len(ev)), "unscorable": int(len(uns)),
            "unscorable_due_to_30_calendar_day_price_window": int(np.sum(reason_price)),
            "of_which_scorable_with_live_45_day_window": int(np.sum(np.array(reason_price) & np.array(ok45))),
            "unscorable_by_month": uns["date"].dt.month.value_counts().sort_index().to_dict()}


def score_drivers(inp: Inputs) -> dict:
    """Post-hoc, descriptive (added after the registered results): what the served calibrated probability loads on.
    Serving features are RAW trailing returns (bot/signal_pipeline.py:109-124), so they carry the market's move."""
    from research.options_signals.signals import french_daily
    s = inp.events[inp.stream.ev_scorable].copy()
    ff = french_daily()
    m20 = (1 + ff["mkt_rf"] + ff["rf"]).rolling(20).apply(np.prod, raw=True).shift(1) - 1
    s["mkt20_before"] = m20.reindex(pd.to_datetime(s["earnings_date_raw"]).dt.normalize(), method="ffill").to_numpy()
    sp = lambda a, b: float(spearmanr(s[a], s[b]).correlation)
    g = s.groupby("date").agg(p=("calibrated_proba", "mean"), m=("mkt20_before", "first"), n=("ticker", "size"))
    g = g[g["n"] >= 3]
    return {"spearman_proba_vs_own_raw_20d": sp("calibrated_proba", "feat_pre_earnings_return_20d"),
            "spearman_proba_vs_own_raw_5d": sp("calibrated_proba", "feat_pre_earnings_return_5d"),
            "spearman_proba_vs_abs_sue": sp("calibrated_proba", "feat_abs_sue"),
            "spearman_proba_vs_sue": sp("calibrated_proba", "feat_signal"),
            "spearman_proba_vs_market_20d_before": sp("calibrated_proba", "mkt20_before"),
            "date_level_spearman_mean_proba_vs_market_20d": float(spearmanr(g["p"], g["m"]).correlation),
            "n_dates_with_3plus_events": int(len(g)),
            "between_date_share_of_proba_variance": float(s.groupby("date")["calibrated_proba"].transform("mean").var()
                                                          / s["calibrated_proba"].var())}


def main() -> dict:
    inp = Inputs()
    real = simulate(inp.stream, inp.p_real, inp.size_real, inp.sign_prod)["trades"]
    out = {"L1_features": l1_static_rank(inp, real), "L2_L3_partitions": l2_l3_partitions(),
           "L3_refit": l3_refit_matches_cache(inp), "L4_survivorship": l4_survivorship(inp, real),
           "L6_replay_fidelity": l6_replay_window(inp),
           "posthoc_score_drivers": score_drivers(inp)}
    (OUT / "leakage.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
