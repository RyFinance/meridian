"""DESCRIPTIVE (not a trial): large monthly moves in raw BIS daily spot (CCY per USD) that fell in FRAMEWORK §3
excluded currency-months of the FX-EM sample, restricted to currencies that are PASS in FX-EM. Depreciation of the
currency vs USD = positive CCY/USD change. Instrument-level data only; no strategy return."""
import pandas as pd, numpy as np
from pathlib import Path
R = Path(__file__).resolve().parents[3]
reg = pd.read_csv(R / "data/cycle7/fx/fx_regimes.csv"); reg["m"] = pd.to_datetime(reg.month).dt.to_period("M")
cl = pd.read_csv(R / "data/cycle7/fx/eval/candidate_list.csv"); passed = {m[3:] for m in cl[cl.qa_status == "PASS"].market_id}
iso = {"AR": "ARS", "BR": "BRL", "CL": "CLP", "CO": "COP", "CZ": "CZK", "DK": "DKK", "HU": "HUF", "ID": "IDR", "IL": "ILS",
       "IN": "INR", "IS": "ISK", "KR": "KRW", "MX": "MXN", "MY": "MYR", "PE": "PEN", "PH": "PHP", "PL": "PLN", "RU": "RUB",
       "SG": "SGD", "TH": "THB", "TR": "TRY", "ZA": "ZAR"}
rows = []
for cc, ccy in iso.items():
    if ccy not in passed: continue
    d = pd.read_csv(R / f"data/cycle7/fx/raw/bis_xru_d/D_{cc}.csv", usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(pd.to_numeric(d.OBS_VALUE, errors="coerce").values, index=pd.to_datetime(d.TIME_PERIOD)).dropna()
    me = s.groupby(s.index.to_period("M")).last(); ch = me.pct_change()          # CCY per USD
    ex = reg[(reg.ccy == ccy) & reg.exclude].set_index("m")
    for m, v in ch.items():
        if abs(v) >= 0.15 and m in ex.index and m >= pd.Period("1988-01", "M"):
            rows.append(dict(ccy=ccy, month=str(m), ccy_per_usd_change=v, reason=ex.loc[m, "reason"] if not isinstance(ex.loc[m, "reason"], pd.Series) else ex.loc[m, "reason"].iloc[0]))
t = pd.DataFrame(rows).sort_values(["ccy", "month"])
pd.set_option("display.width", 200); print(t.round(3).to_string(index=False))
t.to_csv(Path(__file__).parent / "masked_crash_months.csv", index=False)
