"""Morning signal alert for MANUAL trading (e.g. Questrade): computes the frozen ZB signal at ~09:16 ET and shows a
macOS notification + appends to live/zb_itb/signals.log. Places no orders.
    PYTHONPATH=. .venv/bin/python -m live.zb_itb.notify            # real (launchd ~06:16 PT)
    PYTHONPATH=. .venv/bin/python -m live.zb_itb.notify --dry-run  # print only"""
import argparse, datetime as dt, json, subprocess, time
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York"); H = Path(__file__).parent
CFG = json.loads((H / "config.json").read_text())


def message(sig: dict, px: float | None) -> tuple[str, str]:
    d = sig.get("d", 0)
    if not d:
        return "ZB→ITB: NO TRADE today", "Bond futures flat or data missing."
    side = "BUY (long)" if d > 0 else "SHORT"
    stop = f" Stop ~{px * (1 - d * CFG['protective_stop_pct'] / 100):.2f}." if px else ""
    move = (sig["zb_p1_0900"] / sig["zb_p0_prev1600"] - 1) * 1e4
    return f"ZB→ITB: {side} ITB at the 9:30 open", f"Bonds {move:+.0f}bp overnight. Market-on-open order before 9:28 ET, close at 10:30 ET.{stop}"


def main(dry: bool):
    from research.forward import nyse
    day = dt.datetime.now(ET).date()
    if not nyse.is_session(day):
        print(f"{day}: market closed"); return
    from research.zb_itb.forward import signal
    sig = {}
    for _ in range(25):
        try:
            sig = signal(day)
            if sig.get("zb_p1_0900") is not None: break
        except Exception as e:  # noqa: BLE001
            sig = {"error": repr(e)}
        time.sleep(20)
    try:
        import yfinance as yf
        px = float(yf.Ticker("ITB").history(period="5d")["Close"].iloc[-1])
    except Exception:  # noqa: BLE001
        px = None
    title, body = message(sig, px)
    with open(H / "signals.log", "a") as f:
        f.write(json.dumps({"day": day.isoformat(), "title": title, "body": body, "signal": sig}) + "\n")
    print(title, "|", body)
    if not dry:
        subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}" sound name "Glass"'], check=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); main(ap.parse_args().dry_run)
