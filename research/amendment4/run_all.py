"""research.amendment4.run_all -- regenerate reports/amendment4/ (synthetic only).

    PYTHONPATH=. .venv/bin/python -m research.amendment4.run_all [section ...]

sections: size active stress effn power ci figures (default: all). Each writes its CSV/JSON; meta.json records
paths, inner draws and runtime.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

OUT = pathlib.Path(__file__).resolve().parents[2] / "reports" / "amendment4"


def _meta(key, info):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "meta.json"
    m = json.loads(f.read_text()) if f.exists() else {}
    m[key] = info
    f.write_text(json.dumps(m, indent=2, default=str))


def main(argv=None):
    secs = (argv if argv is not None else sys.argv[1:]) or ["size", "active", "stress", "effn", "power", "ci",
                                                            "figures"]
    for s in secs:
        t0 = time.time()
        if s == "size":
            from research.amendment4 import size_study
            size_study.run(paths=int(os.environ.get("A4_SIZE_PATHS", 40000))).to_csv(OUT / "size_table.csv", index=False)
            info = {"outer_paths": int(os.environ.get("A4_SIZE_PATHS", 40000)), "inner_B": 159, "ar_bias_R": 50}
        elif s == "active":
            from research.amendment4 import active
            import pandas as pd
            pd.concat([active.run(paths=20000), active.single_stage_size(paths=20000)]).to_csv(
                OUT / "active_gating.csv", index=False)
            info = {"paths": 20000, "inner_B": 159}
        elif s == "stress":
            from research.amendment4 import stress
            stress.run(paths=20000).to_csv(OUT / "stress_rule_oc.csv", index=False)
            info = {"paths": 20000, "inner_B": 159}
        elif s == "effn":
            from research.amendment4 import effn_sim
            effn_sim.run(paths=20000).to_csv(OUT / "effective_n_sim.csv", index=False)
            info = {"paths": 20000}
        elif s == "power":
            from research.amendment4 import power_bench
            a, m = power_bench.run(mc_paths=20000)
            a.to_csv(OUT / "realistic_power.csv", index=False)
            m.to_csv(OUT / "realistic_power_mc_check.csv", index=False)
            info = {"mc_paths": 20000, "inner_B": 159}
        elif s == "ci":
            from research.amendment4 import ci
            ci.run(paths=20000).to_csv(OUT / "ci_coverage.csv", index=False)
            info = {"paths": 20000, "inner_B": ci.B_CI}
        elif s == "figures":
            from research.amendment4 import figures
            figures.make(OUT)
            info = {}
        else:
            raise SystemExit(f"unknown section {s}")
        info["seconds"] = round(time.time() - t0, 1)
        _meta(s, info)
        print(f"== {s} done in {info['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
