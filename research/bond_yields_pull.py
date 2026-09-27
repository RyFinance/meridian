"""Pull government bond yield series (2Y-or-nearest + 10Y) for 14 economies
from the LSE vault's "bonds" dataset, and write a manifest.

DATA WORK ONLY. This script pulls and saves raw yield levels; it does not
compute or load any equity/ETF/FX return, and it must not be used to
correlate yields against returns ahead of the pre-registered experiment that
will consume this data.

Economies and the symbol chosen per economy (2Y preferred; nearest among
1Y/3Y/3M used when 2Y is missing from the "bonds" catalog; Mexico has no
short-tenor bond symbol at all in this dataset, so only MX10Y is pulled):

    economy         short              10Y
    US              US2Y               US10Y
    Japan           JP2Y               JP10Y
    UK              UK2Y               UK10Y
    Euro area (DE)  DE2Y               DE10Y
    Australia       AU2Y               AU10Y
    Canada          CA2Y               CA10Y
    Brazil          BR2Y               BR10Y
    Mexico          (none available)   MX10Y
    Korea           KR2Y               KR10Y
    China           CN2Y               CN10Y
    India           IN2Y               IN10Y
    South Africa    ZA3M (no 2Y/1Y/3Y) ZA10Y
    Turkey          TR2Y               TR10Y
    Indonesia       ID1Y (no 2Y)       ID10Y

Run: PYTHONPATH=. .venv/bin/python -m research.bond_yields_pull
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from data.lse_vault import Vault

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "bond_yields"
DATASET = "bonds"

# (economy, short_symbol_or_None, short_tenor_label, long_symbol)
SERIES = [
    ("US", "US2Y", "2Y", "US10Y"),
    ("Japan", "JP2Y", "2Y", "JP10Y"),
    ("UK", "UK2Y", "2Y", "UK10Y"),
    ("EuroArea_DE", "DE2Y", "2Y", "DE10Y"),
    ("Australia", "AU2Y", "2Y", "AU10Y"),
    ("Canada", "CA2Y", "2Y", "CA10Y"),
    ("Brazil", "BR2Y", "2Y", "BR10Y"),
    ("Mexico", None, "none", "MX10Y"),
    ("Korea", "KR2Y", "2Y", "KR10Y"),
    ("China", "CN2Y", "2Y", "CN10Y"),
    ("India", "IN2Y", "2Y", "IN10Y"),
    ("SouthAfrica", "ZA3M", "3M", "ZA10Y"),
    ("Turkey", "TR2Y", "2Y", "TR10Y"),
    ("Indonesia", "ID1Y", "1Y", "ID10Y"),
]


def pull_symbol(vault: Vault, symbol: str) -> pd.DataFrame:
    df = vault.series(symbol, dataset=DATASET)
    if df.empty:
        raise RuntimeError(f"{symbol}: vault returned no rows")
    df = df[["date", "value"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = symbol
    df = df.sort_values("date").reset_index(drop=True)
    return df


def save_parquet(df: pd.DataFrame, symbol: str) -> Path:
    path = OUT_DIR / f"{symbol}.parquet"
    df.to_parquet(path, index=False)
    return path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vault = Vault()

    symbols: list[tuple[str, str, str]] = []  # (economy, tenor_label, symbol)
    for economy, short_sym, short_label, long_sym in SERIES:
        if short_sym is not None:
            symbols.append((economy, short_label, short_sym))
        symbols.append((economy, "10Y", long_sym))

    manifest: dict[str, dict] = {}
    for economy, tenor_label, symbol in symbols:
        print(f"pulling {symbol} ({economy}, {tenor_label}) ...")
        df = pull_symbol(vault, symbol)
        path = save_parquet(df, symbol)
        manifest[symbol] = {
            "economy": economy,
            "tenor_label": tenor_label,
            "dataset": DATASET,
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_of(path),
            "rows": int(len(df)),
            "first_date": df["date"].min().strftime("%Y-%m-%d"),
            "last_date": df["date"].max().strftime("%Y-%m-%d"),
        }
        print(f"  {len(df)} rows, {manifest[symbol]['first_date']} -> {manifest[symbol]['last_date']}")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote manifest: {manifest_path} ({len(manifest)} series)")
    print(f"vault bytes used this run: {vault.bytes_used}")


if __name__ == "__main__":
    main()
