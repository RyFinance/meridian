"""Complete JSON serialization from the one saved development return series.

This does not parse the snapshot or recompute any strategy return. Use only for
the documented negative-cumulative-P&L serialization failure in BUG_LOG.md.
"""
import json

import pandas as pd

from research.sol_beyond_menu.evaluate import OUT, summarize


def main() -> None:
    frame = pd.read_csv(OUT / "overnight_equity_dev.csv", index_col=0, parse_dates=True)
    result = summarize(frame, 252, "overnight_equity")
    result["manifest_sha256"] = "d77434aceca4d62640967a103a84e78529b77061c3fa9270e3f2ebf10ecdfacf"
    (OUT / "overnight_equity_result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "yearly_active_pnl"}, allow_nan=False))


if __name__ == "__main__":
    main()
