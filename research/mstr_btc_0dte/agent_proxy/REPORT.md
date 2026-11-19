# BTC proxy open-to-close drift: frozen out-of-sample test

## Verdict

**No frozen rule clears the precommitted credible-positive-net-edge bar.**  MSTR
produced a positive net validation compound return, but its annualized Sharpe was
0.48, below the 0.50 gate, and its 2025 result was materially negative.  The two
proxies with the clearest development-period slow-open signature—CLSK and
COIN—failed at their exact frozen 2% rules, after all stated costs.

This is research only; no order was placed or proposed.

Knowledge-graph limitation: the project's `/graphify` command and
`graphify-out/wiki/index.md` were unavailable for this task, so the limited raw
inspection described below was used instead.

## Question and executable interpretation

The hypothesis was that a US BTC proxy can under-react to an overnight BTC move
at the regular-session open, then drift further through that session.  It is not
valid to decide at 09:30 to buy an opening auction using the opening price that
is only known after that auction.  Accordingly, the tradeable test is:

1. At 09:29 ET, compare the last *completed* BTC minute at or before 09:28 ET
   against the last completed minute at or before 15:59 ET on the instrument's
   preceding US equity session.  Both must be at most five minutes old.
2. If the frozen positive BTC-off-hours threshold is met, buy at the regular
   opening auction and sell at that same day's regular closing auction.
3. Charge each side 3 bp auction friction and $0.005/share:
   `net = (close × (1 − bp) − 0.005) / (open × (1 + bp) + 0.005) − 1`.

Thus the result directly tests an open-to-close continuation conditional on a
signal known before the trade.  There are no naked shorts, leverage, or extended
hours assumptions.  “Trades” below means completed one-day position pairs
(equivalently position-days); the daily Sharpe includes zero returns on no-trade
sessions.

## Universe and development-only discovery

The intended universe was MSTR, MARA, RIOT, CLSK, COIN, and IBIT.  To avoid
pretending that a business was always a BTC proxy, the usable starts were set
conservatively to MSTR/MARA/RIOT on 2020-08-12, CLSK on 2021-01-04, and COIN on
its 2021-04-14 IPO.  IBIT was excluded: it began in 2024, so it has no eligible
pre-2023 development history under the stated protocol.  MARA and RIOT were
explored but their openings already moved roughly as much as or more than BTC in
the development diagnostic, and their simple long O->C results were weaker.

Discovery used **only sessions through 2022-12-30**.  For BTC-off-hours moves of
at least +1%, the descriptive development regression slopes below are the stock
overnight gap and stock O->C return on BTC off-hours return.  They are not hedge
betas and were not used in the frozen entry signal.

| Name | Observations | Mean BTC off-hours | Mean opening gap | Mean O->C | Gap slope | O->C slope |
|---|---:|---:|---:|---:|---:|---:|
| MSTR | 214 | 3.56% | 3.18% | 0.57% | 0.885 | 0.189 |
| MARA | 214 | 3.56% | 4.72% | -0.32% | 1.244 | 0.141 |
| RIOT | 214 | 3.56% | 4.19% | 0.22% | 0.996 | 0.145 |
| CLSK | 183 | 3.54% | 2.40% | 0.22% | 0.438 | 0.081 |
| COIN | 145 | 3.39% | 2.27% | 0.13% | 0.506 | 0.148 |

CLSK and COIN therefore looked relatively slow at the open in development, but
the observed same-day continuation was small.  The exploratory grid considered
the fixed positive thresholds 0%, 0.5%, 1%, 1.5%, 2%, 2.5%, 3%, 4%, and 5% for
individual names and equal-weight baskets.  This is a meaningful multiple-testing
burden, not an achievement.  The exact three selections were frozen before any
2023+ outcomes were read; see [`frozen_rules.json`](frozen_rules.json) and
[`FREEZE.md`](FREEZE.md).

### Exact frozen rules

| ID | Instrument | Trigger at 09:29 ET | Entry / exit | Development rationale |
|---|---|---|---|---|
| P1 | MSTR | BTC off-hours >= +2.0% | opening auction / same-day closing auction | 138 development trade days; positive in 2020, 2021, and 2022; selected from a positive 1.5%–2.0% neighborhood. |
| P2 | CLSK | BTC off-hours >= +2.0% | opening auction / same-day closing auction | Relatively low opening-response slope; positive development results in 2021 and 2022. |
| P3 | COIN | BTC off-hours >= +2.0% | opening auction / same-day closing auction | Relatively low opening-response slope; positive development results in 2021 and 2022. |

All signal timing, no-trade behavior, sizing, and costs are pinned verbatim in
[`frozen_rules.json`](frozen_rules.json).  The frozen file's SHA-256 was
`b423a16a620a5ec332a20e3e07441d6eadef5b66ed347872b6d86542b64b074f` before the
single validation run.

## Development versus one-time validation

Validation starts 2023-01-01 and ends 2026-08-10, the last US session for which
the supplied BTC minute file still contains a pre-open observation.  Its final
timestamp is 2026-08-11 08:03 UTC, before the following US opening.  The
development and validation statistics are net of 3 bp/side plus $0.005/share.

| Rule | Period | Sessions | Trades | Exposure | Net compound | Annualized Sharpe | Max drawdown | Win rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P1 MSTR | Dev: 2020-08-13–2022-12-30 | 601 | 138 | 22.96% | 82.95% | 0.81 | -42.83% | 54.35% |
| P1 MSTR | Validation: 2023-01-03–2026-08-10 | 903 | 148 | 16.39% | 46.97% | 0.48 | -44.76% | 53.38% |
| P2 CLSK | Dev: 2021-01-05–2022-12-30 | 502 | 122 | 24.30% | 33.38% | 0.54 | -34.41% | 51.64% |
| P2 CLSK | Validation: 2023-01-03–2026-08-10 | 902 | 148 | 16.41% | -74.44% | -0.68 | -81.77% | 45.27% |
| P3 COIN | Dev: 2021-04-15–2022-12-30 | 433 | 94 | 21.71% | 30.62% | 0.62 | -26.38% | 56.38% |
| P3 COIN | Validation: 2023-01-03–2026-08-10 | 903 | 148 | 16.39% | -7.90% | 0.05 | -41.60% | 49.32% |

The validation split is not a single lucky year:

| Validation year | P1 MSTR: net / Sharpe | P2 CLSK: net / Sharpe | P3 COIN: net / Sharpe |
|---|---:|---:|---:|
| 2023 | +35.36% / 1.40 | -11.57% / -0.25 | +5.65% / 0.35 |
| 2024 | +33.25% / 0.83 | -51.37% / -0.93 | +8.45% / 0.41 |
| 2025 | -23.97% / -0.64 | -22.69% / -0.43 | -26.38% / -1.20 |
| 2026 through 2026-08-10 | +7.17% / 0.52 | -23.11% / -1.38 | +9.19% / 0.74 |

The complete annual and fixed-subperiod rows are saved in
[`validation_annual.csv`](validation_annual.csv) and
[`validation_subperiods.csv`](validation_subperiods.csv).

## Cost and adjacent-threshold robustness

The validation was not re-optimized.  The table reports the frozen 2.0% rule at
the baseline, +1 bp/side, and +3 bp/side cost shocks, plus the fixed adjacent
1.5% and 2.5% threshold checks at baseline.  These are diagnostic robustness
checks, not post-hoc replacement strategies.

| Rule | 1.5%, 3 bp/side | Frozen 2.0%, 3 bp | Frozen 2.0%, 4 bp | Frozen 2.0%, 6 bp | 2.5%, 3 bp |
|---|---:|---:|---:|---:|---:|
| P1 MSTR: net compound / Sharpe | +152.79% / 0.86 | +46.97% / 0.48 | +42.68% / 0.46 | +34.48% / 0.41 | +103.15% / 0.75 |
| P2 CLSK: net compound / Sharpe | -28.26% / 0.07 | -74.44% / -0.68 | -75.18% / -0.70 | -76.61% / -0.74 | -63.72% / -0.53 |
| P3 COIN: net compound / Sharpe | +101.33% / 0.77 | -7.90% / 0.05 | -10.58% / 0.02 | -15.72% / -0.04 | +23.54% / 0.36 |

MSTR remains positive under the cost shocks and its adjacent values are positive,
but the **frozen** 2.0% rule misses the precommitted 0.50 Sharpe gate.  COIN's
sign flip between 1.5%, 2.0%, and 2.5% is exactly the sort of threshold
instability that must not be turned into an after-the-fact 1.5% claim.  It needs
a newly frozen study on an untouched future sample, not a retrospective rule
change.  CLSK fails every robustness check.

The full grid is in
[`validation_cost_and_adjacent_robustness.csv`](validation_cost_and_adjacent_robustness.csv).

## Precommitted acceptance bar and decision

Before validation, a candidate had to satisfy all of these conditions:

1. Positive baseline net compound return;
2. Annualized Sharpe >= 0.50;
3. At least 75 trades and maximum drawdown no worse than -50%;
4. Positive net compound under the 6 bp/side shock; and
5. Positive baseline net compound at both adjacent 1.5% and 2.5% thresholds.

P1 fails item 2 (0.48).  P2 fails items 1–5.  P3 fails items 1, 2, and 4.
Therefore, **there is no credible deployable positive-net edge from this
frozen test.**  A result that almost passes one arbitrary cutoff is not a basis
for relaxing the cutoff after looking at validation.

## Data, provenance, and limitations

Inputs were pre-existing local files; no external data were downloaded:

| Purpose | Local source | Coverage used |
|---|---|---|
| BTC minute closes | `/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet` | 2017-08-17 04:00 UTC to 2026-08-11 08:03 UTC; 4,469,515 rows, no duplicate timestamps. |
| MSTR daily OHLCV | `/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/mstr_daily_yf.parquet` | 2019-12-02 to 2026-10-16; only through BTC availability used. |
| MARA/RIOT/CLSK/COIN daily OHLCV | `/Users/rytty/CCP/quant_v7/data/sec_insider/prices/{TICKER}.parquet` | Local archive; only the proxy-date windows above used. |

Important limits:

- The file names and parquet metadata do not provide full immutable vendor
  provenance for the non-MSTR daily archives.  The MSTR input was supplied by
  the task as the official local series, although its filename includes `yf`.
  These are suitable for a paper screen, not a substitute for independently
  archived primary-exchange/SIP auction prints.
- Daily `Open`/`Close` bars are assumed to represent executable regular-session
  auction fills.  Real opening/closing auction participation, queue priority,
  odd-lot effects, market impact, and spreads can be worse than 3 bp/side.
  The explicit cost shocks help but cannot resolve that data limitation.
- Same-day O->C returns avoid most corporate-action adjustment issues.  No
  selected development or validation trade fell on a local `splits != 0` row;
  nevertheless, all OHLC data should be audited again against an institutional
  feed before any live consideration.
- The universe is hand-selected around surviving, still-listed BTC proxies and
  begins after known/assumed BTC-proxy pivots.  It cannot estimate delisting,
  business-model-change, borrow, or historical liquidity selection bias.
  It is intentionally long-only, so it does not claim a short-side result or
  assume an unobserved stock-borrow cost.
- This is one development/one validation pass.  The attractive post-validation
  adjacent cells are explicitly not promoted into a strategy; doing so would
  invalidate the holdout.

## Reproducibility artifacts

- [`proxy_drift_research.py`](proxy_drift_research.py) — two-stage builder and
  backtest.  Run `python proxy_drift_research.py --stage dev`, then freeze rules,
  then exactly once run `python proxy_drift_research.py --stage validate --frozen frozen_rules.json`.
- [`dev_provenance.json`](dev_provenance.json),
  [`dev_underreaction_diagnostics.csv`](dev_underreaction_diagnostics.csv), and
  [`dev_open_to_close_grid.csv`](dev_open_to_close_grid.csv) — development-only
  record.
- [`validation_provenance.json`](validation_provenance.json),
  [`validation_metrics.csv`](validation_metrics.csv),
  [`validation_trades.csv`](validation_trades.csv), and
  [`validation_daily_returns.csv`](validation_daily_returns.csv) — frozen test
  evidence.  The validation provenance records the frozen-rule hash and code
  hash used for the run.
