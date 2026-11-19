"""Export builder option 1-minute candles (OPRA prints) from the LSE vault, 2024-05-01..2026-09-17.
Keeps 09:25-10:45 ET rows on contracts expiring within 60 days. One export per symbol (chained if capped). Run outside the sandbox."""
import glob, io, sys, time
from pathlib import Path
import pandas as pd
from data.lse_vault import Vault
from data.pull_options_1d import EXPORT_ROW_CAP
import hashlib, http.client
from data.pull_options_1d import wait_for_export_slot
from data.lse_vault import VaultError
def export(v, sym, start, end):
    """Chained 1m options export for ONE underlying (the mstr helper hard-codes MSTR)."""
    wait_for_export_slot(v)
    jid = v._call("POST", "/export", body={"dataset": "options", "symbol": sym, "timeframe": "1m", "start": start, "end": end})["job_id"]
    for _ in range(720):
        s = v._call("GET", f"/export/{jid}")
        if s["status"] == "ready": break
        if s["status"] not in ("queued", "running"): raise VaultError(f"export {jid} {s['status']}: {s.get('error')}")
        time.sleep(10)
    for attempt in range(8):
        try:
            raw = v._call("GET", f"/export/{jid}/download", raw=True)
            if hashlib.sha256(raw).hexdigest() == s["sha256"]: return pd.read_parquet(io.BytesIO(raw)), s["rows"]
        except (http.client.HTTPException, OSError): pass
        time.sleep(15 * (attempt + 1))
    raise VaultError(f"export {jid}: download failed")
OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
def keep(df):
    ts = pd.to_datetime(df.ts); ts = ts.dt.tz_convert("America/New_York") if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    hm = ts.dt.hour * 60 + ts.dt.minute; d = ts.dt.tz_localize(None).dt.normalize()
    dte = (pd.to_datetime(df.expiry) - d).dt.days
    m = (hm >= 565) & (hm <= 645) & dte.between(0, 60)
    out = df[m.values].copy(); out["et"] = ts[m.values].values; return out
v = Vault()
for sym in sys.argv[1:] or ["DHI", "LEN", "PHM", "TOL", "KBH"]:
    cursor, end, part = "2024-05-01", "2026-09-18", 0
    if glob.glob(str(OUT / f"{sym}_*.parquet")): print(sym, "cached"); continue
    while True:
        df, rows = export(v, sym, cursor, end)
        assert df.empty or set(df.underlying.unique()) <= {sym}, f'wrong underlying {df.underlying.unique()[:3]}'
        last = str(pd.to_datetime(df.ts).max().date()) if len(df) else end
        capped = rows >= EXPORT_ROW_CAP
        if capped: df = df[pd.to_datetime(df.ts).dt.date.astype(str) < last]
        k = keep(df); k.to_parquet(OUT / f"{sym}_{part:02d}.parquet")
        print(f"{sym} {cursor}..{last}: exported {rows:,}, kept {len(k):,}, capped={capped}", flush=True)
        if not capped: break
        cursor, part = last, part + 1
print("DONE")
