"""Independent, development-only reconstruction of the frozen funding sort.

Reads only archive ZIP basenames ending 2020/2021/2022; never imports the
registered strategy implementation or its saved return/weight artifacts.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/c4/binance_um"
BASE_OUT = Path(__file__).resolve().parent
ASOF = float(sys.argv[1]) if len(sys.argv) > 1 else None
OUT = BASE_OUT / ("asof_original_result" if ASOF is not None else "current_dev_archive")
OUT.mkdir(exist_ok=True)
YEARS = (2020, 2021, 2022)
DAYS = pd.date_range("2020-01-01", "2022-12-31", freq="D", tz="UTC")
SYMS = sorted(p.name for p in (DATA / "klines_1d").iterdir()
              if p.is_dir() and p.name.endswith("USDT")
              and p.name[:-4] not in {"BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
              and any((f := p / f"{p.name}-1d-{y}-{m:02d}.zip").exists()
                      and (ASOF is None or f.stat().st_mtime <= ASOF)
                      for y in YEARS for m in range(1, 13)))


def files(kind: str, symbol: str):
    folder = DATA / kind / symbol
    suffix = "fundingRate" if kind == "fundingRate" else "1d"
    return [p for y in YEARS for m in range(1, 13)
            if (p := folder / f"{symbol}-{suffix}-{y}-{m:02d}.zip").exists()
            and (ASOF is None or p.stat().st_mtime <= ASOF)]


def csv_zip(path: Path, columns: list[str]):
    with zipfile.ZipFile(path) as archive:
        with archive.open(archive.namelist()[0]) as handle:
            data = pd.read_csv(handle, header=None, low_memory=False)
    if not str(data.iat[0, 0]).lstrip("-").isdigit():
        data = data.iloc[1:].reset_index(drop=True)
    data.columns = columns[:data.shape[1]]
    return data


def load_panels():
    n, p = len(DAYS), len(SYMS)
    opens = np.full((n, p), np.nan)
    closes = np.full((n, p), np.nan)
    volume = np.full((n, p), np.nan)
    signal = np.full((n, p), np.nan)
    settlement_count = np.zeros((n, p), dtype=np.int16)
    funding = np.zeros((n, p))
    first = np.full(p, np.datetime64("NaT"), dtype="datetime64[D]")
    records = []
    funding_hours = {h: 0 for h in range(24)}
    kline_non_midnight = 0
    stamp = DAYS.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    for j, symbol in enumerate(SYMS):
        kfiles = files("klines_1d", symbol)
        ffiles = files("fundingRate", symbol)
        kd = pd.concat([csv_zip(path, ["time", "open", "high", "low", "close", "qty", "close_time",
                                        "quote", "count", "taker_qty", "taker_quote", "ignore"])
                        for path in kfiles], ignore_index=True)
        kd["time"] = pd.to_numeric(kd["time"], errors="raise")
        kd = kd.drop_duplicates("time", keep="first").sort_values("time")
        kt = pd.to_datetime(kd["time"], unit="ms", utc=True)
        kline_non_midnight += int(((kt.dt.hour != 0) | (kt.dt.minute != 0) | (kt.dt.second != 0)).sum())
        first[j] = kt.iloc[0].to_datetime64().astype("datetime64[D]")
        ix = DAYS.get_indexer(kt)
        valid = ix >= 0
        for key, dest in (("open", opens), ("close", closes), ("quote", volume)):
            dest[ix[valid], j] = pd.to_numeric(kd[key], errors="raise").to_numpy()[valid]
        if ffiles:
            fd = pd.concat([csv_zip(path, ["time", "interval", "rate"]) for path in ffiles], ignore_index=True)
            fd["time"] = pd.to_numeric(fd["time"], errors="raise")
            fd["rate"] = pd.to_numeric(fd["rate"], errors="raise")
            fd = fd.drop_duplicates("time", keep="last").sort_values("time")
            ft = pd.to_datetime(fd["time"], unit="ms", utc=True).dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
            for hour, count in pd.to_datetime(ft).hour.value_counts().items():
                funding_hours[int(hour)] += int(count)
            rates = fd["rate"].to_numpy(float)
            cumulative = np.r_[0., rates.cumsum()]
            left = np.searchsorted(ft, stamp - np.timedelta64(7, "D"), side="left")
            right = np.searchsorted(ft, stamp, side="left")
            settlement_count[:, j] = right - left
            signal[:, j] = np.where(right - left >= 10, (cumulative[right] - cumulative[left]) / 7., np.nan)
            a = np.searchsorted(ft, stamp, side="right")
            b = np.searchsorted(ft, stamp + np.timedelta64(1, "D"), side="right")
            funding[:, j] = cumulative[b] - cumulative[a]
        records.append({"symbol": symbol, "kline_months": len(kfiles), "funding_months": len(ffiles),
                        "first_kline": str(first[j]), "last_kline": str(kt.iloc[-1].date()),
                        "kline_days": len(kd), "funding_events": 0 if not ffiles else len(fd)})
        if (j + 1) % 100 == 0:
            print(f"loaded {j + 1}/{p} symbols", flush=True)
    return opens, closes, volume, signal, settlement_count, funding, first, pd.DataFrame(records), {
        "funding_hour_utc_counts": {str(h): c for h, c in funding_hours.items() if c},
        "kline_non_midnight_count": kline_non_midnight}


def sharpe(x):
    return float(np.mean(x) / np.std(x, ddof=1) * np.sqrt(365))


def max_drawdown(x):
    nav = np.cumprod(1 + np.asarray(x))
    return float(np.min(nav / np.maximum.accumulate(nav) - 1))


def centred_p(x, block=21, draws=5000, seed=20260925):
    centered = np.asarray(x) - np.mean(x)
    n = len(centered)
    gen = np.random.default_rng(seed)
    starts = gen.integers(0, n, size=(draws, (n + block - 1) // block))
    ix = (starts[:, :, None] + np.arange(block)).reshape(draws, -1)[:, :n] % n
    simulated = centered[ix].mean(axis=1)
    return float((np.count_nonzero(simulated >= np.mean(x)) + 1) / (draws + 1)), simulated


def ols(y, x, names):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    valid = np.isfinite(y) & np.isfinite(x).all(axis=1)
    xx = np.column_stack([np.ones(valid.sum()), x[valid]])
    beta = np.linalg.lstsq(xx, y[valid], rcond=None)[0]
    resid = y[valid] - xx @ beta
    z = xx * resid[:, None]
    meat = z.T @ z
    for lag in range(1, min(21, len(z) - 1) + 1):
        gamma = z[lag:].T @ z[:-lag]
        meat += (1 - lag / 22) * (gamma + gamma.T)
    inverse = np.linalg.pinv(xx.T @ xx)
    se = np.sqrt(np.maximum(0, np.diag(inverse @ meat @ inverse)))
    return {"n": int(valid.sum()), "alpha_ann": float(beta[0] * 365),
            "betas": {name: float(value) for name, value in zip(names, beta[1:])},
            "t_hac21": {name: float(value / error) for name, value, error in zip(names, beta[1:], se[1:])},
            "r2": float(1 - resid.var() / y[valid].var())}


def main():
    print(f"development-only symbols with klines: {len(SYMS)}", flush=True)
    O, C, V, S, CNT, F, first, inventory, timestamp_checks = load_panels()
    inventory.to_csv(OUT / "dev_inventory.csv", index=False)
    n, p = O.shape
    past_volume = pd.DataFrame(V).shift(1).rolling(30, min_periods=15).median().to_numpy()
    past_volume_days = pd.DataFrame(V).shift(1).rolling(30, min_periods=1).count().to_numpy()
    price_return = C / O - 1
    close_return = pd.DataFrame(C).pct_change(fill_method=None).to_numpy()
    prior_vol = pd.DataFrame(close_return).shift(1).rolling(30, min_periods=15).std().to_numpy()
    prior_mom = pd.DataFrame(C).shift(1).div(pd.DataFrame(C).shift(31)).sub(1).to_numpy()
    weights = np.zeros((n, p))
    member = np.zeros((n, p), dtype=bool)
    n_universe = np.zeros(n, dtype=int)
    n_side = np.zeros(n, dtype=int)
    date_days = DAYS.tz_localize(None).to_numpy(dtype="datetime64[D]")
    for i in range(n):
        eligible = ((date_days[i] - first) >= np.timedelta64(60, "D")) & np.isfinite(S[i]) & np.isfinite(past_volume[i])
        if i == 0:
            eligible[:] = False
        else:
            eligible &= np.isfinite(C[i - 1])
        indices = np.flatnonzero(eligible)
        # Stable sorts preserve lexical symbol order for exact ties.
        top = indices[np.argsort(-past_volume[i, indices], kind="stable")[:100]]
        member[i, top] = True
        n_universe[i] = len(top)
        if len(top) < 25:
            continue
        q = int(np.floor(.2 * len(top)))
        n_side[i] = q
        # Funding-rate ties are common at the exchange's rate cap. The frozen
        # tie break is lexical symbol order, not preceding liquidity rank.
        lexical_top = np.sort(top)
        ranked = lexical_top[np.argsort(S[i, lexical_top], kind="stable")]
        weights[i, ranked[:q]] = .5 / q
        weights[i, ranked[-q:]] = -.5 / q
    live = n_universe >= 25
    held_missing = (weights != 0) & ~np.isfinite(price_return)
    later_kline = np.flip(np.maximum.accumulate(np.flip(np.isfinite(price_return), axis=0), axis=0), axis=0)
    later_kline = np.vstack([later_kline[1:], np.zeros((1, p), dtype=bool)])
    held_temporary_gap = held_missing & later_kline
    held_terminal_gap = held_missing & ~later_kline
    price = np.nansum(weights * price_return, axis=1)
    fund = -np.sum(weights * F, axis=1)
    previous = np.vstack([np.zeros((1, p)), weights[:-1]])
    trade = np.abs(weights - previous)
    turnover = trade.sum(axis=1)
    delist_drag = .2 * (np.abs(weights) * held_missing).sum(axis=1)
    gross = price + fund
    base = gross - .0007 * turnover
    stress = gross - .002 * turnover - delist_drag
    daily = pd.DataFrame({"date": DAYS.tz_localize(None), "n_universe": n_universe,
                          "n_per_side": n_side, "price": price, "funding": fund,
                          "turnover": turnover, "delist_drag_stress": delist_drag,
                          "held_missing_count": held_missing.sum(axis=1),
                          "gross": gross, "base": base, "stress": stress,
                          "live": live})
    for book in ("gross", "base", "stress"):
        daily[f"nav_{book}"] = np.nan
        daily.loc[live, f"nav_{book}"] = np.cumprod(1 + daily.loc[live, book].to_numpy())
    daily.to_csv(OUT / "dev_daily_rebuilt.csv", index=False)
    pd.DataFrame(weights, index=DAYS.tz_localize(None), columns=SYMS).loc[live].to_parquet(OUT / "dev_weights_rebuilt.parquet")
    pd.DataFrame(member, index=DAYS.tz_localize(None), columns=SYMS).loc[live].to_parquet(
        OUT / "dev_universe_membership.parquet")
    m, sim = centred_p(base[live])
    block_sensitivity = {str(b): centred_p(base[live], block=b)[0] for b in (7, 14, 21, 42, 63, 90)}
    # Contemporaneous diagnostic factors, never used to select/reweight the strategy.
    ew_all = np.array([np.nanmean(price_return[i, member[i]]) if member[i].any() else np.nan for i in range(n)])
    ew_held = np.array([np.nanmean(price_return[i, weights[i] != 0]) if (weights[i] != 0).any() else np.nan for i in range(n)])
    factor = {}
    for name, score in (("liquidity", past_volume), ("volatility", prior_vol), ("momentum", prior_mom)):
        result = np.full(n, np.nan)
        for i in np.flatnonzero(live):
            ids = np.flatnonzero(member[i] & np.isfinite(score[i]) & np.isfinite(price_return[i]))
            if len(ids) < 10:
                continue
            ranked = ids[np.argsort(score[i, ids], kind="stable")]
            q = max(1, len(ranked) // 5)
            result[i] = np.mean(price_return[i, ranked[-q:]]) - np.mean(price_return[i, ranked[:q]])
        factor[name] = result
    btc = price_return[:, SYMS.index("BTCUSDT")]
    eth = price_return[:, SYMS.index("ETHUSDT")]
    yf = base[live]
    exposures = {
        "btc_only": ols(yf, btc[live, None], ["BTC"]),
        "eth_only": ols(yf, eth[live, None], ["ETH"]),
        "equal_weight_top100_only": ols(yf, ew_all[live, None], ["EW_top100"]),
        "joint_markets": ols(yf, np.column_stack([btc[live], eth[live], ew_all[live]]), ["BTC", "ETH", "EW_top100"]),
        "full_diagnostics": ols(yf, np.column_stack([btc[live], eth[live], ew_all[live],
                                                      factor["liquidity"][live], factor["volatility"][live],
                                                      factor["momentum"][live]]),
                                ["BTC", "ETH", "EW_top100", "liquidity_HML", "volatility_HML", "momentum_HML"]),
        "reported_held_ew_plus_btc": ols(yf, np.column_stack([ew_held[live], btc[live]]), ["EW_held", "BTC"]),
    }
    characteristics = {}
    for name, score in (("log_quote_volume", np.log(np.maximum(past_volume, 1))),
                        ("prior_30d_volatility", prior_vol), ("prior_30d_momentum", prior_mom)):
        long_mean = np.array([np.nanmean(score[i, weights[i] > 0]) if live[i] else np.nan for i in range(n)])
        short_mean = np.array([np.nanmean(score[i, weights[i] < 0]) if live[i] else np.nan for i in range(n)])
        characteristics[name] = {"long_mean": float(np.nanmean(long_mean)),
                                 "short_mean": float(np.nanmean(short_mean)),
                                 "long_minus_short": float(np.nanmean(long_mean - short_mean))}
    # Position-level P&L attribution with each side of turnover charged to its contract.
    contribution = np.nan_to_num(weights * price_return, nan=0.) - weights * F - .0007 * trade
    by_asset = pd.DataFrame({"symbol": SYMS, "base_sum": contribution[live].sum(axis=0),
                             "avg_abs_weight": np.abs(weights[live]).mean(axis=0),
                             "held_days": (weights[live] != 0).sum(axis=0),
                             "missing_held_days": held_missing[live].sum(axis=0)})
    by_asset = by_asset.sort_values("base_sum", ascending=False)
    by_asset.to_csv(OUT / "dev_asset_attribution.csv", index=False)
    monthly = daily.loc[live].assign(month=lambda x: x.date.dt.to_period("M").astype(str)).groupby("month").agg(
        days=("base", "size"), base_sum=("base", "sum"), base_compound=("base", lambda x: np.prod(1 + x) - 1),
        stress_sum=("stress", "sum"))
    monthly.to_csv(OUT / "dev_month_attribution.csv")
    annual = daily.loc[live].assign(year=lambda x: x.date.dt.year).groupby("year").agg(
        days=("base", "size"), base_sum=("base", "sum"), base_compound=("base", lambda x: np.prod(1 + x) - 1),
        stress_sum=("stress", "sum"))
    annual.to_csv(OUT / "dev_year_attribution.csv")
    pd.DataFrame({"date": DAYS.tz_localize(None), "BTC": btc, "ETH": eth, "EW_top100": ew_all,
                  "EW_held": ew_held, **factor}).loc[live].to_csv(OUT / "dev_factor_diagnostics.csv", index=False)
    summary = {
        "window": [str(DAYS[0].date()), str(DAYS[-1].date())],
        "symbols_with_dev_klines": len(SYMS), "symbols_with_dev_funding": int((inventory.funding_events > 0).sum()),
        "days_total": n, "days_dropped": int((~live).sum()), "days_live": int(live.sum()),
        "first_live": str(DAYS[np.flatnonzero(live)[0]].date()),
        "universe_size": {"min_live": int(n_universe[live].min()), "max_live": int(n_universe[live].max()),
                          "mean_live": float(n_universe[live].mean())},
        "books": {name: {"sharpe": sharpe(daily.loc[live, name]),
                         "ann_mean": float(daily.loc[live, name].mean() * 365),
                         "max_dd": max_drawdown(daily.loc[live, name])} for name in ("gross", "base", "stress")},
        "decomposition_ann": {"price": float(price[live].mean() * 365),
                               "funding": float(fund[live].mean() * 365),
                               "base_cost": float((.0007 * turnover[live]).mean() * 365),
                               "stress_cost": float((.002 * turnover[live]).mean() * 365),
                               "stress_delist_drag": float(delist_drag[live].mean() * 365)},
        "mean_turnover": float(turnover[live].mean()),
        "selected_with_15_to_29_volume_days": int((member[live] & (past_volume_days[live] < 30)).sum()),
        "selected_total_asset_days": int(member[live].sum()),
        "timestamps": timestamp_checks,
        "bootstrap_p_21": m, "bootstrap_p_by_block": block_sensitivity,
        "bootstrap_null_mean_sd": [float(sim.mean()), float(sim.std())],
        "held_missing_position_days": int(held_missing[live].sum()),
        "held_temporary_gap_position_days": int(held_temporary_gap[live].sum()),
        "held_terminal_gap_position_days": int(held_terminal_gap[live].sum()),
        "held_gap_by_date": {str(DAYS[i].date()): {"temporary": int(held_temporary_gap[i].sum()),
                                                    "terminal": int(held_terminal_gap[i].sum()),
                                                    "stress_drag": float(delist_drag[i])}
                             for i in np.flatnonzero(np.any(held_missing, axis=1) & live)},
        "held_missing_dates": [str(d.date()) for d in DAYS[np.any(held_missing, axis=1) & live]],
        "held_missing_by_symbol": {SYMS[j]: int(held_missing[live, j].sum()) for j in range(p)
                                   if held_missing[live, j].any()},
        "dollar_neutral_max_error": float(np.max(np.abs(weights[live].sum(axis=1)))),
        "gross_exposure_min_max": [float(np.abs(weights[live]).sum(axis=1).min()),
                                   float(np.abs(weights[live]).sum(axis=1).max())],
        "exposures": exposures,
        "position_characteristics": characteristics,
        "annual": annual.reset_index().to_dict(orient="records"),
        "top_assets": by_asset.head(10).to_dict(orient="records"),
        "bottom_assets": by_asset.tail(10).to_dict(orient="records"),
        "best_months": monthly.sort_values("base_sum", ascending=False).head(5).reset_index().to_dict(orient="records"),
        "worst_months": monthly.sort_values("base_sum").head(5).reset_index().to_dict(orient="records"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps({k: summary[k] for k in ("symbols_with_dev_klines", "days_dropped", "days_live",
                                                   "books", "bootstrap_p_21", "bootstrap_p_by_block",
                                                   "held_missing_position_days")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
