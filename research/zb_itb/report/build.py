"""Fill the report template with chart data and the scoreboard -> report/index.html."""
import json
from pathlib import Path
H = Path(__file__).parent
ROWS = [
    ("BTC overnight → MSTR shares/options (0DTE, spreads, stops)", "none", "MSTR's open prices BTC's move about 1:1"),
    ("BTC → miners, ETH names, Asian BTC stocks, pairs", "none / weak", "decayed, trust-era artifacts, or open-print fills"),
    ("Boyaa (0434.HK) BTC-residual dip buy", "not tradable", "+65 bp at the open print, −25 bp entering at 10:30"),
    ("BTC/ETH/SOL weekend and session patterns, FOMC", "none", "no effect in 2017–22"),
    ("ML on 27 overnight features", "none", "inside shuffled-label noise"),
    ("Oil, metals, country ETFs/ADRs, FX", "none", "opens price the overnight move about 1:1"),
    ("Oil → airlines/cruise; gas → producers/utilities", "none", "priced at the open"),
    ("Grains → ag stocks and food processors", "none", "priced at the open"),
    ("Rates → bond ETFs, insurers, brokers, REITs, banks", "none", "no lag outside housing"),
    ("SPY gap-down fill", "weak", "t 2.8 on 42 trades, out of 288 variants"),
    ("Options on the builder signal", "none", "spreads take the edge; only 9% of legs had prints"),
    ("Model tweaks (sizing, ZN, NAIL, exits, SPY hedge)", "no gain", "the plain rule stays best"),
    ("Housing data releases (new home sales, starts, NAHB)", "none", "no drift after releases; main rule unchanged on those days"),
    ("Weekly mortgage rates, 5-day rate trend, ITB–bond spread", "none", "signs flip between halves"),
    ("Pre-market entry instead of the open", "not worth it", "+13 bp gross but ITB has no pre-market prints; tiny capacity"),
    ("Skip sessions after holidays?", "no", "2010–26 history: post-holiday effect is noise (p 0.71)"),
    ("Trade the builder that lagged most at the open", "none", "+5 bp vs the basket, not significant"),
    ("Rates → housing platforms, home goods, solar, fintech", "none / weak", "only housing-demand names lean positive; none beats ITB"),
    ("FINRA daily short-sale volume (500 stocks, 2022–26)", "not tradable", "real but tiny signal (4–10 bp/day); turnover makes costs eat it"),
    ("CFTC Treasury positioning (weekly) → ITB", "none", "sign flips between periods; SPY reacts the same"),
    ("Treasury auction results → ITB afternoon/overnight", "none", "builders price auction moves within the hour"),
    ("Asian chipmakers → US semis; European peers → US peers", "none", "priced at the open; EU lead failed a 2010–26 check"),
    ("Pre-market earnings → sector peers; S&P futures → small caps", "none", "peers and small caps move before or at the open"),
    ("NAIL (3x homebuilders), long-only", "aggressive option", "+76%/yr backtest but −20% max DD; same edge, levered"),
    ("Regime switch: trade only when builders track bonds", "edge (safety)", "2010–26 t 4.7 vs 2.3 without; explains the dead 2010s"),
    ("UK builders vs overnight Treasuries", "__UK__", "__UKWHY__"),
    ("Rates → Rocket mortgage (RKT)", "edge", "+21 bp in 2020–23, +32 bp in 2025–26; forward-testing"),
    ("Rates → homebuilders (ITB)", "edge", "the strategy on this page"),
]
CLS = {"aggressive option": "warn", "edge (safety)": "up", "not worth it": "warn", "no": "", "edge": "up", "weak": "warn", "none / weak": "warn", "no gain": "", "not tradable": "down", "none": "down"}
def build(uk="running", ukwhy="results pending"):
    rows = "".join(f'<tr><td>{a}</td><td><span class="pill {CLS.get(b.replace("__UK__", uk), "")}">{b.replace("__UK__", uk)}</span></td><td>{c.replace("__UKWHY__", ukwhy)}</td></tr>' for a, b, c in ROWS)
    html = (H / "template.html").read_text().replace("__DATA__", (H.parent / "report_data.json").read_text()).replace("__SCOREBOARD__", rows)
    (H / "index.html").write_text(html); print("wrote", H / "index.html", len(html))
if __name__ == "__main__":
    import sys
    build(*sys.argv[1:3]) if len(sys.argv) > 2 else build()
