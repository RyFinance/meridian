"""
Tradability audit for a Canadian retail investor implementing a Core Premia
Book (trend + carry across ~40-60 equity index / gov bond / FX / commodity
markets).

This script writes ONLY reference/feasibility artifacts:
  - etf_universe.csv     : ETF universe table (task 1)
  - futures_specs.csv    : micro/mini futures contract specs (task 2)
  - rounding_error.csv   : synthetic contract-rounding arithmetic (task 3)
  - costs.json           : CAD/USD conversion costs + account-type + tax notes
                            (tasks 4-6)

NO strategy returns, NO backtests, NO signals are computed or written here.
Run with:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python \
    research/core_premia_data/tradability/run_audit.py
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from data_tables import (  # noqa: E402
    ETF_UNIVERSE, FUTURES_SPECS, ACCOUNT_FACTS, TAX_NOTE, AUM_CLASS_LEGEND,
)

OUT_DIR = "/Users/rytty/CCP/quant_v7/reports/core_premia_20260925/tradability"
os.makedirs(OUT_DIR, exist_ok=True)


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Task 1: ETF universe CSV
# ---------------------------------------------------------------------------
etf_fields = ["bucket", "country", "ticker", "listing", "inception", "aum_class",
              "expense_ratio", "spread_bps", "shortable", "cad_hedged_alt", "source"]
write_csv(os.path.join(OUT_DIR, "etf_universe.csv"), ETF_UNIVERSE, etf_fields)

# ---------------------------------------------------------------------------
# Task 2: futures specs CSV
# ---------------------------------------------------------------------------
fut_fields = ["exchange", "symbol", "name", "asset_class", "multiplier", "ref_price",
              "tick", "tick_value", "notional_usd", "ibkr_commission_usd", "exch_fee_usd", "source"]
write_csv(os.path.join(OUT_DIR, "futures_specs.csv"), FUTURES_SPECS, fut_fields)

# ---------------------------------------------------------------------------
# Task 3: contract-rounding error arithmetic (SYNTHETIC ARITHMETIC ONLY)
# ---------------------------------------------------------------------------
# Methodology:
#   - Equal risk-per-market allocation across N markets (N = 40, 50, 60) for a
#     book targeting `target_vol` annualized portfolio vol.
#   - Standard risk-parity/trend-book convention: assume the N markets'
#     positions are approximately uncorrelated at the position-sizing stage
#     (correlation is what the trend/carry signals + diversification are
#     supposed to exploit, not something to presume away the sizing problem).
#     Under the uncorrelated assumption, if every market contributes equal
#     dollar-vol `v`, portfolio variance = N * v^2, so portfolio vol = v *
#     sqrt(N). Setting portfolio vol = target_vol * account_size gives:
#         desired_dollar_vol_per_market (v) = target_vol / sqrt(N) * account_size
#         ideal_notional = v / market_ann_vol
#     This 1/sqrt(N) convention is the standard "equal risk contribution,
#     uncorrelated" sizing rule; it is materially less punishing than a naive
#     1/N split and is the fairer test of contract-rounding capacity.
#   - smallest_contract_notional is drawn from the FUTURES_SPECS table (the
#     cheapest micro/mini instrument available for that asset class, in USD).
#   - contracts_held = round(ideal_notional / smallest_contract_notional)
#   - achieved_notional = contracts_held * smallest_contract_notional
#   - rounding_error = achieved_notional / ideal_notional - 1
#   - a market is "unholdable" if contracts_held == 0 (rounds down to zero
#     because even one micro contract's risk exceeds the ideal allocation
#     several-fold, i.e. ideal_notional < 0.5 * smallest_contract_notional).
#
# Approximate market vols supplied by the task: equity 18%, bonds(10y) 7%,
# FX 8%, commodities 25%. This is arithmetic on contract sizes, not a
# backtest of strategy returns.

TARGET_VOL = 0.10  # 10% annualized book vol target
MARKET_VOL = {"equity_index": 0.18, "gov_bond": 0.07, "fx": 0.08, "commodity": 0.25}
BUCKET_MIX = {"equity_index": 0.30, "gov_bond": 0.30, "fx": 0.20, "commodity": 0.20}  # illustrative diversified mix

# cheapest USD-notional micro instrument per asset class, pulled from FUTURES_SPECS
# (manually curated: MES for equity, CGB-scale-down not available so we use a
#  synthetic "smallest govt bond exposure" via 2YY-style yield future BPV
#  reasoning is not comparable in notional terms, so for bonds we instead use
#  a duration-adjusted price-future proxy: since CME has no micro PRICE-based
#  Treasury note, the smallest practical price-based US bond exposure is a
#  standard 10-Year T-Note future, ZN, at ~$100,000 face -- this is the
#  binding constraint the audit is meant to surface).
SMALLEST_CONTRACT_USD = {
    "equity_index": dict(symbol="MES", notional=5 * 6650),          # 33,250
    "gov_bond": dict(symbol="ZN (standard 10Y T-Note; NO micro price future exists)", notional=100000 * 1.09),  # ~109,000 (approx price 109 per 100 face)
    "fx": dict(symbol="M6E", notional=12500 * 1.08),                 # 13,500
    "commodity": dict(symbol="MGC", notional=10 * 3800),             # 38,000
}

rounding_rows = []
for account_size in (25_000, 100_000, 250_000):
    for n_markets in (40, 50, 60):
        for bucket, weight in BUCKET_MIX.items():
            n_in_bucket = round(n_markets * weight)
            if n_in_bucket == 0:
                continue
            mkt_vol = MARKET_VOL[bucket]
            smallest = SMALLEST_CONTRACT_USD[bucket]["notional"]
            symbol = SMALLEST_CONTRACT_USD[bucket]["symbol"]
            # desired dollar-vol contribution per market in this bucket, spread
            # equally across all n_markets (equal risk per market, book-wide,
            # 1/sqrt(N) uncorrelated risk-parity convention -- see methodology note)
            desired_dollar_vol = (TARGET_VOL / (n_markets ** 0.5)) * account_size
            ideal_notional = desired_dollar_vol / mkt_vol
            contracts = round(ideal_notional / smallest)
            achieved_notional = contracts * smallest
            unholdable = contracts == 0
            rounding_error = (achieved_notional / ideal_notional - 1) if ideal_notional > 0 else None
            # achieved dollar-vol / desired dollar-vol - 1 = risk deviation
            achieved_dollar_vol = achieved_notional * mkt_vol
            risk_dev = (achieved_dollar_vol / desired_dollar_vol - 1) if desired_dollar_vol > 0 else None
            rounding_rows.append(dict(
                account_size_cad=account_size, n_markets=n_markets, bucket=bucket,
                representative_instrument=symbol, market_vol=mkt_vol,
                ideal_notional_usd=round(ideal_notional, 2),
                smallest_contract_notional_usd=round(smallest, 2),
                contracts_held=contracts, achieved_notional_usd=round(achieved_notional, 2),
                unholdable=unholdable,
                notional_rounding_error_pct=None if rounding_error is None else round(rounding_error * 100, 1),
                risk_deviation_pct=None if risk_dev is None else round(risk_dev * 100, 1),
            ))

rounding_fields = ["account_size_cad", "n_markets", "bucket", "representative_instrument",
                    "market_vol", "ideal_notional_usd", "smallest_contract_notional_usd",
                    "contracts_held", "achieved_notional_usd", "unholdable",
                    "notional_rounding_error_pct", "risk_deviation_pct"]
write_csv(os.path.join(OUT_DIR, "rounding_error.csv"), rounding_rows, rounding_fields)

# summary stats: fraction unholdable + mean abs risk deviation, per account size
summary = {}
for account_size in (25_000, 100_000, 250_000):
    rows = [r for r in rounding_rows if r["account_size_cad"] == account_size]
    n_unholdable = sum(1 for r in rows if r["unholdable"])
    frac_unholdable = n_unholdable / len(rows)
    abs_dev = [abs(r["risk_deviation_pct"]) for r in rows if r["risk_deviation_pct"] is not None]
    mad = sum(abs_dev) / len(abs_dev) if abs_dev else None
    summary[str(account_size)] = dict(
        n_bucket_rows=len(rows), fraction_unholdable=round(frac_unholdable, 3),
        mean_abs_risk_deviation_pct=round(mad, 1) if mad is not None else None,
    )

# ---------------------------------------------------------------------------
# Tasks 4-6: costs.json (CAD/USD conversion, account types, taxes)
# ---------------------------------------------------------------------------
costs = dict(
    generated="2026-09-26",
    disclaimer="Synthetic feasibility/cost arithmetic only. Not financial or tax advice. No strategy returns.",
    cad_usd_conversion=dict(
        norberts_gambit=dict(
            method="Buy DLR.TO (CAD) then journal/convert to DLR.U.TO (USD) at broker, or reverse",
            typical_all_in_cost_pct=0.15,
            note=("Bid-ask spread on DLR is typically ~1 cent/share; on a CAD 20,000 conversion this is "
                  "~CAD 30 round-trip (~0.15%) at a zero-commission broker plus a flat journaling fee at "
                  "brokers that charge one (e.g. ~CAD 9.95 at Questrade); IBKR does not require manual "
                  "journaling for DLR and the cost is essentially just the bid-ask spread + commission."),
            source="https://www.questrade.com/learning/investing-basics/norberts-gambit-currency-conversion ; "
                   "https://moneyengineer.ca/2025/08/21/tracking-norberts-gambit-costs-with-questrade/",
        ),
        ibkr_fx_conversion=dict(
            typical_all_in_cost_pct=0.03,
            note=("IBKR's IdealPro FX conversion spread is typically ~0.5-1 pip on major pairs (roughly "
                  "0.01-0.03%) plus a small minimum commission -- the cheapest widely-available option for "
                  "a Canadian retail account, materially cheaper than Norbert's Gambit for accounts already "
                  "at IBKR."),
            source="https://www.interactivebrokers.com/en/trading/forex.php (IBKR FX conversion / IdealPro spread disclosures)",
        ),
        bank_spread=dict(
            typical_all_in_cost_pct=2.5,
            note="Retail bank foreign-exchange counter/telephone conversion typically embeds a 2-3% spread vs. interbank rate.",
            source="qualitative industry knowledge; compare posted bank FX rates vs. Bank of Canada noon rate on any given day",
        ),
        currency_exposure_note=(
            "Every USD-listed ETF (e.g. IVV, TLT, GLD) leaves the Canadian investor with unhedged USD "
            "exposure on top of the strategy's own FX-market bets, unless a CAD-hedged share class is used. "
            "This compounds with the book's own systematic FX carry/trend positions and should be tracked "
            "as a separate FX exposure line, not netted informally against strategy signals."
        ),
    ),
    account_types=ACCOUNT_FACTS,
    taxes_not_advice=TAX_NOTE,
    rounding_error_summary=summary,
    aum_class_legend=AUM_CLASS_LEGEND,
)

with open(os.path.join(OUT_DIR, "costs.json"), "w") as f:
    json.dump(costs, f, indent=2, default=str)

print("Wrote:", OUT_DIR)
print(json.dumps(summary, indent=2))
