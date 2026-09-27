# Cycle 6 paper-rule dossier (PAPER agent, 2026-09-26)

Scope: transcription of source rules, published per-class statistics, circulation dates and AQR benchmark metadata for
the cycle-6 menu (`research/cycle6/FRAMEWORK.md` §1). **No returns of any kind were computed.** MOP trend and KMVP carry
rules are already transcribed with page cites in `research/PROTOCOL_AMENDMENT_5_REPLICATION_2026-09-25.md` (A5) and
`research/CORE_PREMIA_COMPONENT_1_TREND_PREREG_AMENDMENT_5_2026-09-25.md`; they are reused, not re-transcribed, except
for the KMVP Table 2 check in §5. Machine-readable stats: `research/cycle6/paper_stats.json`.

Conventions: "p." = journal page unless marked "MS p." (manuscript page). "paper-silent" = the text read does not state
the rule; the suggested default is a **researcher degree of freedom** for the director to freeze (alternative not tested).
Quotes are short and verbatim from the version listed; ligatures restored (the extracted text dropped "fi"/"ff").

## 0. Source versions actually read

| Paper | Version read | URL | Journal version accessible? |
|---|---|---|---|
| AMP 2013 | **Journal**, JF 68(3) pp. 929–985 (author copy) | https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf | yes (this is it) |
| FP 2014 | Accepted manuscript "This draft: May 10, 2013" (MS pages; table numbers match JFE) | https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf | **no**: https://docs.lhpedersen.com/BettingAgainstBeta.pdf has an expired TLS certificate (not bypassed); Elsevier paywalled |
| KLN 2016 | NBER WP 20815 "Common Factors in Return Seasonalities", Dec 2014 (same text as AQR-hosted 19 Dec 2014 copy) | https://www.nber.org/system/files/working_papers/w20815/w20815.pdf | **no**: Wiley paywall; SSRN 403; Aalto portal has no file |
| BSV 2021 | SSRN version "First version: April 2017 / This Version: January 2019" | https://www.institutional-investment.de/uploads/media/Robeco_Study_Global-Factor-Premiums.pdf (mirror of SSRN 3325720) | **no**: EUR repository PDF behind a Cloudflare challenge (not bypassed); ScienceDirect JS/paywall |
| KMVP 2018 | **Journal**, JFE 127 pp. 197–225 | URL cited in A5 | yes |

Consequence: FP, KLN and BSV journal-version numbers may differ from those below. Any fidelity target taken from the
KLN WP or BSV SSRN version must be labelled as such in the spec (see §3 flag on KLN t-stats).

---

## 1. Asness, Moskowitz & Pedersen (2013), "Value and Momentum Everywhere" — XSMOM-*, VAL-*

| Rule | Verbatim quote | Cite | Paper-silent → suggested default |
|---|---|---|---|
| Momentum signal (all non-stock classes) | "the return over the past 12 months skipping the most recent month" ; stocks: "past 12-month cumulative raw return … skipping the most recent month's return, MOM2–12" | §I.B, p. 937 (stocks p. 936) | Return type (raw vs excess) for non-stock classes not separately stated; futures/forward returns are already excess → use the class's excess-return series. Missing month inside window: paper-silent → ineligible. |
| Skip month rationale | "we do so to maintain uniformity across asset classes" | p. 937 | — |
| VAL-EQ (country indices) | "we use the previous month's BE/ME ratio for the MSCI index of the country" | p. 937 | Free-data BE/ME for MSCI indices likely unavailable → any substitute (CAPE, D/P) is a declared deviation (AQR Century uses CAPE; BSV uses D/P). |
| VAL-CM | "the log of the spot price 5 years ago (actually, the average spot price from 4.5 to 5.5 years ago), divided by the most recent spot price" | p. 937 | "Spot price" source paper-silent → nearest-futures price as spot proxy; averaging frequency (daily vs month-end) paper-silent → month-end prices of months t−66…t−54. |
| VAL-FX | "the log of the average spot exchange rate from 4.5 to 5.5 years ago divided by the spot exchange rate today minus the log difference in the change in CPI in the foreign country relative to the U.S. over the same period" ; "the 5-year change in purchasing power parity" | p. 937 | Quote orientation paper-silent → USD per unit foreign currency (so "negative of the 5-year return on the exchange rate" = cheap when foreign currency fell). CPI publication lag paper-silent → use CPI known at t (≥1-month lag). |
| VAL-FI (primary) | "we use the 5-year change in the yields of 10-year bonds as our value measure" | p. 937 | Point-to-point vs 4.5–5.5y average paper-silent; Table I Panel C labels it "yield to yield 5 years ago" (p. 944) → point-to-point y_t − y_{t−60}. |
| VAL-FI alternatives (reported, not primary) | "real bond yield, which is the yield on 10-year bonds minus the 5-year forecast in inflation" ; "term spread … yield on 10-year bonds minus the short rate" | p. 947; Table I Panel C p. 944 | Only a declared variant; primary = 5-yr yield change. |
| Rank-weighted factor (used for AQR VME) | "w_it^S = c_t(rank(S_it) − Σ_i rank(S_it)/N)" ; "scaled to one dollar long and one dollar short" | Eq. (1), p. 938 | Tie handling paper-silent → average ranks. Min N paper-silent → framework's ≥4. |
| Factor return | "r_t^S = Σ_i w_it^S r_it" | Eq. (2), p. 939 | Timing: signal at end of t−1, return in t (standard; not stated explicitly). |
| Tercile portfolios (also reported) | "sorting them into three equal groups … for the nonstock asset classes we equal weight securities" | §I.C, p. 938 | Not the AQR construction; report only. |
| Vol scaling | none in class factors; fn 10: "Weighting the nonstock asset classes by their ex ante volatility gives similar results" | p. 938 | Gross shadow unscaled ($1/$1). |
| Rebalancing | "the strategies we study here are all naively rebalanced exactly monthly" | §V, p. 976 | — |
| Returns: EQ | "do not include any returns on collateral … comparable to returns in excess of the risk-free rate" | §I.A.2, p. 935 | — |
| Returns: FX | "computed from currency forward contracts or MSCI spot price data and Libor rates … implicitly include the local interest rate differential" | §I.A.3, p. 935 | — |
| Returns: FI | "Bond index returns come from Bloomberg and Morgan Markets" | §I.A.4, p. 935 | Currency/hedging of bond excess returns paper-silent → local-currency excess return (futures-equivalent). |
| Returns: CM | "daily excess return of the most liquid futures contract … compound the daily returns to a total return index" | §I.A.5, pp. 935–936 | — |
| Universe EQ | 18 developed markets, "January 1978 to July 2011, with the minimum number of equity indices being 8 and all 18 … after 1980" | pp. 934–935 | — |
| Universe FX | 10 currencies (incl. USD), "January 1979 to July 2011 … minimum number of currencies is 7" | p. 935 | — |
| Universe FI | 10 countries, "January 1982 to July 2011, where the minimum number of country bond returns is 5" | p. 935 | Panel C alternative-value sample starts 01/1983. |
| Universe CM | 27 futures, "January 1972 to July 2011, with the minimum number of commodities being 10" | p. 935 | — |
| Global aggregation | "equal volatility weights across the markets and asset classes" (Table I caption) | Table I, p. 940 | Not needed per class. |

**Table I Panel B (pp. 942–943), rank-weighted "Factor" column, annualized excess of 1-month T-bill**

| Class | Sample | VAL mean / sd / SR | MOM mean / sd / SR |
|---|---|---|---|
| Country indices | 01/1978–07/2011 | 5.7% / 9.5% / 0.60 | 7.4% / 11.8% / 0.63 |
| Currencies | 01/1979–07/2011 | 3.9% / 9.0% / 0.44 | 3.0% / 9.6% / 0.32 |
| Fixed income | 01/1982–07/2011 | 0.5% / 6.4% / 0.07 | 1.0% / 5.8% / 0.17 |
| Commodities | 01/1972–07/2011 | 7.3% / 23.7% / 0.31 | 11.5% / 22.8% / 0.51 |

P3–P1 tercile spreads and Panel C FI alternatives are in `paper_stats.json` only where rank-weighted (Panel C real-yield
factor: 1.9% / 2.8% / 0.70, 01/1983–07/2011). Flag: Panel C FI vols (≈2.5–2.9%) are far below Panel B FI vol (6.4%) for
what the caption calls the same asset class; paper-silent why (possibly a different scaling). Do not mix the two panels.

---

## 2. Frazzini & Pedersen (2014), "Betting Against Beta" — BAB-EQ, BAB-FI

Version: accepted MS dated May 10, 2013 (MS page numbers). Equations are garbled in extraction; formulas below are the
MS equations re-typed from the extraction and should be spot-checked against the JFE PDF when accessible.

| Rule | Verbatim quote | Cite | Paper-silent → suggested default |
|---|---|---|---|
| Beta estimator | β̂_i^TS = ρ̂ σ̂_i / σ̂_m ; "estimated volatilities for the stock and the market and ρ̂ is their correlation" | Eq. (14), MS p. 17 | — |
| Windows | "a 1-year rolling standard deviation for volatilities and a 5-year horizon for the correlation" | MS p. 17 | Rolling-window weighting: equal-weight (implied by "rolling"). |
| Return horizon | "1-day log returns to estimate volatilities and overlapping 3-day log returns … for correlation" | MS p. 17 | — |
| Minimum data | "at least 6 months (120 trading days) of non-missing data to estimate volatilities and at least 3 years (750 trading days) … for correlations" | MS p. 17 | — |
| Monthly-data fallback | "If we only have access to monthly data, we use rolling 1 and 5-year windows and require at least 12 and 36 observations" ; fn 12: daily returns not available for "U.S. Treasury bonds" | MS pp. 16–17 | Applies to Treasury maturity buckets. |
| Shrinkage | "we set w = 0.6 and β^XS = 1 for all periods and across all assets"; β̂_i = w β̂_i^TS + (1−w) β̂^XS | Eq. (15), MS p. 17 | **Confirmed** w = 0.6 toward 1. |
| Market for beta: futures | "For equity indexes, country bonds, and currencies, the betas are computed with respect to a GDP-weighted portfolio" | MS p. 16 | GDP weights source/lag paper-silent → annual World Bank/IMF nominal USD GDP lagged 1 year; declare. |
| Market for beta: Treasuries | "Betas are computed with respect to an equally weighted portfolio of all bonds in the database" | MS p. 15 | Our buckets → equal-weighted average of the bucket excess returns. |
| Ranking & legs | "ranked in ascending order on the basis of their estimated beta … assigned to one of two portfolios: low-beta and high-beta" (split at asset-class median) | MS pp. 18–19 | Median with odd N paper-silent → middle asset gets zero weight automatically under Eq. 16. |
| Weights | w_H = k(z − z̄)^+, w_L = k(z − z̄)^−, k = 2/(1′|z − z̄|); "by construction we have 1′w_H = 1 and 1′w_L = 1" | Eq. (16), MS p. 19 | Ties → average rank. |
| Beta-neutral BAB | "both portfolios are rescaled to have a beta of one at portfolio formation" ; r_BAB = (1/β_L)(r_L − r_f) − (1/β_H)(r_H − r_f) | Eq. (17), MS p. 19 | Leg betas = Σ w·β̂ (shrunk betas). |
| Rebalance | "The portfolios are rebalanced every calendar month" | MS p. 19 | Signal: beta at end of previous month (Table III caption). |
| Futures data | "daily return on futures, forwards, or swap contracts in excess of the relevant financing rate" ; "January 1963 and March 2012" | MS p. 16 | — |
| Treasury data | CRSP Fama bond portfolios "for maturities ranging from 1 to 10 years between January 1952 and March 2012" | MS p. 15 | Table VI uses 7 buckets (1–12, 13–24, 25–36, 37–48, 49–60, 61–120, >120 months). Our FI buckets are a construction deviation. |
| Class combos (not per class) | "rescale each return series to 10% annualized volatility using rolling 3-year estimates up to month t-1" | MS p. 26; Table VIII caption | Per-class rows are **unscaled** (beta-1 legs). |
| Treasury interpretation | "ranking on betas … is empirically equivalent to ranking on duration or maturity" | MS p. 20 | — |

**Published stats (monthly % → annualized ×12 by us; vol and SR as published, annualized)**

| Table | Class | Sample | Mean (mo → ann) | Vol | SR | t |
|---|---|---|---|---|---|---|
| VIII A | Equity indices | 1965–2012 (table title; per-class start paper-silent) | 0.55 → 6.6% | 13.08% | 0.51 | 2.93 |
| VIII A | Country bonds | idem | 0.03 → 0.36% | 2.93% | 0.14 | 0.67 |
| VIII A | Foreign exchange | idem | 0.17 → 2.04% | 9.59% | 0.22 | 1.23 |
| VIII A | Commodities | idem | 0.18 → 2.16% | 19.67% | 0.11 | 0.72 |
| VI | US Treasury (maturity) BAB | 01/1952–03/2012 (">10y" bucket missing 1962-08 to 1971-12) | 0.17 → 2.04% | 2.43% | 0.81 | 6.26 |

Table VIII $Long/$Short (EI 1.29/0.86; CB 1.48/0.88) indicate unscaled beta-1 legs. BSV Table I attributes FP start
years EI 1984, CB 1989, FX 1977, CM 1989 (BSV reading, not stated in FP). FI (country 10y) BAB in FP is "Country Bonds",
not maturity buckets; the framework's BAB-FI maturity-bucket design maps to **Table VI** (US Treasuries only).

---

## 3. Keloharju, Linnainmaa & Nyberg (2016), "Return Seasonalities" — SEAS-EQ, SEAS-CM (KLN has no FI/FX)

Version: NBER WP 20815 (Dec 2014). Page numbers = WP page labels.

| Rule | Verbatim quote | Cite | Paper-silent → suggested default |
|---|---|---|---|
| Signal (stocks, applied "throughout") | "each stock's average same-calendar-month return from the prior 20-year period" ; "we demean stock returns in the cross section before taking the average" ; "at least five years of historical data" ; "We use the same demeaning procedure and sample selection rules throughout the study" | §3, WP pp. 9–10 | For commodities/countries the 20-year window is implied by "throughout"; declare. |
| CM/EQ portfolios | "We form the high and low portfolios for commodities and country indexes based on historical same- or other-month returns. Each month we include assets that have at least five years of historical return data." | §5.4.3, WP p. 29 | Within-leg weights paper-silent → equal weight. |
| Leg size | "two until December 1993 and three after this point" (commodities); "three countries in the long and short legs throughout" | Table 8 caption, WP p. 51 | Fixed-count legs, not ranks. BSV instead uses rank weights (§4). |
| Sample | portfolios formed from "the end of December 1974" ; "The sample period ends in January 2011" ; commodities 24 futures Jan 1970–Jul 2011 (KMVP data); MSCI 15 country indexes Jan 1970–Dec 2011 | Table 8 caption; WP pp. 28–29 | Return type for MSCI countries (USD vs local, excess vs total) paper-silent → USD excess of T-bill. |
| Rebalance | monthly (portfolios "constructed each month") | Table 8 caption | — |
| Vol scaling | none mentioned | — | Unscaled equal-weight legs. |

**Table 8 Panel C (WP p. 53), monthly %, all months**: commodities same-month L/S **0.93 (t 1.93)**; country indexes
same-month L/S **0.48 (t 2.20)**; same-minus-other: commodities 1.15 (t 1.97), countries 0.84 (t 2.76). Excl. January:
0.96 (2.03) and 0.50 (2.20). **Volatility and Sharpe are not published** (paper-silent); `paper_stats.json` carries an
explicitly *derived* SR ≈ t/√years (≈0.32 CM, ≈0.37 EQ over ~36 years), not a published number.

**Flag:** BSV Table I lists KLN "Seasonal" t = 2.76 (equity indices, SR 0.45) and 1.97 (commodities, SR 0.32). These equal
the WP's **same-minus-other** t-stats, not the same-month L/S t-stats (2.20, 1.93). Either the JF version changed the
numbers or BSV quoted the difference strategy; unresolvable without the JF text. A paper-stat tier for SEAS built on
KLN would have only a mean (no vol) → by FRAMEWORK §5 the vol/Sharpe legs are unassessable.

---

## 4. Baltussen, Swinkels & van Vliet (2021), "Global Factor Premiums" — SEAS-* (all four classes) + corroboration

Version: SSRN Jan 2019 (pages = PDF pages). Journal version inaccessible; the published JFE may differ.

| Rule | Verbatim quote | Cite | Paper-silent → suggested default |
|---|---|---|---|
| Seasonality (all classes) | "We use the return on an asset in a certain month over the prior 20 years (requiring at least 12-months of data)" | App. A.I, p. 53 | "12-months of data" ambiguous (12 months total vs 12 same-month obs) → declare; no cross-sectional demeaning mentioned (KLN demeans). |
| Trend | 12-month measure; "We skip the last month on trend investing" | App. A.I, p. 52 | BSV trend ≠ MOP (skip month). Corroboration only. |
| Momentum | "12-month-minus-1-month excess return" | p. 52 | — |
| Value | equity D/P; bonds "10-year bond yield over the past 1-year inflation"; FX equal mix of absolute and relative PPP; commodities "5-year reversal in spot prices, as defined in" AMP | pp. 52–53 | Differs from AMP for EQ, FI, FX. |
| Carry | KMVP definitions; bonds "10-year yield minus the short (3-month) yield and omit the … roll-down"; FX short-rate differential; commodities slope of futures curve | p. 53 | Differs from KMVP for FI (no roll-down). |
| BAB | "estimating the betas over a 36-month period (requiring at least 12-months of data) relative to the global asset class level portfolio return" ; legs sized so "the ex-ante betas are the same" | pp. 53–54 | Monthly betas, not FP daily. |
| Weights | w = z_t(Rank(S) − (N_t+1)/2) ; "requiring a minimum of two markets" | App. A.II, p. 54 | — |
| Position sizing | "size positions in each market … by its simple 3-year rolling volatility estimate or beta estimate (for BAB only)"; floor "10% quantile … or 2.5% (0.25)" | pp. 54–55 | — |
| Class vol target | "using a 10-year rolling window such that each factor strategy-asset class combination targets an ex-ante volatility of 10% per annum" | p. 55 | So BSV Sharpe ≈ scale-free; means/vols not tabulated per class. |
| Returns | "in excess of local financing rates and expressed in U.S. dollars" | p. 11 | — |
| Samples | replication 1981–2011 (Table II); "new sample" 1800–1980 & 2012–2016 (Table IV A); full 1800–2016 (Table IV B) | pp. 10–11, 42, 44 | No sub-period equal to 1985–2016. |

**BSV per-class Sharpe ratios (only statistic tabulated per class)**

| Style | Table II 1981–2011 (EQ / FI / CM / FX) | Table IV-A new sample (EQ / FI / CM / FX) |
|---|---|---|
| Seasonality | 0.36 / −0.09 / 0.48 / 0.00 | 0.60 / 0.73 / 0.85 / 0.30 |
| Trend | 0.62 / 0.53 / 0.88 / 0.53 | 0.75 / 0.49 / 0.23 / 0.60 |
| Momentum | 0.61 / 0.29 / 0.62 / 0.23 | 0.37 / 0.31 / −0.07 / 0.32 |
| Value | 0.34 / 0.29 / 0.22 / 0.32 | 0.27 / 0.28 / 0.50 / 0.03 |
| Carry | 0.87 / 0.71 / 0.44 / 0.53 | 0.68 / 0.44 / 0.36 / 0.52 |
| BAB | 0.37 / 0.36 / 0.01 / 0.13 | 0.34 / −0.02 / −0.06 / −0.04 |

Mean and vol per class are **paper-silent** (10% ex-ante target implies mean ≈ SR×~10% only approximately; not a
published number). Hence a BSV-based SEAS paper-stat tier can test Sharpe only; mean/vol legs are unassessable.
BSV also publishes a raw-data file (EUR figshare 14237024, "Raw data series used in Figure 1, Table 2, and Table 4") — a
candidate external SEAS class benchmark; **not downloaded** (downloads need user permission; commercial-use restriction
stated on the page).

---

## 5. KMVP (2018) Table 2 Panel A, Carry1M rows — check against A5

Table 2 is on **p. 208** (Panel A); Eq. (19) weights and Eq. (20) return on **p. 207**; A5's cite "§3.2–3.4 pp.207–210,
Eqs. 19–20 and Table 2 pp.208–209" is consistent. Weight rule matches A5: "w_t^i = z_t(rank(C_t^i) − (N_t+1)/2)" with z_t
so that "the sum of the long and short positions equals 1 and −1" (p. 207). Table 2 caption confirms the global factor
weights each class "by the inverse of its full-sample standard deviation" (A5's in-sample statement is consistent).

| Class | Carry1M mean | St.dev | SR | Sample (from §3.1 and Table 1, p. 205) |
|---|---|---|---|---|
| Global equities | 9.58 | 10.48 | 0.91 | Mar-1988 – Sep-2012 |
| Fixed income 10Y global (level) | 3.85 | 7.45 | 0.52 | Nov-1983 – Sep-2012 |
| Commodities | 11.22 | 18.78 | 0.60 | Jan-1980 (text) / Feb-80 (Table 1) – Sep-2012 |
| Currencies | 5.29 | 7.80 | 0.68 | Nov-1983 – Sep-2012 |
| (US Treasuries maturity, info) | 0.46 | 0.67 | 0.68 | Aug-1971 – Sep-2012 |
| (Global carry factor, info) | 7.18 | 5.96 | 1.20 | "1983 until 2012" (Fig. caption, p. 209) |

Paper-silent: first **return** month of each class strategy and minimum N per class (FI has 3 bonds at Nov-1983) →
suggested: first month after the first month-end with ≥4 carry signals (framework §1), declared as a coverage deviation.
Class carry formulas: FX Eq. (7) p. 201; commodities Eq. (9) p. 202 with synthetic spot/1-month futures from the two
nearest contracts; bonds Eq. (11)–(12) p. 203 computed "using this exact formula" from zero-coupon yields.
**Flag:** FRAMEWORK lists CARRY-CM as energy only, but Table 2's commodity row is all 24 commodities; an energy-only
replica has no matching published row (Panel B groups energy/metals/agri but trades across groups). As written, CARRY-CM
paper-stat fidelity is not comparable → director decision needed before specs.

---

## 6. Earliest evidenced public circulation

| Paper | Evidence | Earliest | Later candidate | Suggested cutoff (first full month after) |
|---|---|---|---|---|
| AMP | SSRN 1363476, "posted on March 6, 2009", AFA 2010 Atlanta paper — https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID1363476_code277060.pdf?abstractid=1363476 (SSRN returned 403 to direct fetch; date from SSRN listing via search) | 2009-03-06 | — | **2009-04-01** |
| FP | NBER conference draft "This draft: September 13, 2010" — https://users.nber.org/~confer/2010/BEf10/Frazzini.pdf (meeting date unverified); NBER WP 16601, Dec 2010 — https://www.nber.org/papers/w16601 ; SSRN 1723048 | 2010-09-13 (draft date; public posting date unverified) | Dec 2010 | **2011-01-01** (later candidate; 2010-10-01 if the conference draft is accepted as public) |
| KLN | SSRN 2224246 "Return Seasonalities", posted Feb 25, 2013 (SSRN listing via search; 403 on direct fetch); NBER WP 20815 Dec 2014 (verified; contains the commodity/country evidence) — https://www.nber.org/papers/w20815 | 2013-02-25 | Dec 2014 | **2015-01-01** recommended (whether the Feb-2013 version already had the commodity/country tests is unverified); 2013-03-01 if the director accepts the SSRN date |
| BSV | Paper cover "First version: April 2017" (no public posting evidence); SSRN 3325720 posted Jan 31, 2019 (listing via search) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3325720 ; Advisor Perspectives write-up 2019-02-18 | 2019-01-31 | — | **2019-02-01** |
| MOP, KMVP | fixed in A5 | — | — | 2011-01-01, 2013-09-01 |

---

## 7. AQR benchmark mapping (metadata only; header rows, notes and definition images/text boxes read; **no return values read or printed**)

Files: `data/core_premia/commod_bench/benchmarks/`. Definition text for VME/TSMOM sits in embedded EMF images and was
read by extracting text records; Century definitions are PNG images, viewed. Date columns were read for coverage only.

| Style × class | Benchmark (file / sheet / column) | Notes |
|---|---|---|
| TSMOM-EQ/FI/FX/CM | tsmom / `TSMOM Factors` / `TSMOM^EQ`, `TSMOM^FI`, `TSMOM^FX`, `TSMOM^CM` (overall `TSMOM`) | row 18 headers; dates 1985-01-31 … 2026-05-29 |
| XSMOM-EQ/FX/FI/CM | vme / `VME Factors` / `MOMLS_VME_EQ`, `MOMLS_VME_FX`, `MOMLS_VME_FI`, `MOMLS_VME_COM` | row 22 headers; dates 01/31/1972 … 07/31/2026; "data pre-February 1984 is static" |
| VAL-EQ/FX/FI/CM | vme / `VME Factors` / `VALLS_VME_EQ`, `VALLS_VME_FX`, `VALLS_VME_FI`, `VALLS_VME_COM` | as above |
| CARRY-EQ/FI/FX/CM (secondary per A5) | century / `Century of Factor Premia` / `Equity indices Carry`, `Fixed income Carry`, `Currencies Carry`, `Commodities Carry` | row 19 headers; dates 07/30/1926 … 02/27/2026; bond carry = "ten-year term spread", CM = nearest vs next-nearest |
| BAB-EQ | century / `Century of Factor Premia` / `Equity indices Defensive` | Defensive = negated beta, "36-month rolling regression" vs EW of all country indices (≠ FP daily 1y/5y) |
| BAB-FI (maturity buckets) | **none** (construct mismatch). Nearest: `Fixed income Defensive` = cross-country 10y bonds, 36-month beta vs EW of all bonds | Director must choose: AQR-class tier on a different construct, or FP Table VI paper-stat tier |
| BAB-FX, BAB-CM | none ("We do not construct a defensive strategy for currencies … for commodities") | not in menu |
| SEAS-* | **none** in any AQR file | BSV figshare data is the only external class series found (not downloaded) |
| Alternates (not framework benchmarks) | century `Equity indices/Fixed income/Currencies/Commodities` × `Value`, `Momentum`; `* Multi-style`; `* Market` columns | Century value uses CAPE (EQ), 10y real yield with 3-yr trailing CPI (FI), PPP (FX), negative 5-yr spot change (CM) |

**Scaling conventions (documented):**
- **TSMOM:** position "40%/σ_{t-1}", σ = EW squared daily returns, δ/(1−δ) = 60 days, ×261; class factor = (1/S_t)·Σ over available instruments. No ex-post rescaling documented. (Header text and definition image.)
- **VME class columns:** rank weights, "scaled to one dollar long and one dollar short"; no vol scaling. Only the three global averages use weights by "the inverse of their ex post sample standard deviation".
- **Century class columns:** "zero-cost, one dollar long and short factor portfolios"; defensive = "constant zero-beta (one beta long, one beta short) portfolios which are not zero-cost"; return uses weights w_{i,t−1}; cross-class aggregates weight classes by inverse of "the past 36 months" SD. No constant-vol ex-post scaling documented.
- ⇒ Under FRAMEWORK §5, no benchmark is ex-post constant-vol scaled; replicas should be compared in native units ($1/$1 rank, 40%/σ TSMOM, beta-1 legs for defensive).

Disclosure: no return values were seen. The Century sheet printed empty strings for cells D20:D40 (blank cells, not values).

---

## 8. Consolidated paper-silent list (to freeze in specs)

1. AMP: spot source for CM value; month-end vs daily averaging of 4.5–5.5y window; FX quote orientation and CPI lag; FI yield change point-to-point; bond return currency; tie handling; minimum N.
2. AMP VAL-EQ needs MSCI BE/ME — likely unavailable free → declared deviation or infeasible.
3. FP: GDP-weight source/lag for EI/CB market; per-class sample starts; minimum N; per-class vol not scaled (confirm gross shadow unscaled).
4. KLN: within-leg weights; 20-year window for non-stocks (implied); MSCI return definition; no vol/Sharpe published.
5. BSV: meaning of "at least 12-months of data"; no per-class mean/vol; journal-version differences unknown.
6. KMVP: first return month and minimum N per class; energy-only CM has no published row.
7. Circulation: FP and KLN dates depend on accepting conference/SSRN drafts; recommended later candidates given.
