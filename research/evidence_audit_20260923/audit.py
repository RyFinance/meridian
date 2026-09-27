"""Read-only audit of registrations and forward readiness; no decision is recorded."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from research.forward.registry import verify_chain, spec_hash

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/evidence_audit_20260923"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = [json.loads(x) for x in (ROOT / "research/preregistrations.jsonl").read_text().splitlines() if x.strip()]
    rows = []
    for item in records:
        rel = item.get("file", "")
        p = ROOT / rel
        actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        rows.append({"file": rel, "family_directory": rel.split("/")[1] if "/" in rel else "",
                     "kind": "validation_unlock" if "unlocks" in item else "registration",
                     "registered_at": item.get("registered_at", ""),
                     "registered_sha256": item.get("sha256", ""), "current_sha256": actual or "MISSING",
                     "hash_matches": actual == item.get("sha256"),
                     "note": item.get("note", "")})
    with (OUT / "registered_trials.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    regpath = ROOT / "reports/forward/registry.jsonl"
    chain = verify_chain(regpath)
    forward = [json.loads(x) for x in regpath.read_text().splitlines() if x.strip()]
    spec = [r for r in forward if r["kind"] == "spec_registration" and r["strategy_id"] == "momentum_gold_v1"]
    decisions = [r for r in forward if r["kind"] == "decision" and r["strategy_id"] == "momentum_gold_v1"]
    s = spec[-1] if spec else None
    paper = json.loads((ROOT / "reports/momentum_gold_20260919/forward_paper_spec.json").read_text())
    paper.pop("audit_2026_09_21", None)  # later annotation is explicitly outside frozen rule bytes
    result = {"registry_chain_ok": chain.ok, "registry_head_seq": chain.head_seq,
              "registry_head_hash": chain.head_hash,
              "external_anchors_checked": chain.anchors_checked,
              "momentum_gold_registered": bool(spec), "forward_decision_count": len(decisions),
              "registered_payload_hash_valid": bool(s and spec_hash(s["payload"]["spec"]) == s["spec_hash"]),
              "paper_rules_equal_registered": bool(s and paper == s["payload"]["spec"]),
              "expected_next_decision": paper.get("expected_next_decision"),
              "expected_next_fill": paper.get("expected_next_fill"),
              "registry_entries": len(rows), "plan_hash_mismatches": [r["file"] for r in rows if not r["hash_matches"]],
              "manual_action_remaining": "Record the Oct 1 decision after the official close and anchor the resulting registry head externally before the Oct 2 open; no decision exists now."}
    (OUT / "readiness.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
