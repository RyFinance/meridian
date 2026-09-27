"""Independent, development-only IEF/SHY audit; never reads the prior evaluator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/treasury_certification_20260923"

def prices(name: str) -> pd.Series:
    path = ROOT / f"data/multiasset/etf/{name}.parquet"
    frame = pd.read_parquet(path, columns=["date", "open"],
                            filters=[("date", ">=", pd.Timestamp("2003-01-02")),
                                     ("date", "<=", pd.Timestamp("2014-12-31"))])
    assert frame.date.max() <= pd.Timestamp("2014-12-31")
    assert frame.date.is_unique and frame.open.gt(0).all()
    return frame.set_index("date").open.sort_index().rename(name)


def main():
    paths = {name: ROOT / f"data/multiasset/etf/{name}.parquet" for name in ("IEF", "SHY", "TLT", "SPY")}
    joined = pd.concat([prices(k) for k in paths], axis=1, join="inner")
    assert joined.index.min() == pd.Timestamp("2003-01-02")
    assert joined.index.max() == pd.Timestamp("2014-12-31")
    # The registered execution enters at the first open and exits at the last.
    r = joined.pct_change().iloc[1:].copy()
    active = (r.IEF - r.SHY).to_numpy()
    active[0] -= 0.0003
    active[-1] -= 0.0003
    stress = active.copy()
    stress[[0, -1]] -= 0.0006
    barbell = np.empty(len(r))
    weight = np.array([1/3, 2/3], dtype=float)
    prev_month = None
    for i, (date, tlt, shy) in enumerate(zip(joined.index[:-1], r.TLT.to_numpy(), r.SHY.to_numpy())):
        month = date.to_period("M")
        if prev_month is not None and month != prev_month:
            weight[:] = [1/3, 2/3]
        pair = np.array([tlt, shy])
        barbell[i] = weight @ pair
        weight *= (1 + pair) / (1 + barbell[i])
        prev_month = month
    n = len(active)
    annual = float(active.mean() * 252)
    sr = float(active.mean() / active.std(ddof=1) * np.sqrt(252))
    years = (joined.index.max() - joined.index.min()).days / 365.25
    gate = 1.8 / np.sqrt(years)
    # Independent loop: circular blocks, mean-centred null; fixed published seed.
    rng = np.random.default_rng(20260923)
    null_mean = np.empty(5000)
    for i in range(5000):
        starts = rng.integers(0, n, size=int(np.ceil(n / 21)))
        ix = np.concatenate([(s + np.arange(21)) % n for s in starts])[:n]
        null_mean[i] = (active[ix] - active.mean()).mean()
    p = float((1 + (null_mean >= active.mean()).sum()) / 5001)
    equity = (r.SPY - r.SHY).to_numpy()
    corr = float(np.corrcoef(active, equity)[0, 1])
    # Label each open-to-open interval by the entry date, as the frozen study does.
    dates = joined.index[:-1]
    yearsums = {str(y): float(active[dates.year == y].sum()) for y in sorted(set(dates.year))}
    # Keep complete calendar-year blocks for adverse sequence and multiyear losses.
    blocks = [active[dates.year == y] for y in sorted(set(dates.year))]
    futures = {}
    rng = np.random.default_rng(948521)
    for horizon in (3, 5):
        x = np.empty(10000)
        sharpe = np.empty(10000)
        maxdd = np.empty(10000)
        for i in range(10000):
            path = np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), size=horizon)])
            nav = np.cumprod(1 + path)
            x[i] = nav[-1] - 1
            sharpe[i] = path.mean() / path.std(ddof=1) * np.sqrt(252)
            maxdd[i] = np.min(np.r_[1., nav] / np.maximum.accumulate(np.r_[1., nav]) - 1)
        futures[str(horizon)] = {"loss_probability": float(np.mean(x < 0)),
                                 "negative_sharpe_probability": float(np.mean(sharpe < 0)),
                                 "worst_decile_total_return": float(np.quantile(x, 0.1)),
                                 "median_max_drawdown": float(np.median(maxdd)),
                                 "worst_decile_max_drawdown": float(np.quantile(maxdd, 0.1))}
    result = {"input_sha256": {k: hashlib.sha256(v.read_bytes()).hexdigest() for k,v in paths.items()},
              "observations": n, "annual_active_mean": annual, "active_sharpe": sr,
              "gate": float(gate), "stress_annual_active_mean": float(stress.mean()*252),
              "bootstrap_p_independent": p, "batch_alpha": 0.05/3,
              "equity_active_correlation": corr, "annual_active_sum": yearsums,
              "annual_vs_duration_barbell": float((r.IEF.to_numpy() - barbell).mean()*252 - .0006*252/n),
              "alternate_futures": futures, "validation_read": False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
