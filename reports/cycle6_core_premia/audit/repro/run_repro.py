"""Build independent gross/net monthly series for the six sleeves + core; write repro_<ID>.csv and weights."""
from __future__ import annotations

import json
import sys

import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import OUT, calendar_monthly, net_period_returns, run_book, verify_snapshot  # noqa: E402
import sleeves as S  # noqa: E402

SPECS = {
    "TSMOM-FI": ("FI", lambda cut=None: S.tsmom_weights("FI", cut)),
    "TSMOM-CM": ("CM", lambda cut=None: S.tsmom_weights("CM", cut)),
    "XSMOM-FX": ("FX", lambda cut=None: S.xsmom_weights("FX", cut)),
    "VAL-FX": ("FX", lambda cut=None: S.val_fx_weights(cut)),
    "CARRY-FX": ("FX", lambda cut=None: S.carry_fx_weights(cut)),
    "SEAS-FX": ("FX", lambda cut=None: S.seas_bsv_weights("FX", cut)),
    "CORE": ("CORE", lambda cut=None: S.core_weights(cut)),
    # builder-convention variants (used only to prove the residual divergences are fully explained)
    "VAL-FX__cpi_geomean": ("FX", lambda cut=None: S.val_fx_weights(cut, cpi_geo=True)),
    "SEAS-FX__floor_excl_zero": ("FX", lambda cut=None: S.seas_bsv_weights("FX", cut, floor_excl_zero=True)),
}


def build(sid, cut=None):
    cls, fn = SPECS[sid]
    W, d = fn(cut)
    bp = 2 if cls == "CORE" else S.BP[cls]
    cal = calendar_monthly(d)
    per = net_period_returns(d)
    g, n = run_book(W, cal, per, bp)
    last = str(d.dropna(how="all").index.max().to_period("M"))
    g, n = g[g.month <= last], n[n.month <= last]   # drop holding months after the snapshot's last data
    return W, g, n


def weights_long(W):
    rows = [(str(t), k, float(v)) for t, s in W.items() for k, v in s.items()]
    return pd.DataFrame(rows, columns=["signal_month", "market_id", "weight"])


if __name__ == "__main__":
    ver = verify_snapshot()
    (OUT / "snapshot_verification.json").write_text(json.dumps(ver, indent=1))
    ids = sys.argv[1:] or list(SPECS)
    for sid in ids:
        W, g, n = build(sid)
        out = n.merge(g.rename(columns={"ret": "gross_ret", "n_held": "gross_n_held", "unpriced": "gross_unpriced"}),
                      on="month", how="outer").rename(columns={"ret": "net_ret"})
        out.to_csv(OUT / f"repro_{sid}.csv", index=False)
        weights_long(W).to_csv(OUT / f"repro_weights_{sid}.csv", index=False)
        print(sid, len(out), out.month.min(), out.month.max())
