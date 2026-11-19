"""Deterministic paper-only next-month sleeve targets for the frozen Cycle-6 BOOK.

No data acquisition, broker integration, registry mutation, or strategy return
calculation. The caller supplies a verified through-asof sleeve-return panel,
next-month gross notionals and a through-asof H.15 3m rate. The frozen BOOK
spec is hash-verified; the algorithm follows research.cycle6.engine.book.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle6.engine.book import erc_weights


BOOK_SPEC = Path("research/cycle6/specs/BOOK.md")
BOOK_SHA256 = "8843f97fe7eb6137f338f458eb9d09f406daea082d19e186cc37a577601a706b"


def _verified_params(path: Path = BOOK_SPEC) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BOOK_SHA256:
        raise ValueError("frozen BOOK specification hash mismatch")
    text = raw.decode()
    payload = text.split("```json\n", 1)[1].split("\n```", 1)[0]
    spec = json.loads(payload)
    return spec["book"]


def paper_targets(sleeves: pd.DataFrame, *, asof: str,
                  gross_next: dict[str, float], tbill_ann_asof: float,
                  spec_path: Path = BOOK_SPEC) -> dict:
    """Pure, no-lookahead target for the month after *asof*.

    ``sleeves`` has monthly net excess returns through asof, PeriodIndex M;
    unavailable earlier months are NaN. ``gross_next`` is next month's
    preregistered gross-notional estimate for each eligible sleeve, not an
    observed future return. Result is a paper-only sleeve allocation.
    """
    p = _verified_params(spec_path)
    if not isinstance(sleeves.index, pd.PeriodIndex) or sleeves.index.freqstr != "M":
        raise ValueError("sleeves must have monthly PeriodIndex")
    if sleeves.index.has_duplicates or not sleeves.index.is_monotonic_increasing:
        raise ValueError("duplicate/nonmonotonic months")
    t = pd.Period(asof, freq="M")
    if sleeves.empty or sleeves.index[-1] != t:
        raise ValueError("panel must end exactly at asof; future or stale rows refused")
    if not np.isfinite(tbill_ann_asof):
        raise ValueError("nonfinite asof T-bill rate")
    hist = sleeves.iloc[max(0, len(sleeves) - p["cov_months"]):]
    elig = [c for c in sleeves.columns if pd.notna(sleeves.at[t, c])]
    method, w, S = "cash", None, None
    if elig:
        H = hist[elig]
        common = H.dropna()
        if len(common) >= p["cov_months"]:
            C = common.cov().to_numpy()
            S = (1 - p["shrink"]) * C + p["shrink"] * np.diag(np.diag(C))
            w = erc_weights(S)
            method = "erc" if w is not None else "fallback"
        if w is None:
            sd = H.std(ddof=1)
            cnt = H.count()
            ok = [c for c in elig if cnt[c] >= p["fallback_min_obs"] and sd[c] > 0]
            if ok:
                inv = 1 / sd[ok].to_numpy()
                w = inv / inv.sum()
                S = np.diag(sd[ok].to_numpy() ** 2)
                elig, method = ok, "inv_vol"
            else:
                elig, method = [], "cash"
    out = {"status": "PAPER_ONLY_UNREGISTERED", "asof": str(t), "target_month": str(t + 1),
           "book_spec_sha256": BOOK_SHA256, "method": method,
           "n_sleeves": 0, "k": 0.0, "alloc": 0.0, "gross": 0.0,
           "exante_vol": 0.0, "cash_fin_adj_monthly_excess": 0.0,
           "scaled_sleeve_weights": {}, "gross_inputs": {}}
    if w is not None:
        vol = math.sqrt(12 * float(w @ S @ w))
        k = p["vol_target"] / vol if vol > 0 else 0.0
        g = np.array([float(gross_next[c]) for c in elig])
        if not np.isfinite(g).all() or np.any(g <= 0):
            raise ValueError("each eligible sleeve needs positive finite next-month gross estimate")
        gross = k * float(np.sum(w * g))
        if gross > p["gross_cap"]:
            k *= p["gross_cap"] / gross
            gross = p["gross_cap"]
        alloc = k * float(w.sum())
        out.update({"n_sleeves": len(elig), "k": float(k), "alloc": float(alloc),
                    "gross": float(gross), "exante_vol": float(k * vol),
                    "scaled_sleeve_weights": {c: float(k * wi) for c, wi in zip(elig, w)},
                    "gross_inputs": {c: float(gi) for c, gi in zip(elig, g)}})
    tbm = float(tbill_ann_asof) / 12
    a = out["alloc"]
    if a <= 1:
        adj = (1 - a) * (max(0.0, tbm - p["cash_spread"] / 12) - tbm)
    else:
        adj = -(a - 1) * p["financing_spread"] / 12
    out["cash_fin_adj_monthly_excess"] = float(adj)
    return out
