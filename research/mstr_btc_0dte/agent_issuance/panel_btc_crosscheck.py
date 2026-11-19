"""Cross-check: descriptive weekly issuance panel BTC quantities vs the events agent's
validated purchase events.

Panel   : research/mstr_btc_0dte/agent_issuance/issuance_btc_raw.csv   (96 rows, 90 accessions, 2024-09-13..2026-10-05)
Validated: research/mstr_btc_0dte/agent_events/validated_purchase_events.csv (106 rows, 2020-08-11..2026-10-05)

No return statistic is computed anywhere in this script. Read-only over both CSVs.
Run:  cd /Users/rytty/CCP/quant_v7 && .venv/bin/python research/mstr_btc_0dte/agent_issuance/panel_btc_crosscheck.py
"""
import pandas as pd

PANEL = "research/mstr_btc_0dte/agent_issuance/issuance_btc_raw.csv"
VALID = "research/mstr_btc_0dte/agent_events/validated_purchase_events.csv"
WINDOW_START = "2024-09-13"  # panel first filing date

p = pd.read_csv(PANEL)
v = pd.read_csv(VALID)
p["segment_start"] = pd.to_datetime(p["segment_start"])
p["segment_end"] = pd.to_datetime(p["segment_end"])
p["span_days"] = (p["segment_end"] - p["segment_start"]).dt.days

ok = True

def check(name, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

# ---------------------------------------------------------------- 1. overlap
print("== 1. per-accession overlap ==")
pt = (p.groupby("accession")
        .agg(qty_sum=("btc_qty", "sum"), rows=("btc_qty", "size"), filing_date=("filing_date", "first"))
        .reset_index())
vt = v.groupby("accession").agg(val_qty=("purchase_btc", "sum"), val_rows=("purchase_btc", "size")).reset_index()
m = pt.merge(vt, on="accession", how="inner")
m["diff"] = m["qty_sum"] - m["val_qty"]
print(f"overlap accessions: {len(m)}  (rows: {int(m['rows'].sum())})")
mm = m[m["diff"] != 0]
print(f"exact quantity matches: {(m['diff'] == 0).sum()} / {len(m)}")
for _, r in mm.iterrows():
    print(f"  MISMATCH accession={r['accession']} filing={r['filing_date']} "
          f"panel={r['qty_sum']} validated={r['val_qty']} diff={r['diff']}")
check("overlap: exactly 72 accessions", len(m) == 72, f"got {len(m)}")

# ------------------------------------------------------- 2. panel-only rows
print()
print("== 2. panel-only accessions ==")
onlyp = set(p["accession"]) - set(v["accession"])
po = p[p["accession"].isin(onlyp)].sort_values(["filing_date", "segment_start"])
po_kind = []
for _, r in po.iterrows():
    if r["span_days"] >= 60:
        kind = "recap"
    elif r["btc_qty"] == 0:
        kind = "zero-week"
    else:
        kind = "purchase"
    po_kind.append((r["filing_date"], r["accession"], r["segment_start"].date(), r["segment_end"].date(),
                    int(r["btc_qty"]), r["btc_cost_musd"], kind))
print(f"panel-only accessions: {len(onlyp)}  rows: {len(po)}")
for fd, acc, s, e, q, c, kind in po_kind:
    extra = ""
    if kind == "zero-week" and c and c > 0:
        extra = f"  [cost field artifact: {c}]"
    print(f"  {kind:9s} {fd} {acc} {s}..{e} qty={q} cost={c}{extra}")

recaps = po[po["span_days"] >= 60]
check("panel-only: exactly 3 quarterly recap rows", len(recaps) == 3, f"got {len(recaps)}")
for _, r in recaps.iterrows():
    qa = p[(p["segment_start"] >= r["segment_start"]) & (p["segment_end"] <= r["segment_end"]) &
           (p["span_days"] < 60)]["btc_qty"].sum()
    check(f"recap {r['segment_start'].date()}..{r['segment_end'].date()} duplicates weekly sum",
          int(r["btc_qty"]) == int(qa), f"recap={int(r['btc_qty'])} weekly sum={int(qa)}")

panel_only_purch = po[(po["span_days"] < 60) & (po["btc_qty"] > 0)]
print(f"panel-only purchase events (validated-side misses): {len(panel_only_purch)}"
      f" -> {sorted(int(x) for x in panel_only_purch['btc_qty'])}")

# --------------------------------------------- 3. validated-only in window
print()
print("== 3. validated-only accessions ==")
onlyv = v[~v["accession"].isin(set(p["accession"]))]
ov_win = onlyv[onlyv["filing_date"] >= WINDOW_START]
ov_pre = onlyv[onlyv["filing_date"] < WINDOW_START]
print(f"validated-only in window (filing >= {WINDOW_START}): {len(ov_win)}")
for _, r in ov_win.sort_values("filing_date").iterrows():
    print(f"  {r['filing_date']} {r['accession']} qty={r['purchase_btc']}")
print(f"validated-only pre-window (< {WINDOW_START}): {len(ov_pre)}  "
      f"range {ov_pre['filing_date'].min()}..{ov_pre['filing_date'].max()}  [outside panel scope by design]")
check("validated-only in window: exactly 3 events", len(ov_win) == 3, f"got {len(ov_win)}")

# ------------------------------------------------------- 4. totals identity
print()
print("== 4. totals reconciliation (purchases, panel window) ==")
panel_total = p[p["span_days"] < 60]["btc_qty"].sum()   # exclude the 3 quarterly recap duplicates
val_total = v[v["filing_date"] >= WINDOW_START]["purchase_btc"].sum()
panel_extra = int(panel_only_purch["btc_qty"].sum()) + int(mm["diff"].sum())
val_extra = int(ov_win["purchase_btc"].sum())
expected = panel_extra - val_extra
print(f"panel purchases (excl. quarterly recap rows): {panel_total}")
print(f"validated purchases (filing >= window start): {val_total}")
print(f"delta = {panel_total - val_total}   | panel-side extras (4020+220+3) = {panel_extra}"
      f"   | validated-side extras (4603+950+1665) = {val_extra}   | expected = {expected}")
check("identity: panel - validated == ep - ev", panel_total - val_total == expected)

print()
print("RESULT:", "ALL CHECKS PASS" if ok else "CHECKS FAILED")
