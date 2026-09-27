"""A1 audit figures (PNG) from the JSON/CSV outputs."""
from __future__ import annotations

import csv
import json

from research.power_audit_a1.common import OUT
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, INK, INK2, SURF = "#2a78d6", "#0b0b0b", "#52514e", "#fcfcfb"


def main():
    sm = json.load(open(OUT / "sleeve_miss.json"))
    base = [r for r in sm["decomposition"] if r["variant"].startswith("base") and r["s_sleeve"] == 0.6][0]
    rep = [r for r in sm["cycle4_simulator_reseeded"] if r["s_sleeve"] == 0.6][0]
    labels = ["cycle-4 analytic\n(binomial)", "one-factor\nanalytic (A1)", "A1 MC\n100k", "cycle-4 MC code\nre-seeded 100k",
              "cycle-4 MC\n3k (reported)"]
    vals = [base["analytic_binomial_cycle4"], base["analytic_one_factor"], base["mc_audit"], rep["cycle4_mc_code_reseeded"], 0.507]
    errs = [0, 0, 1.96 * base["mc_se"], 1.96 * rep["se"], 1.96 * 0.0091]
    nw = list(csv.DictReader(open(OUT / "hac_t_size_grid.csv")))
    nw = [r for r in nw if abs(float(r["nominal_alpha"]) - 0.05 / 3) < 1e-6]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), facecolor=SURF)
    for a in ax:
        a.set_facecolor(SURF)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        a.tick_params(colors=INK2, labelsize=8)
        a.grid(axis="y", color="#e4e3df", lw=0.8)
        a.set_axisbelow(True)
    ax[0].bar(range(5), vals, yerr=errs, color=BLUE, width=0.55, error_kw=dict(ecolor=INK2, lw=1, capsize=3))
    ax[0].set_xticks(range(5), labels)
    ax[0].set_ylim(0.44, 0.53)
    for i, v in enumerate(vals):
        ax[0].text(i, v + errs[i] + 0.002, f"{v:.3f}", ha="center", fontsize=8, color=INK)
    ax[0].set_title("17-sleeve screen, s=0.6, m=5: P(joint pass) (bars: 95% MC CI)", fontsize=10, color=INK, loc="left")
    ax[1].barh(range(len(nw)), [float(r["size_mc"]) / float(r["nominal_alpha"]) for r in nw], color=BLUE, height=0.55)
    ax[1].axvline(1.0, color=INK2, lw=1, ls="--")
    ax[1].set_yticks(range(len(nw)), [r["case"] for r in nw])
    ax[1].invert_yaxis()
    ax[1].set_title("Literal NW t, plug-in lags: actual size / nominal (alpha = 0.05/3)", fontsize=10, color=INK, loc="left")
    ax[1].grid(axis="x", color="#e4e3df", lw=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "audit_a1_summary.png", dpi=140, facecolor=SURF)


if __name__ == "__main__":
    main()
