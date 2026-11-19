"""Pre-market IB Gateway check (launchd ~05:55 PT on NYSE days). If the trader is set to IBKR and Gateway isn't reachable,
show a macOS notification so you can log in before the 09:27 ET order deadline (06:27 PT). Places no orders."""
import datetime as dt, subprocess
from zoneinfo import ZoneInfo
from live.zb_itb.broker import ROOT, BrokerError, load_env


def main():
    from research.forward import nyse
    if not nyse.is_session(dt.datetime.now(ZoneInfo("America/New_York")).date()):
        print("market closed"); return
    if load_env(ROOT / ".env.broker").get("BROKER", "alpaca").lower() != "ibkr":
        print("broker is not ibkr"); return
    try:
        from live.zb_itb.broker_ibkr import IBKR
        b = IBKR(load_env(ROOT / ".env.ibkr")); eq = b.account().get("equity"); b.ib.disconnect()
        msg = (f"IB Gateway OK · equity ${float(eq):,.0f}", "Today's ZB→ITB run is ready.")
    except (BrokerError, Exception) as e:  # noqa: BLE001
        msg = ("IB Gateway NOT reachable", "Log in to IB Gateway before 06:27 PT, or today runs on the Alpaca paper fallback.")
        print(repr(e)[:200])
    print(*msg)
    subprocess.run(["osascript", "-e", f'display notification "{msg[1]}" with title "{msg[0]}" sound name "Glass"'], check=False)


if __name__ == "__main__":
    main()
