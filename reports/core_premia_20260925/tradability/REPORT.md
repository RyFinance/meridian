# Core Premia Book — Canadian Retail Tradability Audit

*Written by the tradability agent (2026-09-26). Saved by the director session. Not financial advice.*

**Not financial, tax, or investment advice.** Synthetic feasibility/cost arithmetic only — no strategy returns, no backtests. Code in `research/core_premia_data/tradability/` (`data_tables.py`, `run_audit.py`), outputs in `reports/core_premia_20260925/tradability/` (`etf_universe.csv`, `futures_specs.csv`, `rounding_error.csv`, `costs.json`). No commits made; `bot/`, `reports/forward/`, cron/launchd untouched.

## 1. ETF universe (37 rows in `etf_universe.csv`)
- **Equity index**: solid US (IVV/VTI), Canada (XIU.TO), Japan (EWJ), EM (EEM) coverage — mega/large AUM, ~1-2bp spreads. UK/Germany/Eurozone/Australia (EWU/EWG/EZU/EWA) are mid-AUM, thinner (~6bp est.) borrow.
- **Government bonds**: full US curve (SHY/IEF/TLT) and Canada (XSB/XGB/XLB.TO) covered. **Gap**: no liquid US/TSX-listed pure UK Gilt, Eurozone govt, Japan JGB, or Australia govt-bond ETF reachable from a standard IBKR Canada account — these markets are effectively futures-only or UCITS-access-only for retail.
- **Currency (Invesco CurrencyShares)**: FXE/FXY/FXB/FXA/FXC/FXF confirmed live. **FXS (SEK) confirmed closed/liquidated 2020-05-22** (Invesco press release Dec 2019). FXCH (CNY) shows as closed in issuer history — flagged for direct re-verification with Invesco before relying on it.
- **Commodities**: GLD/IAU/SLV/DBC covered well; USO/UNG are futures-roll vehicles with material contango/decay — poor buy-and-hold trend proxies, noted explicitly.
- Shortability marked qualitatively (no live IBKR HTB query was run — treat as indicative, re-check before any real position).

## 2. Futures specs (23 rows in `futures_specs.csv`)
CME micro equity (MES/MNQ/M2K/MYM), CME micro Treasury **yield** futures (2YY/10Y/30Y — cash-settled on yield, BPV $10/bp, **not** notional-comparable to price-based bonds), CME micro FX (M6E/M6A/M6B/MCD, plus **M6J is the correct JPY ticker, not "MJY"**), COMEX/NYMEX micro metals/energy (MGC/SIL/MCL, nat-gas ticker flagged for direct confirmation), Eurex Mini-DAX/EURO STOXX, and Montreal Exchange CGB/SXF/SXM. **Key gap**: CME has no micro *price-based* Treasury note/bond future — the smallest price-based US bond exposure is a standard ZN contract (~$100k+ face), a binding constraint used in the rounding-error test below.

## 3. Contract-rounding error (`rounding_error.csv`)
Equal-risk-per-market sizing (1/√N uncorrelated risk-parity convention, target 10% book vol, vols: equity 18%/bonds 7%/FX 8%/commodities 25%):

| Account | Fraction of buckets unholdable | Mean abs. risk deviation |
|---|---|---|
| CAD 25,000 | **100%** | 100% |
| CAD 100,000 | **75%** | 81% |
| CAD 250,000 | **42%** | 68% |

At CAD 25k, even a single micro contract in any market blows the per-market risk budget by several multiples — the account cannot run a 40-60 market book at all without concentrating risk in far fewer markets. At CAD 250k, bond exposure (forced into a full-size ZN, no micro price future) remains unholdable at target risk in nearly every scenario; FX and equity buckets become marginally workable.

## 4. CAD/USD conversion costs (`costs.json`)
Norbert's Gambit (DLR/DLR.U): ~0.15% all-in. IBKR direct FX conversion: ~0.03% (cheapest, if already an IBKR client). Bank counter conversion: ~2.5-3%. Every USD-listed ETF/future also leaves latent unhedged USD exposure layered on top of the book's own FX trend/carry bets.

## 5. Account types
- **TFSA**: no margin, no short selling, futures not a qualified investment — 50% penalty tax on FMV if held (CRA Folio S3-F10-C1/C2).
- **RRSP**: same futures/margin restriction as TFSA, **but** gets the Canada-US treaty withholding exemption on US dividends (Article XXI) that TFSA does not — RRSP is the tax-preferred wrapper for a long-only US ETF sleeve; TFSA is not.
- A long/flat ETF-only variant is registrable; the futures/short-selling sleeve requires a **separate non-registered margin account**.
- Futures/short margin accounts need CIRO-approved futures trading application, KYC, risk disclosures (CIRO Rule 5790 "greatest of" margin methodology); broker-set minimums apply (not an IIROC/CIRO-mandated dollar minimum).

## 6. Taxes (not advice)
Futures gains/losses default to capital treatment (s.9/39, with s.39(4) election to elect capital treatment consistently across all futures); personal FX gains are capital with a CAD 200 de minimis exemption. **A systematic, monthly-or-faster-rebalanced 40-60-market futures book is a plausible candidate for CRA business-income recharacterization** (fully taxable, not 50%-inclusion capital gains) — this is facts-and-circumstances, not guaranteed either way. Get a professional opinion.

## Blunt verdict by account size
- **CAD 25,000**: Not implementable as a diversified 40-60 market futures book. Even all-micro contracts blow the risk budget everywhere. Only a highly concentrated (~5-10 market) or ETF-only long/flat variant is realistic here.
- **CAD 100,000**: Still broadly infeasible for full diversification (75% of bucket/scenario combinations unholdable); workable only with a reduced market set and acceptance of large risk-budget deviations, concentrated mostly in FX and equity micros.
- **CAD 250,000**: Closest to viable but still compromised — bond-market risk is structurally hard to size correctly (no micro price-based Treasury future), and ~42% of bucket-scenarios remain unholdable at target risk. A genuine 40-60-market equal-risk trend/carry futures book realistically needs a substantially larger account than CAD 250k, or a redesign (fewer markets, unequal risk weights, ETF proxies for illiquid buckets) to be implementable at retail scale.

This is not financial advice — verify all figures (spreads, AUM, borrow, fees, symbols flagged "verify") directly with issuers/exchanges/IBKR before any real allocation.