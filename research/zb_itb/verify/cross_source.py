"""Cross-source check 2024-05..2026-09-16: yfinance 60m builder bars vs LSE vault 5m bars (tick-built), and F3 (ZB signal) re-run on vault prices."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
from research.zb_itb.verify.long_history import daily
for s in ["DHI", "LEN", "PHM", "TOL"]:
    yf = build(s); yf = yf[yf.d.notna() & (yf.d != 0)]
    v = daily(s)
    j = yf.join(v[["o930", "c1025", "o935"]], how="inner")
    j = j[j.index <= "2026-09-16"]
    do = np.abs(np.log(j.entry_h1 / j.o930)) * 1e4; dc = np.abs(np.log(j.exit / j.c1025)) * 1e4
    g_yf = (j.d * np.log(j.exit / j.entry_h1) - 0.0004); g_v = (j.d * np.log(j.c1025 / j.o930) - 0.0004); g_v935 = (j.d * np.log(j.c1025 / j.o935) - 0.0004)
    t = lambda p: p.mean() / p.std() * np.sqrt(len(p))
    print(f"{s}: n {len(j)} | open |diff| median {do.median():.1f}bp p95 {do.quantile(.95):.1f} | 10:30 close |diff| median {dc.median():.1f}bp p95 {dc.quantile(.95):.1f} | "
          f"F3 yf {g_yf.mean()*1e4:+.1f}bp (t {t(g_yf):+.2f}) vs vault {g_v.mean()*1e4:+.1f}bp (t {t(g_v):+.2f}) | vault entry 09:35: {g_v935.mean()*1e4:+.1f}bp (t {t(g_v935):+.2f})")
