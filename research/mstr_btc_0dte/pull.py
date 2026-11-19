"""Pull MSTR daily per-contract option candles (OPRA prints) from the LSE vault, 2020-01..2026-09.
Reuses the chained export from data/pull_options_1d. Run: PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.pull"""
from pathlib import Path
from data.lse_vault import Vault
from data.pull_options_1d import export_all

OUT = Path(__file__).parents[2] / "data" / "lse" / "options_mstr" / "MSTR.parquet"

if __name__ == "__main__":
    df = export_all(Vault(), "MSTR", "2020-01-01", "2026-09-17")
    df.to_parquet(OUT)
    print(df.shape, df.columns.tolist(), df.iloc[:, 0].min(), df.iloc[:, 0].max())
