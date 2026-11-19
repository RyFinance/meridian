"""Synthetic month-end ETF total-return price panel for the SPEC section 7 replay (descriptive research only).

Built only from frozen cycle-8 inputs:

* the cycle-8 sleeves (``research.cycle8.engine.sleeves.load`` + ``monthly_sleeves``) computed on the verified
  snapshot view ``data/cycle8/snapshot_store/versions/cycle8_v1/view/proc`` (objects re-hashed first);
* the cycle-8 daily-reset LETF simulation ``reports/cycle8_max_return/out/p7_letf_daily_sim.parquet``
  (column ``P7-2x_eq_letf``) for SSO; its SHA-256 is recorded in the provenance file.

Ticker mapping (monthly simple returns; every series starts at 20.00 in its listing currency on 1985-01-31):

=========  ====  =====================================================================================
XEQT.TO    CAD   EQ_G_tfsa
ZAG.TO     CAD   BOND
ZGLD.TO    CAD   GOLD
CASH.TO    CAD   CASH
DBMF       USD   RF_USD + X_TREND                         (funded trend in USD)
RSSB       USD   EQ_G_tfsa + (BOND - CASH)                in CAD, priced in USD via USDCAD
RSST       USD   EQ_G_tfsa + X_TREND                      in CAD, priced in USD via USDCAD
GDE        USD   0.9*EQ_G_tfsa + 0.9*(GOLD - CASH) + 0.1*CASH   in CAD, priced in USD via USDCAD
SSO        USD   monthly compounding of daily P7-2x_eq_letf (USD)
USDCAD     CAD   cycle-8 fx_monthly USDCAD (CAD per USD, month-end)
=========  ====  =====================================================================================

"In CAD, priced in USD" means: CAD index I_t = 20 * prod(1 + r_cad), USD close = I_t * USDCAD_0 / USDCAD_t, so the
CAD value of one share follows the CAD return exactly.  Approximations are listed in ``APPROXIMATIONS`` and written
into the frozen provenance file.  Dates are calendar month-ends (some fall on weekends; the replay's report dates
are the same dates).  No returns other than these sleeves are computed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research import data_snapshot

REPO = Path(__file__).resolve().parents[2]
CYCLE8_STORE = REPO / "data" / "cycle8" / "snapshot_store"
CYCLE8_VERSION = "cycle8_v1"
LETF_SIM = REPO / "reports" / "cycle8_max_return" / "out" / "p7_letf_daily_sim.parquet"
LETF_COLUMN = "P7-2x_eq_letf"

STORE = REPO / "data" / "cycle9" / "autopilot_replay" / "store"
# v1 (frozen 2026-09-28, source files in source/) modelled GDE without the income on its 10% collateral cash; v2
# fixes that (GDE only; every other series is byte-identical).  Frozen versions are never overwritten.
V1_VERSION = "autopilot_replay_synth_v1"
V1_SOURCE_DIR = REPO / "data" / "cycle9" / "autopilot_replay" / "source"
SOURCE_DIR = REPO / "data" / "cycle9" / "autopilot_replay" / "source_v2"
VERSION = "autopilot_replay_synth_v2"
PRICE_FILE = "synthetic_etf_prices.csv"
FX_FILE = "usdcad_monthly.csv"
PROVENANCE_FILE = "synthetic_provenance.json"

START, END = "1985-01", "2026-05"
START_PRICE = 20.0
CLOSE_DECIMALS = 6

CURRENCY = {"XEQT.TO": "CAD", "ZAG.TO": "CAD", "ZGLD.TO": "CAD", "CASH.TO": "CAD", "DBMF": "USD", "RSSB": "USD",
            "RSST": "USD", "GDE": "USD", "SSO": "USD"}
FORMULAS = {
    "XEQT.TO": "EQ_G_tfsa (CAD)",
    "ZAG.TO": "BOND (CAD)",
    "ZGLD.TO": "GOLD (CAD)",
    "CASH.TO": "CASH (CAD)",
    "DBMF": "RF_USD + X_TREND (USD funded trend)",
    "RSSB": "EQ_G_tfsa + (BOND - CASH) in CAD, priced in USD via USDCAD",
    "RSST": "EQ_G_tfsa + X_TREND in CAD, priced in USD via USDCAD",
    "GDE": "0.9*EQ_G_tfsa + 0.9*(GOLD - CASH) + 0.1*CASH in CAD (90/90 fund: 10% collateral cash), priced in USD "
           "via USDCAD",
    "SSO": f"monthly compounding of daily {LETF_COLUMN} from p7_letf_daily_sim.parquet (USD)",
    "USDCAD": "fx_monthly USDCAD (CAD per 1 USD, month-end)",
}
APPROXIMATIONS = [
    "Stacked ETFs' equity legs (RSSB, RSST, GDE) are modelled with the cycle-8 global equity sleeve EQ_G_tfsa "
    "(45% US / 25% CA / 25% developed ex-NA / 5% EM, CAD, 0.20% fee, TFSA withholding drag). Real RSST and GDE hold "
    "US-only equity and RSSB holds global equity without a Canadian tilt; SSO (from the S&P 500 2x daily-reset "
    "simulation) is the only US-only equity series.",
    "Stacked overlays are financed at the CAD T-bill rate (the - CASH terms, and X_TREND is an excess return), not "
    "at each fund's actual financing cost; the stacked return is computed in CAD and then converted to a USD price, "
    "so the USD listing adds no separate currency exposure beyond what the CAD sleeves already carry.",
    "RSSB's bond leg uses the cycle-8 BOND sleeve (60% Canada 10Y + 40% hedged US 10Y), not US Treasuries only.",
    "Fee differences are ignored: every synthetic ETF carries only the fees embedded in the cycle-8 sleeves (EQ "
    "0.20%, BOND 0.10%, GOLD 0.25%, TREND 2.0% drag inside X_TREND). Actual MERs (e.g. RSSB/RSST/GDE/DBMF higher "
    "than XEQT) are not charged.",
    "DBMF uses the cycle-8 time-series-momentum trend proxy (X_TREND), not DBMF's own replication method.",
    "Prices never split: high-growth series reach share prices far above real ETFs' (RSST ends near USD 57,000 and "
    "SSO near USD 8,100). In the full 1985 replay the accounts grow with these prices, so share counts stay large; "
    "but a replay window that starts late with a small account sees much coarser whole-share rounding than a real "
    "account would.",
    "Total-return prices: distributions are reinvested inside the price; there are no cash distributions.",
    "Dates are calendar month-ends, some of which are weekends; the replay uses the same dates as report dates.",
]


def sha256_file(path: Path) -> str:
    return data_snapshot.digest(Path(path))[0]


def load_sleeves(store: Path = CYCLE8_STORE, version: str = CYCLE8_VERSION) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Verify the frozen cycle-8 snapshot (objects only), then compute cycle-8 monthly sleeves from its view.

    Returns (sleeves, fx_monthly, cycle-8 manifest SHA-256)."""
    from research.cycle8.engine import sleeves as S  # local import: pandas-heavy, only needed here

    manifest = data_snapshot.verify(Path(store), version, source=False)
    view_proc = Path(store).resolve() / "versions" / version / "view" / "proc"
    d = S.load(view_proc)
    return S.monthly_sleeves(d), d["fx_monthly"], manifest["manifest_sha256"]


def monthly_letf(path: Path = LETF_SIM, column: str = LETF_COLUMN) -> pd.Series:
    daily = pd.read_parquet(path)[column].dropna()
    key = pd.DatetimeIndex(daily.index).to_period("M").to_timestamp("M")
    out = (1.0 + daily).groupby(key).prod() - 1.0
    out.index.name = "date"
    return out


def ticker_returns(M: pd.DataFrame, fx: pd.Series, sso: pd.Series, start: str = START,
                   end: str = END) -> tuple[pd.DataFrame, pd.Series]:
    """Monthly returns per ticker in CAD (``*_cad`` for USD-priced stacked ETFs) or USD, over [start, end]."""
    W = M.loc[start:end]
    idx = W.index
    r = pd.DataFrame(index=idx)
    r["XEQT.TO"] = W["EQ_G_tfsa"]
    r["ZAG.TO"] = W["BOND"]
    r["ZGLD.TO"] = W["GOLD"]
    r["CASH.TO"] = W["CASH"]
    r["DBMF"] = W["RF_USD"] + W["X_TREND"]
    r["RSSB_cad"] = W["EQ_G_tfsa"] + (W["BOND"] - W["CASH"])
    r["RSST_cad"] = W["EQ_G_tfsa"] + W["X_TREND"]
    # GDE is a 90/90 fund: 90% equity, 90% gold futures (excess return GOLD - CASH) and 10% collateral cash
    r["GDE_cad"] = 0.9 * W["EQ_G_tfsa"] + 0.9 * (W["GOLD"] - W["CASH"]) + 0.1 * W["CASH"]
    r["SSO"] = sso.reindex(idx)
    usdcad = fx["USDCAD"].reindex(idx)
    body = r.iloc[1:]
    bad = body.columns[body.isna().any()].tolist()
    if bad or usdcad.isna().any():
        raise ValueError(f"missing sleeve data in {start}..{end}: {bad} usdcad_nan={int(usdcad.isna().sum())}")
    return r, usdcad


def price_panel(r: pd.DataFrame, usdcad: pd.Series, start_price: float = START_PRICE) -> pd.DataFrame:
    """Wide month-end closes in each ticker's listing currency; the first month is the base (start_price)."""
    growth = (1.0 + r.iloc[1:]).cumprod()
    growth = pd.concat([pd.DataFrame(1.0, index=r.index[:1], columns=r.columns), growth])
    px = pd.DataFrame(index=r.index)
    for t in ("XEQT.TO", "ZAG.TO", "ZGLD.TO", "CASH.TO", "DBMF", "SSO"):
        px[t] = start_price * growth[t]
    fx0 = float(usdcad.iloc[0])
    for t in ("RSSB", "RSST", "GDE"):
        px[t] = start_price * growth[f"{t}_cad"] * fx0 / usdcad
    px = px[sorted(px.columns)]
    if not np.isfinite(px.to_numpy()).all() or (px <= 0).any().any():
        raise ValueError("non-positive or non-finite synthetic price")
    return px


def _fmt(x: float) -> str:
    return f"{x:.{CLOSE_DECIMALS}f}"


def panel_csv_bytes(px: pd.DataFrame) -> bytes:
    lines = ["date,ticker,close,currency"]
    for d, row in px.iterrows():
        ds = pd.Timestamp(d).date().isoformat()
        for t in px.columns:
            lines.append(f"{ds},{t},{_fmt(float(row[t]))},{CURRENCY[t]}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def fx_csv_bytes(usdcad: pd.Series) -> bytes:
    lines = ["date,ticker,close,currency"]
    lines += [f"{pd.Timestamp(d).date().isoformat()},USDCAD,{_fmt(float(v))},CAD" for d, v in usdcad.items()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def build(start: str = START, end: str = END, *, cycle8_store: Path = CYCLE8_STORE,
          letf_path: Path = LETF_SIM) -> dict[str, Any]:
    """Compute the panel.  Returns dict(prices_csv, fx_csv, provenance, panel, usdcad, returns)."""
    M, fxm, c8_hash = load_sleeves(cycle8_store)
    sso = monthly_letf(letf_path)
    r, usdcad = ticker_returns(M, fxm, sso, start, end)
    px = price_panel(r, usdcad)
    prices_csv, fx_csv = panel_csv_bytes(px), fx_csv_bytes(usdcad)
    provenance = {
        "kind": "autopilot_replay_synthetic_prices", "dataset_version": VERSION,
        "supersedes": {"version": V1_VERSION,
                       "change": "GDE now earns CASH on its 10% collateral (0.9*EQ + 0.9*(GOLD - CASH) + 0.1*CASH); "
                                 "every other series is unchanged"},
        "window": {"first": px.index[0].date().isoformat(), "last": px.index[-1].date().isoformat(),
                   "months": int(len(px))},
        "start_price": START_PRICE, "close_decimals": CLOSE_DECIMALS,
        "currencies": dict(sorted(CURRENCY.items())), "formulas": FORMULAS, "approximations": APPROXIMATIONS,
        "inputs": {"cycle8_snapshot": {"store": "data/cycle8/snapshot_store", "version": CYCLE8_VERSION,
                                       "manifest_sha256": c8_hash,
                                       "code": "research.cycle8.engine.sleeves.load + monthly_sleeves"},
                   "letf_simulation": {"path": "reports/cycle8_max_return/out/p7_letf_daily_sim.parquet",
                                       "column": LETF_COLUMN, "sha256": sha256_file(letf_path)}},
        "files": {PRICE_FILE: hashlib.sha256(prices_csv).hexdigest(), FX_FILE: hashlib.sha256(fx_csv).hexdigest()},
        "end_prices": {t: round(float(px[t].iloc[-1]), CLOSE_DECIMALS) for t in px.columns},
    }
    return {"prices_csv": prices_csv, "fx_csv": fx_csv, "provenance": provenance, "panel": px, "usdcad": usdcad,
            "returns": r, "cycle8_manifest_sha256": c8_hash}


def _retrieved_at(cycle8_store: Path = CYCLE8_STORE) -> str:
    """Latest ingestion timestamp of the frozen cycle-8 inputs (the synthetic files are derived from them)."""
    m = data_snapshot.load_manifest(Path(cycle8_store), CYCLE8_VERSION)
    return max(r["retrieved_at"] for r in m["payload"]["records"])


def snapshot_spec(source_dir: Path, built: dict[str, Any], version: str = VERSION,
                  retrieved_at: str | None = None) -> dict[str, Any]:
    retrieved_at = retrieved_at or _retrieved_at()
    px = built["panel"]
    first = f"{px.index[0].date().isoformat()}T00:00:00+00:00"
    last = f"{px.index[-1].date().isoformat()}T00:00:00+00:00"
    src = ("synthetic: derived from cycle-8 sleeves (snapshot cycle8_v1, manifest "
           f"{built['cycle8_manifest_sha256']}) and the cycle-8 LETF daily simulation")
    ident = "research/autopilot/synth_prices.py"
    meta = {
        f"prices/{PRICE_FILE}": {"source": src, "source_identifier": ident, "retrieved_at": retrieved_at,
                                 "logical_as_of": px.index[-1].date().isoformat(), "symbol": "AUTOPILOT_SYNTH_ETF",
                                 "first_timestamp": first, "last_timestamp": last,
                                 "row_count": int(px.size), "temporal": True},
        f"prices/{FX_FILE}": {"source": src, "source_identifier": ident, "retrieved_at": retrieved_at,
                              "logical_as_of": px.index[-1].date().isoformat(), "symbol": "USDCAD",
                              "first_timestamp": first, "last_timestamp": last,
                              "row_count": int(len(px)), "temporal": True},
        f"prices/{PROVENANCE_FILE}": {"source": src, "source_identifier": ident, "retrieved_at": retrieved_at,
                                      "logical_as_of": px.index[-1].date().isoformat(),
                                      "symbol": "AUTOPILOT_SYNTH_PROVENANCE", "first_timestamp": None,
                                      "last_timestamp": None, "row_count": 1, "temporal": False},
    }
    return {"dataset_version": version,
            "scopes": [{"name": "prices", "root": str(Path(source_dir).resolve()),
                        "include": [PRICE_FILE, FX_FILE, PROVENANCE_FILE]}],
            "metadata": meta,
            "universe": {"membership_artifact": f"prices/{PROVENANCE_FILE}", "exclusions": [], "symbol_mappings": {},
                         "delistings": [], "note": "fixed autopilot ETF universe (research/autopilot/config.py); "
                                                   "synthetic series, no delistings"},
            "intermediate_artifacts": []}


def write_sources(source_dir: Path, built: dict[str, Any]) -> None:
    source_dir = Path(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    files = {PRICE_FILE: built["prices_csv"], FX_FILE: built["fx_csv"],
             PROVENANCE_FILE: (json.dumps(built["provenance"], sort_keys=True, indent=1) + "\n").encode("utf-8")}
    for name, data in files.items():
        path = source_dir / name
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError(f"{path} exists with different content; synthetic source files are immutable")
        if not path.exists():
            path.write_bytes(data)


def freeze(store: Path = STORE, source_dir: Path = SOURCE_DIR, version: str = VERSION,
           start: str = START, end: str = END) -> dict[str, Any]:
    """Build the panel, write the source files and freeze them; returns the manifest."""
    built = build(start, end)
    write_sources(source_dir, built)
    return data_snapshot.freeze(snapshot_spec(source_dir, built, version), Path(store))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.autopilot.synth_prices",
                                 description="Build and freeze the synthetic replay price panel (research only).")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    ap.add_argument("--version", default=VERSION)
    args = ap.parse_args(argv)
    manifest = freeze(args.store, args.source_dir, args.version)
    print(f"{args.version} manifest_sha256={manifest['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
