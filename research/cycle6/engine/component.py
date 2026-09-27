"""Component pipeline: snapshot panels -> signal -> weights -> gross / net / stress -> control -> active ->
inference, fidelity, guards' diagnostics. ``compute_component`` is pure given the loaded panels; the CLI wrapper
(``runner``) applies the preregistration guards first."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import controls, fidelity, inference, panel, portfolio, styles
from . import io as eio
from . import vol as evol

RANK_STYLES = {"xsmom", "value", "carry", "bab"}


# ------------------------------------------------------------------------------------------------ loading
def load_series_monthly(root, ref: dict, months=None) -> pd.Series:
    s = eio.read_series(root, ref)
    if ref.get("frequency", "monthly") == "daily":
        m = panel.monthly_returns(s.to_frame())[s.name]
    else:
        m = s.groupby(s.index.to_period("M")).last()
    return m if months is None else m.reindex(months)


def load_inputs(params: dict, snapshot_root, membership_path) -> dict:
    cands = eio.load_candidates(snapshot_root, membership_path)
    uni = eio.universe(cands, params["class"])
    if not uni:
        raise ValueError(f"no PASS instruments in class {params['class']}")
    inp = params["inputs"]
    daily = eio.read_wide(snapshot_root, inp["daily_excess"], uni).dropna(how="all")
    months = panel.month_range_of(daily)
    sig_in = {}
    lags = params.get("signal", {}).get("input_lag_months", {})
    for name, rel in (inp.get("signal_inputs") or {}).items():
        w = panel.to_monthly_panel(eio.read_wide(snapshot_root, rel, uni), months, uni)
        sig_in[name] = w.shift(int(lags.get(name, 0)))
    series = {}
    for name, ref in (inp.get("series") or {}).items():
        if ref.get("frequency") == "daily_raw":
            series[name] = eio.read_series(snapshot_root, ref)
        else:
            s = load_series_monthly(snapshot_root, ref, None)
            series[name] = s.shift(int(lags.get(name, 0)))
    return {"daily": daily, "universe": uni, "classes": eio.class_map(cands), "signal_inputs": sig_in,
            "series": series}


# ------------------------------------------------------------------------------------------------ signals
def build_signal(style: str, sp: dict, mret: pd.DataFrame, sig_in: dict, series: dict) -> pd.DataFrame:
    def s_(name):
        v = series[name]
        return v.reindex(mret.index) if isinstance(v.index, pd.PeriodIndex) else v
    if style == "xsmom":
        return styles.momentum_signal(mret, lookback_months=sp["lookback_months"], skip_months=sp["skip_months"])
    if style == "value":
        k = sp["kind"]
        if k == "reversal":
            lvl = sig_in[sp["level_input"]] if sp.get("level_input") else styles.level_from_returns(mret)
            return styles.value_reversal(lvl, window_lo_months=sp["window_lo_months"],
                                         window_hi_months=sp["window_hi_months"])
        if k == "fx_ppp":
            return styles.fx_ppp_value(sig_in[sp["spot"]], sig_in[sp["cpi"]], s_(sp["cpi_us"]),
                                       window_lo_months=sp["window_lo_months"], window_hi_months=sp["window_hi_months"],
                                       cpi_lag_months=sp["cpi_lag_months"])
        if k in ("yield_change", "real_yield"):
            return styles.bond_value(sig_in[sp["yield"]], kind=k, window_lo_months=sp.get("window_lo_months"),
                                     window_hi_months=sp.get("window_hi_months"),
                                     inflation=sig_in.get(sp.get("inflation")) if sp.get("inflation") else None)
        raise ValueError(f"unknown value kind {k}")
    if style == "carry":
        k = sp["kind"]
        if k == "given":
            return sig_in[sp["carry"]]
        if k == "fx":
            return styles.fx_carry(sig_in[sp["foreign_rate"]], s_(sp["us_rate"]))
        if k == "bond":
            return styles.bond_carry(sig_in[sp["yield"]], sig_in[sp["short_rate"]],
                                     sig_in[sp["rolldown"]] if sp.get("rolldown") else None)
        if k == "commodity":
            ma = sp["months_apart"]
            ma = sig_in[ma] if isinstance(ma, str) else float(ma)
            return styles.commodity_carry(sig_in[sp["f_near"]], sig_in[sp["f_far"]], ma)
        raise ValueError(f"unknown carry kind {k}")
    if style == "seas":
        return styles.seasonality_signal(mret, years=sp["years"], min_years=sp["min_years"])
    raise ValueError(f"no generic signal for style {style}")


# ------------------------------------------------------------------------------------------------ BSV
def bsv_builder(sp: dict, mret: pd.DataFrame, min_assets: int):
    """BSV 2021 App. A.II construction: rank weights z(rank - (N+1)/2) on markets with a sizing vol, each position
    divided by its simple rolling vol (optional floors), then the class book scaled to a target ex-ante vol from a
    trailing window. All numbers from the spec; past data only. The covariance cube does not depend on the
    signal, so it is computed once and shared with the placebo books."""
    svol = styles.rolling_vol_monthly(mret, window_months=sp["sizing_vol_window_months"],
                                      min_months=sp["sizing_vol_min_months"])
    method = sp["class_vol_method"]
    cube = (styles.rolling_cov_cube(mret, window_months=sp["class_vol_window_months"],
                                    min_months=sp["class_vol_min_months"]) if method == "ex_ante_cov" else None)

    def builder(sig):
        Wr, elig, n = styles.xs_rank_weights(sig, min_assets=min_assets, eligible=svol.notna())
        Ws = styles.vol_size(Wr, svol, floor_quantile=sp.get("sizing_vol_floor_quantile"),
                             floor_abs=sp.get("sizing_vol_floor_abs"))
        Wt, scale = styles.class_vol_target(Ws, mret, target_vol=sp["class_vol_target"],
                                            window_months=sp["class_vol_window_months"],
                                            min_months=sp["class_vol_min_months"], method=method, cov_cube=cube)
        return Wt, elig, n.where(scale.notna(), 0)
    return builder


# ------------------------------------------------------------------------------------------------ compute
def compute_component(params: dict, data: dict) -> dict:
    style = params["style"]
    daily = data["daily"]
    uni = list(daily.columns)
    mret = panel.monthly_returns(daily)
    rnet = panel.net_period_returns(daily)
    months = mret.index
    sp = params.get("signal", {})
    min_assets = int(params["universe"]["min_assets"])
    cp = params["costs"]
    bp = cp["bp_per_side"]
    cls = data.get("classes", {})
    cost_rate = pd.Series({m: bp[cls.get(m, params["class"])] / 1e4 for m in uni})
    drift = bool(cp.get("drift", True))
    stress_mult = float(cp["stress_multiplier"])

    vol_me = None
    vp = params.get("vol")
    need_vol = style == "tsmom" or params.get("weights", {}).get("rank_vol_scale")
    if need_vol:
        v = evol.ew_vol(daily, com_days=vp["com_days"], annualisation=vp["annualisation"], min_obs=vp["min_obs"],
                        lag_obs=vp.get("lag_obs", 0))
        vol_me = panel.month_end_sample(v, months)

    rank_vol = vol_me if params.get("weights", {}).get("rank_vol_scale") else None
    if style == "tsmom":
        W, elig, n = styles.tsmom_weights(mret, vol_me, lookback_months=sp["lookback_months"],
                                          target_vol=sp["target_vol"], min_assets=min_assets)
        builder = None
    elif style == "bab":
        bname = sp["benchmark"]
        if sp.get("beta_frequency", "daily") == "monthly":
            bench_m = mret.mean(axis=1) if bname == "ew_universe" else data["series"][bname].reindex(months)
            beta_me = styles.fp_betas_monthly(
                mret, bench_m, vol_window_months=sp["vol_window_months"], vol_min_months=sp["vol_min_months"],
                corr_window_months=sp["corr_window_months"], corr_min_months=sp["corr_min_months"],
                overlap_months=sp.get("overlap_months", 1), shrink_w=sp["shrink_w"],
                log_returns=sp.get("log_returns", True))
        else:
            bench = daily.mean(axis=1) if bname == "ew_universe" else data["series"][bname]
            if isinstance(bench.index, pd.PeriodIndex):
                raise ValueError("daily BAB benchmark must be a daily series (frequency 'daily_raw')")
            b_d = styles.fp_betas(daily, bench, vol_window_days=sp["vol_window_days"],
                                  vol_min_days=sp["vol_min_days"], corr_window_days=sp["corr_window_days"],
                                  corr_min_days=sp["corr_min_days"], overlap_days=sp["overlap_days"],
                                  shrink_w=sp["shrink_w"])
            beta_me = panel.month_end_sample(b_d, months)

        def builder(sig=None):
            return styles.bab_weights(beta_me, min_assets=min_assets, signal=sig)
        W, elig, n = builder()
    else:
        signal = build_signal(style, sp, mret, data["signal_inputs"], data["series"]).reindex(index=months,
                                                                                              columns=uni)

        if sp.get("construction", "rank") == "bsv":
            builder = bsv_builder(sp, mret, min_assets)
        else:
            def builder(sig):
                return styles.xs_rank_weights(sig, min_assets=min_assets, vol=rank_vol)
        W, elig, n = builder(signal)
    defined = n >= min_assets

    def evaluate(Wx, defx=defined):
        net = portfolio.net_implementable(Wx, rnet, cost_rate, defx, drift=drift)
        st = portfolio.net_implementable(Wx, rnet, cost_rate, defx, cost_multiplier=stress_mult, drift=drift)
        gr = portfolio.gross_shadow(Wx, mret, defx)
        return {"net": net["ret"], "stress": st["ret"], "gross": gr["ret"], "net_exposure": net["net_exposure"]}

    gross = portfolio.gross_shadow(W, mret, defined)
    net = portfolio.net_implementable(W, rnet, cost_rate, defined, drift=drift)
    stress = portfolio.net_implementable(W, rnet, cost_rate, defined, cost_multiplier=stress_mult, drift=drift)

    ctl = params["control"]
    if ctl["type"] == "always_long":
        if style != "tsmom":
            raise ValueError("always_long control is for time-series styles")
        Wc, _, nc = styles.tsmom_weights(mret, vol_me, lookback_months=sp["lookback_months"],
                                         target_vol=sp["target_vol"], min_assets=min_assets, force_long=True)
        c = evaluate(Wc, nc >= min_assets)
    elif ctl["type"] == "random_rank":
        if builder is None:
            raise ValueError("random_rank control needs a rank style")
        c = controls.random_rank_books(elig, lambda s: builder(s)[0], evaluate, n_books=ctl["n_books"],
                                       seed=ctl["seed"])
    elif ctl["type"] == "calendar_shuffle":
        sig_fn = lambda m: styles.seasonality_signal(m, years=sp["years"], min_years=sp["min_years"])  # noqa: E731
        c = controls.calendar_shuffle_books(mret, sig_fn, lambda s: builder(s)[0], evaluate,
                                            n_books=ctl["n_books"], seed=ctl["seed"])
    else:
        raise ValueError(f"unknown control {ctl['type']}")
    control = pd.DataFrame({"net": c["net"], "stress": c["stress"], "gross": c["gross"],
                            "net_exposure": c["net_exposure"]})

    cutoff = pd.Period(params["post_pub_cutoff"], "M")
    post_idx = net.index[net.index >= cutoff]
    if ctl["type"] == "always_long":
        ratio = controls.exposure_ratio(net["net_exposure"], control["net_exposure"])
        act_full, mbar_full = controls.matched_active(net["ret"], control["net"], ratio)
        act_post, mbar_post = controls.matched_active(net["ret"], control["net"], ratio, post_idx)
        st_post, _ = controls.matched_active(stress["ret"], control["stress"], ratio, post_idx)
        st_full, _ = controls.matched_active(stress["ret"], control["stress"], ratio)
    else:
        idx = net.index.intersection(control.index)
        act_full = (net["ret"] - control["net"]).reindex(idx)
        st_full = (stress["ret"] - control["stress"]).reindex(idx)
        act_post, st_post = act_full[act_full.index >= cutoff], st_full[st_full.index >= cutoff]
        mbar_full = mbar_post = None
    active = pd.DataFrame({"active_full_window": act_full, "active_post_window": act_post,
                           "stress_active_full_window": st_full, "stress_active_post_window": st_post})

    metrics = component_metrics(params, data, W, mret, rnet, gross, net, stress, control, active,
                                {"mbar_full": mbar_full, "mbar_post": mbar_post}, n)
    return {"W": W, "gross": gross, "net": net, "stress": stress, "control": control, "active": active,
            "metrics": metrics}


def component_metrics(params, data, W, mret, rnet, gross, net, stress, control, active, mbar, n_elig) -> dict:
    inf = params["inference"]
    crash = inf.get("crash")
    cutoff = pd.Period(params["post_pub_cutoff"], "M")
    pk = dict(B=inf["B"], seed=inf["seed"], crash=crash, bandwidth_fraction=inf["bandwidth_fraction"],
              overlap=inf.get("overlap", 1))
    ci_B = inf.get("ci_B", 499)

    def ci_for(x):
        x = x.dropna()
        lev = inference.ci_level(len(x), bool(crash), inf.get("ci_level", 0.90), inf.get("ci_level_crash_short", 0.95))
        return inference.calibrated_ci(x, level=lev, B=ci_B, seed=inf["seed"])

    net_post = net["ret"][net.index >= cutoff]
    apnl = portfolio.asset_pnl(W, rnet)
    out = {"id": params["id"], "style": params["style"], "class": params["class"],
           "universe": list(W.columns), "post_pub_cutoff": str(cutoff),
           "n_eligible_defined_months": {"min": int(n_elig[n_elig > 0].min()) if (n_elig > 0).any() else 0,
                                         "max": int(n_elig.max())},
           "defined_months": int(len(net))}
    out["gross"] = inference.basic_stats(gross["ret"])
    out["net_full"] = {**inference.basic_stats(net["ret"]), "ci": ci_for(net["ret"]),
                       "cost_ann": float(net["cost"].mean() * 12), "turnover_ann": float(net["turnover"].mean() * 12)}
    out["net_post"] = {**inference.basic_stats(net_post), "ci": ci_for(net_post)}
    out["stress_full"] = inference.basic_stats(stress["ret"])
    out["stress_post"] = inference.basic_stats(stress["ret"][stress.index >= cutoff])
    out["control_full"] = inference.basic_stats(control["net"])
    out["control_post"] = inference.basic_stats(control["net"][control.index >= cutoff])
    out["exposure_match"] = mbar
    a_post = active["active_post_window"].dropna()
    a_full = active["active_full_window"].dropna()
    out["active_post"] = {**inference.basic_stats(a_post), "p": inference.calibrated_p(a_post, **pk)}
    out["active_full"] = {**inference.basic_stats(a_full), "p": inference.calibrated_p(a_full, **pk)}
    sp_ = active["stress_active_post_window"].dropna()
    out["stress_active_post"] = {**inference.basic_stats(sp_), "p": inference.calibrated_p(sp_, **pk)}
    s_sh = out["stress_active_post"].get("sharpe_ann")
    out["stress_check_A4_3"] = {"p": out["stress_active_post"]["p"]["p"], "sharpe": s_sh,
                                "note": "A4 §3: validation requires p <= alpha/k on the stress series and Sharpe >= 0.30"}
    gs = out["gross"].get("sharpe_ann")
    nb = inference.basic_stats(net["ret_before_cost"]).get("sharpe_ann")
    out["execution_lag_G7"] = {"gross_shadow_sharpe": gs, "lagged_before_cost_sharpe": nb,
                               "retention": (nb / gs) if (gs and nb is not None and gs != 0) else None}
    out["years_full"] = inference.calendar_years(net["ret"])
    out["years_post"] = inference.calendar_years(net_post)
    out["drawdown"] = {"full": inference.max_drawdown(net["ret"].dropna()) if len(net) else None,
                       "post": inference.max_drawdown(net_post.dropna()) if len(net_post) else None}
    out["concentration_full"] = inference.concentration(net["ret"], apnl)
    out["concentration_post"] = inference.concentration(net_post, apnl)
    out["unpriced_held_positions"] = {"net": int(net["unpriced"].sum()), "gross": int(gross["unpriced"].sum())}
    # betas vs external equity / bond series
    refs = {k: data["series"][k] for k in params.get("betas", []) if k in data["series"]}
    if refs:
        out["betas"] = {"net_full": inference.betas(net["ret"], refs),
                        "net_post": inference.betas(net_post, refs),
                        "control_full": inference.betas(control["net"], refs),
                        "active_post": inference.betas(a_post, refs)}
    # fidelity
    fp = params["fidelity"]
    if fp["tier"] == "aqr_class":
        ref = data["series"].get(fp["reference"])
        if ref is None:
            out["fidelity"] = {"tier": "aqr_class", "pass": False, "reasons": ["unassessable: benchmark absent"]}
        else:
            out["fidelity"] = fidelity.aqr_tier(gross["ret"], ref, thresholds=fp.get("thresholds"),
                                                scale_convention=fp.get("scale_convention", "none"),
                                                target_vol_ann=fp.get("target_vol_ann"))
    elif fp["tier"] == "paper_stat":
        out["fidelity"] = fidelity.paper_stat_tier(gross["ret"], fp["paper"], thresholds=fp.get("thresholds"))
        if fp.get("secondary_reference") and fp["secondary_reference"] in data["series"]:
            sec = fidelity.aqr_tier(gross["ret"], data["series"][fp["secondary_reference"]],
                                    thresholds={"n_min": 120, "rho_min": fp.get("secondary_rho_flag", 0.35),
                                                "beta_lo": -np.inf, "beta_hi": np.inf, "te_ratio_max": np.inf})
            out["fidelity_secondary"] = {**sec, "binding": False}
    else:
        raise ValueError(f"unknown fidelity tier {fp['tier']}")
    k = inf.get("k")
    p = out["active_post"]["p"]["p"]
    out["positive"] = None if not k else bool(out["fidelity"]["pass"] and p is not None and p < 0.05 / k)
    out["positive_rule"] = "fidelity pass AND post-pub net active p < 0.05/k (FRAMEWORK §6)"
    return _clean(out)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
