"""Corrected-data re-measurement of the frozen crypto_funding_xs DEVELOPMENT window (amendment 1 §C.8).
Unchanged spec: imports the frozen core.py / evaluate.py (hash-checked) and only redirects outputs so the original
as-run files are preserved.  PYTHONPATH=. .venv/bin/python -m research.crypto_funding_xs.remeasure"""
from __future__ import annotations

import hashlib
import json

from research.crypto_funding_xs import evaluate as ev
from research.struct_common import ROOT, registered

FROZEN = {"research/crypto_funding_xs/core.py": "f7811a55696aae0b4694874c564a0d0f08e14fc57d69ccdec7f157343b668f88",
          "research/crypto_funding_xs/evaluate.py": "e9ef68b9797de7a8f35b7f6666467ae2911672a6deab9dfb3bb7abaa9321157e"}
DOC = "research/crypto_funding_xs/CORRECTED_DATA_REMEASUREMENT.md"


def main():
    for f, h in FROZEN.items():
        assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h, f"frozen file changed: {f}"
    if not registered(DOC):
        raise SystemExit("re-measurement not registered")
    out = ROOT / "reports" / "crypto_funding_xs" / "corrected"
    if (out / "dev_results.json").exists():
        raise SystemExit("already run")
    out.mkdir(parents=True, exist_ok=True)
    ev.OUT = out
    r = ev.run_window(ev.DEV)
    r["selected"] = bool(r["books"]["base"]["sharpe"] >= r["gate"] and r["books"]["stress"]["ann_mean"] > 0
                         and r["bootstrap_p"] < ev.ALPHA_DEV)
    (out / "dev_results.json").write_text(json.dumps(r, indent=2))
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
