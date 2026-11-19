# Pull 60m regular-hours bars via yfinance for check-only tickers; cache locally.
import yfinance as yf, pandas as pd, os
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/macro/cache"
for t in ["MSTR", "IBIT", "COIN", "MARA", "RIOT", "CLSK"]:
    df = yf.Ticker(t).history(period="730d", interval="60m", auto_adjust=True, prepost=False)
    if df.empty:
        print(t, "EMPTY"); continue
    df = df.reset_index().rename(columns={"Datetime": "ts"})
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("America/New_York")
    df = df[df["ts"].dt.strftime("%Y-%m-%d") <= "2026-08-10"]  # sealed holdout cut
    df[["ts", "Open", "High", "Low", "Close", "Volume"]].to_parquet(f"{OUT}/{t}_60m.parquet")
    print(t, len(df), df.ts.min(), df.ts.max())
