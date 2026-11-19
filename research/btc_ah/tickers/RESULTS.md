# BTC-linked tickers: does a slower / less efficient name react to BTC's 16:00→09:25 ET move after the open?

**Verdict: NONE for BTC direction. WEAK at best for an opening-gap reversal in two miners (HUT, WULF).** Neither is a BTC-timing edge. Full table: `variants_all.csv`. Regressions: `regressions.csv`. Per-year: `per_year_all.csv`.

**Holdout disclosure:** the BTC 1m file and the first yfinance pulls were loaded in full before filtering, so bars after 2026-08-10 sat in process memory briefly. Nothing from them was printed, computed on, or saved; every cached file and every result stops at 2026-08-10. The lead should decide whether that counts as a breach.

## Scope
- Tickers: MARA, RIOT, CLSK, HUT, CIFR, WULF, IREN, COIN, HOOD, BTBT, IBIT, BITO, BITX, MSTU, MSTX (15). MSTR is a benchmark only.
- No data from yfinance: BITF (delisted or renamed) and SMLR. Both dropped.
- Rules (4): BTC_follow, BTC_fade, Res_follow, Res_fade (residual gap = gap − β·BTC, β from dev). Each rule is tested at two exits: close, and 09:30 open → 10:30 (first hour, from yfinance 60m).
- Variants: 15 × 4 × 2 = 120. Dev/check t-stats are listed for each.
- Costs: 3 bp per side; 10 bp per side when the raw open is under $5. Round trip = 2 × side.

## Protocol choices (deviations to check)
1. BTC move = close of last 1m bar before 16:00 ET (prior day) → close of last bar before 09:25 ET (no look-ahead). Calendar = MSTR trading days.
2. Splits and dividends handled via adj-close factor on O/H/L/C.
3. Gap beta is estimated on dev rows from 2020-08-11 onward. Pre-2020 gaps do not track BTC (MSTR beta is about 0 before 2020 and about 1.0-1.3 after 2022). Using all dev rows instead would dilute β.
4. Dev = date ≤ 2022-06-30. Tickers with under about 2 years of history before the cut (CIFR, IREN, COIN, HOOD, IBIT, BITO, BITX, MSTU, MSTX) use the first half of their sample as dev.
5. First-hour test: dev = first half of the 60m sample (2024-10-21 to about 2025-09), check = second half.
6. Long-history names include pre-pivot years (HUT 2018-20, WULF pre-2022, RIOT and CLSK pre-2020) when BTC was not their business. A BTC-era sensitivity (dev from 2020-08-11, halves for short names) is in `variants_all_era.csv`. The top names persist but weaken: HUT Res_fade dev t 4.15 (main 5.84), WULF Res_fade 2.63 (3.87). MSTU first-hour BTC_fade is unchanged.

## Multiple testing
- 120 variants. Dev |t|>2: 19. Dev t>2: 6. Check |t|>2: 15. Check t>2: 4. Check t>3.5: 1 (WULF Res_fade).
- Of the 6 dev t>2 rules, only 3 keep a positive check t: HUT, WULF, and MARA Res_fade (check t 0.52). 40 of 120 variants have positive check net, which is about chance.

## Top 3 by dev t (close and first-hour)

| Rule (exit) | Dev n | Dev net bp | Dev t | Check n | Check net bp | Check t | Check win | Avg win / loss bp (check) | Flip (mirror) check net bp, t | Drift (uncond. OC) dev / chk bp |
|---|---|---|---|---|---|---|---|---|---|---|
| HUT Res_fade (close) | 1013 | +110.4 | 5.84 | 984 | +44.9 | 2.44 | 0.53 | +466 / −423 | Res_follow −57, t −3.12 | −55 / +15 |
| WULF Res_fade (close) | 1149 | +55.6 | 3.87 | 984 | +86.7 | 3.92 | 0.53 | +569 / −461 | Res_follow −117, t −5.30 | −15 / +6 |
| MSTU BTC_fade (first hour) | 213 | +78.4 | 2.39 | 213 | −83.0 | −2.50 | 0.42 | +340 / −393 | BTC_follow +71, t +2.14 | −17 / −47 |

- **HUT and WULF**: the rule passes check, but for WULF β ≈ 0.08 in dev, so Res_fade is essentially a raw opening-gap fade (raw gap fade check +73 bp, t 3.2). For HUT, the gap beta is 0.7-1.3 from 2019, so Res_fade is a BTC-adjusted fade.
- **MSTU first hour**: direction flipped between dev and check. The rule fails. MSTX is the same underlying (2× MSTR), and it reproduces the same flip.
- Neither top rule is a BTC-speed effect. HUT Res_fade is also positive in 2018–2019 (+44, +70 bp per trade), before HUT's BTC pivot.

## Per-year, best rule (HUT Res_fade, close; all years, dev and check combined)

| Year | n | Mean net bp | t | Win |
|---|---|---|---|---|
| 2018 | 180 | +44 | 1.79 | 0.34 |
| 2019 | 252 | +70 | 2.35 | 0.52 |
| 2020 | 205 | +230 | 4.38 | 0.61 |
| 2021 | 252 | +105 | 2.31 | 0.59 |
| 2022 | 251 | +80 | 2.23 | 0.54 |
| 2023 | 249 | +49 | 1.28 | 0.53 |
| 2024 | 208 | +77 | 1.82 | 0.56 |
| 2025 | 249 | +68 | 1.92 | 0.53 |
| 2026 YTD | 151 | −58 | −1.44 | 0.49 |

WULF Res_fade per year: positive 2018–2025 (+32 to +169 bp), −6 bp in 2026 YTD.
## Regressions (open→close on BTC move and residual gap, `regressions.csv`)
- The residual-gap coefficient is negative in most names: CLSK check −0.34 (t −4.1), WULF −0.28 (t −4.8), MSTR check −0.27 (t −2.7), BTBT check −0.23 (t −2.7). Opening gaps reverse intraday in this group. BTC's own coefficient is unstable (IREN +2.0 in dev, −2.7 in check).

## Verdict
- BTC direction at the open or in the first hour (BTC_follow / BTC_fade): no tradable edge. Dev and check disagree in sign for MSTU, MSTX (first hour), HOOD (first hour), and IREN (close, BTC_follow). No BTC-direction rule clears a Bonferroni threshold (about t 3.5 for 120 tests) in both halves.
- Residual gap fade: WULF Res_fade (dev t 3.87, check t 3.92) is the only rule above a Bonferroni threshold on both halves. It is essentially a raw opening-gap fade, so it is a generic reversal and not BTC-specific. HUT Res_fade (check t 2.44) is weaker and also shows up in pre-BTC years. Dev is dominated by pre-BTC history for these names.
- Costs: HUT and WULF clear the 6–20 bp round-trip costs, but neither is confirmed out of sample. The sealed window is unused.
