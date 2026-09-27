# Core Premia Book: data feasibility (trend + carry), free data only

2026-09-26, director synthesis. **No signal-conditioned, strategy, control or portfolio return has been computed.**
Only instrument-level QA returns were used (construction error against real proxies).

**Sources**
- `rates_fx_eq/REPORT.md`: acquisition snapshot `core_premia_rates_fx_eq_acq_v1`, manifest
  `8b5e6205cf5fe8084914913e7d278103c302887d0bf3a44aa6c063452ff67e28`, 297 files, verify passes.
- `commod_bench/REPORT.md`, plus `commod_bench/DIRECTOR_EIA_ROLL_CORRECTION.md`.
- `tradability/REPORT.md`.
- The completeness records are the `completeness.json` file in each subfolder.

**Disclosure.** While locating the header row of the AQR TSMOM workbook, the rates/FX/equity agent saw a few rows of
its return values. Nothing uses them.

## 1. Ranked components

Definitions used in the table:
- **Error** = synthetic-construction tracking error ÷ the proxy's volatility, on monthly returns (lower is better),
  against a real ETF or futures overlap.
- **AQR months** = months overlapping the AQR TSMOM benchmark (1985-01 → 2026-05) after the 756-day volatility
  warm-up.
- **Eff. N** = effective independent markets within the class, K/(1+(K−1)ρ̄), with ρ̄ an ASSUMPTION stated per class.
  The book's effective sample is **months, not markets × months** (Amendment 4 §5).

| Rank | Component | Breadth (pass / review) | History | Point-in-time status | Error, median (range) | AQR months | Eff. N (ρ̄) | Tradability, Canadian retail | Main defects |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **FX trend and carry**: H.10 spot plus short-rate differential | 8 G10 pass (AUD, CAD, CHF, EUR, GBP, JPY, NOK, SEK); NZD under review; MXN outside G10 | Daily from 1971 (EUR from 1999) | Spot final; short rates partly monthly-average OECD (lagged 1 month) | **0.11** (0.10–0.15; NZD 0.22) | ≥ 293 | about 3.5 (0.4) | Micro FX futures (M6E, M6A, M6B, MCD, M6J); CurrencyShares ETFs (FXS closed 2020) | No daily euro-legacy FX before 1999. The rate differential is off by 0.16–0.47 pp/yr against forward points (JPY +0.45 pp). LSE FX files have spurious prints (USDCAD +31%) and are not used |
| 2 | **Equity index trend**: country ETF, or price index plus estimated dividends, minus cash | 19 provisional pass (US ×4, CA, UK, DE, FR, IT, CH, JP, HK, AU, SG, KR, TW, MX, IN, CN) | Country ETFs from 1996; US indices from 1928 | ETF adjusted closes (vendor-adjusted); dividends estimated outside the US and DAX | **0.22** (US 0.06; DE 0.15; JP/HK 0.43–0.46; CN 0.84) | median 327, min 136 | about 1.6 (0.6) | US and CA liquid; many country ETFs thin; micro equity futures only for US indices (plus Mini-DAX, Euro Stoxx micro) | Unhedged USD ETFs carry different FX exposure than AQR's futures. CN (FXI = H-shares) is a poor fit. 13 markets fail the $5M ADV floor |
| 3 | **Government bond trend and carry**: yields → duration/convexity + carry − financing | 2 clean (UK, CA) + 3 minor-defect review (US, DE, JP); FR and IT fail | US 1962, UK 1982/93, JP 1986, DE 1997, CA 2001 | Official central-bank curves; no vintages | **US 0.13** vs IEF (0.16 vs ZN); UK 0.31; DE 0.37; JP 0.45; CA 0.54 | 269–497 | about 2.4 (0.5) | US ETFs (SHY, IEF, TLT) and CA (XSB, XGB, XLB) only. No retail ETF for UK/DE/JP govvies. **No micro price-based Treasury future** (micro yield futures are yield-settled) | Flat runs and holiday gaps. Error grows outside the US. FR/IT/ES need more tenors (not pulled) |
| 4 | **Commodity trend**: commodity ETFs, 2006+ | 24 of 28 retrieved: GLD, SLV, USO, UNG, DBC, GSG, DBO, DBE, DBB, DBA, UGA, BNO, CPER, CORN, WEAT, SOYB, PALL, PPLT … | 2006–07+ (GLD 2004) | Adjusted closes; structural breaks (USO 2020, UNG reverse splits) | Fund returns *are* the instrument (no synthetic); roll and decay costs embedded | about 200 (2009+) | about 3 (0.3) | GLD/IAU/SLV/DBC liquid; USO/UNG poor long holds (contango); micro metal/crude futures exist | 4 delisted ETNs unavailable free (iPath JJ* etc.); short history; sector ETFs are baskets |
| 5 | **Energy trend via EIA contracts** (crude, natgas), 1985/1994 → 2024-04 | 2 | Discontinued 2024-04-05 | 14:30 ET NYMEX settlements; publication lag unknown | vs USO: raw C1 TE 17.2% (+15.8 pp/yr drift, **invalid**); spliced held-contract TE 14.1% (+4.2 pp/yr) | about 380 (crude) | — | Not tradable itself; historical extension only | **Must splice rolls: C1(t)/C2(t−1) on the day after expiry.** The agent's "clean as-is" was wrong and has been corrected. It ends in 2024, so it cannot run forward. Heating oil, gasoline and propane are not clean |
| 6 | **Bond carry** (slope + roll-down) | Daily ≥ 2 tenors: US, DE, JP, UK, CA, SE, euro-area AAA; NO only from 2019 | As for bonds | As for bonds | Input-level only | as above | — | as bonds | CH monthly and stale; FR/IT/ES/NZ have one local tenor; JP/AU lack a daily 3M rate (OECD monthly used) |
| 7 | **FX carry** (rate differential) | 8–9 G10 | As for FX | As for FX | ± 0.16–0.47 pp/yr vs forward points | ≥ 293 | — | as FX | As for FX |
| — | **Commodity carry** | Energy-only (crude/natgas C1–C4 slope) to 2024-04 | — | — | — | — | — | — | **Infeasible as a broad factor.** An energy-curve proxy only, and it ends in 2024 |
| — | **Equity carry** | none | — | — | — | — | — | — | **Infeasible with free data**: needs dividend futures or implied dividends |

**Benchmarks, snapshotted** (URL, UTC time, sha256 and terms in `commod_bench/benchmarks_manifest.json`):
- AQR TSMOM (1985-01 → 2026-05; TSMOM plus the CM, EQ, FI and FX columns);
- AQR Century of Factor Premia (1926-07 → 2026-02);
- AQR Value and Momentum Everywhere (1972-01 → 2026-07);
- Ken French: US 3-factor (1926+, including RF), US 5-factor, and Developed / Developed-ex-US / Global-ex-US 3-factor
  (1990+).

## 2. Recommended universe (data-feasible; NOT a frozen component spec)

About 36 markets, below the 40–60 target:
- **FX:** 8 G10 crosses vs USD (AUD, CAD, CHF, EUR, GBP, JPY, NOK, SEK), with NZD if the review clears.
- **Equity:** US S&P 500 plus about 11 developed and liquid markets (CA, UK, DE, FR, IT, CH, JP, AU, HK, KR, TW),
  each ETF-proxied. Drop CN and IN from the trend panel unless an index-level source is accepted.
- **Bonds:** US (7–10y and 20–30y), UK, DE, JP, CA 10y. That is 5 markets, 3 of them under review.
- **Commodities, 2006+:** gold, silver, WTI, Brent, natgas, copper/base metals, agriculture basket, corn, wheat,
  soybeans, platinum, palladium (ETFs). The EIA crude/natgas splice extends history to 1985/1994, is used for history
  only, and needs its own completeness record.

**Effective sample.** About 400–500 months (1985/1993+) for FX, equity and bonds; about 200 months for commodities.
Asset count does not multiply effective months.

## 3. Tradability (Canadian retail; not advice)

- **Futures/risk-parity book:**
  - **CAD 25k:** 100% of buckets cannot be held at target risk. Not implementable.
  - **CAD 100k:** 75% cannot be held.
  - **CAD 250k:** 42% cannot be held.
  - Bonds are structurally unholdable at target risk: there is no micro price-based Treasury future, only a
    full-size ZN (about USD 100k+ face).
- **Registered accounts (TFSA/RRSP):** cannot hold futures or short.
  - A long/flat ETF-only variant is registrable, but it must be a **separate registration**.
  - RRSP, not TFSA, gets the US-dividend treaty exemption.
- **CAD/USD conversion:** IBKR about 0.03%, Norbert's gambit about 0.15%, banks 2.5–3%.
- **Taxes:** a systematic, frequently rebalanced futures book risks being treated as business income.

## 4. What free data cannot support (blunt)

1. Contract-level futures or forwards for rates, FX, equity indices or non-energy commodities. Everything is
   synthetic or ETF-based, so AQR's futures universe cannot be matched exactly.
2. Commodity carry beyond energy, and energy carry after 2024-04.
3. Equity carry of any kind.
4. Daily euro-legacy FX before 1999. This truncates the 1985–1998 FX panel to monthly or missing.
5. Daily bond yields before 1997 (DE), 2001 (CA) or 2010 (IT); only monthly OECD averages exist for those. Vintages
   and revision histories: none (ALFRED unreachable).
6. Local-currency total-return indices outside the US and DAX. Dividends are estimated; country ETFs are unhedged
   USD.
7. Liquid single-country bond ETFs outside the US and CA, and retail-sized bond futures anywhere.
8. Pre-2006 commodity breadth (ETFs), except crude/natgas via spliced EIA to 2024.
9. The 40–60-market target with clean data: about 36 is realistic, and only about 5 bond markets.
10. Blocked or login-gated sources: FRED, ALFRED and RBA time out; RBNZ returns 403; Stooq has a bot check; MSCI
    needs a login.

## 5. Status and next steps

- Acquisition snapshots exist, and completeness records are written.
- **Still needed before any return:**
  - the evaluation snapshot, with frozen universe membership, through `research.data_snapshot`;
  - the EIA splice as a registered construction;
  - an LSE pull of the 19 index series and additional bond tenors (MCP calls failed this session because the
    terminal app was not running; 54 calls were wasted and have since been guarded against);
  - owner registration of Amendments 4 and 5;
  - a frozen component spec.
- Strategy returns stay forbidden until then.
