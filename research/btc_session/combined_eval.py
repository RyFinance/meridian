"""Combined scoreboard for btc_cme_break_v1 + eth_cme_break_v1 (equal weight). Not frozen; reads both eval files."""
import json, statistics as st
from pathlib import Path
R = Path(__file__).parents[2] / "reports" / "forward"
def load(n):
    p = R / n
    return {t["day"]: t["gross"] for t in json.loads(p.read_text())["trades"] if "gross" in t} if p.exists() else {}
b, e = load("btc_cme_break_eval.json"), load("eth_cme_break_eval.json")
days = sorted(set(b) | set(e))
c = [st.mean([x for x in (b.get(d), e.get(d)) if x is not None]) for d in days]
s = {"n_days": len(c)}
if len(c) >= 2:
    sd = st.stdev(c)
    s.update(gross_mean_bp=st.mean(c) * 1e4, t=st.mean(c) / sd * len(c) ** .5 if sd else None, hit=sum(x > 0 for x in c) / len(c),
             cum_net_2bp_pct=sum(x - 2e-4 for x in c) * 100, cum_net_4bp_pct=sum(x - 4e-4 for x in c) * 100)
    s["kill"] = s["cum_net_4bp_pct"] <= -8
    s["gate"] = "pending" if len(c) < 250 else ("PASS" if s["t"] >= 1.65 and s["cum_net_4bp_pct"] > 0 else "FAIL")
(R / "cme_break_combined.json").write_text(json.dumps({"summary": s, "days": dict(zip(days, c))}, indent=2)); print(json.dumps(s, indent=2))
