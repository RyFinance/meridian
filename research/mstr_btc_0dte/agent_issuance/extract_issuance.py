"""Recon step 2: extract the weekly capital-markets panel from Strategy 8-Ks.

Eras in the window 2024-09..2026-10:
  * narrative: prose sentences ("sold an aggregate of X Shares ... net proceeds"
    and "acquired approximately X bitcoins"), incl. explicit no-activity weeks.
  * table: "ATM Program Summary"/"Security"-row tables with Shares Sold,
    optional Notional Value, Net Proceeds, Available per instrument; BTC
    Acquired table; (2026+) preferred repurchase tables.

Outputs (derived only): issuance_panel_raw.csv (per filing x period x security),
issuance_btc_raw.csv, issuance_repurchase_raw.csv, extraction_log.csv.
"""
from __future__ import annotations

import re
import time
import warnings
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
HERE = Path(__file__).resolve().parent
INDEX = HERE / "filings_index.csv"
CACHE_DIR = Path("/private/var/folders/90/ddskxhqn2k30py1w250kbq1r0000gn/T/opencode/mstr_8k_cache")
SEC_BASE = "https://www.sec.gov"
SEC_HEADERS = {"User-Agent": "CCP academic event-study research contact@example.com"}

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
PERIOD_RE = re.compile(rf"During\s*Period\s*({MONTH}\s+\d{{1,2}},\s*\d{{4}})\s*to\s*({MONTH}\s+\d{{1,2}},\s*\d{{4}})", re.I)
SEC_RE = re.compile(r"^(STRF|STRC|STRK|STRD|MSTR|Common)(?:\s+(?:ATM|Stock))?(?=\s|$)", re.I)
SHARES_RE = re.compile(r"^([\d,]+)\s+(?:[A-Z][A-Za-z]*\s+)*Shares?$|^([\d,]+)$", re.I)
NUM_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(million|billion)?")


def clean_text(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" ")).strip()


def parse_money(s: str) -> float | None:
    """Cell -> value in $ millions. None means explicit dash/zero marker. NaN means unknown."""
    t = str(s).replace("\xa0", " ").replace("−", "-").strip()
    t = re.sub(r"\(\d+\)", "", t).strip()  # footnote refs
    t = t.replace("$", "").strip()
    if t in {"", "-", "—", "–", "N/A"}:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(million|billion)?", t)
    if not m:
        return np.nan
    v = float(m.group(1).replace(",", ""))
    if m.group(2) == "billion":
        v *= 1000
    elif m.group(2) == "million":
        pass
    return v


def parse_shares(s: str) -> int | None:
    t = str(s).replace("\xa0", " ").strip()
    if t in {"", "-", "—", "–"}:
        return None
    m = re.match(r"^([\d,]+)(?:\s+\w+)?(\s+Shares?)?$", t)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"^([\d,]+)\s", t)
    return int(m.group(1).replace(",", "")) if m else np.nan


def header_label(cell: str) -> str | None:
    flat = re.sub(r"\s+", "", str(cell)).lower()
    if "sharessold" in flat:
        return "shares"
    if "notional" in flat:
        return "notional"
    if "netproceeds" in flat or ("proceeds" in flat and "available" not in flat):
        return "proceeds"
    if "available" in flat:
        return "available"
    return None


def column_labels(rows: list[list[str]], hdr_idx: int) -> dict[int, str]:
    """Map column position -> field using header rows around hdr_idx (spanned headers repeat)."""
    labels: dict[int, str] = {}
    for r in rows[max(0, hdr_idx - 1): hdr_idx + 2]:
        for ci, cell in enumerate(r):
            lab = header_label(cell)
            if lab:
                labels[ci] = lab
    # inherit for unlabeled columns from nearest labeled column to the left
    width = max((len(r) for r in rows), default=0)
    last = None
    filled = {}
    for ci in range(width):
        if ci in labels:
            last = labels[ci]
        filled[ci] = last
    return filled


def table_era_parse(tables: list[pd.DataFrame], notes: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    sales, btcs, reps = [], [], []
    for ti, table in enumerate(tables):
        v = table.fillna("").astype(str)
        rows = [[re.sub(r"\s+", " ", c.strip()) for c in v.iloc[r].tolist()] for r in range(len(v))]
        joined_flat = re.sub(r"\s+", "", " ".join(" ".join(r) for r in rows)).lower()
        is_atm = "sharessold" in joined_flat and ("netproceeds" in joined_flat or "available" in joined_flat)
        is_btc = "btcacquired" in joined_flat
        is_rep = "sharesrepurchased" in joined_flat
        if not (is_atm or is_btc or is_rep):
            continue
        periods = []
        for r in rows:
            p = PERIOD_RE.search(" ".join(r))
            if p:
                per = (p.group(1), p.group(2))
                if per not in periods:
                    periods.append(per)
        if not periods:
            notes.append(f"t{ti}:noperiod")
            continue
        if len(periods) > 1:
            notes.append(f"t{ti}:multi")
        per = periods[0]
        start, end = pd.Timestamp(per[0]), pd.Timestamp(per[1])

        if is_atm:
            hdr = next((i for i, r in enumerate(rows) if "sharessold" in re.sub(r"\s+", "", " ".join(r)).lower()), None)
            labels = column_labels(rows, hdr) if hdr is not None else {}
            for r in rows:
                first = next((c for c in r if c.strip()), "")
                first_clean = re.sub(r"\(\d+\)", "", first).strip()
                m = SEC_RE.match(first_clean)
                if not m:
                    continue
                sec = m.group(1).upper()
                if sec == "COMMON":
                    sec = "MSTR"
                rec = {"segment_start": start, "segment_end": end, "security": sec, "shares": None,
                       "notional_musd": None, "proceeds_musd": None, "available_musd": None, "fields": {}}
                for ci, cell in enumerate(r):
                    c = cell.strip()
                    if not c or c == "$" or ci == 0:
                        continue
                    lab = labels.get(ci)
                    if lab == "shares":
                        sh = parse_shares(c)
                        if sh is not None and not (isinstance(sh, float) and np.isnan(sh)):
                            rec["shares"] = 0 if rec["shares"] is None else rec["shares"]
                            if sh > 0:
                                rec["shares"] = sh
                        elif c in {"-", "—"}:
                            rec["shares"] = 0
                    elif lab in ("notional", "proceeds", "available"):
                        val = parse_money(c)
                        if val is not None and not (isinstance(val, float) and np.isnan(val)):
                            rec[f"{lab}_musd"] = val
                            rec["fields"][lab] = ci
                        elif val is None and c in {"-", "—", "–"}:
                            rec[f"{lab}_musd"] = 0.0
                            rec["fields"][lab] = ci
                if rec["shares"] is not None or rec["notional_musd"] is not None or rec["proceeds_musd"] is not None or rec["available_musd"] is not None:
                    if rec["shares"] is None:
                        rec["shares"] = 0  # row present but dash not caught
                    sales.append(rec)

        if is_btc:
            hdr = next((i for i, r in enumerate(rows) if "btcacquired" in re.sub(r"\s+", "", " ".join(r)).lower()), None)
            btc_labels: dict[int, tuple[str, float]] = {}
            if hdr is not None:
                for r in rows[max(0, hdr - 1): hdr + 2]:
                    for ci, cell in enumerate(r):
                        flat = re.sub(r"\s+", "", str(cell)).lower()
                        if "btcacquired" in flat and ci not in btc_labels:
                            btc_labels[ci] = ("qty", 1.0)
                        elif "aggregatepurchaseprice" in flat and ci not in btc_labels:
                            btc_labels[ci] = ("cost", 1000.0 if "billions" in flat else 1.0)
                        elif "averagepurchaseprice" in flat and ci not in btc_labels:
                            btc_labels[ci] = ("avg", 1.0)
                        elif "aggregatebtcholdings" in flat and ci not in btc_labels:
                            btc_labels[ci] = ("holdings", 1.0)
                width = max((len(r) for r in rows), default=0)
                filled, last = {}, None
                for ci in range(width):
                    if ci in btc_labels:
                        last = btc_labels[ci]
                    if last is not None:
                        filled[ci] = last
                btc_labels = filled
            value_rows = ([rows[hdr]] if hdr is not None else []) + [rows[rj] for rj in range((hdr or 0) + 1, min((hdr or 0) + 3, len(rows)))]
            for cr in value_rows:
                nums = []
                for c in cr:
                    cc = c.strip()
                    if not cc or cc == "$":
                        continue
                    vv = parse_money(cc)
                    if vv is None and cc in {"-", "—", "–"}:
                        nums.append(0.0)
                    elif vv is not None and not (isinstance(vv, float) and np.isnan(vv)):
                        nums.append(vv)
                if not nums:
                    continue
                rec_b = {"segment_start": start, "segment_end": end, "btc_qty": None, "btc_cost_musd": None, "btc_avg_price": None,
                         "raw": " | ".join(c for c in cr if c.strip())[:220]}
                if btc_labels:
                    for ci, cell in enumerate(cr):
                        cc = cell.strip()
                        if not cc or cc == "$" or ci not in btc_labels:
                            continue
                        field, mult = btc_labels[ci]
                        vv = parse_money(cc)
                        if vv is None and cc in {"-", "—", "–"}:
                            vv = 0.0
                        if vv is None or (isinstance(vv, float) and np.isnan(vv)):
                            continue
                        if field == "qty" and rec_b["btc_qty"] is None:
                            rec_b["btc_qty"] = int(vv)
                        elif field == "cost" and rec_b["btc_cost_musd"] is None:
                            rec_b["btc_cost_musd"] = vv * mult
                        elif field == "avg" and rec_b["btc_avg_price"] is None:
                            rec_b["btc_avg_price"] = vv
                if rec_b["btc_qty"] is None:
                    rec_b["btc_qty"] = int(nums[0])
                if rec_b["btc_cost_musd"] is None and len(nums) > 1:
                    rec_b["btc_cost_musd"] = nums[1]
                if rec_b["btc_avg_price"] is None and len(nums) > 2:
                    rec_b["btc_avg_price"] = nums[2]
                btcs.append(rec_b)
                break

        if is_rep:
            hdr = next((i for i, r in enumerate(rows) if "sharesrepurchased" in re.sub(r"\s+", "", " ".join(r)).lower()), None)
            for r in rows:
                first = next((c for c in r if c.strip()), "")
                first_clean = re.sub(r"\(\d+\)", "", first).strip()
                m = SEC_RE.match(first_clean)
                if not m:
                    continue
                sec = m.group(1).upper()
                if sec == "COMMON":
                    sec = "MSTR"
                shares, cost = None, None
                for ci, cell in enumerate(r):
                    c = cell.strip()
                    if not c or c == "$" or ci == 0:
                        continue
                    sh = parse_shares(c)
                    if shares is None and sh is not None and not (isinstance(sh, float) and np.isnan(sh)):
                        shares = sh
                        continue
                    val = parse_money(c)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        cost = val
                    elif c in {"-", "—", "–"}:
                        cost = 0.0
                if shares is not None or cost is not None:
                    reps.append({"segment_start": start, "segment_end": end, "security": sec,
                                 "shares": shares if shares is not None else 0, "cost_musd": cost if cost is not None else 0.0})
    return sales, btcs, reps


def narrative_parse(text: str) -> dict:
    rec: dict = {}
    m = re.search(r"during the period between\s+(" + MONTH + r"\s+\d{1,2},\s*\d{4})\s+and\s+(" + MONTH + r"\s+\d{1,2},\s*\d{4})", text, flags=re.I)
    if m:
        rec["segment_start"], rec["segment_end"] = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2))
    m = re.search(r"sold an aggregate of\s+([\d,]+)\s+Shares.{0,400}?net proceeds.{0,80}?\$?\s*([\d.]+)\s*(billion|million)", text, flags=re.I | re.S)
    if m:
        rec["common_shares_sold"] = int(m.group(1).replace(",", ""))
        rec["common_net_proceeds_musd"] = float(m.group(2)) * (1000 if m.group(3).lower() == "billion" else 1)
    m = re.search(r"acquired approximately\s+([\d,]+)\s+bitcoins? for approximately\s+\$?\s*([\d.]+)\s*(billion|million).{0,300}?average price of approximately\s+\$?\s*([\d,]+)", text, flags=re.I | re.S)
    if m:
        rec["btc_qty"] = int(m.group(1).replace(",", ""))
        rec["btc_cost_musd"] = float(m.group(2)) * (1000 if m.group(3).lower() == "billion" else 1)
        rec["btc_avg_price"] = float(m.group(4).replace(",", ""))
    m = re.search(r"approximately\s+\$?\s*([\d.]+)\s*(billion|million)\s+of Shares remained available", text, flags=re.I)
    if m:
        rec["common_available_musd"] = float(m.group(1)) * (1000 if m.group(2).lower() == "billion" else 1)
    m = re.search(r"sold an aggregate of\s+([\d,]+)\s+(STRF|STRC|STRK|STRD)\s+Shares.{0,400}?net proceeds.{0,80}?\$?\s*([\d.]+)\s*(billion|million)", text, flags=re.I | re.S)
    if m:
        rec["pref_sales"] = [(m.group(2).upper(), int(m.group(1).replace(",", "")), float(m.group(3)) * (1000 if m.group(4).lower() == "billion" else 1))]
    low = text.lower()
    no_sell = re.search(r"did not sell any shares|no shares were (?:issued|sold)|did not issue any shares", low)
    no_buy = re.search(r"did not (?:purchase|acquire) any bitcoin|no bitcoins? were (?:purchased|acquired)", low)
    if "common_shares_sold" not in rec and no_sell:
        rec["common_shares_sold"] = 0
    if "btc_qty" not in rec and no_buy:
        rec["btc_qty"] = 0
    return rec


def classify_other(text: str) -> str:
    low = text.lower()
    if "convertible senior notes" in low and ("offering" in low or "notes due" in low):
        if "repurchase" in low:
            return "convertible_repurchase"
        return "convertible_issue"
    if "repurchase" in low and "notes" in low:
        return "convertible_repurchase"
    if "atm" in low and ("sales agreement" in low or "at-the-market" in low):
        return "sales_agreement_or_atm_event"
    if "dividend" in low:
        return "dividend"
    if "annual meeting" in low or "special meeting" in low or "proxy statement" in low:
        return "shareholder_meeting"
    if "bitcoin" in low or "btc" in low:
        return "bitcoin_related_other"
    return "other"


def parse_blob(html: str):
    text = clean_text(html)
    table_error = ""
    try:
        tables = pd.read_html(StringIO(html))
    except Exception as exc:  # noqa: BLE001 - record and continue for QA
        tables = []
        table_error = str(exc)[:120]
    narrative = narrative_parse(text)
    got_narrative = (narrative.get("common_shares_sold") is not None) or (narrative.get("btc_qty") is not None) or ("btc_cost_musd" in narrative)
    notes: list[str] = []
    sales, btcs, reps = table_era_parse(tables, notes) if tables else ([], [], [])
    return text, narrative, got_narrative, notes, sales, btcs, reps, table_error


def emit(era, source, f, text, narrative, notes, sales, btcs, reps, table_error, panel, btcs_out, reps_out, log):
    if sales or btcs or reps:
        era = "table"
        for s in sales:
            panel.append({
                "filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession,
                "era": era, "segment_start": s["segment_start"], "segment_end": s["segment_end"],
                "security": s["security"], "shares": s["shares"], "notional_musd": s["notional_musd"],
                "proceeds_musd": s["proceeds_musd"], "available_musd": s["available_musd"],
                "fields": ";".join(f"{k}:{v}" for k, v in sorted(s["fields"].items())),
            })
        for b in btcs:
            btcs_out.append({"filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession,
                             "era": era, "segment_start": b["segment_start"], "segment_end": b["segment_end"],
                             "btc_qty": b["btc_qty"], "btc_cost_musd": b["btc_cost_musd"], "btc_avg_price": b["btc_avg_price"],
                             "raw": b["raw"]})
        for r in reps:
            reps_out.append({"filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession,
                             "segment_start": r["segment_start"], "segment_end": r["segment_end"],
                             "security": r["security"], "shares": r["shares"], "cost_musd": r["cost_musd"]})
        log.append({"filing_date": f.filing_date, "accession": f.accession, "items": f["items"], "era": era,
                    "source": source, "notes": ";".join(notes)[:160], "table_error": table_error})
        return
    got_narrative = (narrative.get("common_shares_sold") is not None) or (narrative.get("btc_qty") is not None) or ("btc_cost_musd" in narrative)
    if got_narrative:
        era = "narrative"
        panel.append({
            "filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession,
            "era": era, "segment_start": narrative.get("segment_start"), "segment_end": narrative.get("segment_end"),
            "security": "MSTR",
            "shares": narrative.get("common_shares_sold"),
            "notional_musd": None, "proceeds_musd": narrative.get("common_net_proceeds_musd"),
            "available_musd": narrative.get("common_available_musd"), "fields": "",
        })
        for (sec, sh, pr) in narrative.get("pref_sales", []):
            panel.append({
                "filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession,
                "era": era, "segment_start": narrative.get("segment_start"), "segment_end": narrative.get("segment_end"),
                "security": sec, "shares": sh, "notional_musd": None, "proceeds_musd": pr, "available_musd": None, "fields": "",
            })
        if narrative.get("btc_qty") is not None or "btc_cost_musd" in narrative:
            btcs_out.append({
                "filing_date": f.filing_date, "acceptance_utc": f["acceptance_utc"], "accession": f.accession, "era": era,
                "segment_start": narrative.get("segment_start"), "segment_end": narrative.get("segment_end"),
                "btc_qty": narrative.get("btc_qty"), "btc_cost_musd": narrative.get("btc_cost_musd"),
                "btc_avg_price": narrative.get("btc_avg_price"), "raw": "",
            })
        log.append({"filing_date": f.filing_date, "accession": f.accession, "items": f["items"], "era": era,
                    "source": source, "notes": ";".join(notes)[:160], "table_error": table_error})
        return
    log.append({"filing_date": f.filing_date, "accession": f.accession, "items": f["items"], "era": "",
                "source": source,
                "notes": ("narrative=" + "|".join(sorted(narrative)) if narrative else "") + (";" + ";".join(notes) if notes else ""),
                "table_error": table_error, "subtype": classify_other(text)})


def fetch_exhibit(accession: str) -> Path | None:
    """Download the press-release exhibit (*ex99*.htm) for an accession, cached in scratch."""
    nodash = accession.replace("-", "")
    cands = sorted(CACHE_DIR.glob(f"EXH_{accession}_*"))
    if cands:
        return cands[0]
    try:
        idxj = requests.get(f"{SEC_BASE}/Archives/edgar/data/1050446/{nodash}/index.json", headers=SEC_HEADERS, timeout=30).json()
        time.sleep(0.12)
    except requests.RequestException:
        return None
    names = [x["name"] for x in idxj.get("directory", {}).get("item", [])]
    ex = [n for n in names if n.lower().endswith((".htm", ".html")) and "ex99" in n.lower()]
    if not ex:
        return None
    name = ex[0]
    p = CACHE_DIR / f"EXH_{accession}_{name}"
    if not p.exists():
        try:
            r = requests.get(f"{SEC_BASE}/Archives/edgar/data/1050446/{nodash}/{name}", headers=SEC_HEADERS, timeout=30)
            r.raise_for_status()
            time.sleep(0.12)
            p.write_text(r.text, encoding="utf-8", errors="replace")
        except requests.RequestException:
            return None
    return p


def main() -> None:
    idx = pd.read_csv(INDEX)
    panel, btcs_out, reps_out, log = [], [], [], []
    for _, f in idx.iterrows():
        html = Path(f.local_path).read_text()
        text, narrative, got_narrative, notes, sales, btcs, reps, table_error = parse_blob(html)
        source = "primary"
        if not (sales or btcs or reps or got_narrative):
            low = text.lower()
            if "press release" in low and ("atm" in low or "at-the-market" in low or "bitcoin" in low):
                p = fetch_exhibit(f.accession)
                if p is not None:
                    ex_html = p.read_text()
                    t2, n2, g2, no2, s2, b2, r2, te2 = parse_blob(ex_html)
                    if s2 or b2 or r2 or g2:
                        text, narrative, got_narrative, notes, sales, btcs, reps, table_error = t2, n2, g2, no2, s2, b2, r2, te2
                        source = "exhibit"
        emit("", source, f, text, narrative, notes, sales, btcs, reps, table_error, panel, btcs_out, reps_out, log)

    pd.DataFrame(panel).to_csv(HERE / "issuance_panel_raw.csv", index=False)
    pd.DataFrame(btcs_out).to_csv(HERE / "issuance_btc_raw.csv", index=False)
    pd.DataFrame(reps_out).to_csv(HERE / "issuance_repurchase_raw.csv", index=False)
    logdf = pd.DataFrame(log)
    logdf.to_csv(HERE / "extraction_log.csv", index=False)
    print("filings:", len(logdf))
    print("era counts:", logdf.era.replace("", "(none)").value_counts().to_dict())
    print("unparsed:")
    print(logdf[logdf.era == ""][["filing_date", "accession", "items", "subtype", "notes", "table_error"]].to_string(index=False))


if __name__ == "__main__":
    main()
