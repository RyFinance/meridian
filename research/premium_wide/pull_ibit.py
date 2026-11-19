from pathlib import Path
from data.lse_vault import Vault
from data.pull_options_1d import export_all
OUT = Path(__file__).parents[2] / "data/lse/options_ibit/IBIT.parquet"
if __name__ == "__main__":
    df = export_all(Vault(), "IBIT", "2024-11-01", "2026-09-17"); df.to_parquet(OUT)
    print(df.shape, df.ts.min(), df.ts.max())
