"""Unit tests for the cycle 8 par-bond repricer (research/cycle8/data_rates/bondmath.py)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_P = Path(__file__).resolve().parents[1] / "research" / "cycle8" / "data_rates" / "bondmath.py"
_spec = importlib.util.spec_from_file_location("c8_bondmath", _P)
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)


def test_par_price_is_one_at_coupon_yield():
    for y in (0.001, 0.02, 0.05, 0.15):
        for n in (0.5, 9 + 11 / 12, 10.0, 19.996):
            assert abs(bm.par_price(y, n, y) - 1.0) < 1e-12


def test_zero_yield_change_returns_carry():
    for y in (0.01, 0.05, 0.12):
        r = bm.par_bond_return(y, y, 10.0, 1 / 12)
        assert abs(r - y / 12) < 1e-12
        rd = bm.par_bond_return(y, y, 20.0, 1 / 252)
        assert abs(rd - y / 252) < 1e-12


def test_100bp_shock_close_to_minus_duration():
    y = 0.05
    dur = bm.modified_duration_par(y, 10.0)
    assert 7.5 < dur < 8.0  # 10y par bond at 5%, semiannual: ~7.79
    r = bm.par_bond_return(y, y + 0.01, 10.0, 1 / 12)
    # first-order: -dur*0.01 + carry; convexity makes the loss slightly smaller
    assert -dur * 0.01 + y / 12 - 0.001 < r < -dur * 0.01 + y / 12 + 0.005
    assert abs(r - (-0.0701)) < 0.01


def test_zero_yield_limit_is_continuous():
    a = bm.par_price(0.0, 9.5, 0.0)
    b = bm.par_price(1e-7, 9.5, 1e-7)
    assert abs(a - 1.0) < 1e-12 and abs(b - 1.0) < 1e-9
    assert abs(bm.par_price(0.0, 9.5, 1e-12) - bm.par_price(0.0, 9.5, 2e-9)) < 1e-6


def test_series_vectorised_matches_scalar():
    y = pd.Series([0.05, 0.051, 0.049, 0.049], index=pd.date_range("2000-01-31", periods=4, freq="ME"))
    r = bm.returns_from_yields(y, 10.0, 1 / 12)
    assert np.isnan(r.iloc[0])
    for i in range(1, 4):
        assert abs(r.iloc[i] - bm.par_bond_return(y.iloc[i - 1], y.iloc[i], 10.0, 1 / 12)) < 1e-15
    assert abs(r.iloc[3] - 0.049 / 12) < 1e-12
