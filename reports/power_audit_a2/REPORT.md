# Program A2: independent Monte Carlo audit of Amendment 2's dev gate and Amendment 3's validation gate (cycle 5)

*Written by the cycle-5 independent Monte Carlo reproducer A2 (built without reading research/power). Saved by the director session.*

**Verdict:** Amendment 3 controls false passes well on every process I tested, if the right return series is gated. Its power and false-pass numbers reproduce within 3 points of section 7. It is not fully sound, though. There are five concrete problems:
- The gate is blind to beta when a long-only book is gated on its raw returns.
- The block bootstrap is oversized on short, monthly, autocorrelated or crash-skewed series.
- The stress leg only bites once the cost drag is larger than the realised Sharpe.
- The 0.30 floor sits at the realistic post-decay effect size.
- The retrospective "→ DECISIVE" upgrades for insider and etf_hybrids assume a dev gate that a new k ≥ 4 family would no longer face.

A proposed Amendment 4 (not registered) is at the end.

**Where things are:**
- Code: `/Users/rytty/CCP/quant_v7/research/power_audit_a2/` (`engine.py`, `dgps.py`, `run_all.py`). It was written from scratch; I did not read or import `research/power`.
- Outputs: `/Users/rytty/CCP/quant_v7/reports/power_audit_a2/`:
  - `dgp_table.csv`, `family_rates.csv`, `power_vs_years.csv`, `vol_turnover.csv`, `bootstrap_coverage.csv`, `xs_breadth*.csv`, `replicate_cycle4.csv`, `meta.json`
  - three PNGs.
- Runtime was 14.6 minutes.

**Method:**
- **p-value:** a real one-sided, mean-centred circular block bootstrap, B = 999, block length = round(n^⅓).
- **Worlds:** 20,000 per stage for the main table and 10,000 for the grids. Families use up to 60,000 null families.
- **Windows:** 12 + 12 years unless stated.
- **Stress series:** net return minus an extra cost of 0.10 Sharpe units, unless stated. The amendments do not define the stress multiple, so this is my assumption.
- **Joint rate:** the dev and validation windows are independent, so joint = P_dev × P_val. I checked this against the direct MC joint and they agree.

## 1. False-pass and power by process and gate (k = 1, 12 + 12 years)

| Process | Frequency | Joint false-pass at S=0: new / old | Joint at S=0.05 (leak), new | Joint power at 0.3: new / old | Joint power at 0.7: new / old | One-stage size at p<.05 / p<.0125 |
|---|---|---|---|---|---|---|
| iid normal | daily | 0.18% / 0.02% | 0.36% | .060 / .013 | **.567 / .313** | .051 / .014 |
| iid normal | monthly | 0.21% / 0.02% | 0.41% | .064 / .014 | .571 / .317 | .058 / .017 |
| AR(1) φ=0.1 | daily | 0.25% / 0.05% | 0.42% | .057 / .020 | .489 / .302 | .051 / .013 |
| AR(1) φ=0.3 | daily | 0.28% / 0.15% | 0.50% | .039 / .025 | .320 / .255 | .054 / .016 |
| AR(1) φ=0.3 | monthly | **0.49%** / 0.20% | 0.76% | .053 / .029 | .372 / .273 | **.072 / .023** |
| t, 4 df | daily | 0.19% / 0.02% | 0.36% | .060 / .013 | .573 / .318 | .051 / .013 |
| t, 4 df | monthly | 0.20% / 0.02% | 0.37% | .068 / .016 | .589 / .339 | .056 / .015 |
| Carry with crashes (λ = 0.2/yr, −6σ jumps) | monthly | **0.36%** / 0.05% | 0.73% | .084 / .025 | .559 / .329 | **.071 / .024** |
| Carry with crashes | weekly | 0.35% / 0.06% | 0.69% | .084 / .025 | .562 / .335 | .072 / .027 |
| Stochastic volatility | daily | 0.16% / 0.01% | 0.36% | .071 / .017 | .590 / .352 | .048 / .010 |
| Long-short (stochastic vol plus residual beta) | weekly | 0.17% / 0.02% | 0.38% | .083 / .022 | .614 / .392 | .051 / .010 |
| **Long-only timing, raw returns** | daily | **6.45% / 1.44%** | 8.5% | .249 / .094 | .642 / .388 | **.279 / .116** |
| Long-only timing, active vs exposure-matched control | daily | 0.13% / 0.01% | 0.35% | .061 / .013 | .568 / .309 | .044 / .009 |
| Clustered events (icc 0.3), calendar-time portfolio | weekly | 0.18% / 0.02% | 0.41% | .061 / .014 | .586 / .324 | .054 / .013 |
| Same events, tested as independent | – | – | – | – | – | **.100** at nominal .05 |
| Cross-sectional quintiles, N=300, tilt 0.3, IC 0.02 (true S 0.61) | monthly | 0.20% (IC=0) | – | – | .430 at true S 0.61 | .059 |

Families (weekly iid, 12 + 12 years). k_val is the number of dev passers:

| k | ρ | Per-candidate false pass, new | Family-wise false pass: new / old | Family-wise at leak 0.05, new | Per-candidate power at 0.7, all true: new / old | Power of the one true member (others null) |
|---|---|---|---|---|---|---|
| 1 | – | 0.22% | 0.22% / 0.02% | 0.44% | .570 / .323 | – |
| 2 | 0 | 0.12% | 0.23% / 0.03% | 0.61% | .484 / .295 | .524 |
| 2 | 0.5 | 0.12% | 0.24% / 0.03% | 0.48% | .478 / .297 | .536 |
| 2 | 0.9 | 0.11% | 0.19% / 0.03% | 0.35% | .461 / .290 | .527 |
| 4 | 0 | 0.04% | 0.18% / 0.01% | 0.40% | .328 / .217 | .396 |
| 4 | 0.5 | 0.03% | 0.14% / 0.01% | 0.34% | .316 / .217 | .387 |
| 4 | 0.9 | 0.02% | 0.06% / 0.01% | 0.17% | .307 / .223 | .391 |

## 2. Discrepancies against the cycle-4 report

Section 7 reproduces. I used κ² = 1.4 via a daily AR(1) with φ = 1/6. Every cell of `validation_gate_oc` is within 1.3 points:
- Joint at S=0.7 is .298 on the current gate (report .29) and .432 on the proposed gate (report .42).
- With k_val = 3 it is .307 (report .30).
- The "val ≥ 0.5 × dev" variant gives .423 (report .41).
- Joint false pass at S=0 is 0.07% current (report 0.08%) and 0.25% proposed (report 0.25%).
- Years for 80% joint power at 0.7 are ∞ current and 48 total proposed. Both match.

Section 4 mostly reproduces. I backed each family's κ² out of the report's own P_val at 0.7. tsy, commodity_roll, fx_hedge and IEF−SHY are all within 2 points. Three discrepancies exceed 3 points:

| Item | Report | A2 | Gap | Cause |
|---|---|---|---|---|
| etf_hybrids, joint at 1.0 on the current gate | .75 | .688 | −6.2 pts | The report's P_dev (.74 → κ² 1.16) and P_val (.44 → κ² 1.28) imply different κ²; its model lets κ² depend on S. |
| etf_hybrids, joint at 0.7 on the proposed gate | .55 | .497 | −5.3 pts | Same cause. |
| **insider / etf_hybrids, "joint at 0.7 with proposed gate → DECISIVE"** | .51 / .55 | **.277 / .279** under the Amendment-2 dev gate | **−23 / −27 pts** | The report keeps the old flat 0.50 dev leg. A new family with k ≥ 4 faces 2.4/√T and p < .05/k, where P_dev at 0.7 falls from .73 to .41. Both would be **MARGINAL**, not DECISIVE. |

Smaller points:
- Amendment 3's "0.25% joint false pass" applies at κ² = 1.4. At κ² = 1 it is 0.16–0.18%, because the 1.8/√T floor binds.
- I did not reproduce PEAD or the multiasset screen, which are single-stage or screen designs.

## 3. Answers to questions 1–7

**Q1. False-pass rates for dev + new validation.**
- Per candidate: 0.22% at k=1, 0.12% at k=2 and 0.02–0.04% at k=4.
- Family-wise: 0.22%, 0.19–0.24% and 0.06–0.18%. It falls as correlation rises.
- At a structural leak of S = 0.05, family-wise false pass is 0.35–0.61%.
- On the worst processes that are gated correctly, joint false pass is 0.36–0.49%: monthly AR(0.3), and carry with crashes. At a 3 + 3-year monthly AR(0.3) window it reaches 0.86%.
- All of these are far below 5%.
- The one real failure is a long-only book gated on raw returns: 6.45%, driven by the market premium alone.

**Q2. Does the rule behave correctly under each process?** Yes for iid, t(4), stochastic vol, long-short, calendar-time events, exposure-matched long-only, and daily AR series with block ≈ n^⅓. The bootstrap p does under-cover in three cases:
- **Autocorrelation:** it is fine on daily data (size .054 at p<.05, .016 at p<.0125 for φ=0.3). It is oversized on monthly data: .066–.072 and .023, rising to .080 and .032 at 5 years. With b=1 (an iid bootstrap) it is badly oversized: .11 and .047.
- **Skew (carry with crashes):** .071–.093 at p<.05, and .024–.039 at p<.0125, which is 2–3× nominal. Skew also raises power at S=0.3 (.084 vs .060), so crash-skewed designs are favoured.
- **Events tested as independent:** the size doubles to .100.

**Q3. Does power grow with sample length?** Yes for the new gate, monotonically. At S=0.7 (iid monthly), joint power over 6 / 16 / 24 / 32 / 40 / 60 total years is .10 / .36 / .57 / .74 / .84 / .96. 80% is reached at about 36–37 total years (iid) and 48 (κ² 1.4), matching cycle 4.
- The old gate plateaus at about .38–.39 at S=0.7.
- At S=0.5 the old gate peaks near .09 and then falls.
- At S ≤ 0.3 the new gate also caps below 0.5 (.28 at 80 years), because the 0.30 floor binds. The old gate's pathology returns at realistic effect sizes.

**Q4. Is breadth being counted as independent?** Take IC 0.02 and N=300 with the signal carrying a persistent style tilt of 0.3:
- **Sharpe:** true Sharpe is 0.61, against 1.06 from the fundamental law.
- **Power:** true joint power is .43, against .95 naively.
- **Breadth curve:** with tilt 0.3, true Sharpe saturates at 0.69 at N=800, where the naive figure is 1.73. Without tilt, naive ≈ true.
- **The gate itself:** it is correct at IC=0, because it runs on the long-short time series (0.20%).
- **Pooled tests:** a pooled N×T OLS t-test rejects 18% (tilt 0.3) and 29% (tilt 0.6) under the null at nominal 5%.

Power must come from the true long-short Sharpe, never from N. This confirms Amendment 3's breadth statement.

**Q5. Is Sharpe 0.7 principled?** No, it is a convenience reference. A 58% post-publication decay applied to typical in-sample Sharpes of 0.5–0.7 gives 0.21–0.29, and the OSAP 2015+ graveyard mean is 0.23.
- **Joint power at realistic sizes:** on 12 + 12 years the new gate has .031 at S=0.23 and .06 at 0.30. 80% power is unreachable at any length while the floor is 0.30. At S=0.4 it needs 173 total years.
- **What passes:** with an N(0.23, 0.25²) prior on S, the expected pass rate is 10.5%. Among passers, E[S | pass] = 0.55 and P(S > 0.3 | pass) = 0.92.
- **What 0.7 describes:** the gate works as a large-effect detector. 0.7 is about 2.5–3× the realistic post-decay effect, so "power at 0.7" overstates what a typical new family can show.

**Q6. Does the protocol favour volatile or high-turnover designs?**
- **Pure volatility:** scaling returns ×5 gives identical pass rates, since every leg is scale-free.
- **Fat tails and stochastic vol:** no advantage (joint .57–.60 at 0.7, against .57 iid).
- **Noise from autocorrelation:** the new gate penalises it correctly. Power at 0.7 falls from .71 to .14 as κ² goes from 0.67 to 4. The old 0.75 gate rewarded noise: its validation false pass rose from 0.4% to 6.2%, and P_val at S=0.3 from .065 to .155. Residual noise-favouring now comes only from bootstrap under-coverage (Q2).
- **Crash skew:** favoured, with about 2× false pass and higher power at low S.
- **Turnover:** the stress leg, "stress mean > 0 on the point estimate", only binds once the stress drag is about as large as the realised net Sharpe (≈ 0.5 SR at 12 years). At net S=0.7, joint power across stress drag in Sharpe units:

  | Stress drag (SR units) | 0.05 | 0.3 | 0.5 | 0.7 | 1.0 | 1.5 |
  |---|---|---|---|---|---|---|
  | Joint power at net S=0.7 | .569 | .574 | .555 | .251 | .021 | .000 |

  - A design whose true stress Sharpe is +0.2 or +0.4 is not penalised at all.
  - A design with stress Sharpe 0 passes 25% of the time.
  - Under the null, a drag of 0.3 leaves false pass unchanged, because dev passers already have Ŝ ≥ 0.52.
  - So the penalty is a step function rather than proportional. It is adequate against clearly negative stress Sharpe (≤ 2% at −0.3) but weak near zero.
- **Dev gate at k ≥ 4:** 2.4/√T binds before the Bonferroni p-leg at κ² ≈ 1. Per-candidate dev power at 0.7 drops to .50 (from .67 at k=2) for little gain: family-wise false pass is already ≤ 0.18%.

**Q7.** Covered in section 2: section 7 agrees within 1.3 points; three section-4 items differ by more than 3 points.

## 4. Is Amendment 3 sound?

On size and length behaviour, yes. Its "uniformly most powerful" claim is overstated, since the gate has a floor, a stress leg and a bootstrap p. It needs targeted fixes.

**PROPOSED Amendment 4 (draft, not registered):**
- **A4.1 Gating series.** Any design with directional exposure gates in both dev and validation on its return net of an exposure-matched control. G2 is then a gate, not a report. Event designs gate on a calendar-time portfolio; event-level independent tests may not gate.
- **A4.2 Bootstrap validity.** The PLAN registers a block length of at least max(n^⅓, 2(1+ρ̂₁)/(1−ρ̂₁)). A block length of 1 is not allowed when |ρ̂₁| > 0.05. If a window has fewer than 180 observations, |skew| > 1, or ρ̂₁ > 0.2, the plan must show the p-test's simulated size on its own design spec. If the size exceeds 1.25α, the gating α is recalibrated to nominal size (in the cases above, roughly halving it).
- **A4.3 Stress leg.** In validation, the stress-cost Sharpe must be ≥ 0.30, the same economic floor as net. In dev, the stress mean must be > 0 as now. This replaces the current near-inactive sign test for turnover. I computed this rule's effect analytically, not by MC: at net 0.7 and drag 0.5, stress-leg pass falls from about .75 to .36 per stage.
- **A4.4 Power reference.** Joint power is reported at S = 0.25 (the post-decay prior), 0.5 and 0.7. The DECISIVE, MARGINAL and INCAPABLE bars keep 0.7, but the plan must state that 0.7 is a large-effect reference. It must also note that edges with S ≤ 0.30 cannot be certified at any length.
- **A4.5 k ≥ 4.** Replace 2.4/√T with 1.8/√T plus p < 0.05/k. Family-wise false pass stays ≤ 0.25% and per-candidate power at 0.7 rises by about 15 points. This is optional; the director decides.
- **A4.6 Record.** The retrospective "→ DECISIVE" labels for insider and etf_hybrids are withdrawn. Under the Amendment-2 dev gate plus the Amendment-3 validation gate they rate MARGINAL (about .28).

No existing files were edited. No commits, trades or changes to bot/ or forward reports were made, and only synthetic data was used.