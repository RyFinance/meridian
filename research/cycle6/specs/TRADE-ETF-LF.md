# TRADE-ETF-LF -- long/flat ETF tradable variant (schema cycle6-variant-v1)

Status: draft by the cycle-6 TRADABLE-VARIANTS agent, 2026-09-26, **before any variant return**. Its own ledger
entry; it never replaces the paper BOOK (`research/cycle6/specs/BOOK.md`, SHA-256
`8843f97fe7eb6137f338f458eb9d09f406daea082d19e186cc37a577601a706b`), whose frozen net output remains the verdict of record.

- Variant code: `research/cycle6/tradable/*.py`, code SHA-256 `82cbf4258647ad57d1a51e506eadd48348504a1512ec81b5da5f1f9877060809` (sha256 over the files'
  bytes concatenated in file-name byte order); engine (read-only: panel, io, inference, guards) `e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422`.
- Snapshot: `cycle6_trade_v1` in `data/cycle6/snapshot_store`, manifest SHA-256 `940335bf4f1a3d188587b9b55c03ba151b598332a8865de4f9ad527d404787c6`
  (66 records: vehicle prices/distributions/splits, USD/CAD, sizing levels, completeness record, and byte copies of the
  frozen BOOK `weights.csv`/`book.csv`/`sleeves.csv`/`metrics.json`, the six included components' `weights.parquet`/
  `net.csv`/`metrics.json`, and the eval panels/series used). Acquisition: `research/cycle6/tradable_data/acquire.py`;
  record `data/cycle6/trade/completeness.json`.
- Guards (`research/cycle6/tradable/vguards.py`, engine semantics): spec hash in `research/cycle6_prereg_ledger.md` under
  this ID; engine, code and snapshot hashes equal the params; no earlier trial for this spec hash (bug-fix entry
  rule as FRAMEWORK §8); 'started'/'ok'/'failed' rows with kind `variant` in `research/cycle6/trial_ledger.csv`.
  The runner also refuses if the frozen BOOK output's `run.spec_sha256` differs from the ledgered BOOK hash or if its
  included sleeves differ from this spec's (CARRY-FX, SEAS-FX, TSMOM-CM, TSMOM-FI, VAL-FX, XSMOM-FX, CORE).
- Command (register with `research.data_snapshot`; reads only the frozen view):
  `python -m research.cycle6.tradable.runner --spec research/cycle6/specs/TRADE-ETF-LF.md --snapshot-root {snapshot_root}
  --membership {membership_path} --out reports/cycle6_core_premia/variants/TRADE-ETF-LF/` with membership
  `trade/vehicle_universe.csv`.

## What is mapped (mechanical; nothing chosen by performance)

Same sleeves, same ERC/scale weights, same signals and instrument weights as the frozen BOOK. For holding month h the
book-level target of instrument i is x_(h,i) = sum_S k_h w_(S,h) W_(S,h-1,i) (BOOK `scaled_weight` x component
weight formed at h-1), plus the core k_h w_CORE,h x (0.6 SPY, 0.4 IEF) as instruments `CORE:SPY`, `CORE:IEF`
(`research/cycle6/tradable/mapping.py`). Vehicle rule, fixed from instrument availability only:
1. **CM**: the ETF that is the instrument's own construction in the frozen candidate list (same ticker).
2. **FX**: the single-currency Invesco CurrencyShares trust for that currency (US-listed).
3. **FI**: a US- or TSX-listed single-country government-bond ETF whose index maturity band contains 10y and lies
   within 5-15y; US-listed preferred when both exist. (IEF 7-10y; ZFM.TO BMO Mid Federal 5-10y per issuer
   description.) ETNs, leveraged/inverse, multi-country and UCITS/non-North-American listings are excluded.
4. **Core**: SPY, IEF (as in BOOK).
5. Otherwise the instrument is **dropped** (weight 0, recorded in `dropped.csv` and metrics).
A vehicle is available in month h iff it has a price in calendar month h-1 and a holding-period return in h (no
backfill before inception; delisted vehicles unavailable after their last price). An instrument whose vehicle is
unavailable in h is dropped for that month.

## Variant (a): long/flat ETF, TFSA/RRSP-eligible

- **Long/flat**: negative book-level instrument weights (summed across sleeves, before mapping) -> 0; no shorts, no
  futures, no leverage. Instruments mapping to the same vehicle (CORE:IEF + FI_US_10Y) are summed after clipping.
- **Scale**: the BOOK's own 10%-ex-ante scaling is kept; the vehicle vector is scaled by min(1, 1/gross) so gross
  <= 1 x NAV (never scaled up after clipping/dropping); the remainder is cash. Scale = min(10% target, cash
  constraint).
- **Accounts**: TFSA and RRSP (withholding as below). Headline: **TFSA, CAD-funded, CAD 100,000, IBKR conversion**.
- Sensitivities (headline only): Norbert 0.15%; spreads x3; IEF 871(k)-exempt.

| Instrument (sleeves) | Vehicle | First month available | Note |
|---|---|---|---|
| CORE:SPY | SPY (USD) | 1993-02 (core itself from 2002-08) | us_ric distributions |
| CORE:IEF, FI_US_10Y (TSMOM-FI) | IEF (USD) | 2002-08 | us_ric_bond distributions |
| FI_CA_10Y (TSMOM-FI) | ZFM.TO (CAD, TSX) | 2010-05 | CA assets; no US withholding |
| FI_CH/DE/ES/FR/IT/JP/NO/NZ/SE/UK_10Y (TSMOM-FI) | **dropped** | - | no US/TSX single-country 5-15y govt ETF |
| FX_EUR (CARRY/SEAS/VAL/XSMOM-FX) | FXE | 2006-01 | |
| FX_JPY | FXY | 2007-03 | |
| FX_GBP | FXB | 2006-07 | |
| FX_AUD | FXA | 2006-07 | |
| FX_CAD | FXC | 2006-07 | for a CAD-funded investor this is close to CAD cash vs a USD position |
| FX_CHF | FXF | 2006-07 | |
| FX_SEK | FXS -> **dropped all months** | never | FXS liquidated 2020-05-22; no free history (Yahoo 404; Stooq bot-check not bypassed; LSE none) |
| FX_NOK, FX_NZD | **dropped** | - | no single-currency ETF ever listed in US/CA |
| CM_GOLD, SILVER, PALLADIUM, PLATINUM (TSMOM-CM) | GLD, SLV, PALL, PPLT | 2004-12, 2006-05, 2010-02, 2010-02 | grantor trusts |
| CM_WTI, NATGAS, BRENT, GASOLINE | USO, UNG, BNO, UGA | 2006-05, 2007-05, 2010-07, 2008-03 | US PTP/K-1 pools (see risks) |
| CM_COPPER, CORN, SOYBEANS, WHEAT | CPER, CORN, SOYB, WEAT | 2011-12, 2010-07, 2011-10, 2011-10 | US PTP/K-1 pools |

## Costs, FX conversion, withholding (declared defaults; sources: tradability `costs.json`, `etf_universe.csv`,
`futures_specs.csv`)

- **Half-spread per side** = etf_universe `spread_bps`/2 on traded notional: SPY 0.5 (IVV mega-class value, SPY not
  listed), IEF 0.5, FXE 1.5, FXY 2, FXB 2, FXA 2.5, FXC 2.5, FXF 3, GLD 0.5, SLV 1, USO 1.5, UNG 3, CPER 3; vehicles
  not in the universe: ZFM.TO 1.5 (XGB value), PALL/PPLT/BNO/UGA/CORN/SOYB/WEAT 3 (CPER/small-AUM value).
- **Commission (IBKR Pro Fixed, declared)**: US-listed USD 0.005/share, min USD 1.00, max 1% of trade value; TSX CAD
  0.01/share, min CAD 1.00, max 0.5%. Minimum tickets apply on integer-rounded paths only.
- **CAD/USD conversion**: primary **IBKR 0.03%** on the traded notional of every vehicle not denominated in the funding
  currency (and on futures P&L when funding is CAD); **Norbert's gambit 0.15%** reported as a sensitivity.
- **Withholding** on cash distributions (Yahoo ex-date amounts / prior close, summed over the holding period, long
  positions only), by tax class: `us_ric` (SPY) and `us_ric_bond` (IEF) -- TFSA 15% (unrecoverable), RRSP 0% (treaty
  Art. XXI), taxable margin account 0% charged (15% withheld is creditable; reported as `withholding_creditable`);
  `ca_listed_us_assets` -- 15% in TFSA and RRSP (no vehicle in this mapping has this class); `ca_domestic` (ZFM.TO)
  and `none` (currency trusts: bank-deposit interest; commodity trusts/pools) -- 0%. Sensitivity: IEF distributions
  exempt as IRC 871(k) interest-related dividends (broker-dependent in practice).
- **Cash/financing (A5 §E)**: cash earns max(0, r_F - 0.50pp); negative cash pays r_F + 2pp; r_F = funding-currency
  3m rate at month-end h-1 (USD: H.15 3m T-bill as BOOK; CAD: the frozen CA short rate used by the paper FX
  construction). Excess = total - r_F/12.

## Execution, sizing, rounding, currencies

- **Execution lag**: identical to BOOK -- weights formed at month-end t, traded at the close of each vehicle's first
  session of t+1; holding period to its first session of t+2 (engine `panel.net_period_returns`). Monthly rebalance.
- **Constant capital** A in the funding currency: every month positions are re-sized against A (P&L withdrawn/topped
  up) so the rounding granularity is stationary; return = P&L / A. A in CAD = 25,000 / 100,000 / 250,000;
  USD-funded accounts use A_CAD / USD-CAD at the first active month.
- **Rounding**: integer shares, round-half-away-from-zero, at the as-traded close (Yahoo split-adjusted Close x later
  split ratios); plus one unrounded ("ideal") path per account type and funding currency at CAD 100,000 (no minimum
  tickets). Turnover = |change in quantity| x current unit notional (drift is implicit).
- **Currencies**: two funding conventions, each reported in its own currency: **CAD-funded** (cash in CAD; USD
  vehicles translated at USD/CAD, FRED DEXCAUS) and **USD-funded** (cash in USD after conversion; CAD vehicles
  translated). Tracking vs the paper BOOK uses the USD-funded excess series (BOOK is USD excess).

## Known limitations (reported, not repaired)

- All TSMOM-FI non-US/CA bonds, NOK, NZD and SEK exposures are dropped; long/flat removes every short. The variant is a
  different, long-biased, cash-heavy portfolio (pre-run weights-only check: max gross 0.57); tracking vs BOOK is
  expected to be loose and is reported, not tuned.
- Commodity pools (USO, UNG, BNO, UGA, CPER, CORN, SOYB, WEAT) are US PTPs issuing K-1s; a broker may restrict them for
  non-US persons and IRC 1446(f) withholding on sale proceeds is assumed not to apply (qualified-notice exception) --
  not verified, not modelled. Currency trusts are small/micro AUM (closure risk: FXS closed in 2020).
- ZFM.TO maturity band is from issuer description, not re-verified live; spreads/commissions are declared defaults.
- Withholding applies to cash distributions only; foreign withholding inside ETFs and ETF expense ratios are embedded in
  total returns.

## Params

```json
{
 "schema": "cycle6-variant-v1",
 "id": "TRADE-ETF-LF",
 "variant": "ETF-LF",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "code_sha256": "82cbf4258647ad57d1a51e506eadd48348504a1512ec81b5da5f1f9877060809",
 "snapshot_manifest_sha256": "940335bf4f1a3d188587b9b55c03ba151b598332a8865de4f9ad527d404787c6",
 "snapshot_version": "cycle6_trade_v1",
 "book_spec_sha256": "8843f97fe7eb6137f338f458eb9d09f406daea082d19e186cc37a577601a706b",
 "inputs": {
  "book_weights": "trade/inputs/book/weights.csv",
  "book_csv": "trade/inputs/book/book.csv",
  "book_metrics": "trade/inputs/book/metrics.json",
  "components": {
   "CARRY-FX": "trade/inputs/components/CARRY-FX/weights.parquet",
   "SEAS-FX": "trade/inputs/components/SEAS-FX/weights.parquet",
   "TSMOM-CM": "trade/inputs/components/TSMOM-CM/weights.parquet",
   "TSMOM-FI": "trade/inputs/components/TSMOM-FI/weights.parquet",
   "VAL-FX": "trade/inputs/components/VAL-FX/weights.parquet",
   "XSMOM-FX": "trade/inputs/components/XSMOM-FX/weights.parquet"
  },
  "core": {
   "sleeve": "CORE",
   "markets": [
    "SPY",
    "IEF"
   ],
   "weights": [
    0.6,
    0.4
   ]
  }
 },
 "data": {
  "etf_adjclose": "trade/etf_adjclose_daily.parquet",
  "etf_close": "trade/etf_close_daily.parquet",
  "etf_splits": "trade/etf_splits.parquet",
  "etf_dividends": "trade/etf_dividends.parquet",
  "fx_spot_monthly": "trade/inputs/eval/signals/fx_spot_monthly.parquet",
  "sizing_levels": "trade/futures_sizing_levels_daily.parquet",
  "usdcad": "trade/usdcad_daily.parquet",
  "tbill": {
   "path": "trade/inputs/eval/series/tbill_3m_daily.parquet",
   "market_id": "TB3M"
  },
  "cad_rate": {
   "path": "trade/inputs/eval/signals/fx_foreign_rate_monthly.parquet",
   "market_id": "FX_CAD"
  },
  "paper_panels": [
   {
    "path": "trade/inputs/eval/panels/daily_excess_FX.parquet"
   },
   {
    "path": "trade/inputs/eval/panels/daily_excess_CM.parquet"
   },
   {
    "path": "trade/inputs/eval/panels/daily_excess_FI10.parquet"
   },
   {
    "path": "trade/inputs/eval/series/core_etf_excess_daily.parquet",
    "prefix": "CORE:"
   }
  ]
 },
 "long_only": true,
 "gross_cap": 1.0,
 "mapping": {
  "CORE:SPY": [
   {
    "vehicle": "SPY",
    "from": null
   }
  ],
  "CORE:IEF": [
   {
    "vehicle": "IEF",
    "from": null
   }
  ],
  "FX_EUR": [
   {
    "vehicle": "FXE",
    "from": null
   }
  ],
  "FX_JPY": [
   {
    "vehicle": "FXY",
    "from": null
   }
  ],
  "FX_GBP": [
   {
    "vehicle": "FXB",
    "from": null
   }
  ],
  "FX_AUD": [
   {
    "vehicle": "FXA",
    "from": null
   }
  ],
  "FX_CAD": [
   {
    "vehicle": "FXC",
    "from": null
   }
  ],
  "FX_CHF": [
   {
    "vehicle": "FXF",
    "from": null
   }
  ],
  "FX_SEK": [
   {
    "vehicle": "FXS",
    "from": null,
    "reason": "FXS liquidated 2020-05-22; no free price history -> unavailable in every month"
   }
  ],
  "FX_NOK": [
   {
    "vehicle": null,
    "reason": "no single-currency NOK ETF ever listed in US/CA"
   }
  ],
  "FX_NZD": [
   {
    "vehicle": null,
    "reason": "no single-currency NZD ETF ever listed in US/CA"
   }
  ],
  "FI_US_10Y": [
   {
    "vehicle": "IEF",
    "from": null
   }
  ],
  "FI_CA_10Y": [
   {
    "vehicle": "ZFM.TO",
    "from": null
   }
  ],
  "FI_CH_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_DE_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_ES_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_FR_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_IT_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_JP_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_NO_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_NZ_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_SE_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "FI_UK_10Y": [
   {
    "vehicle": null,
    "reason": "no US- or TSX-listed single-country government bond ETF with a 5-15y maturity band (ETNs, UCITS, multi-country excluded)"
   }
  ],
  "CM_GOLD": [
   {
    "vehicle": "GLD",
    "from": null
   }
  ],
  "CM_SILVER": [
   {
    "vehicle": "SLV",
    "from": null
   }
  ],
  "CM_PALLADIUM": [
   {
    "vehicle": "PALL",
    "from": null
   }
  ],
  "CM_PLATINUM": [
   {
    "vehicle": "PPLT",
    "from": null
   }
  ],
  "CM_WTI": [
   {
    "vehicle": "USO",
    "from": null
   }
  ],
  "CM_NATGAS": [
   {
    "vehicle": "UNG",
    "from": null
   }
  ],
  "CM_BRENT": [
   {
    "vehicle": "BNO",
    "from": null
   }
  ],
  "CM_GASOLINE": [
   {
    "vehicle": "UGA",
    "from": null
   }
  ],
  "CM_COPPER": [
   {
    "vehicle": "CPER",
    "from": null
   }
  ],
  "CM_CORN": [
   {
    "vehicle": "CORN",
    "from": null
   }
  ],
  "CM_SOYBEANS": [
   {
    "vehicle": "SOYB",
    "from": null
   }
  ],
  "CM_WHEAT": [
   {
    "vehicle": "WEAT",
    "from": null
   }
  ]
 },
 "vehicles": {
  "BNO": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "CORN": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "CPER": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXA": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 2.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXB": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 2.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXC": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 2.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXE": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 1.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.003
  },
  "FXF": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXS": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "FXY": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 2.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "GLD": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 0.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.003
  },
  "IEF": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 0.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "us_ric_bond",
   "borrow_fee_ann": 0.003
  },
  "PALL": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "PPLT": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "SLV": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 1.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.003
  },
  "SOYB": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "SPY": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 0.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "us_ric",
   "borrow_fee_ann": 0.003
  },
  "UGA": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "UNG": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.003
  },
  "USO": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 1.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.003
  },
  "WEAT": {
   "kind": "etf",
   "ccy": "USD",
   "half_spread_bp": 3.0,
   "commission": {
    "type": "per_share",
    "per_share": 0.005,
    "min": 1.0,
    "max_pct": 0.01
   },
   "tax_class": "none",
   "borrow_fee_ann": 0.01
  },
  "ZFM.TO": {
   "kind": "etf",
   "ccy": "CAD",
   "half_spread_bp": 1.5,
   "commission": {
    "type": "per_share",
    "per_share": 0.01,
    "min": 1.0,
    "max_pct": 0.005
   },
   "tax_class": "ca_domestic",
   "borrow_fee_ann": 0.01
  }
 },
 "costs": {
  "conv_rate": 0.0003,
  "conv_rate_note": "IBKR IdealPro ~0.03% primary; Norbert's gambit 0.15% sensitivity",
  "cash_spread": 0.005,
  "financing_spread": 0.02
 },
 "funding": [
  "CAD",
  "USD"
 ],
 "sizes_cad": [
  25000,
  100000,
  250000
 ],
 "post_pub_cutoff": "2019-02",
 "inference": {
  "ci_level": 0.9,
  "ci_B": 499,
  "seed": 20260946
 },
 "accounts": {
  "TFSA": {
   "withholding": {
    "us_ric": 0.15,
    "us_ric_bond": 0.15,
    "ca_listed_us_assets": 0.15
   }
  },
  "RRSP": {
   "withholding": {
    "us_ric": 0.0,
    "us_ric_bond": 0.0,
    "ca_listed_us_assets": 0.15
   }
  }
 },
 "headline": {
  "account": "TFSA",
  "F": "CAD",
  "size_cad": 100000
 },
 "sensitivities": [
  {
   "name": "norbert_0.15pct",
   "conv_rate": 0.0015
  },
  {
   "name": "spread_3x",
   "spread_mult": 3.0
  },
  {
   "name": "ief_871k_exempt",
   "withholding_overrides": {
    "us_ric_bond": 0.0
   }
  }
 ]
}
```
