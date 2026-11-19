# Rebalancing autopilot — specification (cycle 9, item 3)

Deterministic, offline engine that turns (a chosen menu portfolio, a hand-edited holdings file, a snapshot-verified
price file) into a **human-readable** rebalancing report and a hashed paper-log entry. Research tool only.

**Hard constraints (enforced by code and tests):** no broker APIs, no credentials, no network calls anywhere in
`research/autopilot/` (no `requests`, `urllib`, `http`, `socket`, `ssl`, `ftplib`, `smtplib` imports; a test
blocks sockets while the engine runs); no order generation in any broker/FIX/CSV-import format — output is prose +
tables for a human, plus a JSON summary for the log; never writes to `reports/forward/registry.jsonl` (hard guard);
no cron/launchd/scheduler hooks. Nothing it prints is a recommendation to trade.

## 1. Supported configurations

| Config id | Exposures (fraction of NAV) |
|---|---|
| P3@1.0, P3@1.25, P3@1.5 | EQ 0.60·L, BOND 0.40·L |
| P4@1.0, P4@1.25, P4@1.5 | EQ 0.48·L, BOND 0.32·L, GOLD 0.10·L, TREND 0.10·L |
| P6a@1.0, P6a@1.25 | EQ 1.00·L, TREND 0.50·L |

Anything else is refused.

## 2. ETF universe (cycle-8 tickers; exposures per unit of NAV held)

| Ticker | Ccy | EQ | BOND | GOLD | TREND | Notes |
|---|---|---|---|---|---|---|
| XEQT.TO | CAD | 1.0 | | | | global one-ticket equity |
| ZAG.TO | CAD | | 1.0 | | | Canadian aggregate bonds |
| ZGLD.TO | CAD | | | 1.0 | | gold bullion (CAD units) |
| DBMF | USD | | | | 1.0 | managed-futures replication |
| RSSB | USD | 1.0 | 1.0 | | | stacked global equity + US Treasuries |
| RSST | USD | 1.0 | | | 1.0 | stacked US equity + managed futures |
| GDE | USD | 0.9 | | 0.9 | | stacked US equity + gold (kept in the universe; not used by default recipes) |
| SSO | USD | 2.0 | | | | 2x daily-reset S&P 500 (LETF) |
| CASH.TO | CAD | | | | | cash buffer vehicle (or broker cash) |

## 3. Recipes (fixed; weights of invested capital, before the cash buffer)

Account types: `tfsa`, `rrsp`, `nonreg_cash` (no borrowing — stacked recipe), `nonreg_margin` (borrowing allowed —
unlevered sleeves × L with a margin loan of (L − 1) × NAV). TFSA and RRSP can never borrow or short.

| Config | Stacked recipe (tfsa / rrsp / nonreg_cash) | Margin recipe (nonreg_margin) |
|---|---|---|
| P3@1.0 | XEQT .60, ZAG .40 | same (no loan) |
| P3@1.25 | RSSB .25, XEQT .50, ZAG .25 | XEQT .75, ZAG .50, loan .25 |
| P3@1.5 | RSSB .50, XEQT .40, ZAG .10 | XEQT .90, ZAG .60, loan .50 |
| P4@1.0 | XEQT .48, ZAG .32, ZGLD .10, DBMF .10 | same (no loan) |
| P4@1.25 | RSSB .125, RSST .125, ZGLD .125, ZAG .275, XEQT .35 | XEQT .60, ZAG .40, ZGLD .125, DBMF .125, loan .25 |
| P4@1.5 | RSSB .35, RSST .15, ZGLD .15, ZAG .13, XEQT .22 | XEQT .72, ZAG .48, ZGLD .15, DBMF .15, loan .50 |
| P6a@1.0 | RSST .50, XEQT .50 | same (no loan) |
| P6a@1.25 | RSST .625, SSO .25, XEQT .125 (**uses a 2x LETF**) | XEQT .625, RSST .625, loan .25 |

A unit test checks every recipe reproduces its config's exposures exactly (stacked: Σ weights = 1; margin:
Σ weights = L). RSST/GDE/SSO equity is US-only; RSSB bonds are US Treasuries — reports say so.

## 4. Declared parameters

| Parameter | Value |
|---|---|
| Cash buffer | 1.0% of NAV (targets = 0.99 × recipe weights); TFSA/RRSP/cash accounts may never go below 0 cash |
| Drift band (per position) | trade if abs drift > 5.0 pp, or relative drift > 25% of target **and** abs drift > 1.0 pp |
| Margin accounts | also trade if actual leverage (assets / equity) differs from target by > 0.10 |
| Calendar check | at quarter-end reports (Mar, Jun, Sep, Dec): rebalance to target if any abs drift > 1.0 pp |
| When triggered | full rebalance of all positions to target; sells before buys; whole shares only; buys rounded down so cash never goes negative; skip trades < CAD 100 |
| FX | USD needed for USD-listed ETFs: broker conversion cost 0.10% (declared); the report notes the Norbert's-gambit option (DLR.TO/DLR-U.TO, two commissions + spread, ~1–3 days) for large conversions |
| Trading cost estimate | commission CAD 0 per trade (configurable) + half-spread: 0.05% XEQT/ZAG/CASH.TO, 0.03% SSO, 0.10% ZGLD/DBMF/RSSB/RSST/GDE |
| Freshness | price as-of and holdings as-of must be ≤ 5 calendar days before the report date and not after it |
| Leverage cap | effective gross exposure / NAV ≤ config target gross + 0.15; margin accounts: equity / assets ≥ 40% after trades |
| Max single position | 65% of NAV (SSO ≤ 30%) after trades; **except** diversified one-ticket funds XEQT.TO and ZAG.TO, whose cap is their recipe target + 5 pp (change 2026-09-29: the P3@1.25/P3@1.5/P4@1.5 margin recipes target XEQT above 65% by construction, so the flat cap made them unrunnable) |
| Drawdown alerts | on unit value vs its running peak (paper log): INFO at ≥ 50% of the owner's tolerance, WARNING at ≥ 75%, BREACH at ≥ 100%. Alerts never trigger automatic de-risking; the owner decides |
| Owner tolerance | set per config file (25, 35 or 50%) |

## 5. Refusals (no trades are emitted; the report explains why)

Any of: price snapshot fails `research.data_snapshot.verify` (missing/corrupt object, manifest mismatch); price or
holdings file stale/future-dated; a held or target ticker without a price; missing USD/CAD rate; holdings file
unparsable or containing unknown tickers/negative shares; account constraint violated (margin/short in
TFSA/RRSP/cash accounts; negative cash after trades); unsupported config; post-trade leverage cap, equity/assets
floor or position cap breached.

## 6. Inputs and outputs

- **Config** (JSON): config id, account type, owner tolerance, optional overrides of the declared parameters
  (overrides are printed in the report).
- **Holdings file** (CSV or JSON the owner edits): as-of date, positions (ticker, shares), cash CAD, cash USD,
  margin loan CAD (margin accounts), net external flow CAD since the last report (for unit accounting).
- **Prices:** a `research.data_snapshot` store + version containing a price CSV (date, ticker, close, currency)
  and USDCAD; the engine verifies it and records the manifest hash.
- **Outputs:** `report_<date>_<config>.md` (targets, current weights, drift, band decision, proposed trades with
  share counts and estimated costs, FX needed, current drawdown vs tolerance, checks passed/failed); a JSON summary;
  one appended paper-log line (hash-chained: `prev_hash`, `entry_hash` = SHA-256 of canonical JSON) in a separate
  log (default `reports/autopilot/paper_log.jsonl`), never the forward research registry.
- **Determinism:** identical inputs → byte-identical report, JSON and log entry (no wall-clock time in outputs; the
  report date is an input).

## 7. Historical replay (descriptive)

Monthly replay 1985-01..2026-05 per config × account type with synthetic ETF total-return prices built from the
frozen cycle-8 sleeves (snapshot `cycle8_v1`; SSO from the cycle-8 daily-reset simulation), start CAD 100,000
(and CAD 25,000 to show rounding), trades filled at month-end synthetic prices with the cost model, margin interest
at the cycle-8 margin rate. Output per year: rebalance events (band vs calendar), trades, turnover, estimated costs,
FX converted, alerts; plus replay CAGR vs cycle 8's ideal monthly-rebalanced series.
