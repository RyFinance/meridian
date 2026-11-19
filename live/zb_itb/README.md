# ZB → ITB live trader (Alpaca)

Rule and evidence: `research/zb_itb/verify/VERIFICATION.md`. The signal comes from the frozen forward-test code (`research/zb_itb/forward.py::signal`).

## Daily cycle (NYSE days; Mac launchd, Pacific time)
| Job | Runs | Does |
|---|---|---|
| `enter` | 06:12 PT (09:12 ET) | Waits for the ZB 08:00–09:00 bar (09:15 ET) and computes the signal. Sends a market-on-open order by 09:27, then checks the fill at 09:31:30. A late market entry is allowed until 09:35. Places a 3% protective stop. |
| `exit` | 07:29 PT | At 10:30:00 ET, cancels the stop and closes ITB, retrying once. Logs equity. |
| `failsafe` | 12:50 PT (15:50 ET) | Flattens any ITB position or open order that is still there. |

## Safety rails
- **`KILL` file:** if `live/zb_itb/KILL` exists, no new entries are made. Delete the file to resume.
- **Drawdown guard:** writes KILL automatically when equity falls 15% below its high-water mark.
- **PDT guard:** with equity under $25k, no 4th day trade in 5 days, and no trading if the account is flagged.
- **Shorts:** only when equity ≥ $2k, shorting is enabled, and ITB is shortable and easy to borrow. Otherwise the short day is skipped.
- **Size:** whole shares, at most `max_fraction_of_equity` × equity and `max_notional_usd` (config.json).
- **Duplicates:** one entry per day, enforced by client order id.
- **Logs:** every action is logged to `journal.jsonl`; launchd output goes to `~/Library/Logs/quant_v7/zb_itb_live_*.log`.

## Setup
1. In Alpaca, open the **Paper** dashboard and generate API keys (key ID + secret).
2. Paste them into `quant_v7/.env.alpaca` yourself. The file is gitignored and chmod 600. Don't paste keys into chat.
3. Check the connection: `PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader status`
4. Load the jobs (`launchd/*.plist` → `~/Library/LaunchAgents`, then `launchctl bootstrap`).
5. The Mac must be on, awake (`caffeinate` keeps it up during runs) and online on weekday mornings.

## Going live (later, same code)
- Make new **live** keys and set `ALPACA_MODE=live` and `LIVE_CONFIRM=I-UNDERSTAND-REAL-MONEY` in `.env.alpaca`.
- Start with a small `max_notional_usd`.
- Suggested gate before live: at least 20 paper trades with fills close to the official open and 10:30 prices.

## Interactive Brokers (for live trading from Canada)
The same trader switches brokers with one setting. `broker_ibkr.py` uses `ib_async`, which is already installed.
1. Open an IBKR Canada **margin** account and hold USD, so trades don't pay FX conversion each time. Paper trading is included.
2. Install **IB Gateway**, log in to the **paper** account, and turn on the API: Configure → API → Enable ActiveX and Socket Clients, port 4002, and add 127.0.0.1 as a trusted IP.
3. Create `quant_v7/.env.broker` with `BROKER=ibkr`, and `quant_v7/.env.ibkr` with:
   `IBKR_MODE=paper`, `IBKR_PORT=4002`, `IBKR_CLIENT_ID=17` (no passwords; login happens in Gateway).
4. Run `PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader status`. It refuses to trade a non-paper (non-DU) account in paper mode.
5. Gateway has to stay logged in every weekday morning. IBKR forces a daily restart; set it for after 16:00 ET.
- **Costs:** IBKR Pro is about $0.005/share with a $1 minimum. That's fine at ~$25k per trade, but under ~$5k the $1 minimum eats the edge.
- **Check:** whether the US $25k day-trading rule applies to your IBKR Canada account.
