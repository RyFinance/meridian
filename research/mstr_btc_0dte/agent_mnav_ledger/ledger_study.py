#!/usr/bin/env python3
"""Causal gross-BTC-mNAV ledger study for MSTR.

This is deliberately independent of the other mNAV workstreams.  It builds a
BTC-holdings ledger from the *total holdings stated in SEC-timestamped 8-K
purchase disclosures*, rather than carrying forward quarterly holdings
snapshots.  The numerator remains a gross proxy (market capitalization, not
enterprise value): it excludes debt, preferreds, operating assets, and taxes.

Research-timing conventions
----------------------------
* An 8-K or 10-Q/10-K observation first becomes usable on the first MSTR
  regular session strictly after its filing date.  This is more conservative
  than using intraday EDGAR acceptance times.
* The BTC mark is the close of the bar labelled 15:59 America/New_York.  That
  minute finishes at 16:00, alongside the MSTR closing auction.  A missing
  exact bar makes the signal unavailable; no as-of substitution is allowed.
* Signal values use that session's MSTR close and execute at the following
  regular-session MSTR open.
* Yahoo's MSTR history is split-adjusted.  SEC-reported share counts are
  multiplied by ten only when their disclosed "as of" date predates the
  2024-08-01 10-for-1 split.

The program supports a development run ending 2022-12-30 and a separately
invoked validation run.  It writes only inside this agent directory.
"""

from __future__ import annotations

import argparse
import html
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
DAILY_PATH = ROOT / "mstr_daily_yf.parquet"
BTC_PATH = Path("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
EVENT_INDEX_PATH = ROOT / "events" / "8k_all.parquet"
EVENT_DOCS = ROOT / "events" / "docs"
SHARE_ANCHORS_PATH = ROOT / "events" / "share_anchors.csv"
SHARE_COVERS = ROOT / "events" / "covers"

SPLIT_DATE = pd.Timestamp("2024-08-01")
BASELINE_SLIP_BP = 3.0
DOUBLE_SLIP_BP = 6.0
PRE_SPLIT_FEE = 0.0005  # $0.005 / ten split-adjusted shares
POST_SPLIT_FEE = 0.005
DEV_END = pd.Timestamp("2022-12-30")
VALIDATION_START = pd.Timestamp("2023-01-03")
VALIDATION_END = pd.Timestamp("2026-08-10")  # last full MSTR session before BTC source ends


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def to_text(raw: bytes) -> str:
    """A compact, deterministic HTML-to-text conversion for SEC primary docs."""
    text = raw.decode("utf-8", "ignore")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode the SEC's numeric entities (including em-space and em-dash table
    # cells) before normalizing.  This makes a no-purchase table row visibly
    # distinct from a malformed numeric row.
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


NUM = r"([0-9][0-9,]*(?:\.\d+)?)"
SHARE_COVER_PATTERN = re.compile(
    r"As\s+of\s+(?P<asof>[A-Z][a-z]+\s+\d{1,2}\s*,\s*20\d{2})\s*,?\s+"
    r"(?:the\s+)?r\s*egistrant\s+(?:had|has)\s+"
    r"(?P<class_a>\d[\d,]*)\s+(?:a\s*nd|and)\s+"
    r"(?P<class_b>\d[\d,]*)\s+shares\s+of\s+class\s+A\s+common\s+stock\s+"
    r"and\s+class\s+B\s+common\s+stock\s+outstanding\s*,?\s+respectively",
    flags=re.I,
)


def _iso_or_none(value: object) -> str | None:
    stamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(stamp) else pd.Timestamp(stamp).date().isoformat()


def parse_purchase_holding_detail(text: str) -> tuple[float | None, float | None, dict]:
    """Return current 8-K BTC fields plus source-row provenance.

    The ledger takes an explicit total-holdings statement when present.  That
    is intentionally preferred to summing purchases, which can miss an earlier
    purchase disclosure or a multi-purchase release.  An increment is retained
    only as a transparent fallback when the release gives no total.
    """
    lowered = text.lower()
    if "bitcoin" not in lowered and "bitcoins" not in lowered and " btc " not in lowered:
        return None, None, {"source_kind": "not_bitcoin"}
    # Reject financing-only 8-Ks that merely say proceeds *may* be invested,
    # while accepting the later structured BTC monetization disclosures.
    has_purchase = bool(re.search(r"\b(?:purchased|acquired|acquisition of|purchase of)\b", lowered))
    has_structured_btc_update = bool(
        re.search(r"BTC\s+(?:Acquired|Purchased|Sold)\b", text, flags=re.I)
        and re.search(r"Aggregate\s+BTC\s+Holdings", text, flags=re.I)
    )
    if not has_purchase and not has_structured_btc_update:
        return None, None, {"source_kind": "non_purchase_bitcoin_mention"}

    # From 2025 the current acquisition is frequently reported in a compact
    # BTC Update table.  A generic word/number regex sees the header footnote
    # ``BTC Acquired (1)`` before it sees the actual numeric row, so parse this
    # row first and atomically return both fields.  The field order is stable:
    # acquired BTC, aggregate purchase price, average price, aggregate BTC
    # holdings, aggregate purchase price, average price.  This accepts both
    # "in millions" and "in billions" header variants and small quantities
    # without comma separators.
    table_headers = list(re.finditer(r"BTC\s+(Acquired|Purchased|Sold)\b", text, flags=re.I))
    table_candidates: list[dict] = []
    for ordinal, header in enumerate(table_headers):
        activity_type = header.group(1).lower()
        # A single 8-K can disclose multiple weekly periods (for example when
        # a holiday splits the reporting interval).  Each row is available at
        # the same filing time, so the economically correct ledger mark is the
        # one with the *latest stated As of date*, rather than the first table
        # header encountered in the HTML text.
        end = table_headers[ordinal + 1].start() if ordinal + 1 < len(table_headers) else min(len(text), header.start() + 1800)
        table_window = text[header.start():end]
        table_window = re.split(r"\(\s*1\s*\)\s+The bitcoin purchases|Item\s+7\.01", table_window, maxsplit=1, flags=re.I)[0]
        # The final "Average Purchase Price" in the header is immediately
        # followed by the data row.  Use the last numeric token directly
        # before a dollar sign as aggregate holdings.  This handles all three
        # source forms: ordinary purchases; zero as an explicit quantity; and
        # em-dash no-purchase rows.
        holdings_header = re.search(r"Aggregate\s+BTC\s+Holdings", table_window, flags=re.I)
        if not holdings_header:
            continue
        trailing_prices = list(re.finditer(r"Average\s+Purchase\s+Price(?:\s*\([^)]*\))?", table_window[holdings_header.end():], flags=re.I))
        if not trailing_prices:
            continue
        last_price_header = trailing_prices[0]
        row_text = table_window[holdings_header.end() + last_price_header.end():]
        row_text = re.sub(r"^\s*\(\s*\d+\s*\)\s*", "", row_text)
        # Limit the scan to the compact numerical row, never prose in the
        # following financial update.
        row_text = row_text[:450]
        # Do not let the cents portion of a decimal purchase-price value (for
        # example ``47.35 $``) masquerade as a later integer field.
        holding_values = re.findall(r"(?<![\d,\.])(\d{1,3}(?:,\d{3})+|\d+)(?=\s+\$)", row_text)
        if not holding_values:
            continue
        held = float(holding_values[-1].replace(",", ""))
        stripped_row = row_text.lstrip()
        sold = None
        if activity_type == "sold":
            # Sale tables place the activity fields *before* the "As of ...
            # Aggregate BTC Holdings" header.  The holding total above is the
            # source of truth; record the sale amount for reconciliation.
            activity_prefix = table_window[:holdings_header.start()]
            sale_headers = list(re.finditer(r"Average\s+Sale\s+Price(?:\s*\([^)]*\))?", activity_prefix, flags=re.I))
            if sale_headers:
                sale_text = activity_prefix[sale_headers[-1].end():]
                sale_match = re.match(r"\s*(\d[\d,]*)\s*(?:\(\s*\d+\s*\))?\s*\$", sale_text)
                if sale_match:
                    sold = float(sale_match.group(1).replace(",", ""))
            # Some later sale tables place *all* headers before a single
            # numerical row: ``BTC Sold ... Aggregate BTC Holdings ...
            # 1,638 $... 842,138 $...``.  In that source form, the first
            # currency-adjacent integer in the bounded data row is the sales
            # quantity and the final one is the aggregate holdings total.
            # This fallback stays inside the BTC table row and is therefore
            # not allowed to consume a dollar amount from a later section.
            if sold is None and len(holding_values) >= 2:
                sold = float(holding_values[0].replace(",", ""))
            purchased = None
        elif re.match(r"[—–-](?:\s|\$|—|–|-)", stripped_row):
            purchased = 0.0
        else:
            purchase_match = re.match(r"(\d[\d,]*)\b", stripped_row)
            if not purchase_match:
                continue
            purchased = float(purchase_match.group(1).replace(",", ""))
        # Associate dates with the local table row, not merely with text
        # before its ``BTC Sold/Acquired`` header.  Source layouts differ:
        # some put ``As of ...`` before the BTC header, while the July-2026
        # multi-row sale filing puts it after the header.  The nearest
        # preceding ``During Period`` starts the row; the next such marker
        # starts a different row/table and bounds the extraction.
        # Asterisks mark a same-day 4:00 p.m. ET convention in several
        # 2026 releases.  They are footnote punctuation, not part of the
        # stated calendar date, so accept and discard them when deriving the
        # deterministic latest-row key.
        date_pat = r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})(?:\s*\*)?"
        period_pat = r"During\s+Period\s+" + date_pat + r"\s+to\s+" + date_pat
        period_scan_start = max(0, header.start() - 3000)
        prior_context = text[period_scan_start:header.start()]
        period_matches = list(re.finditer(period_pat, prior_context, flags=re.I))
        if period_matches:
            latest_period = period_matches[-1]
            period_start, period_end = latest_period.group(1), latest_period.group(2)
            row_start = period_scan_start + latest_period.start()
            # There may be another BTC update in the same filing, or an ATM
            # table immediately afterward.  Its next period label ends this
            # row's provenance scope before an unrelated financial section
            # can supply a spurious date.
            forward_limit = min(len(text), header.start() + 3000)
            next_period = re.search(period_pat, text[header.start():forward_limit], flags=re.I)
            row_end = header.start() + next_period.start() if next_period else forward_limit
            row_context = text[row_start:row_end]
            asof_values = re.findall(r"\bAs\s+of\s+" + date_pat, row_context, flags=re.I)
            asof = pd.to_datetime(asof_values[0], errors="coerce") if asof_values else pd.NaT
        else:
            local_context = text[max(0, header.start() - 1000):min(len(text), header.start() + 1500)]
            asof_values = re.findall(r"\bAs\s+of\s+" + date_pat, local_context, flags=re.I)
            period_start, period_end = None, None
            asof = pd.to_datetime(asof_values[0], errors="coerce") if asof_values else pd.NaT
        # A row without an intelligible as-of date is retained only as a
        # fallback behind dated rows, preserving deterministic source order.
        sortable_asof = pd.Timestamp.min if pd.isna(asof) else pd.Timestamp(asof)
        table_candidates.append({
            "sortable_asof": sortable_asof,
            "ordinal": ordinal,
            "purchased": purchased,
            "sold": sold,
            "held": held,
            "activity_type": "sale" if activity_type == "sold" else "purchase",
            "disclosed_period_start": _iso_or_none(period_start),
            "disclosed_period_end": _iso_or_none(period_end),
            "disclosed_as_of_date": _iso_or_none(asof),
        })
    if table_candidates:
        selected = max(table_candidates, key=lambda x: (x["sortable_asof"], x["ordinal"]))
        return selected["purchased"], selected["held"], {
            "source_kind": "btc_update_sale_table" if selected["activity_type"] == "sale" else "btc_update_table",
            "activity_type": selected["activity_type"],
            "sale_btc": selected["sold"],
            "table_selection_method": "maximum_disclosed_as_of_date_then_source_order",
            "selected_table_row_ordinal": selected["ordinal"] + 1,
            "table_row_candidate_count": len(table_candidates),
            "disclosed_period_start": selected["disclosed_period_start"],
            "disclosed_period_end": selected["disclosed_period_end"],
            "disclosed_as_of_date": selected["disclosed_as_of_date"],
        }

    purchase_patterns = [
        r"(?:purchased|acquired|acquisition of|purchase of)\s+(?:approximately\s+)?" + NUM + r"(?:\s+additional)?\s+bitcoins?",
        r"(?:approximately\s+)?" + NUM + r"\s+additional\s+bitcoins?",
    ]
    purchases: list[float] = []
    for pattern in purchase_patterns:
        for value in re.findall(pattern, text, flags=re.I):
            try:
                purchases.append(float(value.replace(",", "")))
            except ValueError:
                pass
    # Multiple regexes can see the same phrase.  Preserve non-adjacent rows in
    # a multi-purchase 8-K, but collapse adjacent duplicates.
    deduped: list[float] = []
    for value in purchases:
        if not deduped or value != deduped[-1]:
            deduped.append(value)
    purchased = float(sum(deduped)) if deduped else None

    holding_patterns = [
        r"(?:the company\s+)?holds?\s+(?:an aggregate of\s+)?(?:approximately\s+)?" + NUM + r"\s+bitcoins?",
        r"holdings\s+(?:of|to)\s+(?:approximately\s+)?" + NUM + r"\s+bitcoins?",
        r"held\s+(?:an aggregate of\s+)?(?:approximately\s+)?" + NUM + r"\s+bitcoins?",
        r"(?:holdings|hold)\s+.*?\b(?:to|of)\s+(?:approximately\s+)?" + NUM + r"\s+bitcoins?",
        # The September 2020 8-K predates the standard "holds" wording but
        # explicitly reports the cumulative purchase total.  For this first
        # ledger bridge it is functionally the same reported holding total.
        r"(?:to date,?\s+)?(?:the company\s+)?has purchased\s+a total of\s+" + NUM + r"\s+bitcoins?",
    ]
    candidates: list[tuple[int, float]] = []
    for pattern in holding_patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            try:
                candidates.append((match.start(), float(match.group(1).replace(",", ""))))
            except ValueError:
                pass
    # In a current 8-K, the last total holdings statement is normally the
    # post-purchase total.  Restrict to sane, integral-looking values.
    total = None
    if candidates:
        _, value = max(candidates, key=lambda x: x[0])
        if value > 0:
            total = value
    return purchased, total, {
        "source_kind": "narrative_purchase_disclosure",
        "activity_type": "purchase",
        "sale_btc": None,
        "table_selection_method": "not_applicable_narrative",
        "selected_table_row_ordinal": None,
        "table_row_candidate_count": 0,
        "disclosed_period_start": None,
        "disclosed_period_end": None,
        "disclosed_as_of_date": None,
    }


def parse_purchase_holding(text: str) -> tuple[float | None, float | None]:
    """Backward-compatible convenience view of ``parse_purchase_holding_detail``."""
    purchased, total, _ = parse_purchase_holding_detail(text)
    return purchased, total


def first_session_strictly_after(sessions: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | pd.NaT:
    eligible = sessions[sessions > date.normalize()]
    return eligible[0] if len(eligible) else pd.NaT


def extract_ledger(end: pd.Timestamp, sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    """Parse only SEC primary 8-K files dated no later than ``end``."""
    index = pd.read_parquet(EVENT_INDEX_PATH)
    index["filingDate"] = pd.to_datetime(index["filingDate"])
    index = index.loc[(index["filingDate"] >= "2020-08-01") & (index["filingDate"] <= end)].copy()
    index = index.sort_values(["filingDate", "acceptanceDateTime", "accessionNumber"])

    rows = []
    last_total: float | None = None
    docs_used: dict[str, str] = {}
    missing_docs: list[str] = []
    for record in index.itertuples(index=False):
        doc = EVENT_DOCS / f"{record.accessionNumber}.htm"
        if not doc.exists() or doc.stat().st_size == 0:
            missing_docs.append(record.accessionNumber)
            continue
        raw = doc.read_bytes()
        purchased, explicit_total, provenance = parse_purchase_holding_detail(to_text(raw))
        if purchased is None and explicit_total is None:
            continue
        # A structured purchase or sale update must have an explicit current
        # holding total; only a bare purchase increment may fall back to the
        # prior ledger total.  Sale increments are never subtracted on their
        # own because the filing's explicit post-sale total is the source of
        # truth.
        if explicit_total is not None:
            holdings = explicit_total
            method = "explicit_total_holdings_in_current_purchase_8k"
        elif last_total is not None and purchased is not None:
            holdings = last_total + purchased
            method = "prior_explicit_total_plus_current_purchase"
        else:
            # We cannot establish the opening ledger from a bare increment.
            # Keep this row for audit but do not make it a tradable observation.
            holdings = np.nan
            method = "unusable_increment_without_prior_explicit_total"
        if not pd.isna(holdings):
            last_total = float(holdings)
        effective = first_session_strictly_after(sessions, pd.Timestamp(record.filingDate))
        rows.append(
            {
                "filing_date": pd.Timestamp(record.filingDate).date().isoformat(),
                "acceptance_utc": str(record.acceptanceDateTime),
                "accession": record.accessionNumber,
                "items": record.items,
                "purchase_btc": purchased,
                "sale_btc": provenance.get("sale_btc"),
                "activity_type": provenance.get("activity_type"),
                "explicit_total_btc": explicit_total,
                "ledger_btc": holdings,
                "ledger_method": method,
                "effective_session": effective.date().isoformat() if not pd.isna(effective) else None,
                "source_kind": provenance.get("source_kind"),
                "table_selection_method": provenance.get("table_selection_method"),
                "selected_table_row_ordinal": provenance.get("selected_table_row_ordinal"),
                "table_row_candidate_count": provenance.get("table_row_candidate_count"),
                "disclosed_period_start": provenance.get("disclosed_period_start"),
                "disclosed_period_end": provenance.get("disclosed_period_end"),
                "disclosed_as_of_date": provenance.get("disclosed_as_of_date"),
                "source_primary_document": str(doc.relative_to(REPO)),
                "source_sha256": sha256(doc),
            }
        )
        docs_used[record.accessionNumber] = sha256(doc)
    ledger = pd.DataFrame(rows)
    if ledger.empty:
        raise RuntimeError("No usable BTC purchase-ledger observations were parsed")
    # Same-day multiple filings: only the final accepted filing can be the end
    # of day ledger mark.  Each row already has a complete SEC timestamp.
    ledger["acceptance_utc_ts"] = pd.to_datetime(ledger["acceptance_utc"], utc=True)
    ledger = ledger.sort_values(["effective_session", "acceptance_utc_ts", "accession"]).reset_index(drop=True)
    source_meta = {
        "event_index": str(EVENT_INDEX_PATH),
        "event_index_sha256": sha256(EVENT_INDEX_PATH),
        "documents_used": docs_used,
        "missing_primary_docs_in_requested_date_range": missing_docs,
        "ledger_rule": "explicit current BTC holdings (purchase, no-purchase, or sale update) supersede prior total; only a bare purchase increment after an explicit total is added",
    }
    return ledger, source_meta


def parse_share_cover_detail(doc: Path) -> dict:
    """Extract the sole Class A/B count sentence from an official SEC cover."""
    if not doc.exists() or doc.stat().st_size == 0:
        raise RuntimeError(f"Missing SEC share-cover document: {doc}")
    matches = list(SHARE_COVER_PATTERN.finditer(to_text(doc.read_bytes())))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one Class A/B cover-count sentence in {doc.name}; found {len(matches)}"
        )
    match = matches[0]
    asof = pd.to_datetime(match.group("asof"), errors="coerce")
    class_a = float(match.group("class_a").replace(",", ""))
    class_b = float(match.group("class_b").replace(",", ""))
    if pd.isna(asof) or class_a <= 0 or class_b <= 0:
        raise RuntimeError(f"Invalid Class A/B share count parsed from {doc.name}")
    return {
        "asof": pd.Timestamp(asof),
        "classA": class_a,
        "classB": class_b,
        "total": class_a + class_b,
        "cover_parse_match_count": len(matches),
        "source_primary_document": str(doc.relative_to(REPO)),
        "source_sha256": sha256(doc),
    }


def load_share_anchors(end: pd.Timestamp, sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    """Use primary-cover Class A + B counts only after their SEC filing.

    ``share_anchors.csv`` provides the filing/date/accession index, but every
    numerical value is re-extracted from its cached primary SEC cover page.
    This fails closed on a missing or ambiguous cover sentence, rather than
    silently forward-filling a malformed zero value from a derivative table.
    """
    index = pd.read_csv(SHARE_ANCHORS_PATH)
    index["filingDate"] = pd.to_datetime(index["filingDate"])
    index = index.loc[index["filingDate"] <= end].copy()
    source_rows: list[dict] = []
    documents_used: dict[str, str] = {}
    for record in index.itertuples(index=False):
        doc = SHARE_COVERS / f"{record.accession}.htm"
        parsed = parse_share_cover_detail(doc)
        index_asof = pd.to_datetime(record.asof, errors="coerce")
        index_class_a = pd.to_numeric(record.classA, errors="coerce")
        index_class_b = pd.to_numeric(record.classB, errors="coerce")
        index_total = pd.to_numeric(record.total, errors="coerce")
        index_matches_cover = bool(
            not pd.isna(index_asof)
            and index_asof.normalize() == parsed["asof"].normalize()
            and not pd.isna(index_class_a)
            and not pd.isna(index_class_b)
            and not pd.isna(index_total)
            and float(index_class_a) == parsed["classA"]
            and float(index_class_b) == parsed["classB"]
            and float(index_total) == parsed["total"]
        )
        source_rows.append({
            "filingDate": pd.Timestamp(record.filingDate),
            "form": record.form,
            "accession": record.accession,
            **parsed,
            "index_asof": index_asof,
            "index_classA": index_class_a,
            "index_classB": index_class_b,
            "index_total": index_total,
            "index_matches_cover": index_matches_cover,
        })
        documents_used[record.accession] = parsed["source_sha256"]
    shares = pd.DataFrame(source_rows)
    if shares.empty or not (shares["total"] > 0).all():
        raise RuntimeError("No usable positive Class A + B share anchors")
    mismatches = shares.loc[~shares["index_matches_cover"], [
        "accession", "filingDate", "index_asof", "index_classA", "index_classB", "index_total",
        "asof", "classA", "classB", "total",
    ]].copy()
    shares["effective_session"] = [first_session_strictly_after(sessions, d) for d in shares["filingDate"]]
    shares = shares.dropna(subset=["effective_session"]).copy()
    # Price series is in post-split share units.  The share-as-of date controls
    # whether a reported count needs the 10x mechanical normalization.
    shares["split_factor_to_price_basis"] = np.where(shares["asof"] < SPLIT_DATE, 10.0, 1.0)
    shares["shares_price_basis"] = shares["total"].astype(float) * shares["split_factor_to_price_basis"]
    shares = shares.sort_values(["effective_session", "filingDate", "accession"]).drop_duplicates("effective_session", keep="last")
    cols = [
        "filingDate", "form", "accession", "asof", "classA", "classB", "total",
        "index_asof", "index_classA", "index_classB", "index_total", "index_matches_cover",
        "cover_parse_match_count", "source_primary_document", "source_sha256",
        "split_factor_to_price_basis", "shares_price_basis", "effective_session",
    ]
    return shares[cols].reset_index(drop=True), {
        "share_anchor_index": str(SHARE_ANCHORS_PATH),
        "share_anchor_index_sha256": sha256(SHARE_ANCHORS_PATH),
        "share_cover_documents_used": documents_used,
        "share_cover_extraction": "exactly one Class A + Class B outstanding sentence required from each cached official SEC cover; primary-cover totals supersede derivative index values",
        "share_index_cover_mismatch_count": int(len(mismatches)),
        "share_index_cover_mismatches": mismatches.to_dict(orient="records"),
        "share_rule": "Class A + Class B as reported on primary 10-Q/10-K cover pages; becomes usable first session strictly after filing date",
    }


def btc_1559_marks(sessions: pd.DatetimeIndex, end: pd.Timestamp) -> tuple[pd.Series, dict]:
    """Exact completed 15:59 ET bar marks; never use an earlier substitute."""
    btc = pd.read_parquet(BTC_PATH, columns=["timestamp", "close"])
    btc = btc.loc[btc["timestamp"] <= (end.tz_localize("America/New_York") + pd.Timedelta(hours=23, minutes=59)).tz_convert("UTC")].copy()
    btc = btc.drop_duplicates("timestamp", keep="last").set_index("timestamp").sort_index()
    targets = pd.DatetimeIndex([
        (d.tz_localize("America/New_York") + pd.Timedelta(hours=15, minutes=59)).tz_convert("UTC")
        for d in sessions
    ])
    marks = btc["close"].reindex(targets)
    marks.index = sessions
    return marks.astype(float), {
        "btc_path": str(BTC_PATH),
        "btc_path_sha256": sha256(BTC_PATH),
        "mark": "close of exact one-minute candle labelled 15:59 America/New_York; no as-of fallback",
        "available_marks": int(marks.notna().sum()),
        "requested_marks": int(len(marks)),
    }


def build_panel(end: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(DAILY_PATH).sort_index()
    daily.index = pd.DatetimeIndex(daily.index).tz_localize(None).normalize()
    daily = daily.loc[daily.index <= end].copy()
    sessions = pd.DatetimeIndex(daily.index)
    btc_marks, btc_meta = btc_1559_marks(sessions, end)
    ledger, ledger_meta = extract_ledger(end, sessions)
    shares, share_meta = load_share_anchors(end, sessions)

    panel = daily[["Open", "Close"]].astype(float).copy()
    panel["btc_1559"] = btc_marks
    panel["btc_held"] = np.nan
    panel["holdings_accession"] = None
    panel["shares_price_basis"] = np.nan
    panel["share_filing_date"] = pd.NaT
    panel["share_effective_date"] = pd.NaT
    panel["share_asof"] = pd.NaT
    panel["share_accession"] = None

    # Explicit ledger marks are applied from their conservative effective
    # session onward.  Event order handles two filings that map to one session.
    for row in ledger.itertuples(index=False):
        if pd.isna(row.ledger_btc) or row.effective_session is None:
            continue
        date = pd.Timestamp(row.effective_session)
        panel.loc[panel.index >= date, "btc_held"] = float(row.ledger_btc)
        panel.loc[panel.index >= date, "holdings_accession"] = row.accession
    for row in shares.itertuples(index=False):
        date = pd.Timestamp(row.effective_session)
        panel.loc[panel.index >= date, "shares_price_basis"] = float(row.shares_price_basis)
        panel.loc[panel.index >= date, "share_filing_date"] = pd.Timestamp(row.filingDate)
        panel.loc[panel.index >= date, "share_effective_date"] = date
        panel.loc[panel.index >= date, "share_asof"] = pd.Timestamp(row.asof)
        panel.loc[panel.index >= date, "share_accession"] = row.accession

    panel["share_age_sessions"] = np.nan
    available = panel["share_filing_date"].notna()
    # Trading-session age rather than calendar days makes the filter faithfully
    # reflect how long the market has gone without a disclosed share count.
    sess_number = pd.Series(np.arange(len(panel)), index=panel.index)
    file_pos = {d: i for i, d in enumerate(panel.index)}
    panel.loc[available, "share_age_sessions"] = [
        file_pos[pd.Timestamp(d)] if pd.Timestamp(d) in file_pos else np.nan
        for d in panel.loc[available, "share_effective_date"]
    ]
    panel.loc[available, "share_age_sessions"] = (
        sess_number.loc[available].to_numpy() - panel.loc[available, "share_age_sessions"].to_numpy()
    )
    panel["gross_btc_mnav"] = (
        panel["Close"] * panel["shares_price_basis"] / (panel["btc_held"] * panel["btc_1559"])
    )
    panel["log_gross_btc_mnav"] = np.log(panel["gross_btc_mnav"].where(panel["gross_btc_mnav"] > 0))
    panel["data_valid"] = (
        panel["btc_1559"].notna()
        & panel["btc_held"].notna()
        & panel["shares_price_basis"].notna()
        & (panel["gross_btc_mnav"] > 0)
    )
    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "daily_path": str(DAILY_PATH),
        "daily_sha256": sha256(DAILY_PATH),
        "end": end.date().isoformat(),
        "conventions": {
            "filing_availability": "first MSTR session strictly after filing date",
            "btc_mark": btc_meta["mark"],
            "execution": "signal at close, execute following regular-session open",
            "mnav_name": "gross BTC mNAV proxy, not enterprise mNAV",
            "share_split_normalization": "multiply reported count by 10 only where share-as-of date is before 2024-08-01",
        },
        "sources": {**btc_meta, **ledger_meta, **share_meta},
    }
    return panel, meta, ledger, shares


def fee_per_adjusted_share(date: pd.Timestamp) -> float:
    return PRE_SPLIT_FEE if date < SPLIT_DATE else POST_SPLIT_FEE


def simulate_long_cash(
    panel: pd.DataFrame, signal: pd.Series, slip_bp: float, start: pd.Timestamp | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All-in long/cash MSTR portfolio with next-open transitions.

    Fractional shares simply normalize the portfolio to $1 at the first eligible
    open.  Per-share commissions retain the actual historical share basis.
    """
    out = panel[["Open", "Close"]].copy()
    out["signal_close"] = signal.astype(bool)
    # Signal at d executes at d+1 open.  First row deliberately has no order.
    out["target_open"] = out["signal_close"].shift(1).fillna(False).astype(bool)
    # A phase is evaluated as a fresh $1 portfolio.  Its first target is
    # nevertheless determined by the previous session's signal, so the
    # validation boundary does not silently reset the trading state.
    if start is not None:
        out = out.loc[out.index >= start].copy()
    cash = 1.0
    shares = 0.0
    prev_equity = 1.0
    prev_close = np.nan
    rows = []
    trades = []
    for date, row in out.iterrows():
        op, cl = float(row.Open), float(row.Close)
        target = bool(row.target_open)
        before = cash + shares * op
        old_position = shares > 0
        action = "hold_cash"
        commission = 0.0
        if old_position and not target:
            sale_price = op * (1 - slip_bp / 10_000.0)
            commission = fee_per_adjusted_share(date)
            proceeds = shares * (sale_price - commission)
            trades.append({
                "date": date.date().isoformat(), "side": "SELL", "shares_adjusted": shares,
                "market_open": op, "fill_per_share": sale_price, "commission_per_share": commission,
                "slip_bp": slip_bp, "cash_after": proceeds,
            })
            cash, shares, action = proceeds, 0.0, "exit"
        elif (not old_position) and target:
            buy_price = op * (1 + slip_bp / 10_000.0)
            commission = fee_per_adjusted_share(date)
            unit_cost = buy_price + commission
            shares = cash / unit_cost
            cash = 0.0
            trades.append({
                "date": date.date().isoformat(), "side": "BUY", "shares_adjusted": shares,
                "market_open": op, "fill_per_share": buy_price, "commission_per_share": commission,
                "slip_bp": slip_bp, "cash_after": cash,
            })
            action = "enter"
        elif old_position:
            action = "hold_long"
        equity = cash + shares * cl
        daily_return = equity / prev_equity - 1.0 if prev_equity else np.nan
        rows.append({
            "date": date,
            "target_open": target,
            "position_close": shares > 0,
            "action": action,
            "equity": equity,
            "daily_return": daily_return,
            "commission_per_share": commission,
            "mstr_close": cl,
        })
        prev_equity = equity
        prev_close = cl
    curve = pd.DataFrame(rows).set_index("date")
    return curve, pd.DataFrame(trades)


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return np.nan
    return float((equity / equity.cummax() - 1.0).min())


def annualized_sharpe(r: pd.Series) -> float:
    r = r.dropna().astype(float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return np.nan
    return float(np.sqrt(252) * r.mean() / r.std(ddof=1))


def hac_mean_t(r: pd.Series, lags: int = 5) -> float:
    """Newey-West t-statistic for a daily-mean return, no optional packages."""
    x = r.dropna().astype(float).to_numpy()
    n = len(x)
    if n < max(10, lags + 2):
        return np.nan
    e = x - x.mean()
    long_run = np.dot(e, e) / n
    for k in range(1, min(lags, n - 1) + 1):
        gamma = np.dot(e[k:], e[:-k]) / n
        long_run += 2 * (1 - k / (lags + 1)) * gamma
    if long_run <= 0:
        return np.nan
    return float(x.mean() / math.sqrt(long_run / n))


def block_bootstrap_diff(a: pd.Series, b: pd.Series, block: int = 5, reps: int = 10_000, seed: int = 20261017) -> dict:
    x = (a - b).dropna().astype(float).to_numpy()
    n = len(x)
    if n < block:
        return {"n": n, "mean": np.nan, "q025": np.nan, "p_le_zero": np.nan}
    rng = np.random.default_rng(seed)
    starts = np.arange(n - block + 1)
    means = np.empty(reps)
    chunks = math.ceil(n / block)
    for i in range(reps):
        locs = rng.choice(starts, size=chunks, replace=True)
        sample = np.concatenate([x[j:j + block] for j in locs])[:n]
        means[i] = sample.mean()
    return {
        "n": int(n), "mean": float(x.mean()), "q025": float(np.quantile(means, 0.025)),
        "p_le_zero": float(np.mean(means <= 0)),
    }


def summarize(name: str, curve: pd.DataFrame, trades: pd.DataFrame) -> dict:
    r = curve["daily_return"].dropna()
    equity = curve["equity"]
    n = len(r)
    years = n / 252.0
    total = float(equity.iloc[-1] - 1) if len(equity) else np.nan
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 and equity.iloc[-1] > 0 else np.nan
    return {
        "strategy": name,
        "sessions": int(n),
        "active_sessions": int(curve["position_close"].sum()),
        "exposure": float(curve["position_close"].mean()),
        "round_trips": int(min((trades["side"] == "BUY").sum(), (trades["side"] == "SELL").sum())) if not trades.empty else 0,
        "total_return": total,
        "cagr": cagr,
        "sharpe": annualized_sharpe(r),
        "hac_t_mean": hac_mean_t(r),
        "max_drawdown": max_drawdown(equity),
        "mean_daily_return": float(r.mean()) if len(r) else np.nan,
    }


def make_signals(panel: pd.DataFrame, lookback: int, level_sma: int | None, max_share_age: int) -> pd.Series:
    valid = panel["data_valid"] & (panel["share_age_sessions"] <= max_share_age)
    # Need valid endpoints *and* an uninterrupted lookback in the fundamental
    # proxy.  This rejects an old signal bridged across missing 15:59 BTC data.
    log_mnav = panel["log_gross_btc_mnav"].where(valid)
    momentum = log_mnav - log_mnav.shift(lookback)
    complete_window = valid.rolling(lookback + 1, min_periods=lookback + 1).sum().eq(lookback + 1)
    signal = (momentum > 0) & complete_window
    if level_sma is not None:
        sma = panel["gross_btc_mnav"].where(valid).rolling(level_sma, min_periods=level_sma).mean()
        complete_level = valid.rolling(level_sma, min_periods=level_sma).sum().eq(level_sma)
        signal = signal & (panel["gross_btc_mnav"] > sma) & complete_level
    return signal.fillna(False)


def mstr_sma_signal(panel: pd.DataFrame, sma: int = 50) -> pd.Series:
    # Same close-to-next-open decision timing, but no BTC or filing inputs.
    mean = panel["Close"].rolling(sma, min_periods=sma).mean()
    return (panel["Close"] > mean).fillna(False)


def run_phase(phase: str, end: pd.Timestamp, start: pd.Timestamp, rules: list[dict], output_prefix: str) -> None:
    panel, meta, ledger, shares = build_panel(end)
    # Pre-start history remains present for rolling signals; all performance
    # summaries and curves begin only at ``start``.
    panel.to_parquet(HERE / f"{output_prefix}_PANEL.parquet")
    ledger.to_csv(HERE / f"{output_prefix}_BTC_LEDGER.csv", index=False)
    shares.to_csv(HERE / f"{output_prefix}_SHARE_ANCHORS.csv", index=False)
    (HERE / f"{output_prefix}_INPUT_MANIFEST.json").write_text(json.dumps(meta, indent=2, default=str) + "\n")

    all_rows = []
    curves: dict[str, pd.DataFrame] = {}
    trade_rows: dict[str, pd.DataFrame] = {}
    for rule in rules:
        signal = make_signals(panel, rule["lookback"], rule["level_sma"], rule["max_share_age_sessions"])
        for label, slip in [("baseline", BASELINE_SLIP_BP), ("double_cost", DOUBLE_SLIP_BP)]:
            curve, trades = simulate_long_cash(panel, signal, slip, start=start)
            name = f"{rule['id']}__{label}"
            curves[name] = curve
            trade_rows[name] = trades
            row = summarize(name, curve, trades)
            row.update({
                "phase": phase,
                "rule_id": rule["id"],
                "lookback": rule["lookback"],
                "level_sma": rule["level_sma"],
                "max_share_age_sessions": rule["max_share_age_sessions"],
                "cost_case": label,
            })
            all_rows.append(row)

    # Benchmark simulations use the same MSTR execution/cost engine.  The
    # long-only benchmark begins with a signal true at every session; the 50d
    # price trend has matching next-open mechanics.
    benchmarks = {
        "MSTR_BUY_HOLD": pd.Series(True, index=panel.index),
        "MSTR_PRICE_SMA50": mstr_sma_signal(panel, 50),
    }
    for bench_name, bench_signal in benchmarks.items():
        curve, trades = simulate_long_cash(panel, bench_signal, BASELINE_SLIP_BP, start=start)
        curves[bench_name] = curve
        trade_rows[bench_name] = trades
        row = summarize(bench_name, curve, trades)
        row.update({"phase": phase, "rule_id": bench_name, "lookback": np.nan, "level_sma": np.nan, "max_share_age_sessions": np.nan, "cost_case": "baseline"})
        all_rows.append(row)

    summary = pd.DataFrame(all_rows)
    # Rule-vs-benchmark inference is reported only for the baseline case.
    inferences = []
    for rule in rules:
        name = f"{rule['id']}__baseline"
        for bench in ["MSTR_BUY_HOLD", "MSTR_PRICE_SMA50"]:
            aligned = pd.concat([curves[name]["daily_return"], curves[bench]["daily_return"]], axis=1, keys=["rule", "benchmark"]).dropna()
            diff = aligned["rule"] - aligned["benchmark"]
            boot = block_bootstrap_diff(aligned["rule"], aligned["benchmark"])
            inferences.append({
                "phase": phase, "rule_id": rule["id"], "benchmark": bench,
                "n": len(aligned), "mean_daily_excess": float(diff.mean()),
                "hac_t_excess": hac_mean_t(diff), **boot,
            })
    summary.to_csv(HERE / f"{output_prefix}_SUMMARY.csv", index=False)
    pd.DataFrame(inferences).to_csv(HERE / f"{output_prefix}_INFERENCE.csv", index=False)
    for name, curve in curves.items():
        curve.to_csv(HERE / f"{output_prefix}_CURVE_{name}.csv")
    for name, trades in trade_rows.items():
        trades.to_csv(HERE / f"{output_prefix}_TRADES_{name}.csv", index=False)


def development_rules() -> list[dict]:
    """Small, economically motivated pre-freeze grid; no outcome selection here."""
    return [
        {"id": "MOM05", "lookback": 5, "level_sma": None, "max_share_age_sessions": 120},
        {"id": "MOM10", "lookback": 10, "level_sma": None, "max_share_age_sessions": 120},
        {"id": "MOM20", "lookback": 20, "level_sma": None, "max_share_age_sessions": 120},
        {"id": "MOM40", "lookback": 40, "level_sma": None, "max_share_age_sessions": 120},
        {"id": "MOM10_LEVEL50", "lookback": 10, "level_sma": 50, "max_share_age_sessions": 120},
        {"id": "MOM20_LEVEL50", "lookback": 20, "level_sma": 50, "max_share_age_sessions": 120},
        {"id": "MOM40_LEVEL50", "lookback": 40, "level_sma": 50, "max_share_age_sessions": 120},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["development", "validation"], required=True)
    parser.add_argument("--freeze", type=Path, help="Frozen rules JSON required for validation")
    args = parser.parse_args()
    if args.phase == "development":
        run_phase("development", DEV_END, pd.Timestamp("2020-08-11"), development_rules(), "DEV")
        return
    if not args.freeze or not args.freeze.exists():
        raise SystemExit("validation requires --freeze <FROZEN_RULES.json>")
    frozen = json.loads(args.freeze.read_text())
    if frozen.get("phase") != "frozen_before_validation":
        raise SystemExit("freeze file lacks the required phase marker")
    expected_hash = frozen.get("rule_payload_sha256")
    payload = json.dumps(frozen.get("rules"), sort_keys=True, separators=(",", ":")).encode()
    if expected_hash != hashlib.sha256(payload).hexdigest():
        raise SystemExit("freeze file rule payload hash does not match")
    # The original SEALED_* and first remediation output sets are retained as
    # invalidated parser-run records.  This source-audited, correction-only
    # validation must never overwrite either set.
    run_phase("validation", VALIDATION_END, VALIDATION_START, frozen["rules"], "SEALED_REMEDIATION_02")


if __name__ == "__main__":
    main()
