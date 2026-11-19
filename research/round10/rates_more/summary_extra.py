"""Basket-level extras for RESULTS.md: dev win rate and opposite-direction (flip) basket stats, tier costs."""
import math, numpy as np, pandas as pd, importlib.util, sys, io, contextlib
spec = importlib.util.spec_from_file_location("an", "analysis.py"); an = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(an)
def stats(x):
    x = pd.Series(x).dropna(); n = len(x); m, s = x.mean(), x.std(); t = m / s * math.sqrt(n)
    return n, m * 1e4, t, (x > 0).mean()
for g in list(an.GROUPS) + ["placebo", "reference"]:
    names = an.GROUPS[g].split() if g in an.GROUPS else (["SPY"] if g == "placebo" else ["ITB"])
    same = pd.DataFrame({t: an.net(t, "same_1030") for t in names}).mean(axis=1)
    flip = pd.DataFrame({t: an.net(t, "flip_1030") for t in names}).mean(axis=1)
    out = []
    for lab, s in [("dev", same[same.index < an.CUT]), ("chk", same[same.index >= an.CUT])]:
        n, m, t, w = stats(s); out.append(f"{lab} n={n} net={m:+.1f} t={t:+.2f} win={w:.3f}")
    fd, fc = flip[flip.index < an.CUT], flip[flip.index >= an.CUT]
    out.append(f"flip dev={fd.mean()*1e4:+.1f} chk={fc.mean()*1e4:+.1f} (flip chk t={fc.mean()/fc.std()*math.sqrt(len(fc)):+.2f})")
    print(f"{g:18s} " + " | ".join(out))
