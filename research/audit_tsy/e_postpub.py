"""Pre/post-publication split (Hartley-Schwarz SSRN Aug 2019; AllocateSmartly TLT last-3-days post Oct 2019).
  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.e_postpub"""
import json
import numpy as np, pandas as pd
from research.audit_tsy.common import OUT, book, hold_mask, irx_rf, sharpe, tr_from_raw, yf_raw
raw = yf_raw("TLT"); irx = yf_raw("IRX")["Close"]; tr = tr_from_raw(raw); rf_all = irx_rf(raw.index, irx)
T = pd.concat([pd.read_csv(OUT / "c_months_dev.csv", index_col=0), pd.read_csv(OUT / "c_months_val.csv", index_col=0)])
res = {}
def s(x):
    return {"n": int(len(x)), "mean_bp": float(x.mean() * 1e4), "t": float(x.mean() / x.std() * np.sqrt(len(x)))}
for name, (a, b) in {"pre_2003-01_2019-09": ("2003-01", "2019-09"), "post_2019-10_2026-08": ("2019-10", "2026-08"),
                     "val_pre_2015-01_2019-09": ("2015-01", "2019-09")}.items():
    sub = T.loc[a:b]
    idx = raw.index[(raw.index >= a) & (raw.index <= pd.Period(b).end_time)]
    r = tr.reindex(idx).fillna(0); r.iloc[0] = 0
    m, act = book(r, rf_all.reindex(idx).fillna(0), hold_mask(idx), 2e-4)
    res[name] = {"window_ex": s(sub["win_ex"]), "active_month": s(sub["active_month"]), "active_sharpe_daily_base": sharpe(act),
                 "M_excess_sharpe_base": sharpe(m), "d10y_window_bp": float(sub["d10y_lse_bp"].mean())}
(OUT / "e_postpub.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
