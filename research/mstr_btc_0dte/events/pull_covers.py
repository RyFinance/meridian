"""Download 10-Q/10-K cover pages (2020+) and extract shares outstanding (class A + class B) as-filed.
Saves events/covers/*.htm and events/share_anchors.csv. Also scans 8-K texts for ATM sale deltas.
"""
from __future__ import annotations
import json, re, time, html, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
COV = ROOT / "covers"; COV.mkdir(exist_ok=True)
UA = "quant_v7-research (contact: research@example.com)"


def fetch(url: str, tries: int = 4) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def to_text(raw: bytes) -> str:
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", t)


def main():
    frames = []
    for fn in [ROOT / "sub.json", ROOT / "CIK0001050446-submissions-001.json"]:
        j = json.load(open(fn))
        rec = j["filings"]["recent"] if "filings" in j else j
        frames.append(pd.DataFrame(rec)[["accessionNumber", "filingDate", "form", "primaryDocument"]])
    allf = pd.concat(frames).drop_duplicates("accessionNumber")
    allf["filingDate"] = pd.to_datetime(allf["filingDate"])
    q = allf[(allf.form.isin(["10-Q", "10-K"])) & (allf.filingDate >= "2020-01-01")].sort_values("filingDate")
    rows = []
    for _, r in q.iterrows():
        f = COV / f"{r.accessionNumber}.htm"
        url = f"https://www.sec.gov/Archives/edgar/data/1050446/{r.accessionNumber.replace('-', '')}/{r.primaryDocument}"
        if not f.exists():
            try:
                f.write_bytes(fetch(url))
            except Exception as e:
                print("FAIL", r.accessionNumber, e); continue
            time.sleep(1 / 6)
        t = to_text(f.read_bytes())
        m = re.search(
            r"As of ([A-Z][a-z]+ \d{1,2}, \d{4})[^.]{0,80}?registrant had "
            r"([\d,]{5,})\s*(?:and\s+([\d,]{5,})\s*)?shares of class A common stock"
            r"(?:\s*and\s*([\d,]{5,})\s*shares of class B common stock)?", t)
        if m:
            asof, a1, a2, b = m.group(1), m.group(2), m.group(3), m.group(4)
            # two phrasings: "X and Y shares of class A and class B" (a2 is B) or "X shares of class A and Y shares of class B" (b is B)
            classA = float(a1.replace(",", ""))
            classB = float((a2 or b or "0").replace(",", ""))
        else:
            asof = classA = classB = None
        rows.append(dict(filingDate=r.filingDate, form=r.form, accession=r.accessionNumber,
                         asof=asof, classA=classA, classB=classB))
    S = pd.DataFrame(rows)
    S["total"] = S.classA.fillna(0) + S.classB.fillna(0)
    S.to_csv(ROOT / "share_anchors.csv", index=False)
    print(S.to_string(index=False))


if __name__ == "__main__":
    main()
