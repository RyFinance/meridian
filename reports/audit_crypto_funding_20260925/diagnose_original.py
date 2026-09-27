"""Development-only diagnostic adapter for comparing frozen code with rebuild.

The frozen module's archive readers are replaced before use. This file never
calls its unfiltered readers and never opens a 2023+ archive.
"""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.crypto_funding_xs import core

import verify as independent

asof = float(sys.argv[1])
independent.ASOF = asof
syms = sorted(set(independent.SYMS))


def klines(symbol):
    paths = independent.files("klines_1d", symbol)
    if not paths:
        return pd.DataFrame()
    data = pd.concat([independent.csv_zip(path, core.KCOLS) for path in paths], ignore_index=True)
    data["day"] = pd.to_datetime(pd.to_numeric(data["open_time"]), unit="ms").dt.normalize()
    return data.drop_duplicates("day").set_index("day").sort_index()[["open", "close", "quote_volume"]].astype(float)


def funding(symbol):
    paths = independent.files("fundingRate", symbol)
    if not paths:
        return pd.Series(dtype=float)
    data = pd.concat([independent.csv_zip(path, ["calc_time", "funding_interval_hours", "last_funding_rate"])
                      for path in paths], ignore_index=True)
    return pd.Series(pd.to_numeric(data["last_funding_rate"]).to_numpy(),
                     index=pd.to_datetime(pd.to_numeric(data["calc_time"]), unit="ms")).sort_index().groupby(level=0).last()


core.klines = klines
core.funding = funding
panel, first = core.panel(syms, "2020-01-01", "2022-12-31")
w = core.weights(panel, first, "2020-01-01", "2022-12-31")
source = pd.read_parquet(Path(__file__).resolve().parents[1] / "crypto_funding_xs/dev_weights.parquet")
rebuilt = pd.read_parquet(Path(__file__).resolve().parent / "asof_original_result/dev_weights_rebuilt.parquet")
for tag, x in (("source", source), ("rebuilt", rebuilt)):
    diff = (w.fillna(0).reindex(columns=x.columns, fill_value=0) - x.fillna(0)).abs()
    print(tag, "different days", int((diff > 1e-12).any(axis=1).sum()),
          "different cells", int((diff > 1e-12).sum().sum()))
print("2021-03-06 source calculation", w.loc["2021-03-06"][lambda x: x != 0].dropna().to_dict())
o, c, v, s, cnt, f, first_i, inv, checks = independent.load_panels()
ix = independent.DAYS.get_loc(pd.Timestamp("2021-03-06", tz="UTC"))
for symbol in ("KNCUSDT", "YFIUSDT"):
    j = independent.SYMS.index(symbol)
    print(symbol, "signal", s[ix, j], panel["SIG"].loc["2021-03-06", symbol],
          "volume", v[ix - 1, j], panel["V"].loc["2021-03-05", symbol])
for key, arr in (("O", o), ("C", c), ("V", v), ("SIG", s), ("FUND", f)):
    mat = panel[key].reindex(independent.DAYS.tz_localize(None)).reindex(columns=independent.SYMS).to_numpy()
    ok = np.isfinite(mat) & np.isfinite(arr)
    print(key, "unequal finite", int((np.abs(mat[ok] - arr[ok]) > 1e-12).sum()),
          "unequal missing", int((np.isfinite(mat) != np.isfinite(arr)).sum()))
saved_daily = pd.read_csv(Path(__file__).resolve().parents[1] / "crypto_funding_xs/dev_daily.csv", index_col=0)
rebuilt_daily = pd.read_csv(Path(__file__).resolve().parent / "asof_original_result/dev_daily_rebuilt.csv", index_col=0)
weight_diff = (source.fillna(0) - rebuilt.fillna(0).reindex(index=source.index, columns=source.columns, fill_value=0)).abs()
daily_diff = saved_daily["base"] - rebuilt_daily["base"]
comparison = {"different_weight_cells": int((weight_diff > 1e-12).sum().sum()),
              "different_weight_days": int((weight_diff > 1e-12).any(axis=1).sum()),
              "daily_return_difference_above_1e-12": {str(k): float(v) for k, v in daily_diff.items()
                                                       if abs(v) > 1e-12},
              "locked_archive_opened": False}
(Path(__file__).resolve().parent / "comparison.json").write_text(json.dumps(comparison, indent=2))
