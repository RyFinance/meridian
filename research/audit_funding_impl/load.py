"""Independent loader (does NOT import research.crypto_funding_xs). LOCK: only monthly files <= 2022-12 are opened,
and rows are truncated at 2022-12-31 (klines) / calc_time < 2023-01-01 00:00 (funding).
Writes long-format parquet caches + a raw integrity log to reports/audit_funding_impl/."""
from __future__ import annotations
import io, json, re, zipfile
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "data/c4/binance_um"
OUT = ROOT / "reports/audit_funding_impl"
CUT_MONTH = "2022-12"
END_MS = int(pd.Timestamp("2023-01-01").value // 1_000_000)
EXCL = {"BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
MRE = re.compile(r"(\d{4}-\d{2})\.zip$")


def read_rows(p):
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        txt = z.read(names[0]).decode()
    lines = [l for l in txt.splitlines() if l.strip()]
    hdr = None
    if lines and not lines[0].split(",")[0].strip().isdigit():
        hdr, lines = lines[0].split(","), lines[1:]
    rows = [l.split(",") for l in lines]
    return hdr, rows, len(names)


def to_ms(x):
    x = np.asarray(x, dtype=np.int64)
    unit = np.where(x > 10**14, "us", "ms")
    return np.where(x > 10**14, x // 1000, x), int((x > 10**14).sum())


def main():
    log = {"kl_headers": 0, "kl_noheader": 0, "fr_headers": 0, "fr_noheader": 0, "us_timestamps": 0, "multi_member_zip": 0,
           "files_skipped_post_lock": 0, "dup_kline_days": [], "zero_or_nonpos_price": [], "open_ne_prevclose_big": 0,
           "kline_gaps": [], "open_time_not_midnight": [], "hdr_variants": set()}
    kl_all, fr_all = [], []
    dirs = sorted(set(p.name for p in (BIN / "klines_1d").iterdir()) | set(p.name for p in (BIN / "fundingRate").iterdir()))
    for s in dirs:
        if not s.endswith("USDT") or s[:-4] in EXCL:
            continue
        for kind in ("klines_1d", "fundingRate"):
            d = BIN / kind / s
            if not d.exists():
                continue
            for f in sorted(d.glob("*.zip")):
                m = MRE.search(f.name)
                if m is None or m.group(1) > CUT_MONTH:
                    log["files_skipped_post_lock"] += 1
                    continue
                hdr, rows, nm = read_rows(f)
                if nm > 1:
                    log["multi_member_zip"] += 1
                key = ("kl_" if kind == "klines_1d" else "fr_") + ("headers" if hdr else "noheader")
                log[key] += 1
                if hdr:
                    log["hdr_variants"].add(",".join(hdr))
                if not rows:
                    continue
                a = pd.DataFrame(rows)
                ms, nus = to_ms(a[0].astype(np.int64))
                log["us_timestamps"] += nus
                if kind == "klines_1d":
                    df = pd.DataFrame({"sym": s, "t": ms, "open": a[1].astype(float), "high": a[2].astype(float),
                                       "low": a[3].astype(float), "close": a[4].astype(float), "qv": a[7].astype(float),
                                       "file": f.name})
                    kl_all.append(df[df.t < END_MS])
                else:
                    df = pd.DataFrame({"sym": s, "t": ms, "ih": a[1].astype(float), "rate": a[2].astype(float)})
                    fr_all.append(df[df.t < END_MS])
    K = pd.concat(kl_all, ignore_index=True)
    F = pd.concat(fr_all, ignore_index=True)
    K["day"] = pd.to_datetime(K.t, unit="ms")
    log["open_time_not_midnight"] = int((K.day != K.day.dt.normalize()).sum())
    K["day"] = K.day.dt.normalize()
    dup = K[K.duplicated(["sym", "day"], keep=False)]
    log["dup_kline_days"] = {"rows": len(dup), "conflicting_values": int(dup.groupby(["sym", "day"])[["open", "close"]].nunique().gt(1).any(axis=1).sum())}
    K = K.drop_duplicates(["sym", "day"]).sort_values(["sym", "day"])
    bad = K[(K.open <= 0) | (K.close <= 0) | (K.high <= 0) | (K.low <= 0)]
    log["zero_or_nonpos_price"] = len(bad)
    gaps = []
    for s, g in K.groupby("sym"):
        dd = g.day.diff().dt.days
        if (dd > 1).any():
            gaps.append({"sym": s, "n": int((dd > 1).sum()), "max_gap_days": int(dd.max()), "at": str(g.day[dd.idxmax()].date())})
    log["kline_gaps"] = gaps
    prev = K.groupby("sym").close.shift()
    log["open_ne_prevclose_big"] = int(((K.open / prev - 1).abs() > 0.02).sum())
    log["open_vs_prevclose_abs_gt_2pct_examples"] = K.loc[((K.open / prev - 1).abs() > 0.02), ["sym", "day", "open"]].head(10).astype(str).values.tolist()
    F["ts"] = pd.to_datetime(F.t, unit="ms")
    Fdup = F.duplicated(["sym", "t"]).sum()
    log["funding_dup_rows"] = int(Fdup)
    F = F.drop_duplicates(["sym", "t"]).sort_values(["sym", "t"])
    off = F.t % 3_600_000
    F["year"] = F.ts.dt.year
    log["funding_calc_ms_offset_by_year"] = {int(y): {"n": int(len(g)), "exact_hour": float((g.t % 3_600_000 == 0).mean()),
                                                     "max_offset_ms": int((g.t % 3_600_000).where(lambda x: x < 1_800_000, 0).max())}
                                              for y, g in F.groupby("year")}
    log["funding_interval_hours_counts"] = {str(k): int(v) for k, v in F.ih.value_counts().items()}
    log["funding_interval_non8_syms_dev"] = sorted(F.loc[F.ih != 8, "sym"].unique().tolist())
    log["hdr_variants"] = sorted(log["hdr_variants"])
    log["n_syms_klines"] = int(K.sym.nunique()); log["n_syms_funding"] = int(F.sym.nunique())
    log["kline_max_day"] = str(K.day.max()); log["funding_max_ts"] = str(F.ts.max())
    K.drop(columns=["t"]).to_parquet(OUT / "klines_dev.parquet")
    F.drop(columns=["year"]).to_parquet(OUT / "funding_dev.parquet")
    (OUT / "data_integrity.json").write_text(json.dumps(log, indent=1, default=str))
    print(json.dumps({k: v for k, v in log.items() if k != "kline_gaps"}, indent=1, default=str)); print("gaps", len(gaps), gaps[:15])

if __name__ == "__main__":
    main()
