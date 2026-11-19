#!/usr/bin/env python3
"""Forward paper-test runner for the frozen mNAV M1 rule (FORWARD_PLAN_M1.md).

Study registration: FORWARD_PLAN_M1.md + this file are registered together in
research/preregistrations.jsonl (kind forward_paper_test) BEFORE the first
forward session (2026-10-19).  Research only; never submits orders.

What it does, per run:
  1. Rebuilds the frozen proxy/panel (mnav_core.build_panel) from the same
     sources: mstr_daily_yf.parquet, the BTC-Acum 1-minute file, and the
     cached 10-Q/10-K documents.  Optionally refreshes the filing cache from
     SEC submissions JSON; any fetch/parse problem falls back to the cache.
  2. Recomputes the frozen M1 signal (p_t - p_{t-10} > 0 and p_t > SMA50),
     exactly the registered spec.
  3. Simulates the paper book from 2026-10-19: signal after close t, position
     at open t+1, marks at each close (nav, bench_nav).  Base costs
     3 bp/side + $0.005/share.  Benchmark: MSTR buy-and-hold, same window.
  4. Writes forward_m1_marks.csv for the whole forward window.  Idempotent:
     previously written marks must reproduce bit-for-bit (to 1e-12), else the
     run fails loudly for investigation instead of silently rewriting history.
  5. Prints descriptive-only stats (no gate exists; nothing is promoted).

Data duties (manual, disclosed in the plan): refresh mstr_daily_yf.parquet and
the BTC 1-minute file before scoring.  This runner never edits them.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from mnav_core import (
    MSTR_DAILY,
    ROOT,
    build_panel,
    observations_from_filings,
    premium_trend_signal,
)

FWD_START = "2026-10-19"
WARMUP_START = "2022-01-03"
MARKS = ROOT / "forward_m1_marks.csv"
FORWARD_DIR = ROOT / "sec_source" / "forward_filings"
FORWARD_MANIFEST = FORWARD_DIR / "MANIFEST.json"
DEV_MANIFEST = ROOT / "sec_source" / "dev_filings" / "MANIFEST.json"
HOLDOUT_MANIFEST = ROOT / "sec_source" / "holdout_filings" / "MANIFEST.json"
SUBMISSIONS_CACHE = ROOT / "sec_source" / "submissions.json"
CIK = 1050446
SLIP = 3.0 / 10_000.0
COMMISSION = 0.005
SEED = 20260817
DRAWS = 2000
BLOCK = 21.0
HEADERS = {"User-Agent": "CCP academic forward paper test contact@example.com"}
PRECISION = 1e-12


def get(session: requests.Session, url: str, *, is_json: bool = False):
    for n in range(4):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                time.sleep(0.11)
                return r.json() if is_json else r.content
            if r.status_code in {403, 429, 500, 502, 503}:
                time.sleep(n + 1)
                continue
            raise RuntimeError(f"SEC HTTP {r.status_code}: {url}")
        except requests.RequestException:
            if n == 3:
                raise
            time.sleep(n + 1)
    raise RuntimeError(f"Unretrievable SEC source: {url}")


def refresh_filings() -> str:
    """Best-effort fetch of new 10-Q/10-K filings into sec_source/forward_filings.

    Returns a status string.  Never raises: on any problem the cached manifests
    are used unchanged (the plan's disclosed manual data duty then applies).
    """
    cached = []
    for manifest in (DEV_MANIFEST, HOLDOUT_MANIFEST, FORWARD_MANIFEST):
        if manifest.exists():
            cached += json.loads(manifest.read_text())
    newest_cached = max(pd.Timestamp(r["filing_date"]) for r in cached)

    try:
        session = requests.Session()
        try:
            sub = get(session, f"https://data.sec.gov/submissions/CIK{CIK:010d}.json", is_json=True)
        except Exception:
            sub = json.loads(SUBMISSIONS_CACHE.read_text())
            print("submissions fetch failed; using cached submissions.json", file=sys.stderr)
        recent = sub["filings"]["recent"]
        fresh = [
            {"form": f, "filing_date": fd, "report_date": rd, "accession": acc, "primary_document": doc}
            for f, fd, rd, acc, doc in zip(
                recent["form"], recent["filingDate"], recent["reportDate"],
                recent["accessionNumber"], recent["primaryDocument"],
            )
            if f in {"10-Q", "10-K"} and pd.Timestamp(fd) > newest_cached
        ]
        if not fresh:
            return "no new filings"
        fresh.sort(key=lambda r: r["filing_date"])
        FORWARD_DIR.mkdir(exist_ok=True)
        added = []
        for rec in fresh:
            accession_nodash = rec["accession"].replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_nodash}/"
                   f"{rec['primary_document']}")
            body = get(session, url)
            name = f"{rec['filing_date']}_{rec['form']}_{rec['accession']}.html"
            (FORWARD_DIR / name).write_bytes(body)
            record = {
                "form": rec["form"], "filing_date": rec["filing_date"], "report_date": rec["report_date"],
                "accession": rec["accession"], "primary_document": rec["primary_document"],
                "url": url, "file": name, "sha256": hashlib.sha256(body).hexdigest(),
            }
            added.append(record)
        # Parse every added record before committing the manifest, so a wording
        # change in a future filing cannot half-import silently.
        manifest = json.loads(FORWARD_MANIFEST.read_text()) if FORWARD_MANIFEST.exists() else []
        try:
            manifest.extend(added)
            trial_path = FORWARD_DIR / "MANIFEST.trial.json"
            trial_path.write_text(json.dumps(manifest, indent=2) + "\n")
            observations_from_filings(trial_path)  # raises ValueError if unparsable
            trial_path.unlink()
        except Exception as exc:
            (FORWARD_DIR / "MANIFEST.trial.json").unlink(missing_ok=True)
            return f"new filings not imported (parse check failed: {exc}); using cache"
        FORWARD_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        return f"imported {len(added)} new filing(s)"
    except Exception as exc:
        return f"refresh failed ({exc}); using cache"


def stationarity_bootstrap_p(rs: np.ndarray, rb: np.ndarray, rng: np.random.Generator) -> dict:
    n = len(rs)
    p = 1.0 / BLOCK
    diffs = np.empty(DRAWS)
    wins = 0
    for b in range(DRAWS):
        idx = np.empty(n, dtype=int)
        i = int(rng.integers(0, n))
        for t in range(n):
            idx[t] = i
            i = int(rng.integers(0, n)) if rng.random() < p else (i + 1) % n
        d = _sr(rs[idx]) - _sr(rb[idx])
        diffs[b] = d
        wins += int(d > 0)
    return {"p_diff_gt_0": wins / DRAWS, "q05": float(np.quantile(diffs, 0.05)), "q95": float(np.quantile(diffs, 0.95))}


def _sr(x: np.ndarray) -> float:
    s = np.asarray(x, dtype=float).std(ddof=1)
    return float(np.sqrt(252.0) * np.mean(x) / s) if s > 0 else float("nan")


def simulate_forward(fwd: pd.DataFrame, desired: pd.Series) -> pd.DataFrame:
    cash, shares = 1.0, 0.0
    bench_comm = COMMISSION
    bench_shares = 1.0 / (float(fwd.iloc[0].mstr_open) * (1 + SLIP) + bench_comm)
    rows = []
    for i, (date, row) in enumerate(fwd.iterrows()):
        want_long = bool(desired.iloc[i])
        price = float(row.mstr_open)
        if want_long and shares == 0:
            cash, shares = 0.0, cash / (price * (1 + SLIP) + COMMISSION)
        elif not want_long and shares > 0:
            cash, shares = shares * (price * (1 - SLIP) - COMMISSION), 0.0
        rows.append({
            "date": date.date().isoformat(),
            "signal_prior_close": int(want_long),
            "long_after_open": int(shares > 0),
            "nav": cash + shares * float(row.mstr_close),
            "bench_nav": bench_shares * float(row.mstr_close),
            "btc_gap_session": int(pd.isna(row.btc_close_4pm_et)),
        })
    return pd.DataFrame(rows)


def main() -> None:
    frozen = json.loads((ROOT / "FROZEN_RULES.json").read_text())
    m1 = next(r for r in frozen["rules"] if r["id"] == "M1")
    assert (m1["premium_momentum_days_L"], m1["premium_sma_days_S"], m1["btc_momentum_days"]) == (10, 50, None)

    status = refresh_filings()
    print(f"filing refresh: {status}")
    manifests = [p for p in (DEV_MANIFEST, HOLDOUT_MANIFEST, FORWARD_MANIFEST) if p.exists()]
    obs = sorted(
        (o for p in manifests for o in observations_from_filings(p)),
        key=lambda o: o.filing_date,
    )
    last_filing = max(pd.Timestamp(o.filing_date) for o in obs)

    price = pd.read_parquet(MSTR_DAILY).sort_index()
    end = pd.DatetimeIndex(price.index).normalize().max().date().isoformat()
    panel = build_panel(obs, start=WARMUP_START, end=end)
    signal = premium_trend_signal(
        panel,
        premium_momentum_days=m1["premium_momentum_days_L"],
        premium_sma_days=m1["premium_sma_days_S"],
        btc_momentum_days=m1["btc_momentum_days"],
    )
    fwd = panel.loc[FWD_START:].copy()
    if (pd.Timestamp(end) - last_filing).days > 100:
        print(f"WARNING: newest cached filing {last_filing.date()} is >100 days old; "
              f"quarterly observation may be missing (manual data duty).", file=sys.stderr)

    if len(fwd) == 0:
        if not MARKS.exists():
            MARKS.write_text("date,signal_prior_close,long_after_open,nav,bench_nav,btc_gap_session\n")
            print(f"no forward sessions yet (price data ends {end}); initialized {MARKS.name} header")
        else:
            print(f"no forward sessions yet (price data ends {end}); {MARKS.name} unchanged")
        return

    desired = signal.shift(1).reindex(fwd.index).fillna(False).astype(bool)
    new = simulate_forward(fwd, desired)

    if MARKS.exists():
        old = pd.read_csv(MARKS)
        if len(old) > 0:
            merged = new.merge(old, on="date", suffixes=("_new", "_old"))
            if len(merged) != len(old):
                raise SystemExit("idempotence failure: previously marked dates missing from recomputation")
            for col in ("nav", "bench_nav"):
                delta = (merged[f"{col}_new"] - merged[f"{col}_old"]).abs().max()
                if delta > PRECISION:
                    raise SystemExit(
                        f"idempotence failure: {col} changed by up to {delta:.3g} on previously "
                        f"marked dates; upstream data was revised - investigate before continuing")
    new.to_csv(MARKS, index=False)
    print(f"wrote {len(new)} marks to {MARKS.name}; window {new.date.iloc[0]}..{new.date.iloc[-1]}")

    if len(new) >= 2:
        nav = new.set_index("date")["nav"].astype(float)
        rb = new.set_index("date")["bench_nav"].astype(float)
        nav_ret = nav.to_numpy() / np.concatenate([[1.0], nav.to_numpy()[:-1]]) - 1.0
        rb_ret = rb.to_numpy() / np.concatenate([[1.0], rb.to_numpy()[:-1]]) - 1.0
        rng = np.random.default_rng(SEED)
        boot = stationarity_bootstrap_p(nav_ret, rb_ret, rng)
        print("DESCRIPTIVE ONLY (no gate; nothing is promoted without a separately "
              "registered validation and user sign-off):")
        print(f"  paper book: total {nav.iloc[-1] - 1:+.2%}  maxDD {(nav / nav.cummax() - 1).min():.1%}  "
              f"time long {new.long_after_open.mean():.2f}  btc gap sessions {new.btc_gap_session.sum()}")
        print(f"  benchmark:  total {rb.iloc[-1] - 1:+.2%}")
        print(f"  block-bootstrap SR diff (21-session blocks, {DRAWS} draws, seed {SEED}): "
              f"P(D>0)={boot['p_diff_gt_0']:.3f} q05={boot['q05']:+.3f} q95={boot['q95']:+.3f}")


if __name__ == "__main__":
    main()
