# Cross-sectional mechanism scout and survivorship audit (cycle 4)

*Written by the cycle-4 cross-sectional / survivorship agent. Saved by the director session. Survivorship code and outputs: `research/survivorship_audit/`, `reports/survivorship_audit/`.*

I've finished all four parts. Nothing survivor-free, free and uncontaminated has enough power to validate a moderate edge in its free history, and even the best candidate's tradability for a US account is unverified. **Crypto perp funding carry** comes closest: about a 26% chance of passing the dev gate at the base IC assumption, and about 52% if its IC is 1.5 times my base case.

No signal→return relationship was computed on real data. Real data were read only for coverage, names and dates, plus about 60 HTTP listing or availability probes. All return numbers below come from the synthetic model. Literature magnitudes marked "approx." are from memory and should be checked before any registration.

On the two numbers you asked for:
- **Weekly FINRA short-volume long-short on current-survivor US stocks, 2018–2026:** the survivor bias runs **against** the "high short volume underperforms" hypothesis. Size is about **−0.8 to −2.2 %/yr** on the hypothesis spread if the signal loads 0.3 on distress, and **near zero to −0.9 %/yr** at a loading of 0.1. As an IC that is about 0.001–0.003.
- **Binance perp funding cross-section:** the archive keeps delisted contracts, so the residual bias is about 0. It is capped at a few %/yr in favour of carry if the final-settlement gap were large. A live-only symbol list would bias carry **in favour** by **about +17 to +34 %/yr**.

## 1. Ranked mechanisms (before any return was seen)

The score weights the seven criteria in your priority order: power 0.24, mechanism 0.18, point-in-time integrity 0.15, survivorship 0.14, independent observations 0.11, implementation 0.10, independence from prior work 0.08. The power score comes from the net t-statistic over the free history, and is set to 1 for families already tested (spent). Full per-row text, including mechanism, literature, decay, data, traps and implementation, is in `reports/xsec_scout/mechanism_ranking.csv` and `.json`.

"Dev power" below is P(pass the 1.8/√T development gate), on 60% of the free history.

| # | Mechanism | Score | Net Sharpe (assumed IC) | Dev power | Survivorship | Prior use / contamination |
|---|---|---|---|---|---|---|
| 1 | C1 Crypto perp funding carry (Binance USD-M, delisted kept) | 3.93 | 0.58 (IC 0.02/wk) | 0.26 | free by universe | never tested |
| 2 | C3 Crypto leverage crowding (open interest × funding, Binance metrics 2020-09+) | 3.43 | 0.28 | 0.10 | free | never tested |
| 3 | C2 Crypto cross-sectional 1–4 week momentum/reversal | 3.35 | 0.26 | 0.10 | free | the 2022–25 alt-vs-BTC path is known |
| 4 | U1 FINRA daily short-volume ratio, weekly holding | 3.08 | 0.09 (IC 0.008) | 0.06 | bias against the hypothesis | never tested; not an OSAP predictor |
| 5 | U7 Net issuance / buybacks | 3.06 | 0.27 | 0.16 | against | F1 dev failed; 2015+ validation locked; excluded |
| 6 | U12 Forced index/ETF flows | 3.01 | 0.45 | 0.33 | deleted names unpriced | graveyard: dead |
| 7 | U2 FINRA short interest / days-to-cover | 3.00 | 0.22 | 0.10 | against | OSAP ShortInterest already viewed |
| 8 | G1 Country index value/momentum/carry | 3.00 | 0.41 | spent | free | spent (E1/E2, multiasset, policy_trend) |
| 9 | U3 Liquidity-provision reversal | 2.96 | 0.34 (gross 0.85) | 0.15 | **in favour** | OSAP STreversal viewed; Codex run crashed before any results |
| 10–20 | BAB, FX cross-section, 13F breadth, QMJ/distress, dividend events, fails-to-deliver, insiders, commodity basis, Wikipedia attention, options demand, peer earnings spillover | 2.18–2.86 | ≤0.24, or spent | ≤0.17 | mixed | mostly viewed or spent |

**Decay evidence**, from the project's own `predictor_decay.csv` (2015+ Sharpe, EW / ex-microcap):
- ShortInterest 0.79 / 0.21; IO_ShortInterest 0.81 / 0.74
- DelBreadth 0.52 / 0.52
- ShareIss1Y 0.82 / 0.60
- DivOmit 0.82 / 0.36
- STreversal 0.38 / 0.31
- GP 0.85 / 1.07

McLean–Pontiff replication: −58% after publication.

## 2. Survivorship audit

**What the repo's stock data are:**
- **Every stock cache is survivor-only.**
  - `data/raw`: 502 names, 2015+.
  - `data/multiasset/stocks`: 503 names, 2003+.
  - `data/lse/candles_1d`: 496 names.
  - `stocks_raw_2014`: 103; `raw_legacy`: 20.
  - Not one name ends before 2026-06.
- **The universe was selected today, which is look-ahead.** It is today's Wikipedia S&P 500 list, and the top-75 subset is ranked on 63-day dollar volume computed 2026-08-18.
- **The LSE catalog doesn't fix it.** It has 3,855 live stocks and 127 non-live, all of which stopped after 2026-04-13. Its crypto list has 56 live coins; the repo's crypto cache has 60, and its two non-live ones (MKR, RNDR) are renames, not deaths.
- **Point-in-time S&P coverage by the repo cache:** 50% (2008), 63% (2013), 77% (2019), 84% (2022), 93% (2025).
- **Adding the LSE live names still listed after S&P removal** raises that to 70%, 77%, 89%, 94% and 98%. What stays missing is mostly acquisitions plus SIVB.
- **Why names left the S&P** (Wikipedia ledger reasons): 47% acquired, 38% market cap, 8% spin-off, 2% distress.

**Simulation** (`survivor_sim.py`, `targeted_bias.py`). The model:
- A barrier/delisting world with Shumway-style loss at delisting: mean loss 30%, 55% for the Nasdaq case.
- M&A exits at 3%/yr.
- An index made of the largest 15% of firms, reconstituted annually with a buffer.
- Index exits run about 5%/yr. Coverage decays a little faster than the repo's (72% at 7 years back vs the repo's 77%), so index-view biases are, if anything, slightly high.

Signs: + means the survivor view shows a higher top-minus-bottom spread than the truth. For a distress-loaded signal (short volume, short interest, junk), + means the bias works **against** "distressed names underperform". For reversal, + means **in favour**.

**Base world** (performance delistings ≈3.7%/yr), %/yr:

| View (what the data are) | Signal | h=1 | h=5 | h=21 | h=252 |
|---|---|---|---|---|---|
| Listed-today universe (e.g. the LSE live stocks) | distress 0.3 / 0.6 | +3.1 / +6.4 | +3.0 / +6.3 | +3.1 / +6.5 | +2.9 / +5.5 |
| Listed-today universe | reversal | +2.2 | +3.0 | +3.4 | +5.0 |
| Point-in-time S&P mask ∩ today's members (repo best case) | distress 0.3 / 0.6 | +2.5 / +3.3 | +1.1 / +3.2 | +0.9 / +3.0 | +1.6 / +3.4 |
| Same | reversal | +0.4 | +2.0 | +2.0 | +3.5 |
| Point-in-time S&P mask ∩ still listed (adds LSE names) | distress 0.6 / reversal | +2.5 / +0.3 | +2.3 / +1.0 | +2.1 / +1.1 | +2.9 / +2.1 |
| All firms, but the delisting return missing (Shumway) | distress 0.6 / reversal | +2.5 / +2.0 | +2.4 / +2.3 | +2.2 / +2.2 | +1.5 / +1.6 |

- **Noise:** index views have a standard error of about 0.3–0.6 %/yr; a pure-noise signal (distress loading 0) shows ≤0.7 %/yr.
- **The loading scale:** a loading of 0.3 corresponds to a point-biserial correlation of about 0.065 with next-year delisting; 0.6 to about 0.13.
- **The Nasdaq-like world** (7%/yr deaths, 55% mean loss) roughly doubles to triples these numbers. The low-distress world (1.5%/yr) roughly halves them.

**Rule of thumb for the director:**
1. **The bias per year hardly changes with horizon.** Rebalancing daily does not remove it.
2. **What horizon changes is its size relative to alpha.** Expressed as an IC, the bias grows with √h: 0.001–0.004 at h=1–5 days, 0.03–0.05 at h=252. At a weekly horizon it is 5–30% of an IC-0.01–0.02 effect; at an annual horizon it is as big as the whole effect.
3. **Direction follows the leg.** The survivor universe inflates whichever leg holds future-dead names: distressed, shorted, losers.
4. **Momentum's sign depends on how persistent growth is.** In the model the bias is negative: the h-transform lifts losers. The repo's measured survivor inflation of momentum, about +16 CAGR points for a top-20 book, comes from persistent growth into the index, which the model understates. Treat any survivor-universe momentum or quality result as unknown in sign.

**Non-stock universes:**
- **Binance archive:** 952 funding symbols are archived and 385 (40%) are not trading now. LUNA, ANC, BZRX, SRM, OMG, WAVES and others remain; funding history starts 2020-01 and metrics 2020-09.
- **Country indices, FX and futures:** effectively survivor-free.
- **ETFs:** from memory, roughly 5–8%/yr of US ETFs close, and the ones that close are small and underperforming. Major sector and country ETFs are unaffected.

## 3. Point-in-time traps by candidate

| Trap | Where it bites |
|---|---|
| Ticker recycling or reuse | LUNAUSDT spot became Terra 2.0 after 2022-05; US recycled tickers give yfinance false histories |
| Ticker changes / CIK–ticker / CUSIP–ticker mapping | FINRA symbols (BRK.B), 13F CUSIPs, the Wikipedia ledger's old tickers (HFC, GPS) |
| Publication lag | FINRA short interest: file carries only the settlement date, published about 7–8 business days later. 13F: filing date, up to 45 days after quarter-end. SEC fails-to-deliver: about 2 weeks. Reg SHO: time of day the file lands |
| Restatements | FINRA short-interest revision flag; 13F-HR/A amendments; XBRL 10-K/A (use accepted-at time, not period end) |
| Convention changes | Funding interval 8h→4h for some perps; settlement T+2 (2017) → T+1 (2024); Wikimedia bot reclassification |
| Scope and contents | Reg SHO covers off-exchange volume only; FINRA files include ETFs; the Binance archive includes stock-token perps (AAPLUSDT) and BUSD duplicates |
| Timestamps | UTC crypto day vs US close; bulk economic-calendar rows are in Berlin time (known project issue); earnings before-open vs after-close |
| Universe selection | Today's S&P list and dollar-volume ranking; Binance listing-date selection (coins are listed after they get hot) |

## 4. Top 5: feasible with free data and survivorship-resistant

I left out U3 (its bias runs in favour of the hypothesis), U7 (its validation window is locked and reserved for delisted-inclusive data), U12 (removed names are unpriced) and everything spent.

The power figures below use `research/power` (the quintile long-short core), plus a true-IC regime spread τ and bets correlated through a factor tilt.

| # | Universe / signal | Timing | Hold | Effective sample | Power at base IC (and ×1.5) |
|---|---|---|---|---|---|
| 1 | **C1** Top-100 Binance USDT perps by 30-day volume, delisted included. Signal: trailing 7-day funding. Long the low-funding quintile, short the high; returns include funding | Funding stamp t → trade next hourly bar | 1 week | 343 weeks, 2020-01→2026-08; effective breadth ≈25 (naive 100) | IC 0.02: gross/net Sharpe 0.72 / 0.58, t 1.48, dev 0.26 (0.52) |
| 2 | **C2** Same universe; 1–4 week return rank | Close t (UTC) → t+1 | 1 week | as above | IC 0.015: net 0.26, dev 0.10 (0.22) |
| 3 | **C3** Binance metrics: open-interest growth × funding (crowding) | 5-min snapshot → next bar | 1 week | 312 weeks, effective breadth ≈24 | IC 0.015: net 0.28, dev 0.10 (0.21) |
| 4 | **U1** Point-in-time S&P members priced by the repo cache plus LSE live names; 20-day abnormal FINRA short-volume ratio, sector-neutral; short the high end | File for day t → trade t+1 close or t+2 open | 1 week | 421 weeks, 2018-08→2026; effective breadth ≈31 (naive 450; naive fundamental-law Sharpe 1.22) | IC 0.008: gross 0.35 / net 0.09, dev 0.06; IC 0.016: net 0.44, dev 0.20 |
| 5 | **U2** Same US universe; change in FINRA days-to-cover | Settlement date + 8 business days → next close | 2–4 weeks | 209 two-week periods from 2017-12; effective breadth ≈21 | IC 0.015: net 0.22, dev 0.10 (0.19) |

**Main power finding:** cross-sectional breadth does not escape the power problem once you allow for:
- factor-tilted signals (effective breadth 20–30, not N);
- IC that varies by regime (τ 0.04–0.10);
- costs.

Only C1 gets past 50% development power, and only if its IC is at least about 0.03, which is optimistic after decay. For U1 and U2, a gross-IC mechanism test (power 0.15–0.39) is the honest first step; net-of-cost passes are unlikely.

## 5. Contamination notes

- **Every US anomaly design** (short interest, 13F, issuance, dividends, reversal, quality, BAB) is knowledge-contaminated. The edge graveyard viewed OSAP's 2015–2024 returns for 212 predictors.
- **U1 (daily short volume)** is the only US signal here with no viewed OSAP analogue.
- **Crypto:** the project never tested a cross-section. But I (and the director) know that 2022–25 was a bad period for alts relative to BTC, with the LUNA and FTX collapses. That weakens C2 most.
- **Codex reversal:** it has a registration file but produced no stock-leg results, so it does not contaminate U3.

## 6. Limitations

- **The simulation is a stylized barrier model** with no true momentum, industry structure or distress-risk pricing. Its index churn is somewhat higher than the S&P's, the sign of the momentum bias depends on the model, and "weekly" crypto uses a 252-day clock.
- **The IC, τ, correlation and cost inputs are assumptions**, not estimates.
- **Binance may not be tradable for a US person**; this needs checking before any registration. The Binance delisting-settlement gap was not measured.
- **Two data-access points were left unresolved:**
  - SEC fails-to-deliver files return 403 unless the request carries a contact email. That is your decision; I did not send your email.
  - My FINRA per-facility files reach back to 2009-08, which differs from the other scout's 2018-08 date for the consolidated file.
- **FINRA publication times are unverified.**
- **The LSE-live coverage gain counts ticker matches only**, and the rename map is illustrative.
- **The OSAP decay numbers are academic, CRSP-based and gross.**

No existing files were edited and nothing was committed. `research/power` was imported, not modified.

Files are in `/Users/rytty/CCP/quant_v7`:
- `research/survivorship_audit/`: `stock_coverage.py`, `binance_listing_check.py`, `survivor_sim.py`, `pit_member_coverage.py`, `targeted_bias.py`
- `reports/survivorship_audit/`: `stock_coverage.json`, `binance_listing.json`, `sim_bias_summary.csv`, `sim_results.csv`, `sim_index_calibration.csv`, `sim_summary.json`, `sim_bias_vs_horizon.png`, `targeted_bias.csv`, `pit_member_coverage.csv`, `sp500_removal_reasons.csv`
- `research/xsec_scout/`: `rank_mechanisms.py`, `power_top5.py`
- `reports/xsec_scout/`: `mechanism_ranking.csv`, `mechanism_ranking.json`, `power_top5.csv`