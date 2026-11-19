# FROZEN rules (written before any step-2 (2024-01..2026-08-10) result was computed)

Selection used step-1 data only (MSTR RTH minutes 2020-08-12..2023-12-31). Dev = dates <= 2022-06-30 (451 days).
Pick rule: within each family, base fills, 3 bp/side, not flipped, dev n >= 50, highest dev t-stat.
Check (2022-07..2023-12) was printed in the same table but was NOT used for the pick.

Shared mechanics (both rules)
- Minute bars from 09:30 ET (index 0 = 09:30 bar). Stale minutes carry the last close.
- Trigger: the first minute m whose CLOSE is beyond the 09:30 open by X. Known at the close of bar m.
- Entry: open of bar m+1 (worst fill: high of bar m+1 for longs, low for shorts). No entry if m+1 >= exit minute.
- Exit: open of the exit bar (worst fill: low for longs, high for shorts), or the stop if hit first.
- Costs: 3 bp per side (6 bp round trip) on step 1. Step 2 uses 8 bp per side (3 + 5 extra slippage).
- Flip control = same trigger, same timing, side reversed.

## Rule DN (direction-neutral reversal), FROZEN
- Trigger: first minute with close <= open*(1-0.5%) (dip) OR close >= open*(1+0.5%) (rip). Either side.
- Side: dip -> LONG; rip -> SHORT (fade the move).
- Exit: 10:00 ET open, or stop at 1% from entry (checked on bars after entry, before exit).
- One trade per day maximum. Mon/Fri and all weekdays both reported.
- Step-1 dev (<=2022-06): n 444, mean +8.9 bp, t 1.14. Check (2022-07..2023-12): n 375, mean -10.4 bp, t -1.42.

## Rule BC (BTC-conditioned reversal), FROZEN
- BTC sign s = sign(BTC close 09:24 / close prev-weekday 15:59 - 1), known at 09:25 ET.
- Trigger: wait ONLY for the side against BTC: if s > 0 wait for close <= open*(1-1.0%);
  if s < 0 wait for close >= open*(1+1.0%). The first crossing of the other side is ignored (as in the prior rule).
- Side: s (trade in BTC's direction after the against-BTC move).
- Exit: 10:00 ET open. No stop.
- Step-1 dev (<=2022-06): n 245, mean +12.0 bp, t 0.875. Check: n 196, mean +12.0 bp, t 0.95.

## Flip controls for the frozen rules
- DN flip: same trigger, side = trigger direction (buy rips / short dips).
- BC flip: same trigger, side = -s (trade against BTC after the against-BTC move).

## Bug found in shares_mgmt/sim.py (affects its time-exit results)
- For time exits, sim_exit returns O[k] even when the entry e is after k. Those trades exit before they enter.
- Share of the prior 'with|PB1%|time10:30' dev mean (+37 bp) from invalid trades: 96 of 564 trades, mean +207 bp.
  Valid trades (entry before 10:30): n 468, mean +2.1 bp. Same pattern for 'against' (valid -2.9 bp) and 'conv' (valid +14.2 bp).
- The prior's 'with'/'against' symmetry (+37/+32) is therefore not evidence of a direction-neutral edge.
  This study uses only valid trades.
