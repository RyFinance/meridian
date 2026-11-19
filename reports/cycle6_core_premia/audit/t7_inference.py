"""Test 7: independent re-implementation of the A4 §6 calibrated Sharpe interval (numpy only: AR(p<=3) by OLS/BIC,
residual or crash-layer innovations, studentised bootstrap-t with HAC(Bartlett, fixed-b 0.10n) SEs, influence-function
Sharpe SE), seed sensitivity, 95% interval, crash layer, and ledger timing of B = 9,999."""
from common import *
import re

def nw(x, L):
    x = x - x.mean(); n = len(x); v = x @ x / n
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (x[l:] @ x[:-l]) / n
    return v

def est(x, L):
    n = len(x); m = x.mean(); sd = x.std(ddof=1); s = m / sd
    z = (x - m) / sd; psi = z - 0.5 * s * (z * z - 1)
    return m, s, np.sqrt(nw(psi, L) / n)

def fit_ar(e, pmax=3):
    n = len(e); best = (np.inf, 0, np.zeros(0), e)
    for p in range(pmax + 1):
        if p == 0:
            u = e[pmax:]; phi = np.zeros(0)
        else:
            Y = e[pmax:]; X = np.column_stack([e[pmax - j - 1:n - j - 1] for j in range(p)])
            phi = np.linalg.lstsq(X, Y, rcond=None)[0]; u = Y - X @ phi
        bic = len(u) * np.log(u.var()) + p * np.log(len(u))
        if bic < best[0]: best = (bic, p, phi, u - u.mean())
    return best[1], best[2], best[3]

def boot_ci(x, level=0.90, B=499, seed=1, crash=None, burn=200):
    x = np.asarray(x, float); n = len(x); L = max(int(np.floor(4 * (n / 100) ** (2 / 9))), int(np.ceil(0.10 * n)))
    m, s, se = est(x, L); p, phi, u = fit_ar(x - m)
    rng = np.random.default_rng(seed); T = np.empty(B)
    for b in range(B):
        if crash is None:
            eps = rng.choice(u, n + burn)
        else:
            cp, J = crash; z = rng.standard_normal(n + burn) + J * (rng.random(n + burn) < cp)
            eps = u.std() * (z - cp * J) / np.sqrt(1 + cp * (1 - cp) * J * J)
        y = np.zeros(n + burn)
        for t in range(n + burn):
            y[t] = eps[t] + sum(phi[j] * y[t - 1 - j] for j in range(p) if t - 1 - j >= 0)
        ys = y[burn:] + m
        mb, sb, seb = est(ys, L); T[b] = (sb - s) / seb
    a = 1 - level
    return ((s - np.quantile(T, 1 - a / 2) * se) * np.sqrt(12), (s - np.quantile(T, a / 2) * se) * np.sqrt(12), s * np.sqrt(12))

b = pidx(pd.read_csv(BOOKDIR / "book.csv", index_col=0)).excess.loc[POST:].to_numpy()
rows = []
rows.append(dict(method="builder metrics.json (A4 ci.py, seed 20260946)", lo=0.05295889396490049, hi=1.099754331486121))
for sd in [20260946, 1, 2]:
    lo, hi, _ = calib_ci(b, 0.90, seed=sd); rows.append(dict(method=f"A4 ci.py 90%, seed {sd}", lo=lo, hi=hi))
los = [calib_ci(b, 0.90, seed=sd)[0] for sd in range(100, 150)]
rows.append(dict(method="A4 ci.py 90%, 50 seeds: min / median / max lower bound", lo=min(los), hi=np.median(los), note=f"max {max(los):.3f}; share lo>0 {np.mean(np.array(los) > 0):.2f}"))
lo, hi, _ = boot_ci(b, 0.90, seed=1); rows.append(dict(method="independent numpy re-impl 90%", lo=lo, hi=hi))
lo, hi, _ = calib_ci(b, 0.95, seed=20260946); rows.append(dict(method="A4 ci.py 95% (A4 §6 rule for crash-exposed, n<120)", lo=lo, hi=hi))
lo, hi, _ = boot_ci(b, 0.95, seed=1); rows.append(dict(method="independent re-impl 95%", lo=lo, hi=hi))
lo, hi, _ = boot_ci(b, 0.90, seed=1, crash=(0.2 / 12, -6.0)); rows.append(dict(method="independent 90% with declared crash layer (0.2/yr, -6 sd)", lo=lo, hi=hi))
lo, hi, _ = boot_ci(b, 0.95, seed=1, crash=(0.2 / 12, -6.0)); rows.append(dict(method="independent 95% with crash layer", lo=lo, hi=hi))
from scipy import stats as ss
rows.append(dict(method="series skew / excess kurtosis", lo=ss.skew(b), hi=ss.kurtosis(b)))
o = pd.DataFrame(rows); print(o.round(3).to_string()); o.to_csv(OUT / "t7_inference.csv", index=False)

# ledger timing
led = open(REPO / "research/cycle6_prereg_ledger.md").read()
tr = pd.read_csv(REPO / "research/cycle6/trial_ledger.csv")
fw = re.search(r"\| (\S+) \| framework \| FRAMEWORK \|", led).group(1)
print("FRAMEWORK (B=9,999 in §9) ledgered:", fw, "| first trial row:", tr.utc.min(),
      "| BOOK spec inference block has crash key:", '"crash"' in open(REPO / "research/cycle6/specs/BOOK.md").read().split("\"inference\"")[1][:200])
