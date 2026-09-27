# New structural-information scout (cycle 5, Program D)

I found one family worth testing, not two. Primary-dealer Treasury inventory (F1) is the only one that clears the power filter and whose data I could assemble cleanly this session. Even F1 is borderline: 0.49 joint power at a true Sharpe of 0.7 with k=2, just under the 0.50 DECISIVE line. If it is registered alone (k=1), power rises to 0.62–0.66.

*Written by the cycle-5 D agent. Saved by the director session.*

The filter comes down to years of history. Under Amendment 3 with k=2 and k_val=2, a DECISIVE verdict needs about 27–28 years of daily-marked P&L, about 31 years for a weekly series with a little autocorrelation, and about 39 years for a monthly one (`research/new_info_scout/years_sweep.py`). Breadth does not change this. So every crypto structural family is INCAPABLE (at most 12 years of history), however many coins or venues it covers. They could only be registered under P1's "large effect" exception.

No returns, and no signal-to-return relationship, were computed. Data pulled was about 30 MB, with a manifest. One disclosure: raw file headers showed me about 15 dealer-position numbers (5 weeks of total Treasury positions from 2013-04, plus about 10 unrelated series on 2026-09-16). I computed nothing from them.

## Ranked families (20)

"Joint @0.7" is joint dev+validation power at a true net Sharpe of 0.7, k=2, from `plan_check`. False-pass is 0.0006 for every specced design. "Implied S" is the net Sharpe I expect from the literature after decay, with its joint power in brackets.

| # | Family | Free, keyless source | Clean years | Joint @0.7 | Verdict | Implied S (power) | Decision |
|---|---|---|---|---|---|---|---|
| F1 | Primary-dealer Treasury inventory | NY Fed FR 2004 bulk CSV, 1998-01-28+ | 27.8 | **0.49** (0.55 at D=1.0; 0.62–0.66 if k=1) | MARGINAL, borderline DECISIVE | 0.30 (0.03) | **RECOMMEND** |
| F3 | Margin debt / retail leverage | FINRA xlsx, 1997-01+ (monthly) | 29.4 | 0.46 | MARGINAL | 0.25 (0.02) | Reject |
| F16 | Buyback / issuance announcements (8-K, 424B) | EDGAR, 2004+ | 22.0 | 0.41 | MARGINAL | 0.53 (0.18) | Reject: no free prices for delisted names; OSAP contaminated; fundamentals F1 failed |
| F10 | Index inclusion / deletion | Wikipedia change ledger | 31.2 | 0.62 | DECISIVE | 0.26 (0.03) | Reject: no free prices for removed or acquired names; known decay (Greenwood–Sammon 2025) |
| F2 | Foreign official custody flows (H.4.1) | FRED WMTSECL1, 2002-12+ | 23.2 | 0.39 | MARGINAL | 0.20 (0.01) | Reject: direction not identified in advance; next to the spent japan_us_flow |
| F15 | TGA / reserves / ON RRP | FRED, 2002-12+ | 23.2 | 0.39 | MARGINAL | 0.20 (0.01) | Reject: the 2022–23 "liquidity" story is known; close to policy/macro |
| F11 | CFTC TFF dealer positions | CFTC, 2006-06+ | 20.1 | 0.32 | MARGINAL | 0.25 (0.01) | Reject: positioning family is EXHAUSTED |
| F4 | Treasury duration supply (MSPD) | fiscaldata, 2001-01+ | 25.5 | 0.28 | MARGINAL | 0.30 (0.02) | Reject: signal autocorrelation about 0.99 leaves 2–3 regimes; 2022 hindsight |
| F5 | Crypto dated-futures basis term structure | BitMEX 2014+, Deribit 2016+, Binance 2020+ | 11.6 | 0.13 | INCAPABLE | 0.5 (0.04) | Reject: funding sibling; Binance USD-M delivery contracts are BTC/ETH only |
| F13 | 13F holdings changes | SEC, 2013q2+ | 13.0 | 0.19 | INCAPABLE | 0.12 | Reject: OSAP breadth/IO already viewed; survivor-only prices |
| F14 | Borrow constraints | No free lending data; FINRA short-interest proxy 2018+ | 8.5 | 0.09 | INCAPABLE | 0.13 | Reject: no data |
| F12 | Repo / SOFR / quarter-end G-SIB window dressing | NY Fed rates 2018+ | 8.4 (21 with GCF) | 0.09 | INCAPABLE | 0.2 | Reject: calendar sibling of month-end; no free tradable instrument |
| F9 | Stablecoin supply | DefiLlama, 2017-11+ | 7.6 | 0.07 | INCAPABLE | 0.4 | Reject: history is re-derived, not point-in-time |
| F8 | Forced liquidations | Binance COIN-M snapshots, 2023-06 to 2024-10 only | 1.3 (6 via proxy) | 0.05 | INCAPABLE | 0.43 | Reject |
| F7 | Open interest / long-short ratios | Binance metrics, 2020-09+ | 6.0 | 0.05 | INCAPABLE | 0.35 | Reject: same window as the frozen funding claim |
| F6 | Cross-exchange basis dispersion | Venue archives | 6.6 | 0.04 | INCAPABLE | 0.8 | Reject: a price transformation |
| F17 | ETF creation / redemption | No free shares-outstanding history | 0 | – | NO DATA | – | Reject |
| F18 | Option market-maker inventory | OCC publishes aggregates only | 0 | – | NO DATA | – | Reject: options family exhausted |
| F19 | Cross-market segmentation (TIPS/ADR/CEF) | No free point-in-time data | 0 | – | NO DATA | – | Reject |
| F20 | Treasury settlement fails | Same file as F1 | weekly | – | – | – | Reject: no tradable return defined in advance |

Details:
- **Correlation semantics:** every ρ is stated and labelled ASSUMPTION in the spec files. For F7, F13 and F14, ρ_resid is the variance share of the factor the signal tilts towards, not an average pairwise residual correlation (per audit A1 point 5). Each also has a literal-ρ̄ scenario.
- **D input:** D is floored at 1.0 (A1 Q3). F1 uses D=1.1, which is conservative.

## Recommended experiment 1: F1, primary-dealer Treasury inventory

The honest caveat: DECISIVE means the test could detect a true Sharpe of 0.7. At the plausible 0.3, joint power is only 0.03.

- **Information:** net outright position (long minus short, $mn) of primary dealers in Treasury coupons with maturity over 6 years. The series ids change at each break:

  | Period | Series ids |
  |---|---|
  | 1998-01 to 2001-06 | PDPUSGCS5MNOP (over 5 years, the only split available) |
  | 2001-07 to 2013-03 | PDPUSGCS611NOP + PDPUSGCSM11NOP |
  | 2013-04 to 2021-12 | PDPOSGSC-G6L7 + G7L11 + G11 |
  | 2022-01 onward | G6L7 + G7L11 + G11L21 + G21 (a pure split of G11, so no break) |

  The data is saved at `data/new_info_scout/nyfed_pd/pd_all_timeseries.csv` (2,290 series, about 1,495 weeks).
- **Signal:**
  - z_t = (x_t − mean of the previous 52 weeks) / sd of the previous 52 weeks.
  - It is computed within segments that break on 2001-07-04 and 2013-04-03.
  - It needs at least 13 prior weeks, so the position is flat for 13 weeks after each break.
  - Position w_t = clip(z_t, −2, 2) / 2.
- **Direction (fixed, the reverse is never tested):** long duration when dealer inventory is high (z > 0). The mechanism is that balance-sheet-constrained dealers need a price concession to carry the inventory, which is paid back as they distribute it.
- **Timing:**
  - Data is as of Wednesday t and published about 16:15 ET on the Thursday 8 days later.
  - Enter at the first H.15 date on or after t+9 calendar days.
  - Hold one week and rebalance weekly.
- **Instrument and P&L:**
  - FRED DGS10, already in the repo at `data/c4/fred`.
  - Daily P&L = w × (−7 × Δy); it is price return only, the same construction as `tsy_auction_demand`.
  - IEF total return from 2002-08 is reported as a check but does not gate anything.
- **Costs:** base 1 bp of price per unit of |Δw| per side; stress 3 bp. The stress drag is about 0.10 Sharpe.
- **Windows:** development 1998-05-01 to 2012-06-29; validation 2012-07-02 to 2026-08-31, locked. Each has about 13.9 effective years.
- **Null and gates:**
  - Mean-centred circular block bootstrap with 21-day blocks. Do not use a HAC t, per A1 finding 1.
  - Development gate: Amendment 2 with k=2, i.e. Ŝ ≥ 1.8/√T, p < 0.025 and stress mean > 0.
  - Validation gate: Amendment 3 P2, i.e. p < 0.05/k_val, stress mean > 0 and Ŝ ≥ 0.30.
  - A circular shift of z by at least 52 weeks is reported only.
- **Pre-development guards (signals only, no returns):**
  - Report the correlation of z with the `tsy_auction_demand` signal aggregated weekly, and with a coupon-settlement-week dummy.
  - If |corr| > 0.3, charge F1 to that family's shot count.
  - Disclose that the API holds only the latest values (no vintages).
- **Power:**
  - Spec: `research/new_info_scout/specs/nis_f1_pd_treasury_inventory.json` (sha256 `eaeb6075…2fa4`).
  - Output: `reports/new_info_scout/power/nis_f1_pd_treasury_inventory.json` (sha256 `39c2b80f…a8a9`).
  - MDE (80% power): 0.56 single test, 0.90 joint.
  - Joint power at a true Sharpe of 0.7: 0.49 (k=2, D=1.1), 0.55 (D=1.0), 0.62–0.66 (k=1).
  - Years for 80% joint power at 0.7: 46.
- **Independence and contamination:**
  - The data is new; the project has never downloaded it.
  - The mechanism is the same dealer-absorption story as the registered `tsy_auction_demand` (whose development results the director has seen) and the spent `auction_cycle`. Using the inventory stock rather than weekly flows limits the overlap.

## Experiment 2: none recommended

The only second candidate that is strongly MARGINAL with clean data is F3, margin debt (0.46). Its result would rest on about three well-known episodes (2000, 2008, 2022), and it has no predictive literature. I'd leave the second slot empty and register F1 alone at k=1, which raises its power from 0.49 to about 0.62–0.66.

## Main rejection reasons
- **Too few years, so INCAPABLE:** all crypto families (F5–F9) and F12–F14.
- **Enough years but no clean data:** F10, F16, and F17–F19. Free prices are missing for delisted, removed or acquired names, and some sources don't exist for free.
- **Spent family, sibling or knowledge contamination:** F2, F3, F4, F5, F11, F12, F15.

## Data-access notes
- The Binance liquidation archive covers only COIN-M, 2023-06 to 2024-10; there is none for USD-M.
- FINRA's margin file comes back as a bot page to Python but downloads fine with curl.

Everything is in `/Users/rytty/CCP/quant_v7`:
- **Code:** `research/new_info_scout/` (`probe.py`, `probe2.py`, `make_specs.py`, `build_families.py`, `years_sweep.py`)
- **Specs:** `research/new_info_scout/specs/` (16 files)
- **Outputs:** `reports/new_info_scout/families.csv`, `families.json`, `coverage.json`, and `power/`
- **Data:** `data/new_info_scout/` (`MANIFEST.json` has 48 entries)