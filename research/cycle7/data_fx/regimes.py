"""Cycle-7 FX regime table (FRAMEWORK §3), per currency-month. DATA ONLY: no return enters any rule here.

Sources (all free, raw copies under data/cycle7/fx/raw/):
  * IRR = Ilzetzki, Reinhart & Rogoff, ERA_Classification_Monthly_1940-2019.xlsx (sheet 'Fine', monthly to 2019-12)
    and Unified_market_1946-2021.xlsx (sheet 'Unified': 1 = dual/multiple/parallel rates) from ilzetzki.com.
    Coarse code derived from the fine code with IRR's own legend (fine 1-4 -> 1, 5-8 -> 2, 9-12 -> 3, 13 -> 4,
    14 -> 5, 15 -> 6); checked against the 'Coarse' sheet where both exist (mismatches recorded).
  * AREAER 2023 overview, Table 4 (de facto classification as of 2023-04-30), IMF eLibrary PDF. Only this
    vintage was reachable (2020-2022, 2024, 2025 overview PDFs not found at the same path).

Rules (FRAMEWORK §3, applied mechanically):
  (a) exclude if IRR coarse == 1 (hard peg / band <= +-2% / no separate legal tender).
  (b) NDF-only status recorded (not an exclusion by itself); spot must be onshore (build uses BIS central-bank
      daily rates for NDF currencies) and a free PIT short rate must exist (else no excess return -> no rows).
  (c) exclude if IRR coarse == 6 (dual market, parallel data missing) or IRR Unified dummy == 1 (dual/multiple/
      parallel rates), and the explicit binding-control episodes listed in CONTROLS.
  (d) exclude redenomination months in REDENOM.
  Extension past IRR end (2019-12 fine; unified dummy to its last non-missing month): the last IRR classification is extended only if AREAER
  2023 confirms it on the exclusion-relevant dimension (peg vs non-peg; a dual-market code can never be
  confirmed). If not confirmed -> months after 2019-12 are excluded ('unclassified'). Currencies with no IRR
  column (TWD: not an IMF member, absent from IRR and AREAER) are unclassifiable -> excluded throughout.
  After the unified dummy ends the dual-market flag is unavailable; only the explicit CONTROLS list applies there (disclosed).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "cycle7" / "fx" / "raw"
IRR_COUNTRY = {  # currency -> IRR column label (whitespace-normalised)
    "MXN": "Mexico", "BRL": "Brazil", "CLP": "Chile", "COP": "Colombia", "PEN": "Peru", "ARS": "Argentina",
    "ZAR": "South Africa", "TRY": "Turkey", "PLN": "Poland", "HUF": "Hungary", "CZK": "Czech Rep.",
    "RUB": "Russia", "ILS": "Israel", "INR": "India", "IDR": "Indonesia", "KRW": "Korea", "TWD": None,
    "PHP": "Philippines", "THB": "Thailand", "MYR": "Malaysia", "SGD": "Singapore", "HKD": "Hong Kong",
    "CNY": "China, PR", "DKK": "Denmark", "ISK": "Iceland", "LKR": "Sri Lanka", "VEB": "Venezuela",
    "DEM": "Germany", "FRF": "France", "ITL": "Italy", "NLG": "Netherlands", "BEF": "Belgium", "ESP": "Spain",
    "AUD": "Australia", "CAD": "Canada", "CHF": "Switzerland", "EUR": None, "GBP": "United Kingdom",
    "JPY": "Japan", "NOK": "Norway", "NZD": "New Zealand", "SEK": "Sweden",
}
UNIFIED_ISO = {"MXN": "MEX", "BRL": "BRA", "CLP": "CHL", "COP": "COL", "PEN": "PER", "ARS": "ARG", "ZAR": "ZAF",
               "TRY": "TUR", "PLN": "POL", "HUF": "HUN", "CZK": "CZE", "RUB": "RUS", "ILS": "ISR", "INR": "IND",
               "IDR": "IDN", "KRW": "KOR", "PHP": "PHL", "THB": "THA", "MYR": "MYS", "SGD": "SGP", "HKD": "HKG",
               "CNY": "CHN", "DKK": "DNK", "ISK": "ISL", "LKR": "LKA", "VEB": "VEN", "DEM": "DEU", "FRF": "FRA",
               "ITL": "ITA", "NLG": "NLD", "BEF": "BEL", "ESP": "ESP", "AUD": "AUS", "CAD": "CAN", "CHF": "CHE",
               "GBP": "GBR", "JPY": "JPN", "NOK": "NOR", "NZD": "NZL", "SEK": "SWE"}
# AREAER 2023 Table 4 (as of 2023-04-30), transcribed from the extracted PDF text; mapped to IRR coarse buckets:
# no separate legal tender / currency board / conventional peg / stabilized / horizontal band -> 1;
# crawling peg / crawl-like -> 2; other managed / floating -> 3; free floating -> 4.
AREAER_2023 = {
    "MXN": ("free floating", 4), "BRL": ("floating", 3), "CLP": ("floating", 3), "COP": ("floating", 3),
    "PEN": ("floating", 3), "ARS": ("crawling peg (3/22)", 2), "ZAR": ("floating", 3),
    "TRY": ("crawl-like (7/22)", 2), "PLN": ("free floating", 4), "HUF": ("floating", 3),
    "CZK": ("floating", 3), "RUB": ("free floating", 4), "ILS": ("floating", 3), "INR": ("floating", 3),
    "IDR": ("floating", 3), "KRW": ("floating", 3), "PHP": ("floating", 3), "THB": ("floating", 3),
    "MYR": ("floating", 3), "SGD": ("crawl-like", 2), "HKD": ("currency board", 1),
    "CNY": ("other managed (3/22)", 3), "DKK": ("conventional peg (ERM II)", 1), "ISK": ("floating", 3),
    "LKR": ("crawl-like (5/22)", 2), "VEB": ("other managed (as of 2021-04-30)", 3),
    # cycle-6 G10 (only relevant to FX-DEEP bookkeeping; DEEP months end 1976-07)
    "AUD": ("free floating", 4), "CAD": ("free floating", 4), "JPY": ("free floating", 4),
    "NOK": ("free floating", 4), "SEK": ("free floating", 4), "GBP": ("free floating", 4),
    "CHF": ("floating (1/22)", 3), "NZD": ("floating", 3),
}
NDF_ONLY = {"KRW", "TWD", "INR", "IDR", "PHP", "BRL", "CLP", "COP", "PEN", "CNY", "MYR", "ARS"}
# (c) explicit binding capital-control episodes (inclusive months)
CONTROLS = {
    "MYR": [("1998-09", "2005-07", "capital controls / ringgit peg (FRAMEWORK §3 example)")],
    "RUB": [("2022-03", "2026-09", "capital controls from 2022-02-28 (FRAMEWORK §3 example), still in force")],
    "ARS": [("2011-11", "2015-12", "cepo cambiario (FX purchase controls)"),
            ("2019-09", "2025-04", "cepo cambiario reinstated 2019-09-01; most individual limits lifted 2025-04-14")],
}
# (d) redenomination months
REDENOM = {"TRY": ["2005-01"], "RUB": ["1998-01"], "BRL": ["1994-07"], "PLN": ["1995-01"], "MXN": ["1993-01"],
           "ILS": ["1985-09"], "ISK": ["1981-01"], "PEN": ["1991-07"], "ARS": ["1992-01"],
           "VEB": ["2008-01", "2018-08", "2021-10"]}


def _norm(s) -> str:
    return " ".join(str(s).replace("nan", " ").split())


def load_irr():
    f = RAW / "irr" / "ERA_Classification_Monthly_1940-2019.xlsx"
    out = {}
    for sheet in ("Fine", "Coarse"):
        d = pd.read_excel(f, sheet_name=sheet, header=None)
        labels = {_norm(f"{d.iloc[4, i]} {d.iloc[5, i]}"): i for i in range(2, d.shape[1])}
        body = d.iloc[7:, :].copy()
        per = pd.PeriodIndex([pd.Period(str(x).replace("M", "-"), "M") for x in body.iloc[:, 1]], freq="M")
        cols = {}
        for ccy, lab in IRR_COUNTRY.items():
            if lab is None:
                continue
            i = labels.get(_norm(lab))
            if i is None:
                raise KeyError(f"IRR column not found: {lab}")
            cols[ccy] = pd.to_numeric(pd.Series(body.iloc[:, i].to_numpy(), index=per), errors="coerce")
        out[sheet] = pd.DataFrame(cols)
    u = pd.read_excel(RAW / "irr" / "Unified_market_1946-2021.xlsx", sheet_name="Unified", header=None)
    iso = {str(u.iloc[5, i]).strip(): i for i in range(1, u.shape[1])}
    ub = u.iloc[10:, :]
    lab = ub.iloc[:, 0].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    ok = lab.str.match(r"^\d{4}(M\d{1,2})?$")  # January rows are labelled with the year only
    ub, lab = ub[ok], lab[ok]
    uper = pd.PeriodIndex([pd.Period((x + "-1") if "M" not in x else x.replace("M", "-"), "M") for x in lab],
                          freq="M")
    uni = {c: pd.to_numeric(pd.Series(ub.iloc[:, iso[i3]].to_numpy(), index=uper), errors="coerce")
           for c, i3 in UNIFIED_ISO.items() if i3 in iso}
    return out["Fine"], out["Coarse"], pd.DataFrame(uni)


def fine_to_coarse(f):
    return np.select([f <= 4, f <= 8, f <= 12, f == 13, f == 14, f == 15], [1, 2, 3, 4, 5, 6], np.nan) \
        if np.ndim(f) else np.nan


def build(currencies, start="1971-01", end="2026-09"):
    fine, coarse_sheet, uni = load_irr()
    months = pd.period_range(start, end, freq="M")
    rows, coarse_mismatch = [], {}
    for c in currencies:
        f = fine[c].reindex(months) if c in fine else pd.Series(np.nan, index=months)
        cz = pd.Series(np.where(f.notna(), np.select([f <= 4, f <= 8, f <= 12, f == 13, f == 14, f == 15],
                                                     [1, 2, 3, 4, 5, 6], np.nan), np.nan), index=months)
        if c in coarse_sheet:
            cs = coarse_sheet[c].reindex(months)
            both = cz.notna() & cs.notna()
            coarse_mismatch[c] = int((cz[both] != cs[both]).sum())
        un = uni[c].reindex(months) if c in uni else pd.Series(np.nan, index=months)
        irr_last_m = f.last_valid_index()
        irr_last = cz[irr_last_m] if irr_last_m is not None else np.nan
        ar = AREAER_2023.get(c)
        confirmed = False
        if ar is not None and irr_last_m is not None and irr_last != 6:
            confirmed = (irr_last == 1) == (ar[1] == 1)
        for m in months:
            src, co, fi = None, cz[m], f[m]
            if pd.notna(co):
                src = "IRR fine (coarse derived)"
            elif irr_last_m is not None and m > irr_last_m:
                if confirmed:
                    co, fi, src = irr_last, f[irr_last_m], f"IRR {irr_last_m} extended; AREAER 2023 confirms ({ar[0]})"
                else:
                    src = (f"IRR ends {irr_last_m}; AREAER 2023 {ar[0] if ar else 'n/a'} does not confirm IRR coarse "
                           f"{irr_last:.0f}" if pd.notna(irr_last) else "IRR ends; no AREAER")
            elif irr_last_m is None:
                src = "no IRR/AREAER classification (not covered)"
            else:
                src = "IRR missing for month"
            reasons = []
            if pd.isna(co):
                reasons.append("(a/c) unclassified: " + src)
            elif co == 1:
                reasons.append(f"(a) IRR coarse 1 (fine {fi:.0f})")
            elif co == 6:
                reasons.append("(c) IRR coarse 6 dual market, parallel data missing")
            if pd.notna(un[m]) and un[m] == 1:
                reasons.append("(c) IRR Unified dummy = 1 (dual/multiple/parallel rates)")
            ctrl = [w for a, b, w in CONTROLS.get(c, []) if pd.Period(a, "M") <= m <= pd.Period(b, "M")]
            if ctrl:
                reasons.append("(c) " + "; ".join(ctrl))
            red = str(m) in REDENOM.get(c, [])
            if red:
                reasons.append("(d) redenomination month")
            rows.append({"ccy": c, "month": m.to_timestamp(how="end").normalize(), "irr_fine": fi,
                         "irr_coarse": co, "classification_source": src,
                         "irr_unified_dual": un[m], "areaer_2023": ar[0] if ar else None,
                         "ndf_only": c in NDF_ONLY, "capital_control_episode": "; ".join(ctrl) or None,
                         "redenomination": red, "exclude": bool(reasons), "reason": " | ".join(reasons) or None})
    return pd.DataFrame(rows), coarse_mismatch
