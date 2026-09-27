# Structural-premium development gate calibration

`research/structural_null_calibration_20260923/calibrate.py` generated 3,000 independent **zero-mean after-cost** worlds per archetype, each eight years of daily observations. It applied the current 1.8/√T Sharpe threshold and the project's exact `BootstrapP` circular-block p algorithm (21 sessions, 3,000 resamples). A batch of three uses p < 0.05/3. The stress-cost condition is neutral in this synthetic exercise; real stress drag would reduce pass rates. There are no strategy prices or returns in these simulations.

| Archetype | Sharpe gate only | Full single p<.05 | Full batch-three p<.0167 | Any of three independent null siblings |
|---|---:|---:|---:|
| Rare-crash carry (zero-mean mixture) | 4.53% | 4.53% | **2.50% ± 0.29%** | **7.93% ± 0.49%** |
| Exposure-matched long-only | 3.80% | 3.80% | 1.77% ± 0.24% | 4.27% ± 0.37% |
| Heavy-tailed long-short | 4.13% | 4.13% | 2.23% ± 0.27% | 5.37% ± 0.41% |
| Mean-reverting relative value | 0% | 0% | 0% (upper 95% bound about 0.10%) | 0% |
| Persistent timing | 10.33% | 5.30% | 1.73% ± 0.24% | 5.90% ± 0.43% |
| Sparse event exposure | 3.43% | 3.43% | 1.50% ± 0.22% | 4.17% ± 0.36% |

**Finding:** the batch-three gate is around its nominal per-candidate size for most archetypes, but rare-crash carry is anti-conservative in these synthetic worlds: **7.93%** of three-candidate all-null families produce at least one false pass. Heavy-tailed long-short and persistent timing families are also near or above 5% within Monte Carlo error. The family calculation assumes independent siblings; actual siblings may share shocks. A positive carry test therefore needs a calibrated tail-aware null and family accounting. This is a diagnostic, **not** a retrospective change to any registered threshold or verdict. The structural-frontier Treasury result remains a fail under its registered p threshold.

Limits: the six processes are illustrations, not fitted replicas of particular markets; the original structural batch used 5,000 bootstrap resamples and included actual stress costs. No validation data were opened.
