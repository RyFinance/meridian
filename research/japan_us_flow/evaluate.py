"""Frozen J1 development experiment; deliberately never loads validation JP bars."""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.null_lab.api import builders, run_null
from research.null_lab.engines import sharpe
from research.null_lab.gates import BootstrapP, Gate


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/lse/japan_us_flow"
OUT = ROOT / "reports/japan_us_flow"
JP_TIMES = ("00:00", "00:30", "01:00", "01:30", "02:00", "03:30", "04:00", "04:30", "05:00", "05:30")
BASE_COST = 0.0001
STRESS_COST = 0.0003
SEED = 20260923


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def valid_ohlc(frame: pd.DataFrame) -> bool:
    v = frame[["open", "high", "low", "close"]].to_numpy(float)
    return bool(np.isfinite(v).all() and (v > 0).all() and
                (v[:, 1] >= v[:, [0, 3]].max(axis=1)).all() and
                (v[:, 2] <= v[:, [0, 3]].min(axis=1)).all())


def japan_signs() -> tuple[dict[date, float], dict]:
    jp = pd.read_parquet(DATA / "JP225_30m_dev.parquet").sort_values("time")
    official = set(pd.to_datetime(pd.read_parquet(DATA / "JPX_official_calendar_reference.parquet", columns=["date"])["date"]).dt.date)
    jp["date"] = jp.time.dt.date
    signs = {}
    reasons = {"lse_dates": 0, "not_official_session": 0, "wrong_bar_schedule": 0, "bad_ohlc": 0, "accepted": 0}
    for day, frame in jp.groupby("date", sort=True):
        reasons["lse_dates"] += 1
        if day not in official:
            reasons["not_official_session"] += 1
            continue
        if tuple(frame.time.dt.strftime("%H:%M")) != JP_TIMES:
            reasons["wrong_bar_schedule"] += 1
            continue
        if not valid_ohlc(frame):
            reasons["bad_ohlc"] += 1
            continue
        s = np.sign(np.log(float(frame.iloc[-1].close) / float(frame.iloc[0].open)))
        signs[day] = float(s)
        reasons["accepted"] += 1
    return signs, reasons


def roll_exclusions() -> set[date]:
    excluded = set()
    for year in range(2016, 2021):
        for month in (3, 6, 9, 12):
            first = date(year, month, 1)
            first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
            third_friday = first_friday + timedelta(days=14)
            thursday = third_friday - timedelta(days=1)
            excluded.update(thursday + timedelta(days=i) for i in range(5))
    return excluded


def es_session_rows(signs: dict[date, float]) -> tuple[pd.DataFrame, dict]:
    path = ROOT / "data/lse/futures_30m/ES_F.parquet"
    es = pd.read_parquet(path)
    es = es[(es.ts >= "2016-05-25") & (es.ts < "2021-01-04")].copy()
    et = es.ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    es["date"] = et.dt.date
    es["hm"] = et.dt.strftime("%H:%M")
    x = es[es.hm.isin(["09:30", "15:30"])].copy()
    entry = x[x.hm == "09:30"].drop_duplicates("date").set_index("date")
    exit_ = x[x.hm == "15:30"].drop_duplicates("date").set_index("date")
    all_days = sorted(set(entry.index) & set(exit_.index))
    prev_close = exit_.close.shift(1)
    rolls = roll_exclusions()
    rows = []
    counts = {"es_full_sessions": len(all_days), "japan_missing": 0, "roll_excluded": 0,
              "bad_ohlc": 0, "rth_jump_excluded": 0, "eligible": 0}
    for day in all_days:
        if not (date(2016, 6, 1) <= day <= date(2020, 12, 31)):
            continue
        e, z = entry.loc[day], exit_.loc[day]
        old = float(prev_close.loc[day])
        active = True
        if day not in signs:
            counts["japan_missing"] += 1
            active = False
        if day in rolls:
            counts["roll_excluded"] += 1
            active = False
        if not valid_ohlc(pd.DataFrame([e, z])) or not np.isfinite(old) or old <= 0:
            counts["bad_ohlc"] += 1
            active = False
        rth = float(z.close / e.open - 1) if np.isfinite(e.open) and e.open > 0 else np.nan
        if not np.isfinite(rth) or abs(rth) > 0.10:
            counts["rth_jump_excluded"] += 1
            active = False
        if active:
            counts["eligible"] += 1
        rows.append({"date": day, "eligible": active, "japan_sign": signs.get(day, np.nan),
                     "es_overnight_sign": np.sign(e.open / old - 1) if old > 0 else np.nan,
                     "rth": rth if np.isfinite(rth) else 0.0})
    return pd.DataFrame(rows), counts


def net_returns(position: np.ndarray, rth: np.ndarray, cost: float) -> np.ndarray:
    return position * rth - cost * np.abs(position)


class J1Engine:
    name = "Japan sign to ES US RTH, development only"
    periods = 252

    def __init__(self, rth: np.ndarray, eligible_ix: np.ndarray, n_days: int):
        self.rth = np.asarray(rth, float)
        self.ix = np.asarray(eligible_ix, int)
        self.n_days = n_days

    def run(self, signals: np.ndarray, paths=None) -> dict:
        if paths is not None:
            raise ValueError("No resampled price path registered")
        signals = np.atleast_2d(np.asarray(signals, float))
        if signals.shape[1] != len(self.rth):
            raise ValueError("Signal length mismatch")
        if not np.isin(signals, [-1, 0, 1]).all():
            raise ValueError("Positions must be signs")
        base = np.zeros((len(signals), self.n_days))
        stress = np.zeros_like(base)
        base[:, self.ix] = net_returns(signals, self.rth, BASE_COST)
        stress[:, self.ix] = net_returns(signals, self.rth, STRESS_COST)
        return {("dev", "base"): base, ("dev", "stress"): stress}


def stats(x: np.ndarray) -> dict:
    x = np.asarray(x, float)
    wealth = np.cumprod(1 + x)
    peak = np.maximum.accumulate(np.r_[1.0, wealth])
    return {"annual_mean": float(x.mean() * 252),
            "sharpe": float(sharpe(x[None, :], 252)[0]),
            "max_drawdown": float(np.min(np.r_[1.0, wealth] / peak - 1))}


def concentration(frame: pd.DataFrame, returns: np.ndarray, months: int) -> dict:
    d = pd.to_datetime(frame.date)
    best = None
    for start in d:
        end = start + pd.DateOffset(months=months)
        mask = (d >= start) & (d < end)
        val = float(np.sum(returns[mask.to_numpy()]))
        if best is None or val > best[0]:
            best = (val, start, end, mask.to_numpy())
    rest = returns[~best[3]]
    return {"removed_start": best[1].date().isoformat(), "removed_end_exclusive": best[2].date().isoformat(),
            "removed_sum": best[0], "remaining": stats(rest)}


def main() -> None:
    signs, japan_audit = japan_signs()
    frame, es_audit = es_session_rows(signs)
    if frame.empty:
        raise RuntimeError("No ES sessions")
    eligible = frame.eligible.to_numpy(bool)
    ix = np.flatnonzero(eligible)
    real_sign = frame.loc[eligible, "japan_sign"].to_numpy(float)
    rth = frame.loc[eligible, "rth"].to_numpy(float)
    control_sign = frame.loc[eligible, "es_overnight_sign"].to_numpy(float)
    if len(real_sign) <= 504 or not np.isfinite(control_sign).all():
        raise RuntimeError("Insufficient or invalid eligible sessions")
    engine = J1Engine(rth, ix, len(frame))
    # Exactness test: the null engine's J1 daily returns equal direct arithmetic.
    engine_result = engine.run(real_sign[None, :])
    direct = np.zeros(len(frame))
    direct[ix] = net_returns(real_sign, rth, BASE_COST)
    np.testing.assert_allclose(engine_result[("dev", "base")][0], direct, atol=1e-15, rtol=0)
    j1 = direct
    j1_gross = np.zeros(len(frame)); j1_gross[ix] = net_returns(real_sign, rth, 0)
    j1_stress = engine_result[("dev", "stress")][0]
    c1 = np.zeros(len(frame)); c1[ix] = net_returns(control_sign, rth, BASE_COST)
    c2 = np.zeros(len(frame)); c2[ix] = net_returns(np.ones(len(ix)), rth, BASE_COST)
    p2 = np.zeros(len(frame)); p2[ix] = net_returns(-real_sign, rth, BASE_COST)
    years = (date(2020, 12, 31) - date(2016, 6, 1)).days / 365.25
    threshold = 1.8 / np.sqrt(years)
    paired = j1 - c1
    paired_p = float(BootstrapP(len(paired), 21, 5000, SEED).pvalues(paired[None, :])[0])
    gate = Gate(dev_sharpe=threshold, k=1)
    null = run_null(builders.shift(real_sign, min_offset=252), engine, gate,
                    n_worlds=5000, seed=SEED, family_size=1, with_composite=False,
                    dev_only=True)
    observed_sr = stats(j1)["sharpe"]
    null_sr = null["arrays"]["sr_dev"][:, 0]
    p_at_least_observed = float((1 + np.count_nonzero(null_sr >= observed_sr)) / (len(null_sr) + 1))
    passed = bool(stats(j1)["sharpe"] >= threshold and stats(j1_stress)["annual_mean"] > 0 and
                  stats(paired)["annual_mean"] > 0 and paired_p < 0.05)
    yearly = {}
    for year, sub in frame.groupby(pd.to_datetime(frame.date).dt.year):
        rows = sub.index.to_numpy()
        yearly[str(year)] = {"j1_annual_mean": float(j1[rows].mean() * 252),
                             "c1_annual_mean": float(c1[rows].mean() * 252),
                             "j1_total": float(j1[rows].sum()),
                             "trades": int(eligible[rows].sum())}
    result = {"status": "PASS_DEVELOPMENT_ONLY" if passed else "FAIL_DEVELOPMENT",
              "plan_sha256": file_hash(ROOT / "research/japan_us_flow/PLAN.md"),
              "amendment_sha256": file_hash(ROOT / "research/japan_us_flow/PLAN_AMENDMENT_1.md"),
              "input_sha256": {"jp": file_hash(DATA / "JP225_30m_dev.parquet"),
                               "official_date_mask": file_hash(DATA / "JPX_official_calendar_reference.parquet"),
                               "es": file_hash(ROOT / "data/lse/futures_30m/ES_F.parquet")},
              "window": ["2016-06-01", "2020-12-31"], "years": years,
              "days": len(frame), "trades": len(ix), "japan_audit": japan_audit, "es_audit": es_audit,
              "dev_sharpe_gate": threshold, "j1_gross": stats(j1_gross),
              "j1_base": stats(j1), "j1_stress": stats(j1_stress),
              "c1_own_overnight": stats(c1), "c2_always_long": stats(c2),
              "p2_reversed_japan": stats(p2), "j1_minus_c1": stats(paired),
              "j1_minus_c1_bootstrap_p": paired_p,
              "corr_j1_c1": float(np.corrcoef(j1, c1)[0, 1]),
              "null": {"p_pass_dev": null["candidate"]["p_pass_dev"],
                       "p_sharpe_at_least_observed": p_at_least_observed,
                       "sr_dev": null["candidate"]["sr_dev"],
                       "signal": null["signal"], "n_worlds": null["n_worlds"]},
              "best_12m_removed": concentration(frame, j1, 12),
              "best_24m_removed": concentration(frame, j1, 24),
              "yearly": yearly,
              "validation": "LOCKED; no validation JP data loaded or validation returns computed"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev_results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
