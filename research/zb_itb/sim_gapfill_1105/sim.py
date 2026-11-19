"""Simulated fills for shares the paper broker never filled, so the desk shows the signal's performance.
Same rules as the earlier sims: entry at the official open (opening auction, yfinance daily Open), 3% protective stop
filled at the stop price, 10:30 market exit = open of the 10:30 minute (Alpaca SIP 1m), IBKR-style fees.
Usage: python sim.py  (writes result.json next to this file and prints journal rows)"""
import sys, json, datetime as dt; sys.path.insert(0, ".")
from pathlib import Path
from zoneinfo import ZoneInfo
import yfinance as yf
from live.zb_itb.broker import Alpaca, load_env
from live.zb_itb.trader import virtual_fees, CFG

ET = ZoneInfo("America/New_York"); HERE = Path(__file__).parent
GAPS = [  # day, account, side, missing qty, why
    ("2026-10-30", "NAIL", "buy", 58, "the paper MOO and late entry were rejected (buying power); 0 of 58 filled"),
    ("2026-11-05", "ITB", "sell", 15, "paper broker filled 5 of 20 before the 09:35 cutoff"),
    ("2026-11-05", "NAIL", "sell", 54, "short signal skipped: broker equity $1,922.51 is under Alpaca's $2,000 shorting minimum"),
]
a = Alpaca(load_env(Path(".env.alpaca.itb"))); D = "https://data.alpaca.markets/v2/stocks"
out = []
for day, sym, side, qty, why in GAPS:
    d = dt.date.fromisoformat(day)
    t0 = dt.datetime.combine(d, dt.time(9, 29), ET).astimezone(dt.timezone.utc); t1 = t0 + dt.timedelta(minutes=63)
    bars = a._req("GET", f"{D}/{sym}/bars", params={"timeframe": "1Min", "start": t0.isoformat(), "end": t1.isoformat(),
                                                   "feed": "sip", "limit": 10000, "adjustment": "raw"}).get("bars") or []
    m = {dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET).strftime("%H:%M"): b for b in bars}
    y = yf.download(sym, start=day, end=(d + dt.timedelta(days=1)).isoformat(), progress=False, auto_adjust=False)
    entry = round(float(y["Open"].iloc[0].item() if hasattr(y["Open"].iloc[0], "item") else y["Open"].iloc[0]), 4)
    s = 1 if side == "buy" else -1
    stop = round(entry * (1 - s * CFG["protective_stop_pct"] / 100), 2)
    win = [b for k, b in sorted(m.items()) if "09:30" <= k <= "10:29"]
    low, high = min(b["l"] for b in win), max(b["h"] for b in win)
    stopped = (low <= stop) if s > 0 else (high >= stop)
    exit_px = stop if stopped else m["10:30"]["o"]
    gross = round(s * qty * (exit_px - entry), 2); fees = round(virtual_fees(qty, exit_px), 2)
    row = {"ts_et": f"{day}T10:30:00{dt.datetime.combine(d, dt.time(10, 30), ET).strftime('%z')[:3]}:00", "event": "sim_trade",
           "simulated": True, "account": sym, "symbol": sym, "day": day, "side": side, "qty": qty, "entry_price": entry,
           "exit_price": exit_px, "stop_price": stop, "stopped": stopped, "window_low": low, "window_high": high,
           "gross_pl": gross, "fees": fees, "net_pl": round(gross - fees, 2), "ret_pct": round(s * (exit_px / entry - 1) * 100, 3),
           "reason": f"SIMULATED force fill: {why}. Missing shares at the official open, 3% stop, 10:30 exit, IBKR-style fees. The broker never saw them."}
    out.append(row); print(json.dumps(row))
json.dump(out, open(HERE / "result.json", "w"), indent=1)
