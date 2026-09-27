"""Re-report, without recalculating returns or the A4 p-value, FOMC event N.

Consumes only the wave-1 saved development return table/result and writes a
new wave-2 re-analysis artifact. It neither reads a holdout nor changes a
frozen preregistration or old report.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.amendment4.event_effective_n import event_effective_n


def main() -> None:
    folder = Path("reports/sol_beyond_menu")
    original = json.loads((folder / "scheduled_fomc_risk_result.json").read_text())
    frame = pd.read_csv(folder / "scheduled_fomc_risk_dev.csv", parse_dates=["date"])
    events = frame.loc[frame["event"] == 1]
    cap = event_effective_n(events["active_net"], events["date"].dt.year,
                            original["effective_n"], overlap_multiplicity=1)
    threshold = original["positive_threshold"]
    out = {"kind": "re-analysis; no new strategy-return trial",
           "source_result": "reports/sol_beyond_menu/scheduled_fomc_risk_result.json",
           "source_development_series": "reports/sol_beyond_menu/scheduled_fomc_risk_dev.csv",
           "original_daily_effective_n": original["effective_n"],
           "patched_event_effective_n": cap,
           "calibrated_p_unchanged": original["calibrated_p"],
           "why_p_unchanged": "A4 calibrated p is calculated from the calendar-time active-return series and does not consume the effective-N diagnostic.",
           "positive_threshold": threshold,
           "passes_p": bool(original["calibrated_p"] < threshold),
           "verdict": "FAIL"}
    target = folder / "fomc_event_n_rereport.json"
    target.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
