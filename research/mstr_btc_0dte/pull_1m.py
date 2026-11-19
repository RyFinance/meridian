"""Pull MSTR option 1-minute candles (OPRA prints) from the LSE vault, 2020-08-10..2026-09-17, chained under the
2.5M-row export cap. Keeps only Monday/Friday rows on contracts expiring within 4 days. Resumable: each export
chunk is saved under data/lse/options_mstr/1m/ and the next export restarts on the last day seen."""
import glob, hashlib, http.client, io, time
from pathlib import Path
import pandas as pd
from loguru import logger
from data.lse_vault import Vault, VaultError
from data.pull_options_1d import wait_for_export_slot, EXPORT_ROW_CAP

OUT = Path(__file__).parents[2] / "data/lse/options_mstr/1m"
START, END = "2020-08-10", "2026-09-18"

def export(v, start, end):
    wait_for_export_slot(v)
    jid = v._call("POST", "/export", body={"dataset": "options", "symbol": "MSTR", "timeframe": "1m",
                                          "start": start, "end": end})["job_id"]
    for _ in range(720):
        s = v._call("GET", f"/export/{jid}")
        if s["status"] == "ready":
            break
        if s["status"] not in ("queued", "running"):
            raise VaultError(f"export {jid} {s['status']}: {s.get('error')}")
        time.sleep(10)
    for attempt in range(8):
        try:
            raw = v._call("GET", f"/export/{jid}/download", raw=True)
            if hashlib.sha256(raw).hexdigest() == s["sha256"]:
                return pd.read_parquet(io.BytesIO(raw)), s["rows"]
        except (http.client.HTTPException, OSError) as e:
            logger.warning(f"download retry {attempt + 1}: {type(e).__name__}")
        time.sleep(15 * (attempt + 1))
    raise VaultError(f"export {jid}: download failed")

def keep(df):
    ts = pd.to_datetime(df.ts)
    ts = ts.dt.tz_convert("America/New_York") if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    d = ts.dt.tz_localize(None).dt.normalize()
    exp = pd.to_datetime(df.expiry)
    m = d.dt.dayofweek.isin([0, 4]) & ((exp - d).dt.days.between(0, 4))
    return df[m.values]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    v = Vault()
    cursor = START
    done = sorted(glob.glob(str(OUT / "chunk_*.parquet")))
    if done:
        cursor = open(OUT / "cursor.txt").read().strip()
    while True:
        df, rows = export(v, cursor, END)
        last_day = str(pd.to_datetime(df.ts).max().date()) if len(df) else END
        capped = rows >= EXPORT_ROW_CAP
        if capped:  # drop the possibly-partial last day; restart there
            df = df[pd.to_datetime(df.ts).dt.date.astype(str) < last_day]
        k = keep(df)
        k.to_parquet(OUT / f"chunk_{len(glob.glob(str(OUT / 'chunk_*.parquet'))):03d}_{cursor}.parquet")
        logger.info(f"{cursor}..{last_day}: {rows:,} rows exported, {len(k):,} kept, capped={capped}")
        if not capped:
            break
        cursor = last_day
        open(OUT / "cursor.txt", "w").write(cursor)
    logger.info("done")
