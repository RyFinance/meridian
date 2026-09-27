import numpy as np
import pandas as pd

from research.commodity_roll import validation_checks as vc
from research.struct_common import ROOT


def test_registered_pairs_reproduce_dev_book():
    _, b = vc.registered_pairs(vc.WINDOWS["dev"], "base")
    d = pd.read_csv(ROOT / "reports" / "commodity_roll" / "dev_daily.csv", index_col=0, parse_dates=True)["base"]
    assert len(b) == len(d)
    assert (b - d.reindex(b.index)).abs().max() < 1e-12


def test_period_mapping():
    cal = pd.bdate_range("2019-12-20", "2020-08-10")
    fs = pd.Series(vc.first_session_flags(cal), index=cal)
    per_id = fs.shift(1, fill_value=True).cumsum().reindex(cal[1:])
    per_open = pd.Series(cal[fs.to_numpy()], index=range(2, int(fs.sum()) + 2))
    for k in per_id.unique():
        days = per_id[per_id == k].index
        assert per_open[k] < days[0]
        assert days[0] == cal[cal.get_loc(per_open[k]) + 1]


def test_block_p_centred():
    x = np.random.default_rng(1).normal(0, 0.01, 2000)
    assert 0.2 < vc.block_p(x - x.mean(), 21, draws=1000) < 0.8
    assert vc.block_p(x - x.mean() + 0.002, 21, draws=1000) < 0.01


def test_fred_truncates_and_positive():
    s = vc.fred("DCOILWTICO", "2016-12-30")
    assert s.index.max() <= pd.Timestamp("2016-12-30")
    assert (s > 0).all()
