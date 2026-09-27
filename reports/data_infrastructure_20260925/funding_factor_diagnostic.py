"""Development-only explanation of the already frozen Binance funding book.

No strategy construction or alternate portfolio is performed. Uses the
independent as-of audit weights and only 2020–2022 raw archive ZIPs.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / "reports/audit_crypto_funding_20260925"
module_spec = importlib.util.spec_from_file_location("independent_dev_loader", AUDIT / "verify.py")
loader = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(loader)
loader.ASOF = 1790334912.0
loader.SYMS = [symbol for symbol in loader.SYMS if loader.files("klines_1d", symbol)]


def coefficient(y, x):
    ok = np.isfinite(y) & np.isfinite(x).all(axis=1)
    return np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), x[ok]]), y[ok], rcond=None)[0]


def main():
    O, C, V, S, _, F, _, _, _ = loader.load_panels()
    dates = loader.DAYS.tz_localize(None)
    symbols = loader.SYMS
    weights = pd.read_parquet(AUDIT / "asof_original_result/dev_weights_rebuilt.parquet")
    membership = pd.read_parquet(AUDIT / "asof_original_result/dev_universe_membership.parquet")
    W = weights.reindex(index=dates, columns=symbols, fill_value=0).fillna(0).to_numpy(float)
    M = membership.reindex(index=dates, columns=symbols, fill_value=False).fillna(False).to_numpy(bool)
    live = M.sum(axis=1) >= 25
    R = C / O - 1
    R = np.nan_to_num(R, nan=0)
    past_v = pd.DataFrame(V).shift(1).rolling(30, min_periods=15).median().to_numpy()
    past_r = pd.DataFrame(C).pct_change(fill_method=None).to_numpy()
    volatility = pd.DataFrame(past_r).shift(1).rolling(30, min_periods=15).std().to_numpy()
    factor = np.full(len(dates), np.nan)
    funding_spread = np.full(len(dates), np.nan)
    rank_relation = []
    for i in np.flatnonzero(live):
        ids = np.flatnonzero(M[i] & np.isfinite(volatility[i]) & np.isfinite(C[i]) & np.isfinite(O[i]))
        if len(ids) < 10:
            continue
        ordered = ids[np.argsort(volatility[i, ids], kind="stable")]
        q = max(1, len(ids) // 5)
        factor[i] = np.mean(R[i, ordered[-q:]]) - np.mean(R[i, ordered[:q]])
        universe = np.flatnonzero(M[i] & np.isfinite(S[i]))
        funding_spread[i] = float(np.mean(S[i, W[i, :] < 0]) - np.mean(S[i, W[i, :] > 0]))
        funding_pct = pd.Series(S[i, universe]).rank(pct=True).to_numpy()
        vol_pct = pd.Series(volatility[i, universe]).rank(pct=True).to_numpy()
        liq_pct = pd.Series(past_v[i, universe]).rank(pct=True).to_numpy()
        index = {symbol: position for position, symbol in enumerate(universe)}
        long_ids = [index[j] for j in universe if W[i, j] > 0]
        short_ids = [index[j] for j in universe if W[i, j] < 0]
        rank_relation.append({"date": str(dates[i].date()), "n": len(universe),
                              "spearman_funding_vs_vol": float(pd.Series(funding_pct).corr(pd.Series(vol_pct), method="spearman")),
                              "spearman_funding_vs_liquidity": float(pd.Series(funding_pct).corr(pd.Series(liq_pct), method="spearman")),
                              "long_vol_percentile": float(np.nanmean(vol_pct[long_ids])),
                              "short_vol_percentile": float(np.nanmean(vol_pct[short_ids])),
                              "long_liquidity_percentile": float(np.nanmean(liq_pct[long_ids])),
                              "short_liquidity_percentile": float(np.nanmean(liq_pct[short_ids]))})
    rank_table = pd.DataFrame(rank_relation)
    rank_table.to_csv(OUT / "funding_rank_relationships.csv", index=False)
    long = np.where(W > 0, W, 0)
    short = np.where(W < 0, W, 0)
    previous = np.vstack([np.zeros((1, W.shape[1])), W[:-1]])
    parts = {
        "long_price": np.sum(long * R, axis=1),
        "short_price": np.sum(short * R, axis=1),
        "long_funding": -np.sum(long * F, axis=1),
        "short_funding": -np.sum(short * F, axis=1),
        "base_fees": -.0007 * np.abs(W - previous).sum(axis=1),
    }
    parts["base_total"] = sum(parts.values())
    factor_table = pd.read_csv(AUDIT / "asof_original_result/dev_factor_diagnostics.csv")
    factor_table["date"] = pd.to_datetime(factor_table["date"])
    controls = factor_table.set_index("date").reindex(dates)
    # Same six-factor diagnostic design as the prior audit. Linear betas of the
    # components must sum to the frozen portfolio's beta exactly.
    X = np.column_stack([controls[name].to_numpy() for name in
                         ("BTC", "ETH", "EW_top100", "liquidity", "volatility", "momentum")])
    betas = {name: {"univariate_volatility": float(coefficient(series[live], factor[live, None])[1]),
                    "conditional_volatility": float(coefficient(series[live], X[live])[5]),
                    "annual_mean": float(np.mean(series[live]) * 365)}
             for name, series in parts.items()}
    by_year = {}
    contribution = W * R - W * F - .0007 * np.abs(W - previous)
    for year in (2020, 2021, 2022):
        mask = live & (dates.year == year)
        per_asset = contribution[mask].sum(axis=0)
        active = (W[mask] != 0).any(axis=0)
        positive = per_asset[active][per_asset[active] > 0]
        by_year[str(year)] = {"days": int(mask.sum()), "asset_count_held": int(active.sum()),
                              "assets_positive": int((per_asset[active] > 0).sum()),
                              "net_pnl_sum": float(per_asset.sum()),
                              "gross_positive_asset_pnl_sum": float(positive.sum()),
                              "top_five_positive_sum": float(np.sort(positive)[-5:].sum()),
                              "top_five_share_of_positive_pnl": float(np.sort(positive)[-5:].sum() / positive.sum())
                              if positive.sum() > 0 else None,
                              "top_five_positive_share_of_net": float(np.sort(positive)[-5:].sum() / per_asset.sum())
                              if per_asset.sum() != 0 else None,
                              "mean_trailing_funding_spread": float(np.nanmean(funding_spread[mask])),
                              "realized_funding_pnl_sum": float(np.sum(parts["long_funding"][mask] + parts["short_funding"][mask])),
                              "realized_price_pnl_sum": float(np.sum(parts["long_price"][mask] + parts["short_price"][mask]))}
    daily = pd.DataFrame({"date": dates, "live": live, "volatility_factor": factor,
                          "trailing_funding_spread": funding_spread, **parts})
    daily.loc[live].to_csv(OUT / "factor_decomposition_daily.csv", index=False)
    result = {
        "factor_definition": "Within each frozen daily top-100 eligible universe, rank contracts by sample standard deviation of their prior 30 calendar-day close-to-close returns (shifted one day; at least 15 observed returns). The daily high-minus-low factor is equal-weight same-day perp close/open return of the highest-volatility fifth minus that of the lowest-volatility fifth, restricted to names with a valid day-t bar; q=floor(n/5). This diagnostic factor never changes the strategy.",
        "component_exposure": betas,
        "rank_relationships_mean": {column: float(rank_table[column].mean()) for column in rank_table
                                    if column not in ("date", "n")},
        "rank_relationships_median": {column: float(rank_table[column].median()) for column in rank_table
                                      if column not in ("date", "n")},
        "annual_breadth_and_regime": by_year,
        "source_snapshot": "asof_original_result; development archive ZIPs through 2022 only",
    }
    (OUT / "funding_factor_diagnosis.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
