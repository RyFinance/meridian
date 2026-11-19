"""Conservative SEC-timestamped event study for MSTR BTC-purchase disclosures.

Inputs outside this folder are read-only.  The only files written are derived
events, trade rows, and summaries in this agent_events directory.  Filing
bodies are fetched from SEC on demand and never cached.
"""
from __future__ import annotations

import json
import re
import time
import warnings
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAILY = ROOT / "mstr_daily_yf.parquet"
BTC = Path("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
INPUT = HERE / "sec_purchase_candidates_primary_only.csv"
HEADERS = {"User-Agent": "CCP academic event-study research contact@example.com"}
BASELINE_BP = 3.0
FEE = 0.005
RNG = np.random.default_rng(20261017)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def clean_html(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" ", strip=True))


def get_text(session: requests.Session, url: str) -> tuple[str, str]:
    for n in range(4):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                time.sleep(0.11)
                return r.text, clean_html(r.text)
            if r.status_code in {403, 429, 500, 502, 503}:
                time.sleep(n + 1)
                continue
            raise RuntimeError(f"SEC HTTP {r.status_code}: {url}")
        except requests.RequestException:
            if n == 3:
                raise
            time.sleep(n + 1)
    raise RuntimeError(f"Unretrievable SEC source: {url}")


def table_btc_qty(html: str, filing_day: pd.Timestamp) -> int | None:
    """Return new BTC quantity from the current-period table, including zero.

    Strategy's 2025+ forms report both a weekly table and often a quarterly
    cumulative table.  Select the table with the latest "During Period" date
    not later than the filing date, rather than mistaking an aggregate holding
    or quarterly summary for the current weekly purchase.
    """
    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        return None
    options = []
    date_pat = re.compile(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}")
    for table in tables:
        values = table.fillna("").astype(str)
        flat = " ".join(values.to_numpy().ravel())
        normalized = re.sub(r"\s+", "", flat).lower()
        if "btcacquired" not in normalized and "btcpurchased" not in normalized:
            continue
        dates = pd.to_datetime(date_pat.findall(flat), errors="coerce")
        dates = [d.normalize() for d in dates if not pd.isna(d) and d.normalize() <= filing_day]
        if not dates:
            continue
        qtys = []
        # Find a BTC-Acquired/Purchased header cell and look down its column.
        for col in range(values.shape[1]):
            col_values = values.iloc[:, col].tolist()
            header_rows = [
                i for i, val in enumerate(col_values)
                if "btcacquired" in re.sub(r"\s+", "", val).lower()
                or "btcpurchased" in re.sub(r"\s+", "", val).lower()
            ]
            for header in header_rows:
                for val in col_values[header + 1:]:
                    compact = re.sub(r"\s+", "", val).replace("−", "-")
                    if re.fullmatch(r"[\d,]+", compact):
                        qtys.append(int(compact.replace(",", "")))
                        break
                    if compact in {"-", "—", "–"}:
                        qtys.append(0)
                        break
        if qtys:
            # Duplicated visual columns occur in SEC HTML; all should agree.
            options.append((max(dates), max(qtys)))
    if not options:
        return None
    latest_day = max(day for day, _ in options)
    return max(qty for day, qty in options if day == latest_day)


def narrative_btc_qty(text: str) -> int | None:
    """Extract a current disclosure's stated BTC purchase amount (pre-2025)."""
    patterns = [
        r"announced that.{0,650}?(?:purchased|acquired).{0,90}?([0-9][0-9,]*)\s+(?:additional\s+)?bitcoins?",
        r"completed (?:its )?acquisition of\s+([0-9][0-9,]*)\s+additional\s+bitcoins?",
        r"issued a press release announcing that.{0,500}?purchased.{0,90}?([0-9][0-9,]*)\s+bitcoins?",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return int(m.group(1).replace(",", ""))
    # The 2022-12-28 Item 8.01 uses bullet points rather than "announced
    # that" phrasing.  Restrict this broader fallback to an Other Events 8-K,
    # so an earnings document's historical accounting narrative cannot qualify.
    if "item 8.01" in text.lower():
        bullet_matches = re.findall(
            r"(?:during the period|on\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})"
            r".{0,350}?(?:purchased|acquired)\s+approximately\s+([0-9][0-9,]*)\s+bitcoins?",
            text,
            flags=re.I,
        )
        if bullet_matches:
            return sum(int(v.replace(",", "")) for v in bullet_matches)
    return None


def source_window(text: str) -> str:
    lower = text.lower()
    anchors = [lower.find("btc update"), lower.find("bitcoin holdings update"), lower.find("item 8.01")]
    start = min((x for x in anchors if x >= 0), default=0)
    return text[start:start + 3500]


def funding_label(text: str) -> str:
    window = source_window(text).lower()
    atm = bool(re.search(r"\batm\b|at-the-market|sales agreement|issuance and sale of shares|share sales", window))
    convertible = bool(re.search(r"convertible (?:notes?|note offering)|notes offering", window))
    if atm and convertible:
        return "ATM/equity + convertible explicitly mentioned"
    if atm:
        return "ATM/equity explicitly mentioned"
    if convertible:
        return "convertible explicitly mentioned"
    return "cash/unspecified in current disclosure"


def is_current_filing(text: str, accession: str) -> bool:
    lower = text.lower()
    # All final weekly updates contain BTC Update.  Earlier direct acquisitions
    # were filed under Item 8.01.  The lone 2020 9/15 form reports the 9/14
    # acquisition directly under Item 8.01 but does not use the later phrasing.
    return "btc update" in lower or "bitcoin holdings update" in lower or "item 8.01" in lower or accession == "0001193125-20-245835"


def build_events() -> pd.DataFrame:
    raw = pd.read_csv(INPUT).drop_duplicates("accession").copy()
    raw["filing_date"] = pd.to_datetime(raw["filing_date"])
    raw["acceptance_utc"] = pd.to_datetime(raw["acceptance_utc"], utc=True)
    session = requests.Session()
    rows, failures = [], []
    for n, row in raw.sort_values("filing_date").reset_index(drop=True).iterrows():
        try:
            html, text = get_text(session, row.source_url)
            table_qty = table_btc_qty(html, row.filing_date)
            narrative_qty = narrative_btc_qty(text)
            # Current 2025+ tables are the source of truth.  Else use the
            # direct narrative only when the filing is itself a current 8-K.
            qty = table_qty if table_qty is not None else narrative_qty
            if not is_current_filing(text, row.accession) or qty is None or qty <= 0:
                continue
            acceptance_et = row.acceptance_utc.tz_convert("America/New_York")
            rows.append({
                "filing_date": row.filing_date.date().isoformat(),
                "acceptance_utc": row.acceptance_utc.isoformat(),
                "acceptance_et": acceptance_et.isoformat(),
                "acceptance_et_clock": acceptance_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "accession": row.accession,
                "items": row["items"],
                "purchase_btc": int(qty),
                "funding_label": funding_label(text),
                "source_url": row.source_url,
                "source_method": "SEC EDGAR 8-K primary document; EDGAR acceptanceDateTime",
            })
        except Exception as exc:
            failures.append({"accession": row.accession, "source_url": row.source_url, "error": str(exc)})
        if (n + 1) % 25 == 0:
            print(f"validated source documents {n + 1}/{len(raw)}; positive events={len(rows)}")
    events = pd.DataFrame(rows).drop_duplicates("accession").sort_values("acceptance_utc").reset_index(drop=True)
    pd.DataFrame(failures, columns=["accession", "source_url", "error"]).to_csv(HERE / "event_source_failures.csv", index=False)
    if failures:
        raise RuntimeError(f"{len(failures)} source retrieval/parsing failures; do not run a partial study")
    return events


def map_trade_dates(events: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    dates = pd.DatetimeIndex(daily.index).normalize()
    positions = {d: i for i, d in enumerate(dates)}
    mapped = events.copy()
    entry_dates, entry_locs = [], []
    for _, e in mapped.iterrows():
        et = pd.Timestamp(e["acceptance_utc"]).tz_convert("America/New_York")
        # Acceptance at 16:00:00 or later is treated as after the close.
        proposed = et.tz_localize(None).normalize() + pd.Timedelta(days=0 if et.hour < 16 else 1)
        eligible = dates[dates >= proposed]
        if len(eligible) == 0:
            entry_dates.append(pd.NaT)
            entry_locs.append(np.nan)
        else:
            entry_dates.append(eligible[0])
            entry_locs.append(positions[eligible[0]])
    mapped["entry_date"] = entry_dates
    mapped["entry_loc"] = entry_locs
    return mapped.dropna(subset=["entry_date"]).copy()


def event_trade_rows(events: pd.DataFrame, daily: pd.DataFrame, hold: int, slippage_bp: float = BASELINE_BP) -> pd.DataFrame:
    x = events.copy()
    dates = pd.DatetimeIndex(daily.index).normalize()
    x["exit_loc"] = x["entry_loc"].astype(int) + hold
    x = x.loc[x.exit_loc < len(daily)].copy()
    x["exit_date"] = [dates[i].date().isoformat() for i in x.exit_loc.astype(int)]
    close = daily["Close"].astype(float).to_numpy()
    x["entry_close"] = [close[i] for i in x.entry_loc.astype(int)]
    x["exit_close"] = [close[i] for i in x.exit_loc.astype(int)]
    slip = slippage_bp / 10_000.0
    x["gross_return"] = x.exit_close / x.entry_close - 1.0
    x["net_return"] = ((x.exit_close * (1 - slip) - FEE) / (x.entry_close * (1 + slip) + FEE)) - 1.0
    x["hold_sessions"] = hold
    x["sample"] = np.where(pd.to_datetime(x.entry_date) <= pd.Timestamp("2022-12-31"), "development_2020_2022", "holdout_2023_2026")
    return x


def summary_stats(values: pd.Series) -> dict:
    a = values.dropna().astype(float).to_numpy()
    if len(a) == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "t_stat": np.nan, "boot_ci_low": np.nan, "boot_ci_high": np.nan, "compound_event": np.nan}
    se = np.std(a, ddof=1) / np.sqrt(len(a)) if len(a) > 1 else np.nan
    boot = RNG.choice(a, size=(10_000, len(a)), replace=True).mean(axis=1) if len(a) > 1 else np.array([a[0]])
    return {
        "n": int(len(a)),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "t_stat": float(np.mean(a) / se) if se and se > 0 else np.nan,
        "boot_ci_low": float(np.quantile(boot, 0.025)),
        "boot_ci_high": float(np.quantile(boot, 0.975)),
        "compound_event": float(np.prod(1 + a) - 1),
    }


def episodes(trades: pd.DataFrame, daily: pd.DataFrame, slippage_bp: float = BASELINE_BP) -> tuple[pd.DataFrame, pd.Series]:
    """No-leverage episode implementation and close-to-close equity curve."""
    if trades.empty:
        return pd.DataFrame(), pd.Series(dtype=float)
    t = trades.sort_values(["entry_loc", "exit_loc"]).copy()
    eps = []
    cur = None
    for _, r in t.iterrows():
        if cur is None or int(r.entry_loc) > cur["exit_loc"]:
            if cur is not None:
                eps.append(cur)
            cur = {"entry_loc": int(r.entry_loc), "exit_loc": int(r.exit_loc), "signal_count": 1, "first_entry_date": r.entry_date, "last_signal_date": r.entry_date}
        else:
            cur["exit_loc"] = max(cur["exit_loc"], int(r.exit_loc))
            cur["signal_count"] += 1
            cur["last_signal_date"] = r.entry_date
    if cur is not None:
        eps.append(cur)
    e = pd.DataFrame(eps)
    close = daily["Close"].astype(float).to_numpy()
    dates = pd.DatetimeIndex(daily.index).normalize()
    slip = slippage_bp / 10_000.0
    e["entry_date"] = [dates[i].date().isoformat() for i in e.entry_loc]
    e["exit_date"] = [dates[i].date().isoformat() for i in e.exit_loc]
    e["entry_close"] = [close[i] for i in e.entry_loc]
    e["exit_close"] = [close[i] for i in e.exit_loc]
    e["net_return"] = ((e.exit_close * (1 - slip) - FEE) / (e.entry_close * (1 + slip) + FEE)) - 1.0
    e["gross_return"] = e.exit_close / e.entry_close - 1.0
    e["sample"] = np.where(pd.to_datetime(e.entry_date) <= pd.Timestamp("2022-12-31"), "development_2020_2022", "holdout_2023_2026")

    # Mark-to-market an all-cash $1 portfolio, deducting actual entry/exit costs.
    equity = pd.Series(1.0, index=dates)
    capital = 1.0
    last = 0
    for _, r in e.iterrows():
        entry, exit_ = int(r.entry_loc), int(r.exit_loc)
        equity.iloc[last:entry + 1] = capital
        shares = capital / (close[entry] * (1 + slip) + FEE)
        equity.iloc[entry:exit_] = shares * close[entry:exit_]
        capital = shares * (close[exit_] * (1 - slip) - FEE)
        equity.iloc[exit_] = capital
        last = exit_ + 1
    equity.iloc[last:] = capital
    return e, equity


def portfolio_summary(episodes_df: pd.DataFrame, equity: pd.Series, sample: str) -> dict:
    if episodes_df.empty:
        return {"episodes": 0, "portfolio_total_net": np.nan, "max_drawdown": np.nan}
    subset = episodes_df.loc[episodes_df["sample"] == sample]
    if subset.empty:
        return {"episodes": 0, "portfolio_total_net": np.nan, "max_drawdown": np.nan}
    first = pd.Timestamp(subset.entry_date.min())
    last = pd.Timestamp(subset.exit_date.max())
    curve = equity.loc[(equity.index >= first) & (equity.index <= last)]
    dd = curve / curve.cummax() - 1
    # Reconstruct cash-only compounding from relevant episodes, so that a 2023
    # summary is not contaminated by capital earned/lost in development.
    total = float(np.prod(1 + subset.net_return.to_numpy()) - 1)
    return {"episodes": int(len(subset)), "portfolio_total_net": total, "max_drawdown": float(dd.min())}


def attach_btc_regime(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    btc = pd.read_parquet(BTC, columns=["timestamp", "close"]).sort_values("timestamp")
    # 16:00 New York is the MSTR close and is known before a MOC order.  merge_asof
    # safely uses the last available BTC minute, rather than assuming every minute.
    target = pd.DataFrame({"entry_date": pd.to_datetime(out.entry_date)})
    target["at"] = target.entry_date.dt.tz_localize("America/New_York") + pd.Timedelta(hours=16)
    target["at"] = target["at"].dt.tz_convert("UTC")
    prior = target[["at"]].copy()
    prior["at"] = prior["at"] - pd.Timedelta(days=5)
    b = btc.rename(columns={"timestamp": "at", "close": "btc_close"})
    # The parquet source is datetime64[us, UTC], while pandas constructs the
    # New York-close targets at ns precision; merge_asof requires an exact dtype.
    b["at"] = b["at"].astype("datetime64[ns, UTC]")
    now = pd.merge_asof(target.sort_values("at"), b, on="at", direction="backward", tolerance=pd.Timedelta(minutes=30))
    then = pd.merge_asof(prior.sort_values("at"), b.rename(columns={"btc_close": "btc_close_5d_ago"}), on="at", direction="backward", tolerance=pd.Timedelta(minutes=30))
    # target order is original row order; use positional values to preserve it.
    out["btc_at_entry"] = now.btc_close.to_numpy()
    out["btc_5d_ago"] = then.btc_close_5d_ago.to_numpy()
    out["btc_prior_5d_return"] = out.btc_at_entry / out.btc_5d_ago - 1
    out["btc_regime"] = np.select(
        [out.btc_prior_5d_return.notna() & (out.btc_prior_5d_return <= 0), out.btc_prior_5d_return.notna() & (out.btc_prior_5d_return > 0)],
        ["BTC down/flat prior 5d", "BTC up prior 5d"], default="BTC path unavailable",
    )
    return out


def ordinary_mstr_summary(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.loc[daily.index >= pd.Timestamp("2020-01-01")].copy()
    d["ret"] = d.Close.pct_change()
    d["sample"] = np.where(d.index <= pd.Timestamp("2022-12-31"), "development_2020_2022", "holdout_2023_2026")
    rows = []
    for sample, g in d.groupby("sample"):
        r = summary_stats(g.ret)
        r.update({"sample": sample, "buy_hold_total": float(g.Close.iloc[-1] / g.Close.iloc[0] - 1), "first_date": g.index.min().date().isoformat(), "last_date": g.index.max().date().isoformat()})
        rows.append(r)
    return pd.DataFrame(rows)


def weekday_matched_mstr_benchmark(events: pd.DataFrame, daily: pd.DataFrame, hold: int, code: str) -> pd.DataFrame:
    """Non-event MSTR forward returns, stratified to the signal weekday mix.

    The later weekly filing regime is overwhelmingly Monday-based.  A simple
    all-days average would therefore be a weak comparator.  This is a benchmark
    only (not an additional rule): it asks whether holding ordinary MSTR over
    same-weekday windows did at least as well, under the same execution cost.
    """
    dates = pd.DatetimeIndex(daily.index).normalize()
    close = daily["Close"].astype(float).to_numpy()
    candidate = pd.DataFrame({"entry_loc": np.arange(len(daily) - hold, dtype=int)})
    candidate["entry_date"] = dates[candidate.entry_loc]
    candidate["exit_loc"] = candidate.entry_loc + hold
    candidate["weekday"] = candidate.entry_date.dt.dayofweek
    candidate["sample"] = np.where(candidate.entry_date <= pd.Timestamp("2022-12-31"), "development_2020_2022", "holdout_2023_2026")
    slip = BASELINE_BP / 10_000.0
    candidate["net_return"] = ((close[candidate.exit_loc] * (1 - slip) - FEE) / (close[candidate.entry_loc] * (1 + slip) + FEE)) - 1.0
    event_entry = pd.to_datetime(events.entry_date)
    candidate = candidate.loc[(candidate.entry_date >= pd.Timestamp("2020-01-01")) & ~candidate.entry_date.isin(event_entry)].copy()
    signal = event_trade_rows(events, daily, hold, BASELINE_BP)
    rows = []
    for sample, sig in signal.groupby("sample"):
        pool = candidate.loc[candidate["sample"] == sample]
        pieces = []
        for weekday, gsig in sig.groupby(pd.to_datetime(sig.entry_date).dt.dayofweek):
            gpool = pool.loc[pool.weekday == weekday, "net_return"].to_numpy()
            if len(gpool) == 0:
                continue
            # Give each weekday its observed event frequency, rather than its
            # number of calendar observations.
            pieces.extend([gpool] * len(gsig))
        if not pieces:
            continue
        # A stratified bootstrap samples one ordinary-MSTR window per actual
        # signal, preserving the filing weekday distribution.
        boot = np.zeros(10_000)
        for p in pieces:
            boot += RNG.choice(p, size=10_000, replace=True)
        boot /= len(pieces)
        means = [p.mean() for p in pieces]
        rows.append({
            "rule": code,
            "sample": sample,
            "event_n": int(len(sig)),
            "non_event_candidate_days": int(len(pool)),
            "weekday_matched_net_mean": float(np.mean(means)),
            "weekday_matched_boot_ci_low": float(np.quantile(boot, .025)),
            "weekday_matched_boot_ci_high": float(np.quantile(boot, .975)),
            "weekday_matched_net_median_of_weekday_means": float(np.median(means)),
        })
    return pd.DataFrame(rows)


def run() -> None:
    events = build_events()
    daily = pd.read_parquet(DAILY).sort_index()
    events = map_trade_dates(events, daily)
    events.to_csv(HERE / "validated_purchase_events.csv", index=False)
    print(f"validated positive purchase events: {len(events)} (dev={(pd.to_datetime(events.entry_date) <= pd.Timestamp('2022-12-31')).sum()}, holdout={(pd.to_datetime(events.entry_date) > pd.Timestamp('2022-12-31')).sum()})")

    all_summaries, annual, cost_rows, regime_rows, funding_rows, matched_rows = [], [], [], [], [], []
    for hold, code in [(1, "P1"), (5, "P5")]:
        baseline_trades = event_trade_rows(events, daily, hold, BASELINE_BP)
        with_btc = attach_btc_regime(baseline_trades)
        with_btc.to_csv(HERE / f"{code.lower()}_event_trades.csv", index=False)
        eps, equity = episodes(baseline_trades, daily, BASELINE_BP)
        eps.to_csv(HERE / f"{code.lower()}_episodes.csv", index=False)
        equity.rename("equity").to_frame().to_csv(HERE / f"{code.lower()}_equity_curve.csv")
        matched_rows.append(weekday_matched_mstr_benchmark(events, daily, hold, code))
        for sample, g in with_btc.groupby("sample"):
            row = summary_stats(g.net_return)
            row.update({"rule": code, "sample": sample, **portfolio_summary(eps, equity, sample)})
            all_summaries.append(row)
            for year, gy in g.groupby(pd.to_datetime(g.entry_date).dt.year):
                ar = summary_stats(gy.net_return)
                ar.update({"rule": code, "sample": sample, "entry_year": int(year)})
                annual.append(ar)
            for regime, gr in g.groupby("btc_regime"):
                rr = summary_stats(gr.net_return)
                rr.update({"rule": code, "sample": sample, "btc_regime": regime})
                regime_rows.append(rr)
            for funding, gf in g.groupby("funding_label"):
                fr = summary_stats(gf.net_return)
                fr.update({"rule": code, "sample": sample, "funding_label": funding})
                funding_rows.append(fr)
        for bp in (3, 10, 20):
            ct = event_trade_rows(events, daily, hold, bp)
            ce, _ = episodes(ct, daily, bp)
            for sample, g in ct.groupby("sample"):
                cr = summary_stats(g.net_return)
                cr.update({"rule": code, "sample": sample, "per_side_slippage_bp": bp, "fee_per_share": FEE, "episodes": int((ce["sample"] == sample).sum()), "portfolio_total_net": float(np.prod(1 + ce.loc[ce["sample"] == sample, "net_return"]) - 1) if (ce["sample"] == sample).any() else np.nan})
                cost_rows.append(cr)

    pd.DataFrame(all_summaries).to_csv(HERE / "rule_summary.csv", index=False)
    pd.DataFrame(annual).to_csv(HERE / "annual_splits.csv", index=False)
    pd.DataFrame(cost_rows).to_csv(HERE / "cost_sensitivity.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(HERE / "btc_regime_splits.csv", index=False)
    pd.DataFrame(funding_rows).to_csv(HERE / "funding_label_splits.csv", index=False)
    pd.concat(matched_rows, ignore_index=True).to_csv(HERE / "weekday_matched_mstr_benchmark.csv", index=False)
    ordinary_mstr_summary(daily).to_csv(HERE / "ordinary_mstr_benchmark.csv", index=False)
    manifest = {
        "run_date": "2026-10-17",
        "source": "SEC EDGAR primary 8-K documents and EDGAR acceptanceDateTime; source URLs recorded per event",
        "price_source": str(DAILY),
        "btc_source": str(BTC),
        "frozen_rules": str(HERE / "FROZEN_RULES.md"),
        "costs": {"per_side_slippage_bp": BASELINE_BP, "per_share_each_side": FEE},
        "development": "2020-2022", "holdout": "2023-2026", "btc_data_last_timestamp": "derived in input dataset; post-2026-08-11 marked unavailable",
        "validated_event_count": int(len(events)),
    }
    (HERE / "event_study_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    run()
