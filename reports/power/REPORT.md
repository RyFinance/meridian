# Power calculator for quant_v7 (research cycle 4, Workload A)

*Written by the cycle-4 power-framework agent. Saved by the director session.*

## Headline findings

1. **The 0.75 validation gate can never reach even 50% power at a true Sharpe of 0.7.** With S < 0.75, P(validation pass) falls towards 0 as the window grows. Under the registered gates, "years for 80% joint power" is infinite for every S ≤ 0.75 (plotted in `power_vs_years.png`).
2. **At a given net Sharpe, breadth does not change power.** Power depends only on years, κ (the autocorrelation/fat-tail factor) and the gate. Breadth only changes how much Sharpe a given per-bet edge buys. With k=1 and daily data, detecting S=0.7 with 80% power needs about 12.6 years for a single test and about 36 years for dev + val under the proposed gate.
3. **Retrospective: every registered two-stage family had 21–32% joint power at S=0.7.** They rate MARGINAL or INCAPABLE. The analytic numbers reproduce null_lab2's independent simulation (tsy_month_end 0.310 vs 0.291, insider 0.319 vs 0.321, etf_hybrids 0.324 vs 0.334).
4. **All three cycle-4 candidates fail the DECISIVE bar at S=0.7.** Binance funding and FINRA SVR are INCAPABLE on their windows. Treasury auctions is MARGINAL (0.27 under the current gates, 0.49 under the proposed gate).

## 1. API summary

| Module | Contents |
|---|---|
| `core.py` | `Autocorr` (ar1 / overlap / ar1_overlap / overlap_persistent / acf / lrv) with `D1`, `D2`, `bartlett(b)`, `newey_west(L)`; `SeriesModel` with `kappa2(S)`, `se`, `se_null`; `single_test_power`, `mde_single_test`, `years_single_test`, `solve_mde`, `solve_years`; `kish_deff`, `breadth_eff`, `block_mean_corr`, `batch_alpha`; `require_explicit_corr`, `CorrelationAssumptionError`, `IndependenceWarning` |
| `designs.py` | `timeseries`, `daily_strategy`, `monthly_strategy`, `event_study` (+ `concurrency_profile`), `cross_sectional_ic`, `long_short` (+ `long_short_core`, `quantile_turnover`), `carry` (+ `crash_moments`, `one_factor_portfolio_moments`, `scale_mixture_moments`), `panel`, `build(kind, params)`. Each returns a `Design`: series model, raw and effective observations, cross-sectional design effect, natural-unit mapping, implied Sharpe, breadth curve, correlation sensitivity, and what an independence assumption would wrongly claim. |
| `gates.py` | `Gate` (legs: `sharpe_c`, `sharpe_abs`, `alpha`/`null_center_sr`, `hac_t`, `stress_drag_sr`, `both_halves_positive`, `fraction_of_dev`, natural-unit threshold); `amendment2_dev_gate`, `current_val_gate`, `power_aware_val_gate`; `joint_pass`, `mde_joint`, `years_joint`; `truncation_corrected_estimate` (conditional median-unbiased), `normal_prior_posterior`; `sleeve_screen_power` |
| `report.py` | `evaluate()` returns the full report dict (observations, SEs, Newey-West check, MDEs, power table incl. null worlds, years for 80%, verdict); `text_table()`; `verdict()` |
| `simulate.py` / `verify.py` | Seeded Monte Carlo verifiers (deterministic CRC seeds); `verify.suite(fast)` is the agreement suite |
| `plan_check.py` | The CLI |
| `design_schema.json` | JSON schema for design specs |
| `specs.py` | Retrospective, prospective and cycle-4 specs; writes `examples/*.json` (18 files) |
| `tables.py` | Builds everything in `reports/power/` |

**Correlations must be stated.** Every correlation or autocorrelation argument is required with no default. A zero correlation for events, panels, cross-sections or carry raises `CorrelationAssumptionError`. It is accepted only with `assume_independent="<written justification>"`, which also emits a loud `IndependenceWarning`. The schema rejects specs that omit ρ.

**CLI** (registration check under Amendment 2, N5):
```
PYTHONPATH=. .venv/bin/python -m research.power.plan_check research/power/examples/<spec>.json [--out reports/power] [--mc 2000] [--strict]
```
- It writes `reports/power/<name>.json` and `<name>.txt`.
- Verdicts:
  - **DECISIVE:** joint power at 0.7 ≥ 50% and P(pass both | S=0) ≤ 5%.
  - **INCAPABLE:** joint power at 0.7 < 25%, or false-pass > 10%.
  - **MARGINAL:** everything in between.
- These thresholds are my proposal.
- `--strict` sets exit codes 0/1/2; `--mc` adds a Monte Carlo check of the two-stage numbers.
- Supported designs: timeseries, event_study, cross_sectional_ic, long_short, carry, panel, sleeve_screen.
- Specs can carry scenario grids.
- Validation criteria can be `sharpe`, `tstat`, `hac_t`, `fraction_of_dev`, `natural` (e.g. bp per event) or `none`.

Rebuild everything with `PYTHONPATH=. .venv/bin/python -m research.power.tables`.

## 2. Formulas and references

**Time-series design effect (Newey–West population form).**
- D1 = 1 + 2 Σ(1 − k/n) ρ_k. For AR(1) this is (1+φ)/(1−φ); for H-period overlap, D1 = H (Hansen–Hodrick 1980).
- Overlap only creates IC autocorrelation if the signal persists: ρ_k = φ_s^k·(H−k)/H. A refreshed signal gives none; I found this by Monte Carlo.
- A block bootstrap with block b sees the Bartlett-window version, D_boot = 1 + 2 Σ_{k<b}(1 − k/b) ρ_k (Künsch 1989; Lahiri 2003).
- A Newey–West estimate with L lags sees D_NW = 1 + 2 Σ_{k≤L}(1 − k/(L+1)) ρ_k. Its actual size when D_NW differs from D is reported.

**Sharpe standard error** (Lo 2002 for autocorrelation; Mertens 2002 / Opdyke 2007 for skew and kurtosis):
- Var(ŝ) = [D1 − γ3·s·√(D1·D2) + (γ4−1)/4 · s²·D2] / n, where s is the per-period Sharpe.
- Annualised: Var(Ŝ) = κ²(S)/Y.

**Gate reduction and joint power.**
- Every leg is one-sided on the same Ŝ, so the gate threshold is h = max(c/√Y, s0, null_center + z_{1−α}·√(D_null/Y), t0·√(D_null/Y), stress_drag/vol).
- P(pass | S) = Φ((S − h)/SE).
- Joint power = P_dev × P_val, because the windows are disjoint. For an effect-size validation gate I integrate over the dev estimate instead.
- The stress leg is (stress − base cost)/vol in Sharpe units.
- α = 0.05/k (Amendment 2, N2); c = 1.8, or 2.4 when k ≥ 4 (N3).

**Events** (Kish 1965; Moulton 1986/1990; Fama 1998; Mitchell & Stafford 2000; Jaffe 1974 / Mandelker 1974):
- deff = 1 + ρ(m_w − 1), where m_w = E[A²]/E[A] is the size-weighted number of concurrently held events.
  - For seasonal Poisson arrivals this is computed exactly.
  - For same-date clusters it is (1 + cv²)·m̄.
- N_eff = N/deff.
- Calendar-time equivalence: S = (μ_e − cost)/σ_e · √(N_yr/deff). The event-level test with clustered SEs and the fixed-dollar calendar-time portfolio test coincide.

**Cross-section** (Grinold 1989; Grinold & Kahn 2000; Buckle 2004; Clarke, de Silva & Thorley 2002/2006; Qian, Hua & Sorensen 2007):
- Var(IC_t) = (1 + (N−1)ρ_bet)/N and N_eff = N/(1 + (N−1)ρ_bet).
- ρ_bet = ρ_resid × ρ_signal. A common mode that the signal does not load on cancels in a demeaned book.
- Setting `rho_signal=1` gives your literal formula N/(1+(N−1)ρ̄).
- The formula applies to the covariance IC (the P&L of a fixed-scale linear book, which is what a Sharpe gate tests). Self-normalised Pearson/Spearman ICs have a smaller sd, so the formula is conservative for them.

**Long-short quantile book.**
- Mean spread = σ_cs · IC · E[s_top − s_bot], which is 2φ(z_q)/q without tilt.
- Variance comes from an exact large-N Gauss–Hermite integration over a one-factor tilt model, plus finite-N sampling. There is also an "equicorrelated_bets" mode that applies the literal formula.
- Turnover per leg: τ = 1 − Φ₂(z, z; ρ_sig)/q. Cost per rebalance = 4τ·c + borrow.
- The net Sharpe is what gets powered.

**Carry.**
- An equal-weight book has N_eff = K/(1+(K−1)ρ̄), including block structures.
- Skew and excess kurtosis are required inputs. `crash_moments` gives exact cumulants for a normal + Bernoulli jump. `one_factor_portfolio_moments` shows that a common crash does not diversify away.
- A time-varying signal is handled as a lognormal scale mixture.

**Panel.**
- The equal-weight book (equivalent to time-clustered SEs) has N_eff = K/(1+(K−1)ρ̄).
- Naive pooled K·T analysis understates the SE by √(deff·D).

**Winner's curse.** I report two corrections: the conditional median-unbiased estimate (Andrews, Kitagawa & McCloskey 2019) and an N(0, 0.5²)-prior posterior mean. The prior sd of 0.5 is my assumption.

## 3. Monte Carlo agreement (`reports/power/mc_agreement.csv`)

53 of 54 formula checks are within tolerance: |Δ| ≤ max(3 pp, 3 MC SE) for probabilities and 5% relative for sds. Four checks carry wider, documented tolerances: turnover 10%, fat-tail κ 7.5%, sample skew 15%, and the spread mean uses 3 MC SE.

| Design | Checks | Analytic vs MC (examples) |
|---|---|---|
| Daily AR(1), φ 0.15, literal 21-day block bootstrap, two-stage 12 + 11.6y | 8 | Joint at S=0.7: current 0.298 vs 0.288; proposed 0.447 vs 0.436. At S=0: 0.0007 vs 0.000 |
| κ (Lo) | 1 | 1.164 vs 1.165 |
| Monthly, 3-month overlap (D=3) | 3 | Size 0.050 vs 0.050; κ0 1.73 vs 1.77 |
| Events: 510/yr, 20-day hold, seasonal clusters | 8 | Power at icc 0.02, S 0.7: 0.715 vs 0.718; sd(mean CAR) exact. Naive independent-event t false-positive rate 0.144 vs 0.148 |
| Events: 5-pair month-end clusters | 1 | 0.528 vs 0.525 |
| Cross-sectional IC (N=200) incl. overlap_persistent | 12 | sd(IC) 0.323 vs 0.320; power 0.167 vs 0.167; sd(mean IC) with D: 0.0261 vs 0.0258 |
| Decile long-short (sort, turnover, cost) | 8 | sd 207 vs 206 bp; net P(Ŝ ≥ 0.5) 0.765 vs 0.758; turnover 0.311 vs 0.328 (see limitations) |
| Carry with common crash | 7 | Power 0.847 vs 0.848; κ 1.117 vs 1.158 under 3%/month −6 sd crashes |
| Panel, 30 markets (equicorrelated and blocks) | 4 | Power 0.676 vs 0.674; naive pooled false-positive 0.364 vs 0.360 |
| 17-sleeve screen | 3 | 0.022 vs 0.020; 0.196 vs 0.220; **0.475 vs 0.507 is the one miss** (the analytic treats inclusions as independent, so it is 2–3 pp conservative) |

Two informational rows are not formula checks: a literal Newey-West t with 6 lags on 120 overlapping monthly observations is oversized (7.6% at nominal 5%). That is a real finite-sample warning for monthly-overlap plans.

## 4. Retrospective (`reports/power/retrospective.csv`, real windows)

| Family | Dev + val (y) | k | Dev threshold (binding leg) | P_dev @0.7 | P_val @0.7 | **Joint @0.5 / 0.7 / 1.0** | False-pass | MDE joint | **Verdict** | Joint @0.7 with proposed gate → verdict | null_lab2 @0.7 | Actual outcome |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tsy_month_end | 12.0 + 11.6 | 1 | 0.52 (c/√T) | 0.70 | 0.44 | .11 / **.31** / .70 | 0.001 | 1.09 | MARGINAL | .45 → MARGINAL | .29 | Dev 0.664; val 0.69 FAIL |
| commodity_roll | 10.4 + 9.7 | 2 | 0.56 (c/√T) | 0.72 | 0.42 | .06 / **.30** / .81 | 0.000 | 0.99 | MARGINAL | .63 → DECISIVE | .58 (dev only) | Val 0.21 FAIL |
| fx_hedge_rebal (5 × 72 events) | 6.0 + 5.7 | 1 | 0.73 | 0.47 | 0.45 | .08 / **.21** / .54 | 0.001 | 1.26 | **INCAPABLE** | .24 → INCAPABLE | .49 (dev only) | Dev 0.09 FAIL |
| PEAD 2004–14 (single stage) | 11.0 | 1 | 0.64 (HAC t) | 0.57 | – | .33 / **.57** / .87 | 0.022 | 0.91 | DECISIVE* | – | .61 | HAC t 1.12 FAIL |
| multiasset 17-sleeve screen | 10 + 8.7 | 17 | Ŝ ≥ 0.30, no null | 0.61 | – | .10 / **.19** / .42 | 0.022 | – | **INCAPABLE** | – | .87 (screen only) | Hold-out FAIL |
| IEF−SHY | 12.0 + 11.7 | 3 | 0.61 (p leg) | 0.63 | 0.43 | .07 / **.27** / .74 | 0.000 | 1.05 | MARGINAL | .49 → MARGINAL | .53 (dev only) | Dev failed on p |
| insider | 10 + 10.5 | 4 | 0.50 flat | 0.73 | 0.44 | .11 / **.32** / .73 | 0.001 | 1.07 | MARGINAL | .51 → DECISIVE | .32 | Val FAIL |
| etf_hybrids | 12 + 11.7 | 5 | 0.50 flat | 0.74 | 0.44 | .10 / **.32** / .75 | 0.000 | 1.04 | MARGINAL | .55 → DECISIVE | .33 | Val FAIL |

\* PEAD is DECISIVE only as a single stage: it has no independent validation window.

- **fx_hedge_rebal:** its 360 events have an effective count of 138 at icc 0.4. A 0.7 edge needs 6.3 bp/event net; the realised figure was 0.6.
- **multiasset:** the screen includes 3.3 null sleeves in expectation, which dilute the book.

**Winner's curse** (`winners_curse.csv`):

| Family | Dev estimate | Conditional median-unbiased | N(0, 0.5²) posterior mean | P(val) at posterior: current / proposed gate |
|---|---|---|---|---|
| tsy_month_end | 0.664 | 0.20 | 0.45 | 0.20 / 0.37 |
| commodity_roll | 0.596 (barely above its gate) | −0.39 | 0.48 | 0.14 / 0.62 |

A validation miss on these families was therefore the most likely outcome even with a real edge.

## 5. Prospective (`reports/power/prospective.csv`; base rows use a 50/50 dev/val split, k=1)

| Archetype | Effective units (N_eff) | MDE, single test | MDE, joint (current / proposed) | Joint @0.7 (current / proposed) | Years for 80% @0.7 (single / joint proposed) | Verdict |
|---|---|---|---|---|---|---|
| 500 stocks × 10y daily long-short | 19 (ρ 0.2, tilt 0.25) | 0.79 | 1.34 / 1.33 | .19 / .19 | 12.6 / 36 | INCAPABLE |
| 2,000 stocks × 15y weekly | 20 | 0.64 | 1.17 / 1.09 | .24 / .33 | 12.7 / 36 | INCAPABLE → MARGINAL |
| 8,000 events/yr × 10y | 1,034 events/yr (deff 7.7) | 0.79 (≈ 25 bp net per event) | 1.34 / 1.33 | .19 / .19 | 12.6 / 36 | INCAPABLE |
| 30 markets × 20y monthly, ρ 0.45 | 2.1 | 0.59 | 1.13 / 1.01 | .29 / .43 | 14.4 / 40 | MARGINAL |
| 200 crypto perps × 5y daily, ρ 0.6 | 1.7 | 1.18 | 1.99 / 1.99 | .07 / .07 | 14.1 / 39 | INCAPABLE |
| 4 commodities × 35y monthly, ρ 0.4, crash | 1.8 | 0.45 | 1.01 / 0.77 | .36 / .72 | 14.8 / 42 | MARGINAL → DECISIVE |

Scenario grids (implied net Sharpe from the primitives, and years needed):

- **500 stocks daily:**
  - IC 0.01 gives net Sharpe 0.19–0.42: hopeless.
  - IC 0.02 gives 0.69–1.61. Joint power is 0.18–0.94; the tilted-signal model sits at the high end and the literal-formula worst case at the low end.
  - IC 0.03 gives 1.2–2.8, which is decisive.
- **2,000 stocks weekly:** IC 0.01 is negative net of costs. IC 0.02 gives 0.21–0.50. IC 0.03 gives 0.44–1.08.
- **8,000 events:** a gross 20 bp per event at icc 0.02 gives net Sharpe 0.54 and joint power 0.09. At icc 0.05, even 30 bp gross only reaches 0.71.
- **Breadth ceiling:** N_eff saturates at 1/ρ̄ (`breadth_curves.png`). For 200 perps at ρ 0.6, N_eff is 1.7.

## 6. The three cycle-4 candidates

The cycle-4 specs assume the three are registered as one batch (k=3, so α = 0.0167).

**(a) Binance funding long-short** (dev 3y, val 3.7y; `c4a_*`)
- Single-test MDE is Sharpe 1.21. Joint power at 0.7 is 0.03 (current gate) and 0.06 (proposed). **INCAPABLE**; 80% power at 0.7 would need about 48 years.
- The implied net Sharpe decides it:

| IC | N | ρ | Implied net Sharpe | Joint power (proposed gate) |
|---|---|---|---|---|
| 0.01 | any | any | about 0.2 | ≈ 0 |
| 0.02 | 100 | 0.2–0.4 | 0.84–1.10 | 0.10–0.24 |
| 0.03 | 100 | 0.2 | 1.96 | 0.83 |
| 0.03 | 100 | 0.4 | 1.49 | 0.54 |

- Only IC ≥ 0.03 at N ≥ 100 makes it decisive; the brief's literal breadth formula roughly halves these numbers.
- Weekly rebalancing is not better (0.04 joint at 0.7).

**(b) FINRA short-volume ratio, weekly** (dev 3.4y, val 4.7y)
- Joint power at 0.7 is 0.055 (current) and 0.09 (proposed). **INCAPABLE**.
- At 15 bp one-way costs and weekly signal autocorrelation 0.6, every IC in 0.01–0.02 is **negative net**: turnover of about 0.68 per leg costs roughly 40 bp/week against 20–30 bp of gross spread.
- Viable only with a smoothed signal (autocorrelation ≥ 0.9) and cheaper execution. IC 0.02, autocorrelation 0.95 and 5 bp gives net 0.83, joint power 0.16, and needs about 32 years for 80%.

**(c) Treasury auction surprises** (about 41/yr, 12y + 12.5y assumed split)
- deff 1.74 (clusters of about 3 auctions per week on one instrument, signed icc 0.3). About 1,004 events are worth about 576 independent ones.
- Joint power at 0.7 is 0.27 (current) and 0.49 (proposed): **MARGINAL**.
- MDE is about 14 bp net per event for a single test and about 21 bp for joint power under the proposed gate (event sd 1%).
- 20 bp gross per event at sd 0.7–1.0% passes with 0.75–0.98 probability under the proposed gate; 10 bp gross does not (0.08–0.42).

## 7. Proposed power-aware validation gate (not registered)

**Rule.** Validation passes if, on the validation window:
1. the HAC-t (or mean-centred block-bootstrap) one-sided p is below 0.05/k_val, where k_val is the number of candidates taken to validation together; and
2. the stress mean is above 0.

An economic floor on Ŝ is optional if registered; for these windows a 0.3 floor never binds.

**Size.** P(pass | S=0) ≤ 5%, and joint false-pass ≤ α_dev × 5% (0.25% for k=1). On a one-sided normal location family this test is uniformly most powerful at its size (Karlin–Rubin), so it maximises power at any alternative, including the winner's-curse-corrected dev estimate.

**Operating characteristics on tsy_month_end-like windows** (12 + 11.6y, D 1.4; `validation_gate_oc.csv` and `.png`):

| True S | Current 0.75 gate: P(val) / joint | Proposed (threshold 0.57): P(val) / joint | Proposed, k_val=3: joint | Val ≥ 0.5 × dev estimate and p < .05: joint |
|---|---|---|---|---|
| 0.00 | .015 / .0008 | .050 / .0025 | .0008 | .0025 |
| 0.05 (leak) | .022 / .0015 | .067 / .0045 | .0016 | .0045 |
| 0.3 | .10 / .022 | .22 / .048 | .023 | .048 |
| 0.5 | .24 / .10 | .42 / .18 | .11 | .18 |
| 0.7 | .44 / .29 | .65 / .42 | .30 | .41 |
| 1.0 | .76 / .69 | .89 / .80 | .70 | .77 |
| Years for 80% joint at 0.7 | ∞ | 48 | 58 | 51 |

**Trade-off.** False-pass rises from 0.08% to 0.25% per candidate, still far below 5%. Power at 0.5–0.7 rises by 13–20 points, and 80% joint power becomes reachable at all. The gate does not fix short windows: fx_hedge_rebal only moves from 0.21 to 0.24. A "structural leak" of Sharpe +0.05 passes 0.45% of the time; the N6 guards and the forward rule remain the defence against that.

## 8. Text for the "Power section" of `PLAN_TEMPLATE_v2.md`

```markdown
## Power (Protocol Amendment 2, N5 — required before registration)

**Design spec.** `research/power/examples/<name>.json` (validated against `research/power/design_schema.json`), sha256: `<…>`.
Every correlation parameter is stated explicitly, with its source (own-null sd, published estimate, or ASSUMPTION):
- time-series autocorrelation / long-run variance ratio D = … (source: …)
- cross-sectional / event / cross-market correlation ρ = … and cluster/concurrency structure … (source: …)
- skew / excess kurtosis of the tested series (required for carry / crash-prone books) = …
- stress-cost drag in Sharpe units = (stress − base cost per year) / vol = …
- batch k = … ⇒ α = 0.05/k = …

**Command.** `PYTHONPATH=. .venv/bin/python -m research.power.plan_check <spec> --mc 2000`
Report: `reports/power/<name>.json` (sha256 `<…>`).

| Quantity | Value |
|---|---|
| Raw observations (dev / val) | … / … |
| Effective observations after D and deff (dev / val) | … / … |
| SE of annualised Sharpe (dev / val) | … / … |
| MDE (80%, α) single test, all years — Sharpe and natural units | … |
| Joint dev+val power at true net Sharpe 0.3 / 0.5 / 0.7 / 1.0 | … |
| False-pass P(pass both \| S = 0); at S = +0.05 leak | … ; … |
| Years for 80% joint power at 0.7 | … |
| Implied net Sharpe at the plan's stated primitives (IC, bp/event, …) and its joint power | … |
| **Verdict** (DECISIVE / MARGINAL / INCAPABLE) | … |

**Interpretation, fixed before any return is seen.**
- If the verdict is MARGINAL or INCAPABLE (joint power at 0.7 < 50%), a validation FAIL will be recorded as "not certified (low power)", not as evidence of no edge (N5). The status is still FAIL and no re-specification is allowed.
- If INCAPABLE, state why the test is still worth running (e.g. it can only kill), or do not register it.
- Scenario grid over the uncertain primitives (IC, ρ, costs, N): attach the plan_check scenario table.
```

## 9. Limitations

- **Parameters and data.** Everything is analytic or synthetic. Family vols, D values and stress drags come from their own dev_results.json null sds or from null_lab2 sim_params. Correlations such as fx icc 0.4, PEAD icc 0.02, commodity pair ρ, the cycle-4 ICs and costs are labelled ASSUMPTION in each spec. The IEF and commodity D values are backed out of the reported null p or sd.
- **Normal approximation.** Ŝ is treated as normal and every gate leg as a function of one Ŝ, so estimated-vol and estimated-HAC noise is ignored. The Monte Carlo confirms this to within about 1–3 pp, except:
  - short-sample Newey-West with overlapping monthly data is oversized (+2.5 pp);
  - under rare crashes κ runs 3–5% above the asymptotic Opdyke value.
- **Long-short model.** The tilt model assumes Rademacher (two-block) loadings and Gaussian signals. Turnover ignores the tilt mixture and understates it by about 5% at ρ_s 0.5. Stress costs are a fixed drag.
- **Brief's formula.** Treating ρ̄ as the correlation among held bets (N/(1+(N−1)ρ̄)) is harsher than the structural model with moderate tilt, sometimes by half. Both are reported.
- **Sleeve screen.** The analytic ignores correlated inclusion and is 2–3 pp conservative.
- **Events.** Only fixed-dollar calendar-time portfolios are modelled; equal weight across active events is not. Event seasons are stylised.
- **Stationarity.** The same true Sharpe is assumed in dev and validation. `val_multiplier` exists for decay, but post-publication decay is not in the headline tables.
- **Verdict thresholds.** The 25% and 50% cut-offs and the N(0, 0.5²) prior are my proposals, not registered rules.
- **What this does not do.** It gives no evidence of any edge; it only tells you whether a test can answer its question.

Everything is in `/Users/rytty/CCP/quant_v7/`:
- `research/power/`: `core.py`, `designs.py`, `gates.py`, `report.py`, `simulate.py`, `verify.py`, `plan_check.py`, `specs.py`, `tables.py`, `design_schema.json`, `examples/*.json` (18 specs, including `c4a_binance_funding_ls_{daily,weekly}`, `c4b_finra_svr_weekly`, `c4c_tsy_auction_surprise`)
- `tests/test_power.py`
- `reports/power/`: one `.json` + `.txt` per spec, `retrospective.csv`, `prospective.csv`, `validation_gate_oc.csv`, `winners_curse.csv`, `mc_agreement.csv`, `breadth_curves.csv`, `breadth_curves.png`, `power_vs_years.png`, `validation_gate_oc.png`, `manifest.json`