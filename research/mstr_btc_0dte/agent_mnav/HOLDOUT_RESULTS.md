# mNAV trend sealed validation result (2023-01-03 .. 2026-08-10): FAILED as registered

Plan and gates: `HOLDOUT_PLAN.md` (registered 2026-10-17T00:09:50 PT, before any sealed statistic).
Runner: `holdout_research.py` (crash-fix amendment registered before the successful run). Outputs:
`HOLDOUT_RESULTS.json`, `HOLDOUT_RESULTS_TABLE.txt`, `holdout_run.log`.

## Numbers (903 sessions; 43 BTC-16:00 gap sessions handled by the frozen stance-carry policy)

| | SR base | SR stress | total net | CAGR | maxDD | time long | entries |
|---|---|---|---|---|---|---|---|
| **M1** (10d mom + 50d SMA) | **1.148** | 1.138 | +534.2% | +67.0% | **−47.0%** | 0.36 | 37 |
| M2 (20d mom + 50d SMA) | 0.938 | 0.929 | +316.1% | +48.6% | −50.6% | 0.44 | 34 |
| M3 (M2 + BTC 20d) | 1.078 | 1.068 | +392.5% | +55.7% | −44.0% | 0.31 | 32 |
| Benchmark MSTR B&H | 1.046 | 1.046 | +582.3% | +70.5% | **−84.5%** | 1.00 | — |

Per-year net: M1 {2023 +67.6%, 2024 +103.0%, 2025 **+59.2%**, 2026 **+17.1%**};
B&H {2023 +363.3%, 2024 +369.7%, 2025 **−50.7%**, 2026 **−36.4%**}.

Bootstrap (stationary, 21-session blocks, 2,000 draws, seed 20260817): M1 SR diff point **+0.102**,
P(D>0) = **0.592**, 5–95% interval **[−0.602, +0.871]**.

## Gate outcomes (as registered)

- G1 base Sharpe > B&H **and** P ≥ 0.95: Sharpe higher (1.148 vs 1.046) but **P = 0.592 → ✗**
- G2 stress Sharpe > B&H **and** P ≥ 0.90: **✗** (P = 0.581)
- G3 M1 net total return > 0: **✓** (+534%)
- **Verdict: FAIL.** M2/M3 corroboration also fails the same bars (P 0.39 / 0.51).

## Honest reading

The pre-registered gate is not met, so there is no promotion. The failure mode is power, not sign:
the plan's own power disclosure said a 0.1–0.5 true Sharpe edge would rarely clear P ≥ 0.95 in
3.6 years, and that is exactly what happened (point +0.10, interval straddling zero widely).
What the sealed window does show, descriptively:

- M1 kept up with buy-and-hold's total return (+534% vs +582%) while holding MSTR only **36% of
  sessions**, and with **~half the drawdown** (−47% vs −84.5%).
- The 2025–2026 MSTR bear (B&H −50.7% and −36.4%) is where the trend filter earned its keep
  (M1 +59.2%, +17.1%).
- Costs are immaterial to the outcome (stress SR 1.14; the band is wide, the costs are not).
- No single-year disaster (all four years positive), unlike the failed short-vol family.

This is the first candidate in the MSTR workstream whose *risk profile* beats buy-and-hold in-sample
of the holdout, but it is **not** statistically certified. The proxy also drifts within quarters
(share counts update only at 10-Q/10-K), and one bull/bear cycle is one regime sample.

## Outcome per plan

Recorded as FAIL; no re-runs on this window; nothing promoted to capital. A prospective forward
paper test is registered separately (`FORWARD_PLAN_M1.md`) purely as cheap monitoring — it cannot
convert this result into a validation and commits no capital.
