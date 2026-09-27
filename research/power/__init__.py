"""research.power -- a reusable power calculator for quant_v7 research plans (research cycle 4, Workload A).

Purpose: before a plan registers, know whether it can give a decisive answer. Everything is analytic (numpy/scipy)
and every analytic formula has a seeded Monte Carlo verifier in `research.power.simulate` (checked in
tests/test_power.py). Synthetic only: no project price data is read and no family's evaluate.py is run.

Quick use
---------
    from research.power import designs, gates, report
    d = designs.event_study(events_per_year=510, car_sd=0.07, hold_days=20, icc=0.02,
                            concurrency={"model": "seasonal_poisson", "season_fraction": 0.45},
                            portfolio_autocorr=0.05)
    dev = gates.amendment2_dev_gate(k=1, stress_drag_sr=0.1)
    val = gates.current_val_gate(k=1, stress_drag_sr=0.1)
    pav = gates.power_aware_val_gate(k_val=1, stress_drag_sr=0.1)
    rep = report.evaluate(d, dev_years=10, val_years=10, dev_gate=dev, val_gate=val, pav_gate=pav)
    print(report.text_table(rep))

CLI for plan registration (Amendment 2, N5 power disclosure):
    PYTHONPATH=. .venv/bin/python -m research.power.plan_check research/power/examples/<spec>.json
"""
from research.power.core import (Autocorr, CorrelationAssumptionError, IndependenceWarning, SeriesModel,  # noqa
                                 batch_alpha, breadth_eff, kish_deff)
from research.power import designs, gates, report  # noqa: F401

__all__ = ["Autocorr", "SeriesModel", "CorrelationAssumptionError", "IndependenceWarning", "batch_alpha",
           "breadth_eff", "kish_deff", "designs", "gates", "report"]
