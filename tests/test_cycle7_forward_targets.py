import numpy as np
import pandas as pd
import pytest

from research.cycle6.engine.book import build_book
from research.cycle7.forward_targets import paper_targets


def _panel():
    rng = np.random.default_rng(717)
    months = pd.period_range("2010-01", periods=90, freq="M")
    x = pd.DataFrame(rng.normal(0, .02, (90, 3)), index=months, columns=["a", "b", "c"])
    x["b"] += x["a"] * .2
    return x


def test_targets_match_frozen_book_weights_without_future_returns():
    x = _panel()
    asof = str(x.index[-2])
    target = paper_targets(x.iloc[:-1], asof=asof,
                           gross_next={"a": 1.2, "b": 1.1, "c": 1.0}, tbill_ann_asof=.04)
    params = {"cov_months": 60, "shrink": .25, "vol_target": .1, "gross_cap": 2.,
              "cash_spread": .005, "financing_spread": .02, "fallback_min_obs": 12}
    gross = pd.DataFrame({"a": [1.2], "b": [1.1], "c": [1.]}, index=[x.index[-1]])
    tbill = pd.Series(.04, index=x.index)
    book, weights = build_book(x, tbill, params, gross)
    last = book.iloc[-1]
    expected = dict(zip(weights.loc[weights.month == str(x.index[-1]), "sleeve"],
                        weights.loc[weights.month == str(x.index[-1]), "scaled_weight"]))
    assert target["scaled_sleeve_weights"] == pytest.approx(expected)
    assert target["gross"] == pytest.approx(last["gross"])
    assert target["cash_fin_adj_monthly_excess"] == pytest.approx(last["cash_fin_adj"])
    assert target == paper_targets(x.iloc[:-1], asof=asof,
                                   gross_next={"a": 1.2, "b": 1.1, "c": 1.0}, tbill_ann_asof=.04)


def test_future_row_is_refused():
    x = _panel()
    with pytest.raises(ValueError, match="asof"):
        paper_targets(x, asof=str(x.index[-2]), gross_next={"a": 1, "b": 1, "c": 1}, tbill_ann_asof=.04)
