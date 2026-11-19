# Cycle 7: frozen specs on new samples

2026-09-27. The six cycle-6 fidelity-passing specs were run unchanged: same spec bytes, engine `e9cec9f0…`, and
runner `b1db5652…`, which drift-checks every parameter. Every spec × sample was ledgered before its first return and
run once. k = 6, so the POSITIVE threshold is p < 0.05/6 = **0.00833**.

## POSITIVE flags

| Spec | NEW-SAMPLE POSITIVE | Pooled active Sharpe | p_pool, 5 seeds | 2× costs, active mean | Best-year share |
|---|---|---|---|---|---|
| **CARRY-FX** | **YES** (single sample, FX-EM) | **1.12** | 0.0065 / 0.0071 / 0.0056 / 0.0069 / 0.0064 | +10.8%/yr (book net Sharpe at 2× costs 1.00) | 12% |
| VAL-FX | no (p) | 0.37 | 0.036 – 0.042 | +4.7%/yr | 23% |
| XSMOM-FX | no | 0.35 | 0.150 – 0.157 | +3.9%/yr | 23% |
| TSMOM-FI | no | 0.23 | 0.145 – 0.151 | positive | 22–33% |
| TSMOM-CM | no | 0.19 | 0.122 – 0.127 | positive | 18–28% |
| SEAS-FX | no | 0.18 | 0.204 – 0.215 | +1.7%/yr | 12% |

**Read before relying on CARRY-FX** (descriptive diagnostics in `diagnostics/`; not trials, and they change no flag):
1. **Concentration.** TRY supplies 30% of gross P&L and RUB 22%. Excluding the contributions of the top three (TRY,
   RUB, BRL) leaves a Sharpe of 0.65.
2. **Decay.** Active Sharpe was 1.56 in 1988-02 to 2008-08 (p 0.002), 0.15 in 2008-09 to 2013-08, and **0.67 after
   KMVP publication** in 2013-09 onward (p 0.036, 157 months, crash layer).
3. **NDF currencies.** 29% of P&L comes from NDF-only currencies (BRL, COP, IDR, KRW, PHP, INR, …). For these, the
   construction pays the onshore rate differential, which an offshore investor may not earn. No free NDF data existed
   to measure the gap. Excluding their contributions gives a Sharpe of 0.86.
4. **Exclusion rule.** The FRAMEWORK §3 rule masks several classic carry crash months (RUB 1998-08, IDR 1998-01,
   THB 1997-07, ARS 2002). Only 9 held positions ran into a masked month. At spot moves, their missed P&L is −0.08 of
   the 3.49 total, 2.4%, mostly IDR 1998-01. The masked crisis periods otherwise sit outside the sample by design.
5. **2× costs raise active returns.** Active returns rise at 2× costs because the random-rank control trades more
   than the carry book. The carry book's own net Sharpe at 2× costs is 1.00 (1.01 at base).
6. **Published premium.** EM currency carry is a well-documented premium (e.g. Lustig–Verdelhan; Burnside et al.).
   The universe is new to this spec, but not to the literature.

## Original sample vs each new sample (active = net − spec control)

| Spec | Sample | Months | Instruments | Active Sharpe | 90% CI (seed range of bounds) | 95% CI | Calibrated p (5 seeds) | Net book Sharpe | Book at 2× costs | Best-year share |
|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM-FI | original (cycle 6) | 402 (1993-04→) | 12 | 0.33 | net [0.21, 0.68] | — | 0.022 | 0.47 | — | — |
| TSMOM-FI | **FI-NEW** | 211 (2009-03→) | 14 | 0.18 | [−0.19…−0.15, 0.51…0.57] | [−0.27, …] | 0.212–0.220 | 0.25 | 0.23 | 22% |
| TSMOM-FI | **FI-DEEP** | 44 (1989-08→1993-03) | 5 | 0.64 | [−0.72…−0.50, 1.58…1.73] | [−0.96, …] | 0.172–0.179 | 0.82 | 0.80 | 33% |
| TSMOM-CM | original | 226 (2007-12→) | 12 | 0.45 | net [0.08, 0.78] | — | 0.007 | 0.45 | — | — |
| TSMOM-CM | **CM-NEW** | 177 (2012-01→) | 12 | −0.17 | [−0.70…−0.63, 0.28…0.36] | [−0.75, …] | 0.673–0.686 | −0.18 | −0.21 | 18% |
| TSMOM-CM | **CM-DEEP** | 120 (1997-12→2007-11) | 5 | 0.54 | [0.03…0.09, 1.00…1.03] | [−0.05, 1.06] | 0.017–0.019 | 0.67 | 0.66 | 28% |
| XSMOM-FX* | original | 614 (1975-08→) | 9 | 0.28 | net [−0.04, 0.34] | — | 0.021 | 0.16 | — | — |
| XSMOM-FX* | **FX-EM** | 453 (1989-01→) | 22 | 0.35 | [−0.21…−0.13, 0.83…0.89] | [−0.26, …] | 0.150–0.157 | 0.25 | 0.22 | 23% |
| VAL-FX | original | 559 (1980-03→) | 9 | 0.56 | net [0.17, 0.68] | — | 0.011 | 0.43 | — | — |
| VAL-FX | **FX-EM** | 398 (1993-08→) | 18 | 0.37 | [0.03…0.07, 0.62…0.64] | [−0.02, …] | 0.036–0.042 | 0.28 | 0.27 | 23% |
| CARRY-FX* | original | 625 (1974-09→) | 9 | 0.55 | net [0.18, 0.67] | — | 0.001 | 0.43 | — | — |
| CARRY-FX* | **FX-EM** | 464 (1988-02→) | 22 | **1.12** | [0.54…0.59, 1.60…1.65] | [0.47, …] | **0.0056–0.0071** | 1.01 | 1.00 | 12% |
| SEAS-FX | original | 602 (1976-08→) | 9 | −0.14 | net [−0.51, −0.10] | — | 0.900 | −0.30 | — | — |
| SEAS-FX | **FX-EM** | 441 (1990-01→) | 22 | 0.18 | [−0.20…−0.17, 0.50…0.55] | [−0.28, …] | 0.204–0.215 | −0.02 | −0.19 | 12% |

\* Crash-declared. Every crash-declared sample has at least 120 months, so the 90% interval is primary; 95% is also
reported.

Other table notes:
- **Original row:** its p is the cycle-6 full-sample active p. Only a net-Sharpe CI exists for that sample.
- **Pooled estimates:** TSMOM-FI 0.23 and TSMOM-CM 0.19. Inverse-variance weights; Stouffer p with R = 0, since the
  samples share no months.
- **Full detail:** `pooled.json`, `tables/runs.csv`, `runs/<spec>__<sample>/metrics.json`.

## Data acquisition

| Sample | Source (all free) | Instruments (PASS / total) | History | Point-in-time status | Feasible |
|---|---|---|---|---|---|
| FX-EM | BIS daily central-bank spot (onshore, for NDF currencies); Fed H.10; short rates from OECD (lagged 1 month), LSE MCP daily and BIS policy (fallback); CPI OECD/LSE | 22 / 27 (FAIL: CNY, HKD pegs; TWD no regime source; LKR, VEB no rate) | 1988–2026 | Rates lagged. CPI is the latest vintage with a 2-month lag (no free foreign first releases). Regimes from IRR + AREAER 2023 | yes, all 4 FX specs (399–465 months) |
| FX-DEEP | H.10 historical DEM/FRF/ITL/NLG/ESP + cycle-6 G10 | — | 1973-03 → cycle-6 start | — | **INFEASIBLE**: ≤ 17 defined months < 24 floor |
| FI-NEW | LSE MCP vendor 10y (GR, ID, CN, IN, RU, BR, SG, MY, CL, KR, TR, NG, TH, MX); ÁKK (HU) | 15 / 17 (FAIL: AU TE 0.65, ZA TE 0.63) | 2002–2026 | No vintages (vendor). RU masked from 2022-03 | yes, 211 months |
| FI-DEEP | Fed H.15, BoE zero curves → par, MoF Japan, Bundesbank 8–15y, StatCan, Riksbank | 6 / 7 (CH weekly before 1998) | 1965–1993 | Official daily | yes, 44 months |
| CM-NEW | WisdomTree London ETCs (sugar, cocoa, cotton, cattle, nickel, zinc, coffee, aluminium, hogs, tin, lead, soybean oil), iPath GRN (EUA), KCCA (CCA), EIA heating oil and propane spliced | 16 / 16 | 2008–2026 | Traded lines | yes, 177 months |
| CM-DEEP | EIA WTI, natgas, heating oil, propane, gasoline; GLD, SLV | 7 / 7 | 1994–2007 | EIA settlements | yes, 120 months |

**Infeasible for these specs**, and why:
- **Monthly-only series** (TSMOM needs daily vol): OECD MEI long rates, BoE Millennium, Shiller, JST (annual), SNB
  monthly, World Bank Pink Sheet, IMF commodity prices.
- **FX before 1973:** Bretton Woods fixed rates.
- **Pre-1994 EIA heating oil and gasoline:** no Contract 2 to form a roll.
- **Dead US commodity ETNs** (SGG, JO, NIB, BAL, JJU, JJN, UHN, …): no free daily history.
- **No free daily 10y yield:** NL, BE, AT, DK, FI, IE, PT, PL, CZ, IL, PH, CO, HK, TW.

**Blocked hosts, needs owner (no bypass attempted):**
- `data-api.ecb.europa.eu`, `api.imf.org`, `www.imf.org` (403), rba.gov.au, boi.org.il, suomenpankki.fi,
  fred.stlouisfed.org, rbnz.govt.nz, nbp.pl, bsp.gov.ph, dnb.nl, bankofgreece.gr, home.treasury.gov,
  stat.nbb.be, api.hkma.gov.hk, stooq.com.
- The Banque de France API needs key registration.

## Ledger (`research/cycle7_prereg_ledger.md`)

| Entry | SHA-256 |
|---|---|
| FRAMEWORK | abc598e48bf7a19332e343f45491581122d1c14d22501d9b6c29d984e09325c4 |
| ADDENDUM-1 (FX mask) / ADDENDUM-2 (data decisions) | 9921e7f3… / a20977e1… |
| RUNNER | b1db5652903b8a4be0708d53d162f5fb5d9d0c6d2889cb5f14946f0e633a690e |
| Snapshots fx_em / cm_new / cm_deep / fi_new / fi_deep | 93ef8e0f… / de67e9f2… / 3db28c32… / 67aba110… / a7387d19… |
| k = 6 | ledgered 2026-09-27T14:32:56Z, before the first run (14:33:02Z) |
| Samples | CARRY-FX__FX-EM cac87c1e…, SEAS-FX__FX-EM 4d0853d2…, TSMOM-CM__CM-DEEP def5cf6b…, TSMOM-CM__CM-NEW cef5b1ee…, TSMOM-FI__FI-DEEP c9bc2603…, TSMOM-FI__FI-NEW a10cca65…, VAL-FX__FX-EM bee6a2a4…, XSMOM-FX__FX-EM ca4261ed… |

## Trial count (cycle 7)

- 8 runs (8 ok, 0 failed, 0 reruns, 0 bug fixes) under `research/cycle7/trial_ledger.csv`.
- 1 descriptive recompute of CARRY-FX__FX-EM for attribution. It is not a trial: it asserts equality with the
  ledgered run and changes no flag.

## Housekeeping

`reports/cycle6_core_premia/INCIDENT_sandbox_bypass.md` is written. No sandbox, network or permission change was made
in cycle 7. LSE was reached through the MCP tools only. Nothing was committed.
