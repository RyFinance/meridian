"""Collect LSE MCP macro_series outputs saved by the harness (tool-results/*.txt) into one raw JSON store.

Each saved file is the JSON array the MCP tool returned, possibly truncated by the server at ~60k chars; only
complete {symbol,date,value} records are parsed. Records are de-duplicated on (symbol, date); conflicting values
for the same (symbol, date) are reported. Output: data/cycle7/fx/raw/lse_mcp/lse_macro_series.json + coverage.
"""
from __future__ import annotations
import glob, json, re, hashlib, datetime as dt, sys
from pathlib import Path
import pandas as pd

TR = Path("/Users/rytty/.claude/projects/-Users-rytty-CCP-quant-v7/e3bb65bd-f34a-45ed-8f24-b212b5ca7be8/tool-results")
OUT = Path(__file__).resolve().parents[3] / "data" / "cycle7" / "fx" / "raw" / "lse_mcp"
PAT = re.compile(r'\{"symbol":"([^"]+)","date":"(\d{4}-\d\d-\d\d)","value":(-?[0-9.eE+-]+)\}')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, files = [], []
    for f in sorted(glob.glob(str(TR / "mcp-lse-terminal-macro_series-*.txt"))):
        t = Path(f).read_text()
        n = 0
        for s, d, v in PAT.findall(t):
            rows.append((s, d, float(v), Path(f).name)); n += 1
        files.append({"file": Path(f).name, "sha256": hashlib.sha256(t.encode()).hexdigest(), "records": n,
                      "truncated_by_server": "truncated" in t[-400:],
                      "saved_mtime_utc": dt.datetime.fromtimestamp(Path(f).stat().st_mtime, dt.timezone.utc).isoformat()})
    df = pd.DataFrame(rows, columns=["symbol", "date", "value", "file"])
    conf = df.groupby(["symbol", "date"])["value"].nunique()
    conflicts = conf[conf > 1]
    df = df.drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])
    cov = {}
    for s, g in df.groupby("symbol"):
        d = pd.to_datetime(g.date)
        gaps = d.diff().dt.days
        big = [(str(d.iloc[i - 1].date()), str(d.iloc[i].date())) for i in range(1, len(d)) if gaps.iloc[i] > 12]
        cov[s] = {"first": str(d.min().date()), "last": str(d.max().date()), "n": len(g), "gaps_gt12d": big[:20],
                  "n_gaps_gt12d": len(big)}
    store = {s: {"rows": [{"date": r.date, "value": r.value} for r in g.itertuples()]} for s, g in df.groupby("symbol")}
    (OUT / "lse_macro_series.json").write_text(json.dumps(store))
    (OUT / "lse_pull_record.json").write_text(json.dumps({"tool": "mcp__lse-terminal__macro_series (read-only)",
        "collected_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "files": files, "coverage": cov,
        "conflicts": [list(k) for k in conflicts.index]}, indent=1))
    for s, c in cov.items():
        print(s, c["first"], c["last"], c["n"], c["n_gaps_gt12d"], c["gaps_gt12d"][:4])
    print("conflicts", len(conflicts))

if __name__ == "__main__":
    main()
