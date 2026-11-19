"""Test 9: independent numpy re-implementation of the A4 null-calibrated HAC t (AR(p<=3) BIC null on the demeaned
series, residual bootstrap + declared crash layer, Bartlett HAC t with L = max(NW, ceil(0.10 n)), p=(1+#)/(B+1), max of
plain/crash) and of the calibrated interval; ledger timing checks."""
from harness import *
import re

def nw_var(x, L):
    x = x - x.mean(); n = len(x); v = x @ x / n
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (x[l:] @ x[:-l]) / n
    return v

def tstat(x, L):
    return x.mean() / np.sqrt(nw_var(x, L) / len(x))

def fit_ar(e, pmax=3):
    n = len(e); best = None
    for p in range(pmax + 1):
        if p == 0:
            u = e[pmax:]; phi = np.zeros(0)
        else:
            X = np.column_stack([e[pmax - j - 1:n - j - 1] for j in range(p)]); Y = e[pmax:]
            phi = np.linalg.lstsq(X, Y, rcond=None)[0]; u = Y - X @ phi
        bic = len(u) * np.log(u.var()) + p * np.log(len(u))
        if best is None or bic < best[0]:
            best = (bic, p, phi, u - u.mean())
    return best[1:]

def indep_p(x, B=4999, seed=11, crash=None, burn=200):
    x = np.asarray(x, float); n = len(x); L = max(int(np.floor(4 * (n / 100) ** (2 / 9))), int(np.ceil(0.10 * n)))
    T = tstat(x, L); p_, phi, u = fit_ar(x - x.mean()); rng = np.random.default_rng(seed); cnt = 0
    for b in range(B):
        if crash is None:
            eps = rng.choice(u, n + burn)
        else:
            cp, J = crash; z = rng.standard_normal(n + burn) + J * (rng.random(n + burn) < cp)
            eps = u.std() * (z - cp * J) / np.sqrt(1 + cp * (1 - cp) * J * J)
        y = np.zeros(n + burn)
        for t in range(n + burn):
            y[t] = eps[t] + sum(phi[j] * y[t - 1 - j] for j in range(p_) if t - 1 - j >= 0)
        cnt += tstat(y[burn:], L) >= T
    return (1 + cnt) / (B + 1), p_, L, T

base = run()
rows = []
for label, x in [("full 1988-02+", base), ("post-KMVP 2013-09+", base.loc[KMVP_CUT:])]:
    p0, ar, L, T = indep_p(x.to_numpy()); p1, *_ = indep_p(x.to_numpy(), crash=CRASH)
    rows.append(dict(window=label, n=len(x), t_HAC=T, L=L, ar_order=ar, p_indep_plain=p0, p_indep_crash=p1,
                     p_indep=max(p0, p1), p_A4_code=pval(x)))
t = pd.DataFrame(rows); print(t.round(4).to_string(index=False)); t.to_csv(OUT / "t9_inference.csv", index=False)
led = open(REPO / "research/cycle7_prereg_ledger.md").read()
k_row = re.search(r"\| (\S+) \| k \| k \|.*", led).group(0)[:120]
fw = re.search(r"\| (\S+) \| framework \| FRAMEWORK \|", led).group(1)
tr = pd.read_csv(REPO / "research/cycle7/trial_ledger.csv")
print("FRAMEWORK (pooling §5, POSITIVE rule) ledgered:", fw)
print("k row:", k_row)
print("first cycle-7 run:", tr.utc.min(), "| CARRY-FX run:", tr[tr.spec_id == "CARRY-FX"].utc.tolist())
