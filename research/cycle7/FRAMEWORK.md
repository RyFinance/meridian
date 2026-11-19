# Cycle 7 framework: frozen specs, new samples (written before any cycle-7 return)

2026-09-27. Governs every cycle-7 return. Its SHA-256 is the first entry in `research/cycle7_prereg_ledger.md`.
Binding lessons come from the cycle-6 hostile audit (`reports/cycle6_core_premia/audit/HOSTILE_AUDIT.md`).

## 1. Specs (frozen, byte-identical)

Only these six ledgered cycle-6 specs are run. Their SHA-256 is verified before every run, and the engine SHA-256
must equal `e9cec9f0…9422`:

| Spec | SHA-256 (cycle-6 ledger) | Class | Style / control | Crash declared |
|---|---|---|---|---|
| TSMOM-FI | 188d8cc9… | FI | tsmom / always-long, m̄-matched | no (bw 0.20) |
| TSMOM-CM | 6bd6f56b… | CM | tsmom / always-long, m̄-matched | no (bw 0.20) |
| XSMOM-FX | 2f520f6a… | FX | xsmom / random-rank ×100 | **yes** |
| VAL-FX | 285afa0d… | FX | value (PPP) / random-rank ×100 | no (bw 0.20) |
| CARRY-FX | 4b154993… | FX | carry / random-rank ×100 | **yes** |
| SEAS-FX | 3863dc7f… | FX | seasonality BSV / calendar-shuffle ×100 | no (bw 0.20) |

**Only the data change.** Everything in each spec's params JSON is reused unchanged: signal, weights, universe
`min_assets`, vol, costs, control, inference, seeds. The only exceptions are the data-location keys (`inputs.*`
paths, `snapshot_manifest_sha256`) and the instrument set, which a written sample filter selects mechanically. The
cycle-7 runner builds the data dict and calls the frozen engine's `compute_component` with the spec's own params.

**Exact construction or INFEASIBLE.**
- A sample is infeasible if it cannot supply the spec's inputs at the spec's frequency and construction:
  - daily excess returns for the MOP EW daily vol with 756 observations, for trend and the BSV sizing;
  - point-in-time CPI for PPP;
  - a short rate for FX excess returns and carry.
- Monthly-only yields or prices are therefore infeasible for TSMOM (its vol is daily). This covers OECD monthly long
  rates, BoE Millennium, Shiller and JST (annual).
- FX before 1973 is infeasible (Bretton Woods fixed rates).

## 2. Samples (mechanical filters, fixed now)

| Sample ID | Specs | Instruments | Months |
|---|---|---|---|
| FX-EM | XSMOM-FX, VAL-FX, CARRY-FX, SEAS-FX | Every currency vs USD **not** in the cycle-6 FX universe (AUD CAD CHF EUR GBP JPY NOK NZD SEK) with daily spot and a point-in-time short rate (CPI too, for VAL-FX), after the peg/control exclusion (§3) | All months the spec defines (≥ 4 eligible) |
| FX-DEEP | same four | Cycle-6 G10 set (plus DEM/FRF/ITL/NLG legacy daily spot if a free daily source exists) | Months before each spec's cycle-6 first defined month (XSMOM 1975-08, VAL 1980-03, CARRY 1974-09, SEAS 1976-08) and ≥ 1973-03 |
| FI-NEW | TSMOM-FI | Every 10-year government bond **not** in the cycle-6 FI 10y universe (CA CH DE ES FR IT JP NO NZ SE UK US), with daily yields and a daily/lagged short rate, built with the cycle-6 bond construction | All defined months (≥ 3 eligible) |
| FI-DEEP | TSMOM-FI | Cycle-6 FI 10y markets plus any daily-yield extension of the same markets | Months before 1993-04 (cycle-6 TSMOM-FI first month) |
| CM-NEW | TSMOM-CM | Every commodity not in the cycle-6 CM set (WTI, natgas, Brent, gasoline, gold, silver, platinum, palladium, copper, corn, wheat, soybeans) with a correctly rolled daily excess-return series (single-commodity ETF/ETN total return − cash, or an EIA contract splice with the roll fix) | All defined months (≥ 3 eligible) |
| CM-DEEP | TSMOM-CM | Cycle-6 CM markets plus new CM series | Months before 2007-12 (cycle-6 TSMOM-CM first month) |

Rules that apply to every sample:
- Instrument QA follows cycle-6 FRAMEWORK §3 with the ADDENDUM-1 truncation rule. PASS rows only.
- Instruments that stopped trading are kept.
- A sample with fewer than **24** defined months is **INFEASIBLE** and is not run. (The cycle-6 120-month floor was a
  fidelity floor. There is no fidelity gate in cycle 7.)
- Instruments in a NEW sample may overlap in time with cycle-6 months. They are new because this spec never used
  them.

## 3. FX peg / capital-control exclusion (fixed before returns)

A currency-month is excluded from FX-EM and FX-DEEP if any of the following hold:
- **(a) Peg:** the IMF AREAER / Ilzetzki–Reinhart–Rogoff (IRR) coarse classification is 1 (hard peg or currency
  board), i.e. peg, band ±2% or narrower, or no separate legal tender. Examples: HKD throughout; CNY before 2005-07;
  MYR 1998-09 to 2005-07; ARS before 2002-01; DKK (ERM II band ±2.25%, treated as a peg).
- **(b) Non-deliverable:** the currency is onshore non-deliverable to foreigners, so the offshore market is
  NDF-only. Examples: KRW, TWD, INR, IDR, PHP, BRL, CLP, COP, PEN, CNY. It is **included only if** the spot series is
  the onshore rate and a free point-in-time short rate exists. Status is recorded per currency. Being NDF-only does
  not by itself exclude a currency, because the spec's construction (spot + rate differential) is unchanged. The
  realised deviation (NDF-implied vs onshore rate) is disclosed.
- **(c) Capital controls:** binding controls are recorded, e.g. MYR 1998-09 to 2005-07, ARS, RUB 2022+, TRY episodes.
  Currency-months under IRR "dual market / parallel premium > 10%" are excluded.
- **(d) Redenomination and devaluation:** redenomination months (TRY 2005-01, RUB 1998-01, BRL 1994-07) are
  excluded. A devaluation is kept (it is a return), unless the currency was pegged the month before, which case (a)
  already covers.

The data agent records the classification source per currency-month in `fx_regimes.csv`. Where IRR stops before the
sample end, the last classification is extended only if AREAER confirms it.

## 4. Per-run outputs (identical engine metrics, full new-sample window)

The headline is the **new-sample active series** (net book − spec control, one-session lag, base costs) over the
whole sample window. Reported:
- Sharpe;
- A4 calibrated one-sided p (spec's B = 9,999, crash layer and bandwidth);
- calibrated CI: 90%, or 95% if crash-declared with n < 120;
- the same at 2× costs (ret_before_cost − 2·cost; the control is recomputed at 2× by the engine's stress path, using
  multiplier 2 where supported, else reported from the net-stress path at 3×, labelled);
- best-year share of positive P&L;
- **seed sensitivity:** p and CI recomputed for seeds s0 + {0, 1, 2, 3, 4}, where s0 is the spec's inference seed.

## 5. Pooling and POSITIVE rule (owner's, made exact)

Per spec, over its feasible new samples i:
- **Pooled estimate** Ŝ = Σ w_i Ŝ_i / Σ w_i with w_i = 1/SE_i². Ŝ_i is the monthly active Sharpe. SE_i is the A4
  influence-function HAC SE (`research.amendment4.ci._est`, fixed-b L = max(NW, ⌈0.10 n⌉)).
- **Pooled calibrated p:** z_i = Φ⁻¹(1 − p_i), where p_i is the calibrated p. Then Z = Σ c_i z_i / √(cᵀ R c), with
  c_i = 1/SE_i. R is the correlation of the samples' active series on common months (0 if fewer than 24 common
  months). p_pool = 1 − Φ(Z). With one sample, p_pool = p_1.
- **k** = number of specs with at least one feasible new sample. It is fixed in the ledger before the first cycle-7
  return and never changes.

**NEW-SAMPLE POSITIVE** iff all of the following hold:
- (i) p_pool < 0.05/k for **every one** of the 5 seeds;
- (ii) the pooled active mean at 2× costs is > 0;
- (iii) no calendar year has more than 40% of the positive P&L in the pooled active series (the monthly w-weighted
  average of the samples' active returns);
- (iv) for crash-declared specs, every sample with n < 120 also reports the 95% interval, and the pooled estimate is
  flagged if any such interval includes zero. This is disclosure, not an extra gate.

No combined book is built.

## 6. Ledger and runs

- `research/cycle7_prereg_ledger.md` gets these entries, each before the returns it governs:
  - this file;
  - the runner code hash;
  - each snapshot manifest;
  - one entry per spec × sample (spec hash, sample filter text hash, instrument list hash, snapshot hash);
  - k.
- One run per spec × sample. Every run goes in `research/cycle7/trial_ledger.csv`.
- Genuine bugs are fixed only against the frozen rule or external records, logged before any rerun.
- **No sandbox, network or permission change.** LSE data comes through the LSE MCP tools only.
