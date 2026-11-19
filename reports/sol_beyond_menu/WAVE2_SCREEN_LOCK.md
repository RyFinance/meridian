# Wave-2 screen and holdout lock — before strategy returns

The JKP global monthly author theme factors are the only candidates clearing both a documented economic mechanism and frozen free return inputs without duplicating Claude's trend, cross-sectional momentum, value, carry, defensive or seasonality components. Two themes are preregistered: accruals and debt issuance. Both use 1988-01–2015-12 development and lock 2016-01–2025-12; no return from the latter period is to be evaluated. The remaining requested source families either lack the exact missing field, have too-short/uncorrected source histories, or are spent/overlapping. This is a **pre-return selection record**, not a result.

| Candidate/source family | Exact missing field or conflict | Pre-return decision |
|---|---|---|
| COT hedging pressure | CFTC free positions exist, but complete contract-level daily futures settlements, roll P&L, expiry/delist and margin history across the paper universe do not have a verified free archive. | Stop acquisition; do not replace futures with spot/ETF drift. |
| Commodity skewness | Same missing contract-level futures return/roll/expiry panel. | Stop acquisition. |
| Lucca–Moench pre-FOMC drift | Historical intraday price bars aligned to the changing exact announcement time, with executable spread/auction costs. Fed dates alone are insufficient. | Stop acquisition. |
| Treasury auction concession | Auction results exist; missing when-issued preauction security price and executable matched bond returns. Treasury auction demand is also spent. | Exclude. |
| FINRA aggregate short-interest/short-sale volume | Exchange-listed FINRA short interest begins June 2021, too short for 25% + five-year holdout; daily short-sale volume is not outstanding short interest and is not the wave-1 RRZ construct. | Do not relabel/retune wave-1 trial. |
| ALFRED/FRED, H.15/H.4.1, NY Fed SOMA | Vintages/yields/holdings are public, but macro-surprise, policy trend, Treasury duration and auction-demand mechanisms are spent; no independent preregistered non-overlapping claim clears the sweep. | No speculative run; stop targeted acquisition. |
| SEC EDGAR | Filing timestamps and indexes are free; security-level survivor-free returns, point-in-time mapping and borrow costs needed for a new tradable cross-sectional test are not. | Stop acquisition. |
| Cboe historical statistics | Free aggregate put/call volumes, but exact option-level prints/quotes and contract greeks for new option payoffs are paid; index option-volume breadth/option H1–H4 are spent. | Exclude. |
| LSE Terminal | No verified permission, accessible historical endpoint, or timestamped export is available to this task. | No credential or terminal changes; infeasible. |
| JKP public theme factors | Four complete public regional archives, author methodology, date and factor universe; raw stock-level data are paid WRDS, so research-grade only. | Freeze; run only accruals and debt issuance with locked holdout. |

All run candidates are fixed before inspecting any numerical factor return. The exact archive/availability completeness record and S3 endpoints are in `data/sol_beyond_menu/wave2_raw/completeness.json` and the immutable `sol_wave2_jkp_v1` snapshot.
