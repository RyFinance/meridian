# Month-end index extension in non-Treasury bond sectors (rate-hedged): pre-registration

Status: DRAFT until registered. Written 2026-09-23 before any return of this design was computed.

## Novelty: mechanism-informed test

- `tsy_month_end` found TLT outperforming its exposure-matched control over the last 3 sessions of
  each month, in development (0.66) and validation (0.69). Its shift-null p was about 0.005 in both,
  but it narrowly failed the 0.75 validation gate.
- **This test asks whether the same forced-flow mechanism appears in OTHER bond indices after
  removing the Treasury rate move.** A pass would be independent support for the mechanism, not a
  replay of the Treasury effect.
- **It is explicitly mechanism-informed by the TLT result.** Validation for this design
  (2015–2026) shares calendar years with the TLT validation.

## Mechanism

Bloomberg US Corporate, MBS and TIPS indices also rebalance at month-end, when new issues enter and
index duration extends. Benchmarked managers buy the sector's longer bonds into the close of the
last session. That creates sector-specific month-end demand beyond Treasury duration.

## Rules

- **ETFs:** LQD (corporate IG), MBB (agency MBS; from 2007-03), TIP (TIPS; from 2003-12).
  yfinance adjusted closes.
- **Window:** the TLT M rule. Weight 1 is held at the closes of the 4th-, 3rd- and 2nd-to-last
  sessions of each month, earning the last 3 sessions.
- **Rate hedge (point in time).**
  - At each month's first session, regress each ETF's daily returns on IEF and SHY over the prior
    252 sessions (no intercept, clipped to [0, 2]).
  - The hedged window return is r_ETF − h_IEF r_IEF − h_SHY r_SHY, earned only on window days.
- **Book S:** the equal-weight average of the available sectors' hedged window returns. T-bills
  otherwise.
- **Costs:** base 3 bp, stress 9 bp per side on the ETF leg, plus 2 bp and 6 bp on hedge legs; 24
  round trips a year.

## Control and nulls

- **Primary statistic:** S is already rate-hedged. The comparison is an exposure-matched constant
  hedged position: the constant weight equal to S's average weight times the hedged daily return.
  The active return is S − that control.
- **Gating null:** 1,000 random circular shifts of the holding calendar (≥ 5 sessions), each
  compared with its own exposure-matched control.
- **Diagnostics:**
  - correlation of S's monthly window P&L with the TLT window return;
  - per-sector results;
  - quarter-end vs other months;
  - window-position placebos (3-session windows ending at sessions 3–15).

## Windows

- **Development:** 2003-01-02 → 2014-12-31. LQD from 2003, TIP from 2004-12 after warm-up, MBB from
  2008-03 after warm-up.
- **Validation (locked):** 2015-01-02 → 2026-08-31.

## Gates

**Development.** S is selected if all of these hold:
- active Sharpe ≥ 1.8/√T (T ≈ 12, so about 0.52);
- stress active mean > 0;
- circular-shift p < 0.05.

**Validation:** active Sharpe ≥ 0.75, stress active mean > 0, shift p < 0.05, bootstrap p < 0.05.

## Limits

- The regression hedge may leave residual rate exposure at month-end; the TLT correlation
  diagnostic shows this.
- Sector index-extension sizes are smaller than for Treasuries.
