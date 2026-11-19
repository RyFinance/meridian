"""Edge monitor for the live/paper ZB->homebuilder trades: is the edge still there?

Reads the forward-test scoreboards (reports/forward/zb_itb_eval.json, zb_rkt_eval.json) and prints, per leg:
  n, mean net, t, cumulative, and a sequential probability ratio test (SPRT) of
  H1 "edge = half the backtest" vs H0 "edge = 0", using the backtest's per-trade volatility.
SPRT boundaries (alpha = beta = 5%): log-LR >= +2.94 -> edge confirmed; <= -2.94 -> edge gone; otherwise keep going.
    PYTHONPATH=. .venv/bin/python -m research.zb_itb.monitor
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGS = {  # backtest net mean and per-trade sd (bp), from research/zb_itb/verify
    "zb_itb_v1": {"file": "reports/forward/zb_itb_eval.json", "net_key": "net_2bp", "mu_bt": 22.4, "sd": 110.0},
    "zb_rkt_v1": {"file": "reports/forward/zb_rkt_eval.json", "net_key": "net_5bp", "mu_bt": 45.3, "sd": 230.0},
}
A = math.log((1 - 0.05) / 0.05)   # 2.944

for leg, cfg in LEGS.items():
    f = ROOT / cfg["file"]
    if not f.exists():
        print(f"{leg}: no scoreboard yet ({cfg['file']})"); continue
    trades = [t for t in json.loads(f.read_text()).get("trades", []) if cfg["net_key"] in t]
    x = [t[cfg["net_key"]] * 1e4 for t in trades]
    n = len(x)
    if n < 2:
        print(f"{leg}: {n} scored trades, too few"); continue
    mean = sum(x) / n; sd = (sum((v - mean) ** 2 for v in x) / (n - 1)) ** 0.5
    mu1, s = cfg["mu_bt"] / 2, cfg["sd"]
    llr = sum((mu1 * v - mu1 ** 2 / 2) / s ** 2 for v in x)     # Gaussian LLR, H1 mean mu1 vs H0 mean 0
    verdict = "EDGE CONFIRMED (half-edge beats zero)" if llr >= A else "EDGE GONE (zero beats half-edge)" if llr <= -A else "undecided, keep trading"
    need = math.ceil((2 * s / mu1) ** 2)
    print(f"{leg}: n {n} | mean net {mean:+.1f}bp | t {mean / sd * n ** .5:+.2f} | cum {sum(x) / 100:+.1f}% | SPRT log-LR {llr:+.2f} -> {verdict} | ~{need} trades for t=2 at half edge")
