# Protocol Amendment 6 — PROPOSAL: drawdown tolerances are evaluated on daily paths

**Status: PROPOSAL (cycle 9, item 4). Not in force until the owner registers it.** It re-grades nothing: cycle 8's
registered answers stand as registered.

## Why

Cycle 8 scored drawdown tolerance on month-end bootstrap paths. Its hostile audit found that both P6a answers had
already breached their tolerance on the **daily** historical path (P6a @ 1.0x: 37.8% vs 35%; P6a @ 1.5x: 53.7% vs
50%) while passing the month-end rule. Month-end sampling hides intramonth troughs (1987-10, 2008-10, 2020-03), so it
understates the drawdown an investor actually lives through — and the one a broker's margin clerk sees.

## Rules (proposed)

1. **Daily evaluation.** Any drawdown tolerance, drawdown probability or drawdown-based eligibility is computed on
   daily paths: the historical daily path, and bootstrap paths that carry each resampled period's full daily path
   (e.g. block-bootstrap months with their reconstructed daily returns). Month-end figures may be shown alongside,
   never instead.
2. **Historical-breach flag.** Any answer or recommendation-like output whose **historical daily path** breached the
   tolerance is flagged **"BREACHED IN HISTORY"** in the headline table, regardless of its simulated breach
   probability. The flag cannot be removed by a favourable bootstrap. Reports must also name the best eligible item
   without the flag.
3. **Disclosure of interpolation.** Where a sleeve has no daily data and its daily path is interpolated, the report
   states which sleeves and years, because interpolation understates intramonth drawdowns.
4. **Margin realism.** Leverage studies monitor maintenance margin on the same daily paths used for rule 1.

## Scope

Applies to experiments registered after the owner records this proposal's hash. Cycle 8b (cycle 9, item 2) already
implements rules 1–2 by its own preregistration (`research/cycle9/FRAMEWORK.md` C2, C4).
