"""Reproduce the FROZEN research/crypto_funding_xs target weights for one forward decision day, from a
research/forward_crypto snapshot -- not from the historical Binance archive, and never for a date in
the locked validation window (2023-01-01..2026-08-31; enforced below).

The universe/signal/portfolio construction is the frozen `research.crypto_funding_xs.core.weights`
function, called UNMODIFIED and BY IMPORT, together with its frozen constants (TOP_N, MIN_HIST,
VOL_LOOKBACK, SIG_DAYS, MIN_SETTLE, MIN_UNIVERSE, Q, EXCL_BASE). Nothing in core.py is edited or
monkeypatched. Only the data PLUMBING differs from core.py's historical `panel()`:

  * core.panel() reads local archive files under data/c4/binance_um (funding()/klines(), disk-cached).
  * this module reads today's live snapshot under data/forward_crypto/raw/YYYY-MM-DD (collector.py)
    and builds the same shaped O/C/V/SIG frames for the trailing window the frozen rule needs
    (VOL_LOOKBACK=30 days of quote volume, SIG_DAYS=7 days of funding settlements), then calls
    `core.weights(P, FIRST, day, day)` exactly as the historical evaluator does for one day.

First-listing date (`FIRST`, used for the MIN_HIST=60-day eligibility filter) is taken from
exchangeInfo's `onboardDate`, which the historical code does not have access to (it infers first-kline
date from the archive instead); the two are equivalent for symbols the archive covers, and onboardDate
is the more authoritative source live, since a live snapshot does not carry 60+ days of klines.

This module produces TARGET WEIGHTS ONLY. It never computes a realised return for those targets, and
it refuses outright for any decision day inside or before the frozen rule's locked validation window
(2023-01-01..2026-08-31) -- forward-only means this code has no path to touch that window at all.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.crypto_funding_xs import core as c
from research.forward_crypto.collector import ROOT, RAW_DIR

VALIDATION_LOCK_START = pd.Timestamp("2023-01-01")
VALIDATION_LOCK_END = pd.Timestamp("2026-08-31")
FROZEN_FILES = ("research/crypto_funding_xs/PLAN.md", "research/crypto_funding_xs/core.py",
                "research/crypto_funding_xs/evaluate.py")


class TargetsError(RuntimeError):
    pass


# -- provenance: prove the frozen files are unmodified at the moment targets are generated -----------

def frozen_provenance(root: Path = ROOT) -> dict:
    import hashlib

    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in FROZEN_FILES if (root / p).exists()}


# -- reading a snapshot day --------------------------------------------------------------------------

def snapshot_day_dir(day: str, root: Path = RAW_DIR) -> Path:
    d = root / day
    if not d.exists():
        raise TargetsError(f"no forward_crypto snapshot for {day}: {d} does not exist")
    return d


def _latest_file(day_dir: Path, prefix: str) -> Path | None:
    files = sorted(day_dir.glob(f"{prefix}.*.json"))
    return files[-1] if files else None  # HHMMSS then hash: lexicographic sort == fetch-time order


def _read_envelope(path: Path) -> dict:
    return json.loads(path.read_text())


def load_exchange_info(day_dir: Path) -> dict:
    f = _latest_file(day_dir, "exchangeInfo")
    if f is None:
        raise TargetsError(f"no exchangeInfo snapshot in {day_dir}")
    return _read_envelope(f)["body"]


def load_symbol_klines(day_dir: Path, symbol: str) -> list[list] | None:
    f = _latest_file(day_dir, f"klines.{symbol}")
    return _read_envelope(f)["body"] if f is not None else None


def load_symbol_funding(day_dir: Path, symbol: str) -> list[dict] | None:
    f = _latest_file(day_dir, f"fundingRate.{symbol}")
    return _read_envelope(f)["body"] if f is not None else None


def load_symbol_premium_index(day_dir: Path, symbol: str) -> dict | None:
    f = _latest_file(day_dir, f"premiumIndex.{symbol}")
    return _read_envelope(f)["body"] if f is not None else None


# -- candidate universe (mirrors core.symbols()'s filter, on the live exchangeInfo snapshot) ----------

def candidate_symbols(exchange_info: dict) -> list[str]:
    """Currently-TRADING USDT perps, excluding the frozen rule's non-crypto/index bases. The
    top-100-by-volume and history/eligibility cuts are applied later, inside core.weights()."""
    out = []
    for s in exchange_info.get("symbols", []):
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT" or s.get("status") != "TRADING":
            continue
        sym = s["symbol"]
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if base in c.EXCL_BASE:
            continue
        out.append((sym, s.get("onboardDate")))
    return out


# -- building the day-t panel from the snapshot --------------------------------------------------------

def _day_frames(day_dir: Path, symbols: list[str], decision_day: pd.Timestamp) -> tuple[dict, dict, dict, dict]:
    """O, C, V (quote volume) indexed by UTC day, and SIG (the frozen funding signal) for `decision_day`
    only -- built the same way core.panel() builds them, but from klines/fundingRate JSON instead of
    the local archive, and only for the trailing window the frozen constants actually need."""
    lookback_start = decision_day - pd.Timedelta(days=c.VOL_LOOKBACK + 5)
    days = pd.date_range(lookback_start, decision_day, freq="D")
    O, C, V, SIG, FIRST = {}, {}, {}, {}, {}
    sig_lo = decision_day - pd.Timedelta(days=c.SIG_DAYS)
    for sym in symbols:
        kl = load_symbol_klines(day_dir, sym)
        if not kl:
            continue
        rows = []
        for row in kl:
            open_time = pd.Timestamp(int(row[0]), unit="ms").normalize()
            if open_time >= decision_day:
                continue  # never use the still-forming candle for the decision day itself
            rows.append((open_time, float(row[1]), float(row[4]), float(row[7])))  # open, close, quote_vol
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=["day", "open", "close", "quote_volume"]).drop_duplicates("day")
        df = df.set_index("day").sort_index().reindex(days)
        O[sym], C[sym], V[sym] = df["open"], df["close"], df["quote_volume"]

        fr = load_symbol_funding(day_dir, sym) or []
        settles = [(pd.Timestamp(int(r["fundingTime"]), unit="ms"), float(r["fundingRate"])) for r in fr]
        settles = [(t, r) for t, r in settles if sig_lo <= t < decision_day]
        SIG[sym] = (sum(r for _, r in settles) / c.SIG_DAYS) if len(settles) >= c.MIN_SETTLE else np.nan
    return O, C, V, SIG


def build_day_panel(day_dir: Path, decision_day: pd.Timestamp, exchange_info: dict) -> tuple[dict, dict]:
    cands = candidate_symbols(exchange_info)
    symbols = [sym for sym, _ in cands]
    onboard = {sym: (pd.Timestamp(int(od), unit="ms").normalize() if od else pd.NaT) for sym, od in cands}
    O, C, V, SIG = _day_frames(day_dir, symbols, decision_day)
    have = sorted(O)  # symbols with at least some klines in the snapshot
    lookback_start = decision_day - pd.Timedelta(days=c.VOL_LOOKBACK + 5)
    days = pd.date_range(lookback_start, decision_day, freq="D")
    Odf = pd.DataFrame({s: O[s] for s in have}, index=days)
    Cdf = pd.DataFrame({s: C[s] for s in have}, index=days)
    Vdf = pd.DataFrame({s: V[s] for s in have}, index=days)
    Sdf = pd.DataFrame({decision_day: {s: SIG.get(s, np.nan) for s in have}}).T
    Sdf = Sdf.reindex(days)
    P = {"O": Odf, "C": Cdf, "V": Vdf, "SIG": Sdf}
    FIRST = {s: onboard[s] for s in have if pd.notna(onboard.get(s))}
    return P, FIRST


# -- day open price for execution (kline open if formed, else premiumIndex mark as a fallback) --------

def day_open_prices(day_dir: Path, symbols: list[str], decision_day: pd.Timestamp) -> dict:
    out = {}
    for sym in symbols:
        kl = load_symbol_klines(day_dir, sym) or []
        found = None
        for row in kl:
            open_time = pd.Timestamp(int(row[0]), unit="ms").normalize()
            if open_time == decision_day:
                found = {"open": float(row[1]), "source": "klines_1d_open"}
                break
        if found is None:
            pi = load_symbol_premium_index(day_dir, sym)
            if pi and pi.get("markPrice") is not None:
                found = {"open": float(pi["markPrice"]), "source": "premiumIndex_markPrice_fallback"}
        out[sym] = found
    return out


# -- driver ---------------------------------------------------------------------------------------------

def decision_weights(day: str, root: Path = RAW_DIR) -> dict:
    """Target weights for `day` (YYYY-MM-DD, UTC) from that day's forward_crypto snapshot.

    Refuses for any day inside or before the locked validation window. Returns weights plus enough
    diagnostics (universe size, provenance hashes of the frozen files, data completeness) to record
    as a decision payload -- this function itself records nothing."""
    decision_day = pd.Timestamp(day)
    if decision_day <= VALIDATION_LOCK_END:
        raise TargetsError(f"{day} is on or before the locked validation window end "
                           f"({VALIDATION_LOCK_END.date()}); forward targets may only be generated for "
                           "genuinely future days")
    day_dir = snapshot_day_dir(day, root)
    ei = load_exchange_info(day_dir)
    P, FIRST = build_day_panel(day_dir, decision_day, ei)
    stock_bases = c.tokenized_stock_bases() if decision_day >= pd.Timestamp("2025-01-01") else set()
    W = c.weights(P, FIRST, day, day, stock_bases=stock_bases)
    row = W.loc[decision_day] if decision_day in W.index else pd.Series(dtype=float)
    nonzero = row[row != 0].dropna()
    longs = sorted(nonzero[nonzero > 0].index)
    shorts = sorted(nonzero[nonzero < 0].index)
    prices = day_open_prices(day_dir, list(nonzero.index), decision_day)
    missing_price = [s for s, v in prices.items() if v is None]
    return {
        "decision_day": day,
        "rule": "research/crypto_funding_xs/PLAN.md (frozen; USDT perp funding cross-section, quintile L/S)",
        "frozen_file_sha256": frozen_provenance(),
        "n_candidate_symbols": len(P["O"].columns),
        "n_with_klines": int(P["C"].notna().any(axis=0).sum()),
        "universe_nan_row": bool(row.empty or row.isna().all()),
        "n_long": len(longs), "n_short": len(shorts),
        "weights": {s: float(w) for s, w in nonzero.items()},
        "open_prices": prices,
        "missing_open_price": missing_price,
        "gross": float(nonzero.abs().sum()), "net": float(nonzero.sum()),
    }


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (UTC), must be a forward (post-lock) day")
    ap.add_argument("--root", type=Path, default=RAW_DIR)
    args = ap.parse_args(argv)
    try:
        out = decision_weights(args.day, args.root)
    except TargetsError as e:
        print(f"REFUSED: {e}")
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
