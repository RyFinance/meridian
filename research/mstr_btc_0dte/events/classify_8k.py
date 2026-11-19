"""v2: classify MSTR 8-K docs into BTC purchase / sale / other events, extracting details.
Fixes vs v1: multi-acquisition sum (2022-12-28), 'acquisition of N additional' (2020-09),
'holdings ... to approximately N' (2022-12-28), period-total phrasing (2021-09-13).
Output: events/8k_classified.parquet, events/events_btc.parquet, events/events_btc.csv
"""
from __future__ import annotations
import re
import html
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
NUM = r"([\d][\d,]*(?:\.\d+)?)"

ACQ = [
    r"(?:purchased|acq[u]?ired|acquisition of|purchase of)\s+(?:approximately\s+)?([\d][\d,]*(?:\.\d+)?)(?:\s+additional)?\s+bitcoins?",
    r"(?:approximately\s+)?([\d][\d,]*(?:\.\d+)?)\s+additional\s+bitcoins?",
]


def to_text(raw: bytes) -> str:
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("\u00a0", " ").replace("\u2019", "'")
    return re.sub(r"\s+", " ", t)


def money2usd(num: str, unit: str | None) -> float:
    x = float(num.replace(",", ""))
    return x * {"billion": 1e9, "million": 1e6, "thousand": 1e3}.get((unit or "").lower(), 1.0)


def parse(t: str) -> dict:
    d = {"n_btc": None, "usd": None, "avg_px": None, "holds": None, "sold": None, "kind": "other"}
    # --- format B (2026 tables)
    if re.search(r"BTC (?:Acquired|Purchased|Sold)", t):
        m = re.search(r"BTC (Acquired|Purchased|Sold)[^$]{0,260}?" + NUM + r"\s*\$\s*" + NUM + r"\s*\$\s*" + NUM + r"\s*" + NUM + r"\s", t)
        if m:
            verb, n, usd, avg, holds = m.group(1), float(m.group(2).replace(",", "")), float(m.group(3).replace(",", "")) * 1e6, float(m.group(4).replace(",", "")), float(m.group(5).replace(",", ""))
            d.update(n_btc=n, usd=usd, avg_px=avg, holds=holds, kind=("purchase" if verb != "Sold" else "sale"))
            return d
        m = re.search(r"BTC Sold[^$]{0,260}?" + NUM + r"\s*\$\s*" + NUM + r"\s*\$\s*" + NUM, t)
        if m:
            d.update(sold=float(m.group(1).replace(",", "")), kind="sale")
            return d
    # --- format A narrative: sum all acquisitions
    acq = []
    for pat in ACQ:
        acq += [float(x.replace(",", "")) for x in re.findall(pat, t, re.I)]
    # dedupe adjacent duplicates (same number matched by both patterns)
    if acq:
        dedup = [acq[0]]
        for v in acq[1:]:
            if v != dedup[-1]:
                dedup.append(v)
        acq = dedup
        d["n_btc"] = sum(acq)
        d["kind"] = "purchase"
    m = re.search(r"(?:sold|sale of)\s+(?:approximately\s+)?" + NUM + r"\s+bitcoins?", t, re.I)
    if m:
        d["sold"] = float(m.group(1).replace(",", ""))
        if d["kind"] == "other":
            d["kind"] = "sale"
    # amount: first $ after first acquisition mention
    if acq:
        m0 = None
        for pat in ACQ:
            m0 = re.search(pat, t, re.I)
            if m0: break
        tail = t[m0.end():m0.end() + 260]
        mm = re.search(r"for (?:an aggregate purchase price of |approximately )?\$" + NUM + r"\s*(billion|million|thousand)?", tail, re.I)
        if mm:
            d["usd"] = money2usd(mm.group(1), mm.group(2))
        mm = re.search(r"average price of (?:approximately )?\$" + NUM + r"\s*per bitcoin", tail, re.I)
        if mm:
            d["avg_px"] = float(mm.group(1).replace(",", ""))
    # holdings: candidates from holding-context phrases; prefer the last explicit "to approximately N"
    cands = []
    for pat in [r"holdings (?:of|to)\s+(?:approximately\s+)?" + NUM + r"\s+bitcoins?",
                r"holds? approximately ([\d][\d,]*) bitcoins?",
                r"held (?:an aggregate of )?(?:approximately )?" + NUM + r"\s+bitcoins?",
                r"(?:to|of)\s+approximately\s+([\d][\d,]*) bitcoins?"]:
        for m in re.finditer(pat, t, re.I):
            cands.append((m.start(), float(m.group(1).replace(",", ""))))
    if cands:
        d["holds"] = max(cands, key=lambda x: x[0])[1]
    if d["kind"] == "other" and re.search(r"bitcoin", t, re.I):
        d["kind"] = "mention"
    return d


def main():
    k = pd.read_parquet(ROOT / "8k_all.parquet").sort_values("filingDate")
    rows = []
    for _, r in k.iterrows():
        f = DOCS / f"{r.accessionNumber}.htm"
        t = to_text(f.read_bytes()) if f.exists() else ""
        rows.append({**r.to_dict(), **parse(t), "text_len": len(t)})
    out = pd.DataFrame(rows).sort_values("acceptanceDateTime").reset_index(drop=True)
    out["et"] = pd.to_datetime(out.acceptanceDateTime).dt.tz_convert("America/New_York")
    out.to_parquet(ROOT / "8k_classified.parquet")
    ev = out[out.kind.isin(["purchase", "sale"])].copy()
    ev.to_parquet(ROOT / "events_btc.parquet")
    cols = ["filingDate", "et", "kind", "n_btc", "usd", "avg_px", "holds", "sold", "items"]
    ev[cols].to_csv(ROOT / "events_btc.csv", index=False)
    print("8-K total:", len(out), "| btc events:", len(ev))
    print(ev.groupby([ev.et.dt.year, "kind"]).size().to_string())
    print("\nmentions not events (dates):")
    men = out[(out.kind == "mention")]
    print(men[["filingDate", "items"]].to_string(index=False))
    print("\npurchases missing a number:", int(((ev.kind == "purchase") & ev.n_btc.isna()).sum()))


if __name__ == "__main__":
    main()
