# Round 6 "uk": ZB/ZN overnight move -> UK housebuilders at the London open (08:00 entry)

**Verdict: WEAK.** A gross directional effect shows in both splits for the housebuilder basket, but it is not clearly homebuilder-specific (placebo moves too in check), and it does not survive 20 bp round-trip costs in a CFD long/short. Long-only with 0.5% stamp duty is clearly negative.

## Setup (`analysis.py` builds `panel.pkl`, `sim.py` runs the grid, `extra.py` checks)
- Data: yfinance, frozen in `data/` by `fetch.py`. ZB=F/ZN=F 60m (730d) and 1d; UK names 60m (730d) and 1d. Window 2024-05-28..2026-10-16 (dev to 2025-06-30, check from 2025-07-01).
- Bars are start-labeled ET (futures) and London (UK). "Bar ending at or before T" = start floor(T, 1h) - 1h, exact label, no fallback. DST handled by converting London times to ET per date.
- Signals (sign d, zero-signal days skipped):
  - ZB_LON: ln(ZB close ending <= 08:00 London on D / ZB close ending <= 16:30 London on previous London session D'). Note ZB bars sit on the hour, so 16:30 London (11:30 ET) resolves to the 11:00 ET bar, i.e. the 16:00 London close.
  - ZN_LON: same with ZN=F.
  - ZB_US (simpler): ZB close ending <= 08:00 London on D / ZB close at 16:00 ET on the last US date before it.
- Entry: Open of the 08:00 London bar. Exits: close of 08:00 bar (x08 = 09:00), of 09:00 bar (x09 = 10:00), of 16:00 bar (x1630 = 16:30), daily close (x1d, daily open to close).
- Costs: 10 bp per side (20 bp round trip). Stamp duty 50 bp on purchases of UK-incorporated shares only (HB and LLOY). Placebo ETF/index assumed no stamp.
- Universe: HB = PSN, TW, BKG, BTRW, VTY, CRST, plus equal-weight basket (mean of names trading that day). Placebo = VMID.L, ^FTMC. Control = LLOY.L. BDEV.L returns no data from yfinance (excluded). BTRW.L 60m starts 2024-10-07.

## Variant count
- 3 signals x 4 exits x 10 cells (HB basket + 6 names + 2 placebos + 1 control) = 120 cells, each on dev and check, plus flip. Per-name t above 2 in dev is expected by chance for several cells, so only the basket and the pre-specified rule are interpreted.

## Basket results (gross bp, t | CFD long/short net bp, t | long-only net bp with stamp)
| Rule | Dev gross (t) | Check gross (t) | Dev CFD L/S net (t) | Check CFD L/S net (t) | Dev LO+stamp | Check LO+stamp |
|---|---|---|---|---|---|---|
| ZB_LON x1630 (pre-specified) | +23.0 (2.64) | +30.2 (3.15) | +3.0 (0.34) | +10.2 (1.07) | -56.8 | -56.1 |
| ZB_LON x09 | +10.3 (1.84) | +18.8 (2.77) | -9.7 (-1.72) | -1.2 (-0.17) | -57.6 | -59.3 |
| ZB_LON x1d | +22.2 (2.51) | +29.2 (2.98) | +2.2 (0.25) | +9.2 (0.94) | -61.2 | -57.8 |
| ZN_LON x1d (best dev gross t) | +27.0 (3.11) | +27.6 (2.87) | +7.0 (0.80) | +7.6 (0.79) | -57.2 | -61.0 |
| ZN_LON x1630 | +25.9 (3.02) | +27.5 (2.92) | +5.9 (0.69) | +7.5 (0.80) | -54.4 | -60.6 |
| ZB_US x1630 (simpler) | +13.7 (1.58) | +34.2 (3.67) | -6.3 (-0.72) | +14.2 (1.52) | -62.0 | -53.5 |

Longs-only without stamp (net of 20 bp) are also negative: ZB_LON x1630 dev -6.8, check -6.1 bp.

## Best rule, stated precisely
- Pre-specified: d = sign(ln(ZB 08:00 London bar close / ZB 11:00 ET bar close on the previous London session)). Buy the HB basket at the 08:00 London bar open if d=+1, short if d=-1, exit at the 16:00 bar close (16:30 London).
- Dev-selected on gross basket t: ZN_LON x1d. Check gross +27.6 bp (t 2.87), CFD net +7.6 bp (t 0.79).

## Controls
- **Flip**: reversing the sign gives about -gross minus 20 bp. Check, ZB_LON x1630: -30.2 gross, about -50 net. The direction is right.
- **Placebo** (gross, dev | check, ZB_LON x1630): FTMC +1.2 | +21.6 (t 5.1); VMID.L +1.8 | +14.6 (t 4.0). The UK mid-cap market also moves with the signal in check, so part of the basket's check edge is market beta.
- **Homebuilder minus FTMC** (gross): ZB_LON x1630 dev +21.8, check +8.6. ZN_LON x1d dev +27.6, check +5.4. The homebuilder-specific excess shrinks sharply in check.
- **Control LLOY** (bank, ZB_LON x1630): gross dev -7.0 (t -0.76), check +11.6 (t 1.17). No dev edge.
- **Mechanism**: correlation of the signal with the 08:00 gap is 0.07-0.23 across names, so the open already prices a small part of the move. Correlation with the 08:00-16:30 move is 0.06-0.16. Consistent with partial under-reaction, but weak.

## Single names (ZB_LON x1630 gross, dev | check, t)
- PSN 32.2 (3.16) | 20.7 (1.94); TW 21.2 (2.33) | 26.1 (2.68); BKG 20.0 (2.60) | 20.9 (2.07); BTRW 26.4 (2.22) | 33.5 (3.24); VTY 17.8 (1.18) | 22.7 (1.43); CRST 27.9 (1.76) | 58.2 (3.50).
- Every HB name has positive gross in both splits for this rule. Net of costs no name is clearly positive.

## Verdict and caveats
- WEAK. Gross basket edge of about 20-30 bp at 16:30 exit in both splits, but CFD L/S net is about 0 to +10 bp with t under 1.1, costs are assumed (not measured spreads), and FTMC/VMID show a similar gross move in check.
- Stamp duty kills long-only. Long-only and the 0.5% stamp leave about -55 bp per trade.
- Limits: two years of 60m data, BDEV missing, BTRW short history, CFD financing and borrow ignored. Zero-signal days (stale ZB bars) skipped.
- Not tradable as a standalone rule. If revisited, it needs a measured spread below 5 bp and a placebo-adjusted residual test.
