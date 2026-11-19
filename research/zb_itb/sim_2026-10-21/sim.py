import sys, json, math; sys.path.insert(0, ".")
from live.zb_itb.trader import virtual_fees, CFG, account_cfg
bars = json.load(open(sys.argv[1]))
OFFICIAL_OPEN = {"ITB": 87.50, "NAIL": 28.115}            # yfinance daily Open = opening auction (MOO fill)
PREV_CLOSE = {"ITB": 86.815, "NAIL": 27.35}               # 2026-10-20 closes, when no pre-market print
EQ = {"ITB": 2016.60, "NAIL": 2000.00}                    # broker equity going into 2026-10-21 (broker; the trader sizes from it)
res = {}
for sym in ["ITB", "NAIL"]:
    m = {b["t"][11:16]: b for b in bars[sym]["min"]}
    pre = [b for k, b in sorted(m.items()) if k < "13:30"]
    ref = pre[-1]["c"] if pre else PREV_CLOSE[sym]        # last trade before the 09:27 OPG deadline (latest_trade)
    cush = 1 + float(account_cfg(sym).get("gap_cushion_pct", 1.0)) / 100
    qty = math.floor(min(EQ[sym] * CFG["max_fraction_of_equity"], CFG["max_notional_usd"]) / (ref * cush))
    entry = OFFICIAL_OPEN[sym]
    stop = round(entry * (1 - CFG["protective_stop_pct"] / 100), 2)
    window = [b for k, b in sorted(m.items()) if "13:30" <= k <= "14:29"]
    low = min(b["l"] for b in window); high = max(b["h"] for b in window)
    stopped = low <= stop
    exit_px = stop if stopped else m["14:30"]["o"]        # 10:30 market exit = open of the 10:30 minute
    gross = qty * (exit_px - entry)
    fees = virtual_fees(qty, exit_px)
    res[sym] = dict(qty=qty, ref=ref, entry=entry, m930_open=m["13:30"]["o"], exit=exit_px, stop=stop, stopped=stopped,
                    low=low, high=high, gross=round(gross, 2), fees=round(fees, 2), net=round(gross - fees, 2),
                    ret_pct=round((exit_px / entry - 1) * 100, 3), equity_after=round(EQ[sym] + gross - fees, 2))
    print(sym, res[sym])
json.dump(res, open(sys.argv[2], "w"))
