#!/usr/bin/env python3
"""Render the small exported benchmark summary with Matplotlib."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    methods = data["methods"]
    labels = ["HyperCD* (0)", "HyperCD+ / RUC (1)", "HyperCD+ / lower bound (2)",
              "HyperCD+ (3)", "HyperCD (4)", "HyperCD++ (5)", "VLDB OPTIV"]
    if [m["method"] for m in methods] != ["sigmod_" + str(i) for i in range(6)] + ["vldb_OPTIV"]:
        raise ValueError("Unexpected method ordering")
    colors = ["#00796b"] + ["#64748b"] * 5 + ["#c46d14"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.1), sharey=True)
    for ax, metric, divisor, title, unit in [
        (axes[0], "compute_wall_s", 1, "Decomposition call (including initialization)", "seconds"),
        (axes[1], "peak_rss_kib", 1024, "Peak resident memory (whole process)", "MiB"),
    ]:
        values = [m[metric]["median"] / divisor for m in methods]
        lower = [v - m[metric]["min"] / divisor for v, m in zip(values, methods)]
        upper = [m[metric]["max"] / divisor - v for v, m in zip(values, methods)]
        ax.barh(range(len(methods)), values, color=colors, height=0.58,
                xerr=[lower, upper], error_kw={"elinewidth": 1, "capsize": 2, "ecolor": "#263238"})
        ax.set_xscale("log")
        ax.set_xlim(min(values) / 2, max(values) * 2.7)
        ax.set_title(title, fontsize=10, pad=12)
        ax.set_xlabel(unit + " (log scale)")
        ax.set_axisbelow(True)
        ax.grid(axis="x", which="major", alpha=0.2)
        for i, value in enumerate(values):
            label = f"{value:.3f}" if divisor == 1 else f"{value:.1f}"
            ax.annotate(label, (value, i), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9)
    axes[0].set_yticks(range(len(labels)), labels)
    axes[0].invert_yaxis()
    fig.suptitle("History: single-thread pilot", x=0.02, ha="left", fontsize=16, weight="bold")
    fig.text(0.02, 0.905, f'N = {data["data"]["vertices"]:,}  |  M = {data["data"]["edges"]:,}  |  '
             f'{data["repetitions"]} fresh processes per configuration  |  median and min–max',
             fontsize=10, color="#475569")
    fig.text(0.02, 0.025, "GCC 11.4, matched -O3 builds, CPU 0. Core export is disabled during timed runs.\n"
             "Pilot measurements; paper figure values and the full dataset matrix remain to be checked.",
             fontsize=9, color="#475569")
    fig.subplots_adjust(left=0.245, right=0.98, top=0.80, bottom=0.19, wspace=0.13)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "svg", "pdf"]:
        fig.savefig(args.output.with_suffix("." + suffix), dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
