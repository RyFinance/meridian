"""Shared loading and statistics for the PEAD attack."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.pead_attack.engine import Stream, kelly_sizes
from research.pead_audit.mtm_audit import closes as mtm_closes

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "reports" / "pead_attack" / "inputs"
OUT = ROOT / "reports" / "pead_attack"
STATE = ROOT / "live_backtest" / "state"
FF6 = ["ff_mkt_rf", "smb", "hml", "rmw", "cma", "umd"]


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class Inputs:
    def __init__(self):
        self.events = pd.read_parquet(INPUTS / "events.parquet")
        self.calendar = pd.read_parquet(INPUTS / "calendar.parquet")
        self.closes_fill = pd.read_parquet(INPUTS / "closes_fill.parquet")
        self.manifest = json.loads((INPUTS / "manifest.json").read_text())
        self.dates = pd.DatetimeIndex(self.calendar.index)
        self.b = float(self.manifest["payoff_b"])
        self.stream = Stream.build(self.events, self.calendar, self.closes_fill)
        tick = list(self.closes_fill.columns)
        self.px_mark_df = mtm_closes(tick).reindex(self.dates).ffill()  # mtm_book's mark path semantics
        self.px_mark = self.px_mark_df.to_numpy(dtype=float)
        self.col = {t: j for j, t in enumerate(tick)}
        self.rf = self.calendar["rf"].to_numpy(dtype=float)
        ev = self.events
        self.p_real = ev["calibrated_proba"].to_numpy(dtype=float)
        self.sue = ev["sue"].to_numpy(dtype=float)
        self.sign_prod = np.where(self.sue > 0, 1.0, -1.0)  # ScoredEvent.direction: long iff sue > 0
        self.size_real = kelly_sizes(self.p_real, self.b)


def hac_ols(y: np.ndarray, X: np.ndarray, lags: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """OLS of y on [1, X] with Newey-West (Bartlett) standard errors; mirrors mtm_audit.ols_hac for k regressors."""
    X = np.column_stack([np.ones(len(y)), X])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    u = (y - X @ b)[:, None] * X
    S = u.T @ u
    for L in range(1, lags + 1):
        g = u[L:].T @ u[:-L]
        S += (1 - L / (lags + 1)) * (g + g.T)
    V = XtX_inv @ S @ XtX_inv
    return b, b / np.sqrt(np.diag(V))


def book_stats(ret: np.ndarray, rf: np.ndarray, calendar: pd.DataFrame, gross: np.ndarray | None = None,
               full: bool = False) -> dict:
    """Pre-registered statistics (PLAN section 4): excess Sharpe, CAGR of marked NAV, CAPM alpha (vs French
    Mkt-RF, the audit's regressor), and optionally the FF5+UMD alpha."""
    ex = ret - rf
    sd = ex.std(ddof=1)
    out = {"sharpe": float(ex.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"),
           "cagr": float(np.prod(1 + ret) ** (252 / len(ret)) - 1),
           "ann_excess_mean": float(ex.mean() * 252), "ann_vol": float(sd * np.sqrt(252))}
    mkt = calendar["mkt_rf"].fillna(0.0).to_numpy()
    b, t = hac_ols(ex, mkt)
    out.update({"capm_alpha": float(b[0] * 252), "capm_alpha_t": float(t[0]), "capm_beta": float(b[1])})
    if gross is not None:
        out["avg_gross"] = float(np.mean(gross))
    if full:
        f = calendar[FF6]
        m = f.notna().all(axis=1).to_numpy()
        b6, t6 = hac_ols(ex[m], f.to_numpy()[m])
        out.update({"ff6_alpha": float(b6[0] * 252), "ff6_alpha_t": float(t6[0]),
                    "ff6_loadings": dict(zip(FF6, map(float, b6[1:]))), "ff6_days": int(m.sum())})
    return out
