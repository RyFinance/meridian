"""Development and validation runs for the registered macro-surprise candidates.

  PYTHONPATH=. .venv/bin/python -m research.macro_surprise.evaluate dev
  PYTHONPATH=. .venv/bin/python -m research.macro_surprise.evaluate validation   # needs the unlock

Rules are in research/macro_surprise/PLAN.md (+ PLAN_AMENDMENT_1.md). The development run truncates
prices and the calendar at DEV_END before computing anything. The validation run refuses to start
unless VALIDATION_UNLOCK.md is registered with a matching hash, and only evaluates selected candidates.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.common.inference import deflated_sharpe, sharpe_ci
from research.macro_surprise import signals as sg
from research.return_search.run import cash_rates

ROOT = sg.ROOT
OUT = ROOT / "reports" / "macro_surprise"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN = "research/macro_surprise/PLAN.md"
AMENDMENTS = ["research/macro_surprise/PLAN_AMENDMENT_1.md"]
UNLOCK = "research/macro_surprise/VALIDATION_UNLOCK.md"
PRICE_DIRS = {"EZU": "macro_surprise", "MCHI": "macro_surprise", "INDA": "macro_surprise",
              "EZA": "macro_surprise", "TUR": "macro_surprise", "EIDO": "macro_surprise"}

DEV_SIGNALS = (pd.Timestamp("2015-04-30"), pd.Timestamp("2020-11-30"))
DEV_END = pd.Timestamp("2020-12-31")
VAL_SIGNALS = (pd.Timestamp("2020-12-31"), pd.Timestamp("2026-08-31"))
VAL_END = pd.Timestamp("2026-09-18")

VOL_WINDOW, MIN_HISTORY, MOM_WINDOW = 63, 64, 63
COSTS = {
    "gross": {"per_side": 0.0, "borrow": 0.0, "proceeds_earn_rf": True},
    "base": {"per_side": 0.0010, "borrow": 0.010, "proceeds_earn_rf": True},
    "stress": {"per_side": 0.0030, "borrow": 0.050, "proceeds_earn_rf": False},
}
DEV_GATE_SHARPE, VAL_GATE_SHARPE, ALPHA = 0.50, 0.75, 0.05 / 2
BLOCK, DRAWS, SEED = 21, 5000, 20260923
NW_LAGS = 10
N_TRIALS, TRIAL_SR_SD_ANNUAL = 110, 0.5
BOOKS = ["M1", "M2", "C_EW", "C_MOM"]


# -- guards -----------------------------------------------------------------------------------------
def _registered(path: str) -> bool:
    if not PREREG.exists() or not (ROOT / path).exists():
        return False
    digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    for line in PREREG.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("file") == path and rec.get("sha256") == digest:
            return True
    return False


def frozen_code_ok() -> bool:
    digest = hashlib.sha256(Path(sg.__file__).read_bytes()).hexdigest()
    for line in PREREG.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("file") == AMENDMENTS[-1]:
            return rec.get("signals_code_sha256") == digest
    return False


# -- data -------------------------------------------------------------------------------------------
def load_prices(upto: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    opens, closes = {}, {}
    for econ, (etf, _) in sg.ECONOMIES.items():
        d = pd.read_parquet(ROOT / "data" / PRICE_DIRS.get(etf, "etf_hybrids") / f"{etf}.parquet")
        d.index = pd.to_datetime(d["date"])
        d = d.sort_index().loc[:upto]
        opens[econ], closes[econ] = d["adj_open"], d["adj_close"]
    cal = closes["US"].index
    return pd.DataFrame(opens).reindex(cal), pd.DataFrame(closes).reindex(cal)


def signal_dates(calendar: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    s = pd.Series(calendar, index=calendar)
    last = s.groupby(calendar.to_period("M")).max()
    d = pd.DatetimeIndex(last.to_numpy())
    return d[(d >= start) & (d <= end)]


# -- books ------------------------------------------------------------------------------------------
def _inv_vol(names, vol: pd.Series) -> pd.Series:
    iv = 1.0 / vol[names]
    return iv / iv.sum()


def target_books(score: pd.DataFrame, closes: pd.DataFrame, dates: pd.DatetimeIndex) -> dict[str, dict]:
    """Return {book: {signal_date: weights}}; weights are fractions of NAV (short < 0)."""
    logret = np.log(closes).diff()
    vol = logret.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std()
    hist = closes.notna().cumsum()
    mom = closes / closes.shift(MOM_WINDOW) - 1.0
    order = list(sg.ECONOMIES)
    books: dict[str, dict] = {b: {} for b in BOOKS}
    for t in dates:
        ok = closes.loc[t].notna() & (hist.loc[t] >= MIN_HISTORY) & vol.loc[t].notna()
        z = score.loc[t].where(ok).dropna()
        n = len(z)
        k = n // 3
        zero = pd.Series(0.0, index=order)
        w_ew = zero.copy()
        if n:
            w_ew[z.index] = 1.0 / n
        books["C_EW"][t] = w_ew
        for book, s in (("M1", z), ("C_MOM", mom.loc[t].where(ok).dropna().reindex(z.index))):
            w = zero.copy()
            s = s.dropna()
            if k >= 1 and len(s) >= 3:
                ranked = s.reindex(order).dropna()
                r = ranked.rank(method="first")  # ties -> fixed table order
                top = r.index[r > len(r) - k]
                bot = r.index[r <= k]
                w[top] = _inv_vol(top, vol.loc[t])
                w[bot] = -_inv_vol(bot, vol.loc[t])
            books[book][t] = w
        books["M2"][t] = books["M1"][t].clip(lower=0.0)
    return books


# -- engine -----------------------------------------------------------------------------------------
def simulate(book: dict, opens: pd.DataFrame, closes: pd.DataFrame, rf: pd.Series, cost: dict,
             end: pd.Timestamp) -> pd.DataFrame:
    """Daily marked NAV. Signal close t -> trade at next open; hold units; liquidate at `end` close."""
    cal = closes.index
    pos = {d: i for i, d in enumerate(cal)}
    entries = {}
    for t, w in book.items():
        i = pos[t] + 1
        if i < len(cal) and cal[i] <= end:
            entries[cal[i]] = w
    first = min(entries)
    days = cal[(cal >= first) & (cal <= end)]
    names = closes.columns
    units = pd.Series(0.0, index=names)
    cash, nav_prev, prev_day = 1.0, 1.0, cal[pos[first] - 1]
    rows, contrib_rows = [], []
    for d in days:
        elapsed = (d - prev_day).days
        c_prev = closes.loc[prev_day].fillna(0.0)
        short_val = float(-(units[units < 0] * c_prev[units < 0]).sum())
        interest_base = cash if cost["proceeds_earn_rf"] else cash - short_val
        interest = interest_base * rf.loc[d]
        borrow = short_val * cost["borrow"] * elapsed / 365.0
        cash += interest - borrow
        pnl = pd.Series(0.0, index=names)
        traded = trade_cost = 0.0
        if d in entries:
            o = opens.loc[d]
            held = units != 0
            if held.any() and o[held].isna().any():
                raise ValueError(f"missing open for a held ETF on {d.date()}")
            pnl += (units * (o - c_prev)).where(held, 0.0)
            nav_open = cash + float((units[held] * o[held]).sum())
            w = entries[d].reindex(names).fillna(0.0)
            if o[w != 0].isna().any():
                raise ValueError(f"missing open for a target ETF on {d.date()}")
            target = (w * nav_open / o).where(w != 0, 0.0)
            delta = target - units
            traded = float((delta.abs() * o.fillna(0.0)).sum())
            trade_cost = traded * cost["per_side"]
            cash -= float((delta * o.fillna(0.0)).sum()) + trade_cost
            units = target
            c_now = closes.loc[d]
            pnl += (units * (c_now - o)).where(units != 0, 0.0)
        else:
            c_now = closes.loc[d]
            held = units != 0
            if held.any() and c_now[held].isna().any():
                raise ValueError(f"missing close for a held ETF on {d.date()}")
            pnl += (units * (c_now - c_prev)).where(held, 0.0)
        liq = 0.0
        if d == days[-1]:
            liq = float((units.abs() * closes.loc[d].fillna(0.0)).sum()) * cost["per_side"]
            cash -= liq
        nav = cash + float((units[units != 0] * closes.loc[d][units != 0]).sum())
        gross_long = float((units[units > 0] * closes.loc[d][units > 0]).sum()) / nav
        gross_short = float(-(units[units < 0] * closes.loc[d][units < 0]).sum()) / nav
        rows.append({"date": d, "nav": nav, "return": nav / nav_prev - 1.0, "rf": rf.loc[d],
                     "cost": (trade_cost + liq) / nav_prev, "borrow": borrow / nav_prev,
                     "turnover": traded / nav_prev, "long": gross_long, "short": gross_short})
        contrib_rows.append(pnl / nav_prev)
        nav_prev, prev_day = nav, d
        if d == days[-1]:
            units[:] = 0.0
    out = pd.DataFrame(rows).set_index("date")
    out["excess"] = out["return"] - out["rf"]
    contrib = pd.DataFrame(contrib_rows, index=out.index)
    return out, contrib


# -- statistics -------------------------------------------------------------------------------------
def nw_ols(y: np.ndarray, x: np.ndarray | None, lags: int = NW_LAGS) -> dict:
    """OLS with Newey-West standard errors. x None -> mean only."""
    y = np.asarray(y, float)
    X = np.ones((len(y), 1)) if x is None else np.column_stack([np.ones(len(y)), np.asarray(x, float)])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ beta
    xu = X * u[:, None]
    S = xu.T @ xu
    for L in range(1, lags + 1):
        g = xu[L:].T @ xu[:-L]
        S += (1 - L / (lags + 1)) * (g + g.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(XtX_inv @ S @ XtX_inv))
    return {"coef": beta.tolist(), "t": (beta / se).tolist()}


def block_bootstrap_p(x: np.ndarray, block: int = BLOCK, draws: int = DRAWS, seed: int = SEED) -> float:
    x = np.asarray(x, float)
    n = len(x)
    c = x - x.mean()
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(draws, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(draws, -1)[:, :n] % n
    means = c[idx].mean(axis=1)
    return float((np.sum(means >= x.mean()) + 1) / (draws + 1))


def summarize(f: pd.DataFrame, spy_ex: pd.Series) -> dict:
    r, ex = f["return"], f["excess"]
    nav = (1 + r).cumprod()
    years = len(r) / 252
    dd = nav / nav.cummax() - 1
    sd = ex.std(ddof=1)
    capm = nw_ols(ex.to_numpy(), spy_ex.reindex(ex.index).to_numpy())
    return {
        "days": int(len(r)), "years": years,
        "cagr": float(nav.iloc[-1] ** (1 / years) - 1), "total_return": float(nav.iloc[-1] - 1),
        "excess_sharpe": float(ex.mean() / sd * np.sqrt(252)) if sd > 0 else None,
        "ann_excess_mean": float(ex.mean() * 252), "vol": float(r.std(ddof=1) * np.sqrt(252)),
        "max_dd": float(dd.min()), "annual_turnover": float(f["turnover"].sum() / years),
        "annual_cost_drag": float((f["cost"] + f["borrow"]).sum() / years),
        "avg_long": float(f["long"].mean()), "avg_short": float(f["short"].mean()),
        "mean_nw_t": nw_ols(ex.to_numpy(), None)["t"][0],
        "bootstrap_p_one_sided": block_bootstrap_p(ex.to_numpy()),
        "sharpe_ci95": list(sharpe_ci(ex.to_numpy(), 252, BLOCK, DRAWS, seed=SEED)),
        "spy_alpha_ann": capm["coef"][0] * 252, "spy_alpha_t": capm["t"][0],
        "spy_beta": capm["coef"][1], "spy_beta_t": capm["t"][1],
        "deflated_sharpe_prob": deflated_sharpe(ex.to_numpy(), N_TRIALS, (TRIAL_SR_SD_ANNUAL ** 2) / 252),
        "by_year_return": {int(y): float((1 + g).prod() - 1) for y, g in r.groupby(r.index.year)},
        "by_year_excess_sharpe": {int(y): float(g.mean() / g.std(ddof=1) * np.sqrt(252))
                                  for y, g in ex.groupby(ex.index.year) if len(g) > 20},
    }


def book_exposure(book: dict) -> dict:
    w = pd.DataFrame(book).T
    return {"months": int(len(w)),
            "months_long": {k: int(v) for k, v in (w > 0).sum().items()},
            "months_short": {k: int(v) for k, v in (w < 0).sum().items()},
            "avg_names_long": float((w > 0).sum(axis=1).mean()),
            "avg_names_short": float((w < 0).sum(axis=1).mean())}


# -- runs -------------------------------------------------------------------------------------------
def evaluate(signal_window, end: pd.Timestamp, books_wanted: list[str], folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    opens, closes = load_prices(end)
    rel = sg.releases(upto=end)
    dates = signal_dates(closes.index, *signal_window)
    score, count = sg.diffusion(rel, dates)
    score.to_csv(folder / "signal_z.csv")
    count.to_csv(folder / "signal_counts.csv")
    rf = cash_rates(closes.index, str(end.date()))
    spy_ex = closes["US"].pct_change(fill_method=None) - rf
    books = target_books(score, closes, dates)
    res: dict = {"signal_dates": [str(dates[0].date()), str(dates[-1].date()), int(len(dates))],
                 "return_window_end": str(end.date()),
                 "signals_code_sha256": hashlib.sha256(Path(sg.__file__).read_bytes()).hexdigest(),
                 "books": {}}
    series = {}
    for b in books_wanted:
        pd.DataFrame(books[b]).T.to_csv(folder / f"{b}_targets.csv")
        res["books"][b] = {"exposure": book_exposure(books[b])}
        for label, cost in COSTS.items():
            f, contrib = simulate(books[b], opens, closes, rf, cost, end)
            f.to_csv(folder / f"{b}_{label}_daily.csv")
            res["books"][b][label] = summarize(f, spy_ex)
            series[(b, label)] = f["excess"]
            if label == "base":
                res["books"][b]["contribution_base"] = {k: float(v) for k, v in contrib.sum().items()}
        print(b, {k: round(res["books"][b]["base"][k], 4) for k in
                  ["cagr", "excess_sharpe", "max_dd", "annual_turnover", "annual_cost_drag"]},
              "gross", round(res["books"][b]["gross"]["excess_sharpe"], 3),
              "stress", round(res["books"][b]["stress"]["excess_sharpe"], 3), flush=True)
    if "M1" in books_wanted and "C_MOM" in books_wanted:
        for label in ("base", "stress"):
            reg = nw_ols(series[("M1", label)].to_numpy(),
                         series[("C_MOM", label)].reindex(series[("M1", label)].index).to_numpy())
            res.setdefault("m1_on_cmom", {})[label] = {"alpha_ann": reg["coef"][0] * 252,
                                                       "alpha_t": reg["t"][0], "beta": reg["coef"][1],
                                                       "beta_t": reg["t"][1]}
        res["corr_base"] = pd.DataFrame({b: series[(b, "base")] for b in books_wanted}).corr().round(4).to_dict()
    if "M2" in books_wanted and "C_EW" in books_wanted:
        for label in ("base", "stress"):
            act = (series[("M2", label)] - series[("C_EW", label)].reindex(series[("M2", label)].index)).to_numpy()
            res.setdefault("m2_minus_cew", {})[label] = {
                "ann_mean": float(act.mean() * 252), "nw_t": nw_ols(act, None)["t"][0],
                "info_ratio": float(act.mean() / act.std(ddof=1) * np.sqrt(252)),
                "bootstrap_p_one_sided": block_bootstrap_p(act)}
    return res


def dev_selection(res: dict) -> dict:
    m1 = res["books"]["M1"]
    m1_ok = (m1["base"]["excess_sharpe"] >= DEV_GATE_SHARPE and m1["stress"]["ann_excess_mean"] > 0
             and res["m1_on_cmom"]["base"]["alpha_ann"] > 0)
    m2_ok = m1_ok and res["books"]["M2"]["base"]["excess_sharpe"] > res["books"]["C_EW"]["base"]["excess_sharpe"]
    return {"M1": {"selected": bool(m1_ok), "sharpe_base": m1["base"]["excess_sharpe"],
                   "stress_mean": m1["stress"]["ann_excess_mean"],
                   "alpha_on_cmom": res["m1_on_cmom"]["base"]["alpha_ann"]},
            "M2": {"selected": bool(m2_ok), "sharpe_base": res["books"]["M2"]["base"]["excess_sharpe"],
                   "cew_sharpe_base": res["books"]["C_EW"]["base"]["excess_sharpe"]},
            "selected": [k for k, ok in (("M1", m1_ok), ("M2", m2_ok)) if ok]}


def run(mode: str) -> None:
    if not _registered(PLAN) or not all(_registered(a) for a in AMENDMENTS):
        raise SystemExit("PLAN or amendment not registered with a matching hash")
    if not frozen_code_ok():
        raise SystemExit("signals.py differs from the registered frozen code hash")
    if mode == "dev":
        folder = OUT / "dev"
        if (folder / "results.json").exists():
            raise SystemExit("development already run; results are final")
        res = evaluate(DEV_SIGNALS, DEV_END, BOOKS, folder)
        res["selection"] = dev_selection(res)
        (folder / "results.json").write_text(json.dumps(res, indent=2))
        (folder / "selection.json").write_text(json.dumps(res["selection"], indent=2))
        print("selected:", res["selection"]["selected"])
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked: VALIDATION_UNLOCK.md not registered")
        folder = OUT / "validation"
        if (folder / "results.json").exists():
            raise SystemExit("validation already run once")
        sel = json.loads((OUT / "dev" / "selection.json").read_text())["selected"]
        if not sel:
            raise SystemExit("nothing selected in development")
        res = evaluate(VAL_SIGNALS, VAL_END, sel + ["C_EW", "C_MOM"], folder)
        res["selected_from_dev"] = sel
        (folder / "results.json").write_text(json.dumps(res, indent=2))
    else:
        raise SystemExit("mode must be dev or validation")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
