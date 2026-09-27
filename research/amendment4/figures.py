"""research.amendment4.figures -- PNGs for reports/amendment4/."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def make(out):
    s = pd.read_csv(out / "size_table.csv")
    tests = ["old_NW_t", "old_CBB", "A4prop_CBB", "IM_batch10", "NCT", "NCT_b0.2"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    for ax, a in zip(axes, ("0.05", "0.0125")):
        scen = list(dict.fromkeys(s.scenario))
        w = 0.8 / len(tests)
        for j, t in enumerate(tests):
            v = [s[(s.scenario == sc) & (s.test == t)][f"ratio_{a}"].squeeze() if ((s.scenario == sc) & (s.test == t)).any()
                 else np.nan for sc in scen]
            ax.barh(np.arange(len(scen)) + j * w, v, height=w, label=t)
        ax.axvline(1.0, color="k", lw=0.8)
        ax.axvline(1.5, color="r", lw=0.8, ls="--")
        ax.set_yticks(np.arange(len(scen)) + 0.4)
        ax.set_yticklabels(scen, fontsize=8)
        ax.set_title(f"actual / nominal size at alpha = {a}")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "size_ratio.png", dpi=120)
    plt.close(fig)

    st = pd.read_csv(out / "stress_rule_oc.csv")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=False)
    for ax, S in zip(axes, (0.3, 0.5, 0.7)):
        for r in ("R0_mean_pos", "R1_floor", "R2_half", "R4_gate"):
            d = st[(st.true_net_sharpe == S) & (st.rule == r)]
            ax.plot(d.stress_drag_sr, d.P_joint, marker="o", label=r)
        ax.set_title(f"joint pass, true net S = {S} (12+12y monthly)")
        ax.set_xlabel("stress drag (Sharpe units)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "stress_oc.png", dpi=120)
    plt.close(fig)

    c = pd.read_csv(out / "ci_coverage.csv")
    c = c[c.nominal == 0.9]
    fig, ax = plt.subplots(figsize=(12, 5))
    lab = c.scenario + " n=" + c.months.astype(str) + " " + c.parameter
    for m in c.method.unique():
        d = c[c.method == m]
        ax.plot(range(len(d)), d.coverage, marker="o", ls="", label=m)
    d0 = c[c.method == "calibrated_boot_t"]
    ax.set_xticks(range(len(d0)))
    ax.set_xticklabels((d0.scenario + " n=" + d0.months.astype(str) + " " + d0.parameter), rotation=70, fontsize=7)
    ax.axhline(0.9, color="k", lw=0.8)
    ax.set_title("90% interval coverage (x labels follow the calibrated rows)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "ci_coverage.png", dpi=120)
    plt.close(fig)
