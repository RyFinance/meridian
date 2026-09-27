"""Batched (many-world) re-implementations of three of the project's evaluation engines.

Each engine reproduces a registered engine's accounting exactly, but runs W null worlds at once by
vectorising across worlds (the day or week loop stays). Exactness against the original code is
checked in tests/test_null_lab.py and by `verify_*` below, which feed the same null signals to the
project's own functions and compare daily/weekly returns (tolerance 1e-10).

  CountryEngine  research/macro_surprise/evaluate.py: target_books (M1 construction) + simulate.
                 14 country ETFs, monthly long top-third / short bottom-third, inverse-vol legs,
                 next-open trades, daily marking, base/stress COSTS, cash_rates.
  StockEngine    research/options_signals/evaluate.py: target_weights + backtest. 100-name OPRA
                 universe, weekly quintile long-short, open-to-open, base/stress COSTS.
  TimingEngine   single-asset timing, two books:
                   'spy_cash'  SPY vs cash with research/return_search/run.execute accounting
                               (long-only, monthly decisions, next-open, 5/15 bps, cash_rates);
                   'spy_ief'   SPY-IEF spread with research/rebalancing/evaluate.backtest
                               accounting (daily, 2/6 bps per side per leg).

Null worlds never see a real (unshifted) signal: engines only take signal arrays from the lab's
generators. The country engine refuses a panel equal to the real macro-surprise signal on its locked
validation dates.

Return-path nulls: `paths` is an int array (W, D) of source-day indices into the engine's own
calendar (from generators.stationary_bootstrap). Synthetic prices are rebuilt by chaining the source
days' close-to-close and close-to-open moves; the calendar, cash rates and elapsed days stay those of
the real calendar.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ANN_DAILY = 252
ANN_WEEKLY = 52


# ==================================================================================================
# shared helpers
# ==================================================================================================
def stable_ranks(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ranks 1..n along the last axis for finite entries, ties by position (pandas method='first');
    NaN entries get ranks > n. Returns (ranks, n)."""
    finite = np.isfinite(x)
    key = np.where(finite, x, np.inf)
    order = np.argsort(key, axis=-1, kind="stable")
    ranks = np.empty(x.shape, dtype=float)
    np.put_along_axis(ranks, order, np.broadcast_to(np.arange(1, x.shape[-1] + 1, dtype=float), x.shape), axis=-1)
    return ranks, finite.sum(axis=-1)


def sharpe(x: np.ndarray, periods: int) -> np.ndarray:
    """Row-wise annualised mean/sd (ddof=1)."""
    x = np.asarray(x, float)
    sd = x.std(axis=-1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sd > 0, x.mean(axis=-1) / sd * np.sqrt(periods), np.nan)


def _chain_prices(close: np.ndarray, open_: np.ndarray, src: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic (D, N) close/open paths: day 0 real; day j>=1 uses source day src[j] (>= 1) moves."""
    lc = np.log(close)
    step = lc[src] - lc[src - 1]                      # close-to-close log move of the source day
    gap = np.log(open_[src]) - lc[src - 1]            # previous close -> open log move
    step[0] = 0.0
    lcs = lc[0] + np.cumsum(step, axis=0)
    c = np.exp(lcs)
    o = np.empty_like(c)
    o[0] = open_[0]
    o[1:] = np.exp(lcs[:-1] + gap[1:])
    return c, o


def bootstrap_source(paths: np.ndarray) -> np.ndarray:
    """Map generator indices in [0, D-1) to source days in [1, D) (day 0 has no prior close)."""
    return paths + 1


# ==================================================================================================
# Country ETF long-short (macro_surprise)
# ==================================================================================================
@dataclass
class Window:
    name: str
    sig_idx: np.ndarray          # positions of the window's signal dates in the engine's signal grid
    entry_day: np.ndarray        # calendar positions of the entry day for each signal date
    end_day: int                 # calendar position of the last return day
    first_day: int = field(init=False)

    def __post_init__(self):
        self.first_day = int(self.entry_day[0])


class CountryEngine:
    """macro_surprise M1 book on null signals. Signal grid = the 137 month-ends 2015-04 .. 2026-08."""
    name = "country_ls"
    periods = ANN_DAILY
    START = pd.Timestamp("2014-10-01")    # every ETF trades from here; >= 64 sessions before 2015-04-30

    def __init__(self):
        from research.macro_surprise import evaluate as ev
        from research.return_search.run import cash_rates
        self.ev = ev
        opens, closes = ev.load_prices(ev.VAL_END)
        rf_full = cash_rates(closes.index, str(ev.VAL_END.date()))
        self.full_opens, self.full_closes, self.full_rf = opens, closes, rf_full
        cal = closes.index[closes.index >= self.START]
        self.cal = cal
        self.O = opens.loc[cal].to_numpy(float)
        self.C = closes.loc[cal].to_numpy(float)
        if not (np.isfinite(self.O).all() and np.isfinite(self.C).all()):
            raise ValueError("country panel has gaps after START")
        self.rf = rf_full.loc[cal].to_numpy(float)
        self.elapsed = np.r_[1, np.diff(cal.values).astype("timedelta64[D]").astype(int)]
        self.names = list(closes.columns)
        self.sig_dates = ev.signal_dates(closes.index, ev.DEV_SIGNALS[0], ev.VAL_SIGNALS[1])
        pos = {d: i for i, d in enumerate(cal)}
        self.sig_pos = np.array([pos[d] for d in self.sig_dates])
        self.windows = {}
        for wname, (lo, hi), end in (("dev", ev.DEV_SIGNALS, ev.DEV_END), ("val", ev.VAL_SIGNALS, ev.VAL_END)):
            end_day = int(np.searchsorted(cal.values, np.datetime64(end), side="right") - 1)
            idx = np.flatnonzero((self.sig_dates >= lo) & (self.sig_dates <= hi))
            entry = self.sig_pos[idx] + 1
            keep = entry <= end_day
            self.windows[wname] = Window(wname, idx[keep], entry[keep], end_day)
        self._real = None

    # -- signal ------------------------------------------------------------------------------------
    def real_signal(self) -> np.ndarray:
        """(137, 14) registered macro-surprise score. Only ever used as raw material for nulls."""
        if self._real is None:
            sg = __import__("research.macro_surprise.signals", fromlist=["x"])
            rel = sg.releases(upto=self.ev.VAL_END)
            score, _ = sg.diffusion(rel, self.sig_dates)
            self._real = score.to_numpy(float)
        return self._real

    def _guard(self, signals: np.ndarray) -> None:
        if self._real is None:
            return
        val = self.windows["val"].sig_idx
        real = np.nan_to_num(self._real[val], nan=-999.0)
        for s in signals:
            if np.array_equal(np.nan_to_num(s[val], nan=-999.0), real):
                raise RuntimeError("refusing to evaluate the real macro signal in its locked validation window")

    # -- prices ------------------------------------------------------------------------------------
    def prices(self, paths: np.ndarray | None, w: int) -> tuple[np.ndarray, np.ndarray]:
        if paths is None:
            return self.O[None], self.C[None]
        src = bootstrap_source(paths)
        if src.shape[1] != len(self.cal):
            raise ValueError("path length must equal the calendar length")
        O = np.empty((len(src),) + self.O.shape)
        C = np.empty_like(O)
        for i, s in enumerate(src):
            C[i], O[i] = _chain_prices(self.C, self.O, s)
        return O, C

    def vol_at_signals(self, C: np.ndarray) -> np.ndarray:
        """63-session std (ddof=1) of daily log returns ending at each signal date: (Wp, K, N)."""
        L = self.ev.VOL_WINDOW
        out = np.empty((C.shape[0], len(self.sig_pos), C.shape[2]))
        for k, p in enumerate(self.sig_pos):
            seg = np.log(C[:, p - L:p + 1])
            out[:, k] = np.diff(seg, axis=1).std(axis=1, ddof=1)
        return out

    # -- books -------------------------------------------------------------------------------------
    @staticmethod
    def ls_weights(score: np.ndarray, vol: np.ndarray) -> np.ndarray:
        """M1: long top floor(n/3), short bottom floor(n/3), inverse-vol within each leg.
        score (W, K, N) with NaN = ineligible; vol broadcastable to it."""
        ranks, n = stable_ranks(score)
        k = n // 3
        finite = np.isfinite(score)
        top = finite & (ranks > (n - k)[..., None])
        bot = finite & (ranks <= k[..., None])
        iv = 1.0 / np.broadcast_to(vol, score.shape)
        wt = np.where(top, iv, 0.0)
        wb = np.where(bot, iv, 0.0)
        st, sb = wt.sum(-1, keepdims=True), wb.sum(-1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            w = np.where(st > 0, wt / st, 0.0) - np.where(sb > 0, wb / sb, 0.0)
        valid = (k >= 1) & (n >= 3)
        return np.where(valid[..., None], w, 0.0)

    # -- simulate ----------------------------------------------------------------------------------
    def simulate(self, weights: np.ndarray, O: np.ndarray, C: np.ndarray, window: Window, cost: dict) -> np.ndarray:
        """weights (W, K_window, N) at the window's signal dates -> daily excess returns (W, days)."""
        W = weights.shape[0]
        ps, b, pr = cost["per_side"], cost["borrow"], cost["proceeds_earn_rf"]
        days = np.arange(window.first_day, window.end_day + 1)
        entry = {int(d): j for j, d in enumerate(window.entry_day)}
        units = np.zeros((W, O.shape[2]))
        cash = np.ones(W)
        nav_prev = np.ones(W)
        out = np.empty((W, len(days)))
        for j, d in enumerate(days):
            c_prev = C[:, d - 1]
            short_val = -(np.minimum(units, 0.0) * c_prev).sum(1)
            base = cash if pr else cash - short_val
            cash = cash + (base * self.rf[d] - short_val * b * self.elapsed[d] / 365.0)
            if d in entry:
                o = O[:, d]
                nav_open = cash + (units * o).sum(1)
                target = weights[:, entry[d]] * nav_open[:, None] / o
                delta = target - units
                tc = (np.abs(delta) * o).sum(1) * ps
                cash = cash - ((delta * o).sum(1) + tc)
                units = target
            c_now = C[:, d]
            if d == window.end_day:
                cash = cash - (np.abs(units) * c_now).sum(1) * ps
            nav = cash + (units * c_now).sum(1)
            out[:, j] = nav / nav_prev - 1.0
            nav_prev = nav
        return out - self.rf[days][None, :]

    def run(self, signals: np.ndarray, paths: np.ndarray | None = None,
            windows=("dev", "val"), costs=("base", "stress")) -> dict:
        """signals (W, 137, 14) null scores -> {(window, cost): (W, days) daily excess returns}."""
        self._guard(signals)
        W = signals.shape[0]
        O, C = self.prices(paths, W)
        vol = self.vol_at_signals(C)
        wts = self.ls_weights(signals, vol)
        out = {}
        for wn in windows:
            win = self.windows[wn]
            for cn in costs:
                out[(wn, cn)] = self.simulate(wts[:, win.sig_idx], O, C, win, self.ev.COSTS[cn])
        return out

    # -- exactness check against the project's own functions -----------------------------------------
    def reference(self, signal: np.ndarray, window: str, cost: str) -> np.ndarray:
        """Project code path (target_books + simulate) for ONE null signal on the real price path."""
        ev = self.ev
        score = pd.DataFrame(signal, index=self.sig_dates, columns=self.names)
        win = self.windows[window]
        dates = self.sig_dates[win.sig_idx]
        books = ev.target_books(score, self.full_closes, dates)
        end = self.cal[win.end_day]
        f, _ = ev.simulate(books["M1"], self.full_opens, self.full_closes, self.full_rf, ev.COSTS[cost], end)
        return f["excess"].to_numpy()


# ==================================================================================================
# Stock quintile long-short (options_signals)
# ==================================================================================================
class StockEngine:
    """options_signals weekly quintile book on the 100-name universe (all complete from 2014-06)."""
    name = "stock_ls"
    periods = ANN_WEEKLY
    START = pd.Timestamp("2014-06-02")

    def __init__(self):
        from research.options_signals import evaluate as ev
        from research.options_signals import signals as osg
        self.ev = ev
        names = ev.universe()
        price_upto = ev.VAL_END + pd.Timedelta(days=14)
        opens, closes = ev.load_opens(names, price_upto)
        calendar = opens.index[opens.notna().sum(axis=1) > len(names) // 2]
        opens, closes = opens.reindex(calendar), closes.reindex(calendar)
        self.full_opens, self.full_closes, self.full_cal = opens, closes, calendar
        ff = osg.french_daily()
        self.full_rf = ff["rf"].reindex(calendar.union(ff.index)).ffill().reindex(calendar)
        cal = calendar[calendar >= self.START]
        self.cal = cal
        self.O = opens.loc[cal].to_numpy(float)
        self.C = closes.loc[cal].to_numpy(float)
        if not (np.isfinite(self.O).all() and np.isfinite(self.C).all()):
            raise ValueError("stock panel has gaps after START")
        self.names = names
        rf = self.full_rf.loc[cal].to_numpy(float)
        # signal grid: registered weekly dates of both windows (plus each window's exit-defining date)
        self.windows = {}
        grid = []
        spec = {"dev": (ev.DEV_START, ev.DEV_END), "val": (ev.VAL_START, ev.VAL_END)}
        per = {}
        for wn, (lo, hi) in spec.items():
            d = ev.window_signal_dates(calendar, lo, hi, hi + pd.Timedelta(days=14))
            per[wn] = d
            grid.extend(d)
        self.sig_dates = pd.DatetimeIndex(sorted(set(grid)))
        gpos = {d: i for i, d in enumerate(self.sig_dates)}
        cpos = {d: i for i, d in enumerate(cal)}
        for wn, d in per.items():
            e, x, sidx = [], [], []
            for k in range(len(d) - 1):
                t, tn = d[k], d[k + 1]
                if cpos[t] + 1 >= len(cal) or cpos[tn] + 1 >= len(cal):
                    break
                e.append(cpos[t] + 1)
                x.append(cpos[tn] + 1)
                sidx.append(gpos[t])
            e, x = np.array(e), np.array(x)
            days = (cal[x] - cal[e]).days.to_numpy()
            crf = np.r_[0.0, np.cumsum(np.log1p(rf))]
            rf_hold = np.expm1(crf[x + 1] - crf[e + 1])       # prod over (e, x]
            self.windows[wn] = {"sig_idx": np.array(sidx), "e": e, "x": x, "days": days, "rf_hold": rf_hold}
        self.sig_cal_pos = np.array([cpos[d] for d in self.sig_dates])

    # -- signals -----------------------------------------------------------------------------------
    def price_signal(self, kind: str) -> np.ndarray:
        """Real price-based stock signals on the weekly grid (used only as null raw material):
        'mom_12_1' = C[t-21]/C[t-252]-1; 'rev_1m' = -(C[t]/C[t-21]-1)."""
        c = self.full_closes
        if kind == "mom_12_1":
            s = c.shift(21) / c.shift(252) - 1
        elif kind == "rev_1m":
            s = -(c / c.shift(21) - 1)
        else:
            raise ValueError(kind)
        return s.reindex(self.sig_dates).to_numpy(float)

    # -- books -------------------------------------------------------------------------------------
    @staticmethod
    def quintile_weights(score: np.ndarray, min_names: int = 25) -> np.ndarray:
        """options_signals.target_weights, vectorised: qcut of first-ranks into 5 bins."""
        ranks, n = stable_ranks(score)
        lo, hi = _qedges(n)          # exact numpy/pandas quantile edges of the ranks 1..n
        finite = np.isfinite(score)
        bot = finite & (ranks <= lo[..., None])
        top = finite & (ranks > hi[..., None])
        nt, nb = top.sum(-1, keepdims=True), bot.sum(-1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            w = np.where(top, 1.0 / nt, 0.0) - np.where(bot, 1.0 / nb, 0.0)
        return np.where((n >= min_names)[..., None], w, 0.0)

    def period_returns(self, paths: np.ndarray | None, window: str) -> np.ndarray:
        win = self.windows[window]
        if paths is None:
            return (self.O[win["x"]] / self.O[win["e"]] - 1.0)[None]
        src = bootstrap_source(paths)
        lo = np.log(self.O)
        oo = np.vstack([np.zeros((1, lo.shape[1])), np.diff(lo, axis=0)])   # open-to-open log move
        out = np.empty((len(src), len(win["e"]), lo.shape[1]))
        for i, s in enumerate(src):
            step = oo[s]
            step[0] = 0.0
            cum = np.cumsum(step, axis=0)
            out[i] = np.expm1(cum[win["x"]] - cum[win["e"]])
        return out

    def backtest(self, weights: np.ndarray, R: np.ndarray, window: str, cost: dict) -> np.ndarray:
        """weights (W, K, N), R (Wp, K, N) -> weekly net returns (W, K)."""
        win = self.windows[window]
        prev_w = np.concatenate([np.zeros_like(weights[:, :1]), weights[:, :-1]], axis=1)
        Rb = np.broadcast_to(R, weights.shape)
        prev_r = np.concatenate([np.zeros_like(Rb[:, :1]), Rb[:, :-1]], axis=1)
        gross_prev = (prev_w * prev_r).sum(-1, keepdims=True)
        has = np.abs(prev_w).sum(-1, keepdims=True) > 0
        with np.errstate(invalid="ignore", divide="ignore"):
            drift = np.where(has, prev_w * (1.0 + prev_r) / (1.0 + gross_prev), prev_w)
        turnover = np.abs(weights - drift).sum(-1)
        short_gross = -np.where(weights < 0, weights, 0.0).sum(-1)
        gross = (weights * Rb).sum(-1)
        tc = turnover * cost["per_side"]
        borrow = short_gross * cost["borrow"] * win["days"][None] / 365.0
        proceeds = 0.0 if cost["proceeds_earn_rf"] else short_gross * win["rf_hold"][None]
        return gross - tc - borrow - proceeds

    def run(self, signals: np.ndarray, paths: np.ndarray | None = None,
            windows=("dev", "val"), costs=("base", "stress")) -> dict:
        wts = self.quintile_weights(signals)
        out = {}
        for wn in windows:
            win = self.windows[wn]
            R = self.period_returns(paths, wn)
            w = wts[:, win["sig_idx"]]
            for cn in costs:
                out[(wn, cn)] = self.backtest(w, R, wn, self.ev.COSTS[cn])
        return out

    def reference(self, signal: np.ndarray, window: str, cost: str) -> np.ndarray:
        """Project code path (options_signals.evaluate.backtest) for ONE null signal."""
        ev = self.ev
        score = pd.DataFrame(signal, index=self.sig_dates, columns=self.names)
        lo, hi = (ev.DEV_START, ev.DEV_END) if window == "dev" else (ev.VAL_START, ev.VAL_END)
        dates = ev.window_signal_dates(self.full_cal, lo, hi, hi + pd.Timedelta(days=14))
        bt = ev.backtest(score.reindex(self.full_cal), self.full_opens, self.full_closes, dates,
                         self.full_cal, self.full_rf, ev.COSTS[cost])
        return bt["net"].to_numpy()


def _qedges(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """0.2 / 0.8 quantile edges of 1..n with numpy linear interpolation (what pd.qcut uses)."""
    n = np.asarray(n)
    uniq = np.unique(n)
    lo = np.zeros(n.shape)
    hi = np.zeros(n.shape)
    for u in uniq:
        if u < 1:
            continue
        q = np.quantile(np.arange(1, u + 1, dtype=float), [0.2, 0.8])
        lo[n == u], hi[n == u] = q
    return lo, hi


# ==================================================================================================
# Single-asset timing
# ==================================================================================================
class TimingEngine:
    """book 'spy_cash': return_search.run.execute accounting for SPY vs cash (monthly decisions).
    book 'spy_ief' : rebalancing.evaluate.backtest accounting for the SPY-IEF spread (daily)."""
    periods = ANN_DAILY
    WINDOWS = {
        "spy_cash": {"dev": ("2015-05-01", "2020-12-31"), "val": ("2021-01-01", "2026-09-18")},
        "spy_ief": {"dev": ("2003-02-03", "2014-12-31"), "val": ("2015-01-01", "2026-09-18")},
    }
    COSTS = {"spy_cash": {"base": 0.0005, "stress": 0.0015}, "spy_ief": {"base": 0.0002, "stress": 0.0006}}

    def __init__(self, book: str, active: bool = False):
        from research.return_search.run import cash_rates
        from research.rebalancing import signals as rsg
        self.book = book
        self.active = active          # spy_cash only: returns net of an exposure-matched SPY holding
        self.name = f"timing_{book}" + ("_active" if active else "")
        root = rsg.ROOT
        d = pd.read_parquet(root / "data" / "multiasset" / "etf" / "SPY.parquet")
        d.index = pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()
        d = d.sort_index().loc[:"2026-09-18"]
        self.spy = d
        if book == "spy_cash":
            self.cal = d.index
            self.O = d["open"].to_numpy(float)
            self.C = d["close"].to_numpy(float)
            self.rf = cash_rates(self.cal, "2026-09-18").to_numpy(float)
            month = pd.Series(self.cal.to_period("M"), index=self.cal)
            self.decision = month.ne(month.shift()).to_numpy()
        elif book == "spy_ief":
            ret = rsg.load_returns(upto=pd.Timestamp("2026-09-18"))
            self.ret = ret
            self.cal = ret.index
            self.r = (ret["SPY"] - ret["IEF"]).to_numpy(float)
            self.rs_ = ret[["SPY", "IEF"]].to_numpy(float)
        else:
            raise ValueError(book)
        self.windows = {}
        for wn, (lo, hi) in self.WINDOWS[book].items():
            m = (self.cal >= pd.Timestamp(lo)) & (self.cal <= pd.Timestamp(hi))
            idx = np.flatnonzero(m)
            self.windows[wn] = (int(idx[0]), int(idx[-1]))

    # -- real signals (null raw material only) --------------------------------------------------------
    def real_signal(self, kind: str) -> np.ndarray:
        """Daily signal on self.cal, known at the close of each day.
        spy_cash: 'tsmom' = 1{SPY 252d return > 0}; 'ma200' = 1{close > 200d mean}.
        spy_ief : 'r2' = registered R2_threshold position; 'tsmom' = sign(SPY 252d - IEF 252d return)."""
        if self.book == "spy_cash":
            c = pd.Series(self.C, index=self.cal)
            if kind == "tsmom":
                s = (c / c.shift(252) - 1 > 0).astype(float).where(c.shift(252).notna())
            elif kind == "ma200":
                s = (c > c.rolling(200).mean()).astype(float).where(c.rolling(200).mean().notna())
            else:
                raise ValueError(kind)
            return s.to_numpy(float)
        from research.rebalancing import signals as rsg
        if kind == "r2":
            return rsg.positions(self.ret)["R2_threshold"].to_numpy(float)
        if kind == "tsmom":
            g = (1 + self.ret).cumprod()
            m = g / g.shift(252) - 1
            return np.sign(m["SPY"] - m["IEF"]).where(m["SPY"].notna()).to_numpy(float)
        raise ValueError(kind)

    # -- paths -------------------------------------------------------------------------------------
    def prices(self, paths: np.ndarray | None):
        if self.book == "spy_cash":
            if paths is None:
                return self.O[None], self.C[None]
            src = bootstrap_source(paths)
            O = np.empty((len(src), len(self.cal)))
            C = np.empty_like(O)
            for i, s in enumerate(src):
                c, o = _chain_prices(self.C[:, None], self.O[:, None], s)
                C[i], O[i] = c[:, 0], o[:, 0]
            return O, C
        if paths is None:
            return self.r[None]
        src = bootstrap_source(paths)
        return self.r[src]

    # -- books -------------------------------------------------------------------------------------
    def _spy_cash(self, w_sig: np.ndarray, O: np.ndarray, C: np.ndarray, window: str, cost: float,
                  active: bool = False) -> np.ndarray:
        """execute(): target at decision close i-1 traded at open i; 15 fee iterations; final liquidation."""
        s, e = self.windows[window]
        W = w_sig.shape[0]
        target = np.where(self.decision[None, :], w_sig, np.nan)          # (W, D)
        # start: latest finite target at or before s-1
        first = np.full(W, np.nan)
        for j in range(s - 1, -1, -1):
            f = np.isfinite(target[:, j]) & ~np.isfinite(first)
            first[f] = target[f, j]
            if np.isfinite(first).all():
                break
        cash = np.ones(W)
        shares = np.zeros(W)
        prior = np.ones(W)
        n = e - s + 1
        out = np.empty((W, n))
        expo = np.empty((W, n))
        Ob = np.broadcast_to(O, (W, O.shape[1]))
        Cb = np.broadcast_to(C, (W, C.shape[1]))
        before_last = prior
        for jj, i in enumerate(range(s, e + 1)):
            before_last = prior
            cash = cash * (1 + self.rf[i])
            op, cp = Ob[:, i], Cb[:, i]
            old = shares * op
            nav_open = cash + old
            w = first if jj == 0 else target[:, i - 1]
            ok = np.isfinite(w)
            if ok.any():
                wv = np.where(ok, w, 0.0)
                new_nav = nav_open.copy()
                for _ in range(15):
                    desired = wv * new_nav
                    fee = np.abs(desired - old) * cost
                    new_nav = nav_open - fee
                cash = np.where(ok, cash - ((desired - old) + fee), cash)
                shares = np.where(ok, desired / op, shares)
            marked = shares * cp
            nav = cash + marked
            out[:, jj] = nav / prior - 1
            expo[:, jj] = marked / nav
            prior = nav
        # final liquidation, charged on the last day's marked value
        liq = np.abs(marked) * cost
        out[:, -1] = (prior - liq) / before_last - 1
        ex = out - self.rf[s:e + 1][None]
        if not active:
            return ex
        # exposure-matched static benchmark: mean held SPY weight x SPY close-to-close excess return
        spy_ex = Cb[:, s:e + 1] / Cb[:, s - 1:e] - 1 - self.rf[s:e + 1][None]
        return ex - expo.mean(axis=1, keepdims=True) * spy_ex

    def _spy_ief(self, w_sig: np.ndarray, r: np.ndarray, window: str, per_side: float) -> np.ndarray:
        """rebalancing.backtest: held_t = w_{t-1}; cost_t = 2*ps*|w_{t-1}-w_{t-2}| (first: |w_0|)."""
        s, e = self.windows[window]
        w = np.nan_to_num(w_sig, nan=0.0)
        held = np.concatenate([np.zeros((w.shape[0], 1)), w[:, :-1]], axis=1)
        dw = np.abs(np.diff(w, axis=1, prepend=0.0))
        dw[:, 0] = np.abs(w[:, 0])
        cost = 2 * per_side * np.concatenate([np.zeros((w.shape[0], 1)), dw[:, :-1]], axis=1)
        rb = np.broadcast_to(r, w.shape)
        net = held * rb - cost
        return net[:, s:e + 1]

    def run(self, signals: np.ndarray, paths: np.ndarray | None = None,
            windows=("dev", "val"), costs=("base", "stress")) -> dict:
        """signals (W, D) positions on self.cal -> {(window, cost): (W, days)} daily excess/spread returns."""
        out = {}
        if self.book == "spy_cash":
            O, C = self.prices(paths)
            for wn in windows:
                for cn in costs:
                    out[(wn, cn)] = self._spy_cash(signals, O, C, wn, self.COSTS["spy_cash"][cn], self.active)
        else:
            r = self.prices(paths)
            for wn in windows:
                for cn in costs:
                    out[(wn, cn)] = self._spy_ief(signals, r, wn, self.COSTS["spy_ief"][cn])
        return out

    def reference(self, signal: np.ndarray, window: str, cost: str) -> np.ndarray:
        """Project code path for ONE null signal on the real path."""
        s, e = self.windows[window]
        if self.book == "spy_ief":
            from research.rebalancing.evaluate import backtest
            w = pd.Series(np.nan_to_num(signal, nan=0.0), index=self.cal)
            r = pd.Series(self.r, index=self.cal)
            return backtest(w, r, self.COSTS["spy_ief"][cost]).to_numpy()[s:e + 1]
        from research.return_search import run as rs
        p = {"open": pd.DataFrame({"SPY": self.O}, index=self.cal),
             "close": pd.DataFrame({"SPY": self.C}, index=self.cal)}
        t = pd.DataFrame({"SPY": np.where(self.decision, signal, np.nan)}, index=self.cal)
        rf = pd.Series(self.rf, index=self.cal)
        cal_end = self.cal[e]
        p = {k: v.loc[:cal_end] for k, v in p.items()}
        f = rs.execute(p, t.loc[:cal_end], rf.loc[:cal_end], "etf", stress=(cost == "stress"),
                       start=str(self.cal[s].date()))
        return (f["return"] - rf.reindex(f.index)).to_numpy()
