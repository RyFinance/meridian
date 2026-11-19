"""Review pass: extract decision-relevant text from cached SEC primary documents.

Writes a compact review file (no prices, no returns) that the ledger step reads.
For 8-Ks: prints the body of Item 1.01/1.02/2.03/3.02/5.03/7.01/8.01 headings.
For prospectus-type forms: prints the offering headline line(s).
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
OUT = HERE / "review_extracts.txt"

INDEX = ["1.01", "1.02", "2.03", "3.02", "5.03", "7.01", "8.01"]
ITEM_RE = re.compile(r"Item\s+(?:%s)\b" % "|".join(i.replace(".", r"\.") for i in INDEX))


def clean(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def extract_items(text: str) -> str:
    hits = list(ITEM_RE.finditer(text))
    if not hits:
        return ""
    parts = []
    for m in hits:
        seg = text[m.start() : m.start() + 700]
        parts.append(seg)
        if len(parts) >= 6:
            break
    return " ||| ".join(parts)


def extract_headline(text: str) -> str:
    m = re.search(r"(Up to \$[0-9.,]+[^.]{0,160})", text)
    head = m.group(1) if m else ""
    m2 = re.search(
        r"((?:Prospectus Supplement|Pricing Supplement)[^A-Z]{0,40}(?:\n)?[A-Z][^\n]{0,200})",
        text,
    )
    sub = m2.group(1) if m2 else ""
    caps = re.search(r"((?:Up to )?\$[0-9.,]+ (?:billion|million)?[^.]{0,120})", text)
    amount = caps.group(1) if caps else ""
    return " | ".join(x for x in [head, sub, amount] if x)[:600]


def main() -> None:
    scan = pd.read_csv(HERE / "source_scan.csv")
    lines: list[str] = []
    for _, row in scan.iterrows():
        path = HERE / row["local_cache"]
        if not path.exists():
            lines.append(f"== {row['filing_date']} {row['form']} {row['accession']} MISSING-CACHE")
            continue
        text = clean(path)
        if row["form"] == "8-K":
            body = extract_items(text)
            lines.append(
                f"== {row['filing_date']} {row['form']} {row['accession']} items={row['items']}\n{body[:2000]}\n"
            )
        else:
            body = extract_headline(text)
            lines.append(
                f"== {row['filing_date']} {row['form']} {row['accession']}\n{body[:800]}\n"
            )
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} filings)")


if __name__ == "__main__":
    main()
