"""Sample data.sec.gov/submissions/{CIK}.json for a curated CIK list. This host is
reachable (unlike www.sec.gov/Archives) and returns, per filing: form type, filingDate,
acceptanceDateTime (to the second), and -- for 8-K -- the "items" (e.g. "2.02,9.01").
Used to characterize: 8-K item-code breadth and after-hours-vs-intraday timing, Form 144 /
SC 13D / SC 13G / NT 10-K presence and cadence, 13F-HR filing history for known
institutions, and Form 3/4/5 presence (cross-checked against the bulk sample).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.sample_submissions
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from research.edgar_scout.cik_sample import ALL
from research.edgar_scout.common import DATA_DIR, Manifest, get

ITEM_CODES_OF_INTEREST = {"1.01", "1.03", "2.02", "2.05", "2.06", "3.01", "5.02", "7.01", "8.01"}


def et_hour_from_utc_iso(iso: str) -> int | None:
    """Cheap UTC->ET hour (ignores DST edge days; fine for an after-hours/intraday split)."""
    if not iso:
        return None
    try:
        hour_utc = int(iso[11:13])
    except (ValueError, IndexError):
        return None
    return (hour_utc - 4) % 24  # approx EDT offset; good enough to classify pre/post 16:00 ET


def main() -> None:
    manifest = Manifest()
    resolved, unresolved = {}, []
    item_hits = Counter()
    item_timing = defaultdict(lambda: {"during_0930_1600": 0, "after_hours_or_premarket": 0})
    form_counts_by_bucket = defaultdict(Counter)
    form144_sample, thirteend_g_sample, nt_sample = [], [], []
    thirteenf_hr_by_label = defaultdict(lambda: {"count": 0, "min_period": None, "max_period": None,
                                                   "min_filed": None, "max_filed": None,
                                                   "by_form": Counter()})
    insider_form_counts = Counter()

    for label, cik in ALL.items():
        bucket = label.split("/")[0]
        cik10 = str(cik).zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
        resp = get(url)
        if resp.status_code != 200:
            unresolved.append({"label": label, "cik": cik, "status": resp.status_code})
            manifest.record_refusal(f"submissions/{label.replace('/', '_')}", url, resp.status_code,
                                     resp.text)
            print(f"{label:40s} CIK {cik}: HTTP {resp.status_code}")
            continue
        d = resp.json()
        manifest.record_bytes(f"submissions/{label.replace('/', '_')}.json", url, resp.content, 200)
        name = d.get("name", "")
        resolved[label] = {"cik": cik, "name": name, "tickers": d.get("tickers", []),
                            "sic_description": d.get("sicDescription", ""),
                            "n_recent_filings": len(d["filings"]["recent"]["form"])}
        recent = d["filings"]["recent"]
        n = len(recent["form"])
        for i in range(n):
            form = recent["form"][i]
            form_counts_by_bucket[bucket][form] += 1
            items = recent.get("items", [""] * n)[i]
            acc_dt = recent.get("acceptanceDateTime", [""] * n)[i]
            if form == "8-K" and items:
                for code in items.split(","):
                    code = code.strip()
                    if code in ITEM_CODES_OF_INTEREST:
                        item_hits[code] += 1
                        hr = et_hour_from_utc_iso(acc_dt)
                        key = "during_0930_1600" if (hr is not None and 9 <= hr < 16) else "after_hours_or_premarket"
                        item_timing[code][key] += 1
            if form in ("144", "144/A") and len(form144_sample) < 15:
                form144_sample.append({"label": label, "filingDate": recent["filingDate"][i],
                                        "acceptanceDateTime": acc_dt})
            if form.startswith("SC 13D") or form.startswith("SC 13G"):
                insider_form_counts[form] += 1
                if len(thirteend_g_sample) < 15:
                    thirteend_g_sample.append({"label": label, "form": form,
                                                "filingDate": recent["filingDate"][i]})
            if form.startswith("NT 10-"):
                nt_sample.append({"label": label, "form": form, "filingDate": recent["filingDate"][i]})
            if form in ("13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A"):
                agg = thirteenf_hr_by_label[label]
                agg["count"] += 1
                agg["by_form"][form] += 1
                fd, pr = recent["filingDate"][i], recent["reportDate"][i]
                agg["min_filed"] = fd if agg["min_filed"] is None else min(agg["min_filed"], fd)
                agg["max_filed"] = fd if agg["max_filed"] is None else max(agg["max_filed"], fd)
                if pr:
                    agg["min_period"] = pr if agg["min_period"] is None else min(agg["min_period"], pr)
                    agg["max_period"] = pr if agg["max_period"] is None else max(agg["max_period"], pr)
            if form in ("3", "4", "5", "3/A", "4/A", "5/A"):
                insider_form_counts[form] += 1
                insider_form_counts["_total_345"] += 1

    out = {
        "resolved": resolved,
        "unresolved": unresolved,
        "resolution_rate": len(resolved) / len(ALL),
        "item_code_hits_8K": dict(item_hits),
        "item_code_timing_8K": {k: v for k, v in item_timing.items()},
        "form_counts_by_bucket": {k: dict(v) for k, v in form_counts_by_bucket.items()},
        "form144_sample": form144_sample,
        "sc13d_13g_sample": thirteend_g_sample,
        "sc13d_13g_counts": {k: v for k, v in insider_form_counts.items() if k.startswith("SC")},
        "nt_late_filing_sample": nt_sample,
        "13f_hr_history_by_label": {k: {**v, "by_form": dict(v["by_form"])}
                                     for k, v in thirteenf_hr_by_label.items()},
        "form345_counts_in_recent_1000": {k: v for k, v in insider_form_counts.items()
                                           if k in ("3", "4", "5", "3/A", "4/A", "5/A", "_total_345")},
    }
    (DATA_DIR / "submissions_sample.json").write_text(json.dumps(out, indent=1, default=str))
    manifest.write(DATA_DIR / "submissions" / "manifest.json")
    print(f"resolved {len(resolved)}/{len(ALL)} CIKs; unresolved: {[u['label'] for u in unresolved]}")
    print("8-K item hits:", dict(item_hits))


if __name__ == "__main__":
    main()
