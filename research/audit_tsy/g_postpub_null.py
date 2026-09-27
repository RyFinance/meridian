"""Frozen rule, post-publication sub-period only (2019-10-01 .. 2026-08-31): circular-shift null, 2,000 draws.
  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.g_postpub_null"""
import json
import numpy as np, pandas as pd
from research.audit_tsy.common import OUT, book, hold_mask, irx_rf, sharpe, tr_from_raw, yf_raw
raw = yf_raw("TLT"); irx = yf_raw("IRX")["Close"]; tr = tr_from_raw(raw); rf_all = irx_rf(raw.index, irx)
res = {}
for nm, (a, b) in {"post_pub_2019-10_2026-08": ("2019-10-01", "2026-08-31"), "last_36m_2023-09_2026-08": ("2023-09-01", "2026-08-31")}.items():
    idx = raw.index[(raw.index >= a) & (raw.index <= b)]
    r = tr.reindex(idx).fillna(0); r.iloc[0] = 0
    rf = rf_all.reindex(idx).fillna(0); e = hold_mask(idx)
    obs = sharpe(book(r, rf, e, 2e-4)[1])
    rng = np.random.default_rng(7)
    sh = np.array([sharpe(book(r, rf, pd.Series(np.roll(e.to_numpy(), int(rng.integers(5, len(idx) - 5))), index=idx), 2e-4)[1]) for _ in range(2000)])
    res[nm] = {"years": len(idx) / 252, "active_sharpe_base": obs, "shift_p": float((np.sum(sh >= obs) + 1) / 2001),
               "null_q95": float(np.quantile(sh, .95)), "t_equiv": obs * np.sqrt(len(idx) / 252)}
(OUT / "g_postpub_null.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
