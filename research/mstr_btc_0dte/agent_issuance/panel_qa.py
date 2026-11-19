"""QA anchors for the descriptive weekly issuance panel (agent_issuance/).

Five hand-picked anchor filings are re-checked against the extracted CSVs
(`issuance_panel_raw.csv`, `issuance_btc_raw.csv`, `issuance_repurchase_raw.csv`)
and, when the scratch SEC body cache exists, against the raw filing text.
This is QA for a descriptive artifact: it computes no returns and supports no
hypothesis. Anchor values were taken by hand from the filings during the
2026-10-17 review, covering the table eras: narrative (2024-11-18), zero-common
week (2025-06-16), merged-cell variant (2026-03-09), two-segment weeks
(2026-04-06, 2026-10-05).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = Path("/private/var/folders/90/ddskxhqn2k30py1w250kbq1r0000gn/T/opencode/mstr_8k_cache")
TOL = 0.05  # million USD tolerance on the rounded filing values

ANCHORS = [
    {
        "id": "A1-2024-11-18",
        "accession": "0001193125-24-260452",
        "panel": [("MSTR", 13_593_865, 4600.0)],
        "btc": [(51_780, 4600.0)],
        "repurchase": [],
        "source_strings": ["13,593,865", "51,780", "88,627"],
        "note": "narrative era; the week that funded the 51,780 BTC purchase",
    },
    {
        "id": "A2-2025-06-16",
        "accession": "0000950170-25-086545",
        "panel": [("MSTR", 0, 0.0)],
        "btc": [(10_100, 1051.2)],
        "repurchase": [],
        "source_strings": ["10,100", "1,051.2", "104,080"],
        "note": "zero-common week (preferred-only sales)",
    },
    {
        "id": "A3-2026-03-09",
        "accession": "0001193125-26-097598",
        "panel": [("MSTR", 6_327_541, 899.5), ("STRC", 3_776_205, 377.1)],
        "btc": [(17_994, 1280.0)],
        "repurchase": [],
        "source_strings": ["6,327,541", "899.5", "3,776,205", "377.1", "17,994", "1.28"],
        "note": "merged-cell table variant week",
    },
    {
        "id": "A4-2026-04-06",
        "accession": "0001193125-26-142925",
        "panel": [("MSTR", 582_550, 72.0), ("MSTR", 593_294, 72.0)],
        "btc": [(4_871, 329.9)],
        "repurchase": [],
        "source_strings": ["582,550", "593,294", "4,871", "329.9"],
        "note": "two reporting segments in one 8-K",
    },
    {
        "id": "A5-2026-10-05",
        "accession": "0001193125-26-413164",
        "panel": [("MSTR", 92_894, 15.7)],
        "btc": [],
        "repurchase": [("STRC", 1_033_168, 102.6), ("STRC", 740_634, 73.7)],
        "source_strings": ["92,894", "15.7", "1,033,168", "102.6", "740,634", "73.7"],
        "note": "repurchase-era week; MSTR sold only in the October segment",
    },
]


def match_rows(extracted: list[tuple], expected: list[tuple]) -> list[str]:
    """Match expected tuples (…keys…, musd) against extracted rows; the final
    element is compared with tolerance, earlier elements exactly (ints for
    share/quantity fields)."""
    remaining = list(extracted)
    problems: list[str] = []
    for want in expected:
        want_key = tuple(int(v) if isinstance(v, (int, float)) else v for v in want[:-1])
        hit = None
        for row in remaining:
            row_key = tuple(int(v) if isinstance(v, (int, float)) else v for v in row[:-1])
            if row_key == want_key and abs(float(row[-1]) - float(want[-1])) <= TOL:
                hit = row
                break
        if hit is None:
            problems.append(f"expected {want}; extracted={remaining}")
        else:
            remaining.remove(hit)
    return problems


def main() -> int:
    panel = pd.read_csv(HERE / "issuance_panel_raw.csv")
    btc = pd.read_csv(HERE / "issuance_btc_raw.csv")
    rep = pd.read_csv(HERE / "issuance_repurchase_raw.csv")
    results: list[dict[str, object]] = []
    failures = 0
    for anchor in ANCHORS:
        acc = anchor["accession"]
        p_rows = panel.loc[panel.accession == acc]
        b_rows = btc.loc[btc.accession == acc]
        r_rows = rep.loc[rep.accession == acc]
        problems: list[str] = []
        if p_rows.empty:
            problems.append("no panel rows")
        else:
            problems += match_rows(
                [(r.security, r.shares, r.proceeds_musd) for r in p_rows.itertuples()], anchor["panel"]
            )
        if anchor["btc"]:
            if b_rows.empty:
                problems.append("no btc rows")
            else:
                problems += match_rows([(r.btc_qty, r.btc_cost_musd) for r in b_rows.itertuples()], anchor["btc"])
        if anchor["repurchase"]:
            if r_rows.empty:
                problems.append("no repurchase rows")
            else:
                problems += match_rows(
                    [(r.security, r.shares, r.cost_musd) for r in r_rows.itertuples()], anchor["repurchase"]
                )
        source_status = "not checked (cache absent)"
        cache_files = sorted(CACHE.glob(f"*{acc}*")) if CACHE.exists() else []
        if cache_files:
            text = " ".join(f.read_text(encoding="utf-8", errors="replace") for f in cache_files)
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
            missing = [s for s in anchor["source_strings"] if s not in text]
            source_status = "all strings found" if not missing else f"MISSING strings: {missing}"
            if missing:
                problems.append(f"source-document check failed: {missing}")
        elif CACHE.exists():
            source_status = "no cache file for accession"
        verdict = "PASS" if not problems else "FAIL"
        failures += verdict == "FAIL"
        results.append(
            {
                "anchor": anchor["id"],
                "accession": acc,
                "csv_check": "PASS" if not problems else "FAIL: " + "; ".join(problems),
                "source_doc_check": source_status,
                "note": anchor["note"],
            }
        )

    out = pd.DataFrame(results)
    lines = [
        "# Weekly issuance panel — anchor QA (descriptive artifact)",
        "",
        "Five hand-picked anchor filings re-checked against the extracted CSVs and",
        "(where the scratch SEC cache is present) the raw filing text. No returns,",
        "no hypothesis; this only documents extraction fidelity for the eras used by",
        "the descriptive panel. Anchors were taken by hand from the filings during",
        "the 2026-10-17 review before this QA was written.",
        "",
        "| Anchor | CSV extraction | Source document | Note |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(f"| {r['anchor']} | {r['csv_check']} | {r['source_doc_check']} | {r['note']} |")
    lines += [
        "",
        f"Overall: **{'PASS' if failures == 0 else f'{failures} FAILURES'}** "
        f"({len(results)} anchors; tolerance ±${TOL}M on rounded filing values; shares exact).",
        "",
    ]
    (HERE / "panel_qa_results.md").write_text("\n".join(lines), encoding="utf-8")
    print(out.to_string(index=False))
    print(f"overall failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
