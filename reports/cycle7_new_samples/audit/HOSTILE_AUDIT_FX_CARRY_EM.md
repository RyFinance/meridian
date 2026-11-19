# Hostile audit: FX carry on EM / non-G10 currencies (cycle 7's only POSITIVE)

2026-09-27. Code: `reports/cycle7_new_samples/audit/` (`harness.py`, `t2`–`t9`, `out/`). Independent reproduction:
`audit/repro/`. External data: `audit/data/` (manifest with URL, UTC time and sha256).

- **Sensitivities.** Every sensitivity below is labelled as one. None is a trial, and none can create a pass.
- **Independence.** This session built cycle 7. As mitigations, the reproduction was done blind by a separate agent,
  and inference was re-implemented in numpy.
- **Out of scope.** The "event-N patch" and "wave-1/2/3 holdouts" named in the brief are not artifacts of this
  session. None were touched.

## VERDICT: **WEAKENED**

**The single most important reason:** the premium is real in-sample but is the documented carry factor, and none of
the live versions can be distinguished from zero:
- **Known factors explain it after 2007.** On 2007–2021, against the LRV carry and dollar factors plus EM equity, VIX
  and high yield, alpha is **0.2%/yr (t 0.12, A4 p 0.47)**.
- **Post-publication (2013-09+):** active Sharpe 0.67, 95% interval [−0.18, 1.41].
- **Deliverable-only, post-publication:** 0.29 (p 0.19).
- **Canadian-retail tradable versions:** post-publication 0.05–0.26 before financing, and **negative after broker
  financing**.

## Evidence

| # | Test | Result | Finding |
|---|---|---|---|
| 1 | Blind reproduction | Spec SHA `4b154993…` is byte-identical (cycle-6 ledger, cycle-7 ledger and HEAD). Snapshot `93ef8e0f…` verified, 8/8 files. With the builder's drift normalisation and control seeding: net, control and active match to 1e-15. Active Sharpe 1.1223, p 0.0065, exact | **Reproduces** |
| 1 | Blind version before alignment | Active Sharpe 1.103, p 0.0058. The random-rank control across 20 seeds gives active Sharpe 1.08–1.13 (the builder's seed sits +1.1 sd) | Seed-robust |
| 1 | Divergences | (a) "Drifted weights" normalisation is ambiguous in the spec; the builder's normalised form is correct. (b) TRY in the 2005-01 mask month earns +8e-4 through the engine's day-1 attribution convention | Negligible; not look-ahead |
| 1 | Look-ahead perturbation (3 cuts, both implementations) | Weights before each cut are bit-identical; they change after it | None |
| 2 | LRV HML-FX + DOL, 1988–2021 (n 400) | Active alpha 7.6%/yr (t 3.7, A4 p 0.022); β_HML 0.36 (t 4.3); R² 0.11 | In-sample alpha vs developed-heavy LRV carry, driven by 1988–2008 |
| 2 | USD broad + EEM + ΔVIX + HYG, 2007–2026 (n 233) | Alpha 3.4%/yr (t 2.0, A4 p 0.016); β_EEM 0.08 (t 1.7) | Weak market betas |
| 2 | **LRV + EEM + ΔVIX + HYG, 2007–2021 (n 169)** | **Alpha 0.2%/yr (t 0.12, p 0.47)**; β_HML 0.60 (t 4.5); β_HYG 0.18 (t 2.2); R² 0.49 | **Documented carry factor plus credit beta; no alpha** |
| 2 | DXY only | β 0.03 (t 0.5) | Not a dollar bet |
| 2 | Static short-USD equal-weight EM basket, vol-matched (ex ante, 36 months) | The basket alone: Sharpe 0.67 [0.06, 1.36]. Book − basket: 0.36, p 0.054, 95% CI [−0.07, 0.79]; post-publication 0.43 [−0.02, 0.95] | About half the book is "long EM vs USD"; the excess is inconclusive |
| 3a | Deliverable-only (drop the 10 ever-NDF currencies) | Full 0.87 (p 0.021); **post-publication 0.29 (p 0.19)**, 95% CI [−0.49, 0.90] | Inconclusive post-publication |
| 3b | NDF P&L inside documented onshore/offshore gap episodes (BIS 2004/2014, IMF WP/20/179, Du–Schreger) | 3.9% of total P&L (deduplicated); BRL 2006–14 is 3.3% of it | The NDF assumption does not drive the result |
| 3c | NDF carry haircut 1 / 2 / 4 pp (signal and return) | 1.12 / 1.17 / 1.27 (post-publication 0.66 / 0.73 / 0.95) | Robust. The haircut pushes NDF currencies into the short leg |
| 4 | IBKR Canada deliverable spot set (CZK DKK HUF ILS MXN PLN SGD TRY ZAR ± BRL), RUB dropped | Book before financing: full 0.64–0.75, **post-publication 0.05–0.26**. Active post-publication 0.12–0.38 (p 0.10–0.34) | Inconclusive |
| 4 | Same set with IBKR financing (credit benchmark − spread, TRY flat 5%, ILS 0%; debit benchmark + 1.5–5%) | Post-publication book **−1.06 to −1.13**, 95% CI [−1.7, −0.5]; drag about 12%/yr | **Spot at IBKR destroys the carry** |
| 4 | OANDA Canada CFD route (swap ± admin fee 1–4 pp) | Before fee: post-publication 0.16. After fees: **−0.25**, 95% CI [−0.74, 0.28] | Negative |
| 5 | Crash declaration propagated? | Yes: p uses the crash layer (0.2/yr, −6 sd, bandwidth 0.10). n = 464 ≥ 120, so 90% is primary; 95% [0.47, 1.75] also reported | OK |
| 5 | Distribution | Active: skew +0.13, excess kurtosis 4.3, max drawdown −23%, worst month −11% (2018-08) | Fat-tailed |
| 5 | Crisis windows, active cumulative | 1997-07..98-12 **+25%**; GFC −10%; taper −5%; CNY 2015 −2%; TRY/ARS 2018 −13%; COVID −10%; RUB 2022 −2% | 1997–98 is positive **because** THB, IDR and RUB crash months are masked |
| 5 | Worst-case unmask (spot moves of positions held into masked months booked) | Full 1.07 (p 0.005); post-publication 0.70 | Masked held positions cost only −0.08 cumulative, but the mask also removes the crisis currencies from the universe |
| 6 | **Post-publication (KMVP 2013-09+), live-expectation estimate** | **Active 0.67, 95% CI [−0.18, 1.41], p 0.037; book net 0.51, 95% CI [−0.30, 1.22]** | Not distinguishable from 0 |
| 6 | Sub-periods | 1988–2008: 1.56; 2009+: 0.67 (p 0.010); rolling 5-year Sharpe fell from 2–2.9 (1997–2007) to 0.1–0.5 (2013–2025) | Strong decay |
| 6 | Drop TRY / RUB / both / top-3 (full; post-publication) | 1.04 / 1.12 / 1.03 / 1.08 (full); 0.79 / 0.69 / 0.93 / 0.95 (post-publication; 95% CI lower bounds −0.07 to 0.00) | Not a single-currency artifact |
| 7 | Per-side cost 3 / 6 / 9 / 15 / 30 / 50 bp | Book net full 1.01 → 0.85; post-publication 0.51 → 0.38. **Active rises with costs** (1.12 → 2.66) because the random-rank control pays about 10.5× the book's costs (0.96%/yr vs 0.09%/yr at 3 bp) | The 2×-cost gate passed trivially: a control design flaw |
| 7 | Retail financing markup 1 / 2 pp on gross | Post-publication book 0.24 / −0.02 | Retail financing removes the post-publication premium |
| 8 | CEW (WisdomTree EM currency, ER 0.55%) | Excess Sharpe −0.07 post-2013 (−0.01 since 2009); ρ with book 0.40 | Captures **none** of it |
| 8 | EMLC / LEMB / EBND (EM local-currency bonds) | Excess Sharpe −0.03 to −0.04 post-2013 | Captures **none** of it |
| 9 | Independent calibrated p (numpy AR-sieve null + crash layer) | Full: 0.0026 (A4 code 0.0065, which is more conservative through its Kilian correction). Post-publication: 0.036 (A4 0.037) | Consistent |
| 9 | Ledger timing | FRAMEWORK (pooling §5, POSITIVE rule) at 09:51:13Z; k = 6 at 14:32:56Z; first run 14:33:02Z | Pre-declared |

## Realistic post-decay Sharpe, net of retail cost, for the tradable version

| Route | Post-2013 Sharpe | Basis |
|---|---|---|
| IBKR Canada deliverable spot | **about −1.1** | Flat 5% on TRY balances, 0% on ILS, debit spreads of 1.5–5 pp |
| OANDA / Questrade CFD | **−0.3 to 0.0** | Swap ± 1–4 pp admin fee; before fees 0.12–0.16 |
| Retail ETF (CEW, EMLC) | **about 0** | Observed |
| Institutional forwards, deliverable set, no financing markup | 0.3–0.5 | Deliverable-only post-publication 0.29; book net post-publication 0.51 |

**Realistic retail range: −0.3 to +0.2, central about 0.** The in-sample 1.1 does not survive decay, factor
controls or retail implementation.

## Also disclosed

- The LRV factor file ends 2021-05 (not updated since 2021-06-18).
- FRED high yield is blocked; HYG is used instead.
- Several hosts are blocked and need the owner: fred.stlouisfed.org, hannolustig.com, wisdomtree.com (403) and
  sciencedirect (403).
- Nothing was committed. No builder file, ledger, spec or earlier report was edited. No sandbox or permission change
  was made.
