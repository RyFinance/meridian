"""Walk-forward adaptive hour selection (ADAPTIVE_PREREG.md)."""
import glob, io, json, time, urllib.request, zipfile
import numpy as np, pandas as pd
from pathlib import Path
from research.forward import nyse
H = Path(__file__).parent; ROOT = H.parents[1]

def btc_1m() -> pd.Series:
    a = pd.read_parquet(ROOT.parent / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
    a = a.set_index(pd.to_datetime(a.timestamp)).close
    parts = [a[a.index < "2026-08-10"]]
    for f in sorted(glob.glob(str(ROOT / "data/binance_mstr_token/BTCUSDT-1m-2026-0[89].zip"))):
        z = zipfile.ZipFile(f); raw = z.read(z.namelist()[0]).decode()
        df = pd.read_csv(io.StringIO(raw), header=0 if raw.startswith("open_time") else None).iloc[:, [0, 4]]
        df.columns = ["t", "c"]; s = pd.Series(df.c.astype(float).values, index=pd.to_datetime(df.t.astype("int64"), unit="ms", utc=True) + pd.Timedelta(minutes=1))
        parts.append(s)   # Binance open_time -> close time = open + 1m
    start = int(pd.Timestamp("2026-10-01", tz="UTC").timestamp() * 1000); end = int(pd.Timestamp("2026-10-17", tz="UTC").timestamp() * 1000)
    rows = []
    while start < end:
        u = f"https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1m&startTime={start}&limit=1500"
        for a in range(8):
            try:
                k = json.loads(urllib.request.urlopen(u, timeout=30).read()); break
            except Exception:
                time.sleep(2 * (a + 1))
        else:
            raise RuntimeError("binance fetch failed")
        if not k: break
        rows += [(x[0], float(x[4])) for x in k]; start = k[-1][0] + 60_000; time.sleep(0.2)
    parts.append(pd.Series([c for _, c in rows], index=pd.to_datetime([t for t, _ in rows], unit="ms", utc=True) + pd.Timedelta(minutes=1)))
    s = pd.concat(parts).sort_index(); return s[~s.index.duplicated(keep="last")]

def hourly_panel(s: pd.Series) -> pd.DataFrame:
    s = s.tz_convert("America/New_York")
    hr = s.resample("1h", label="right", closed="right").last()     # price at each :00 (last trade at/before)
    r = np.log(hr).diff().shift(-1)                                   # return from :00 of hour h to h+1, labelled h
    df = pd.DataFrame({"r": r}); df["d"] = df.index.tz_localize(None).normalize(); df["h"] = df.index.hour
    df = df[[nyse.is_session(x.date()) and x.weekday() < 5 for x in df.d]]
    return df.pivot_table(index="d", columns="h", values="r")

def walk(P: pd.DataFrame, T: int, thr=2.0):
    out = []
    for i in range(T, len(P)):
        w = P.iloc[i - T:i]; m = w.mean(); sd = w.std(); n = w.count(); t = m / sd * np.sqrt(n)
        hb, hw = t.idxmax(), t.idxmin()
        side, h = 0, None
        if t[hb] >= thr and t[hb] >= -t[hw]: side, h = 1, hb
        elif t[hw] <= -thr: side, h = -1, hw
        if side and np.isfinite(P.iloc[i][h]):
            out.append((P.index[i], h, side, side * P.iloc[i][h]))
    return pd.DataFrame(out, columns=["d", "h", "side", "g"]).set_index("d")

if __name__ == "__main__":
    s = btc_1m(); print("btc 1m", s.index.min(), s.index.max(), len(s))
    P = hourly_panel(s); P.to_parquet(H / "btc_hour_panel.parquet"); print("panel", P.shape, P.index.min().date(), P.index.max().date())
    for T in (60, 120, 250):
        t = walk(P, T); t = t[t.index >= "2019-01-01"]
        t.to_csv(H / f"adaptive_T{T}.csv")
        for c in (4, 8):
            n = t.g - c / 1e4; y = n.groupby(n.index.year)
            print(f"T={T} cost {c}bp: n={len(n)} mean {n.mean()*1e4:+.2f}bp t={n.mean()/n.std()*np.sqrt(len(n)):+.2f} win={(n>0).mean():.3f} | per-year ROI%:",
                  (y.sum() * 100).round(1).to_dict(), "| trades/yr:", y.size().to_dict())
        print("   hours chosen 2025-26:", t["2025":].h.value_counts().head(6).to_dict(), " side:", t["2025":].side.value_counts().to_dict())
