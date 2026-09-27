# Development-only portfolio overlap

On 2,126 common historical sessions (2006-07-24 to 2014-12-31), the provisional commodity ETF spread's daily correlation was **0.061** with IEF−SHY duration active return, **0.007** with the Treasury month-end TLT active series, and **−0.022** with SPY−SHY. The Treasury duration active series correlated **−0.410** with equity active return over this common subset. Inputs are `reports/commodity_roll/dev_daily.csv`, `reports/tsy_month_end/dev_daily.csv`, and the frozen IEF/SHY/SPY adjusted-open files.

This is useful diversification *potential*, not a backtested portfolio candidate: the commodity spread's independent audit found strong commodity short exposure and borrow/period sensitivity, the duration premium failed its development p gate, and TLT month-end failed validation. Correlations can change outside 2006–2014, especially in inflation or funding shocks. No portfolio weights were fitted or validation series read for this comparison.
