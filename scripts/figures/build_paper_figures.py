# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Build every figure cited in the paper from real JSONL bench output.

Reads docs/papers/2026-when-should-a-rule-learn/results/<bench>_paired.jsonl
and writes figure-{1..5}-*.{png,svg} into the same directory.

Run from the repo root:
    python scripts/figures/build_paper_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from scipy.stats import binom, norm

RESULTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "papers"
    / "2026-when-should-a-rule-learn"
    / "results"
)

BENCHES = [
    ("atis", "ATIS", 26),
    ("hwu64", "HWU64", 64),
    ("banking77", "Banking77", 77),
    ("clinc150", "CLINC150", 151),
]

# Extended suite — added for v1.0 launch as additional stress axes.
# Kept separate so the original 4-bench figures (paper Figures 1-4)
# stay reproducible while the expanded figures (1b, 2b, 3b) include
# everyone.
EXTENDED_BENCHES = [
    ("atis", "ATIS", 26),
    ("snips", "Snips", 7),
    ("trec6", "TREC-6", 6),
    ("ag_news", "AG News", 4),
    ("hwu64", "HWU64", 64),
    ("banking77", "Banking77", 77),
    ("clinc150", "CLINC150", 151),
    ("codelangs", "codelangs", 12),
]

ALPHA = 0.01

# Dendra brand palette (matches landing/brand-tokens.css).
# These tokens are used both for paper figures and the landing-page
# embeds, so the on-page figures look like Dendra rather than like
# raw matplotlib paper exports.
COLOR_INK = "#1a1a1f"
COLOR_INK_SOFT = "#6a6a72"
COLOR_ACCENT = "#bf5700"
COLOR_ACCENT_DEEP = "#8a3f00"
COLOR_GROUND = "#f8f6f1"

COLOR_RULE = COLOR_INK_SOFT
COLOR_ML = COLOR_ACCENT
COLOR_REGIME_A = COLOR_ACCENT_DEEP
COLOR_REGIME_B = COLOR_INK_SOFT


def _apply_dendra_style() -> None:
    """Apply Dendra brand styling globally before any figure renders."""
    plt.rcParams.update(
        {
            "figure.facecolor": COLOR_GROUND,
            "axes.facecolor": COLOR_GROUND,
            "savefig.facecolor": COLOR_GROUND,
            "axes.edgecolor": COLOR_INK,
            "axes.labelcolor": COLOR_INK,
            "axes.titlecolor": COLOR_INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": COLOR_INK,
            "grid.alpha": 0.08,
            "grid.linewidth": 0.6,
            "xtick.color": COLOR_INK,
            "ytick.color": COLOR_INK,
            "xtick.labelcolor": COLOR_INK,
            "ytick.labelcolor": COLOR_INK,
            "xtick.minor.visible": False,
            "ytick.minor.visible": False,
            "text.color": COLOR_INK,
            "font.family": ["Space Grotesk", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": 10.5,
            "axes.titleweight": "500",
            "axes.titlesize": 11.5,
            "legend.frameon": True,
            "legend.facecolor": COLOR_GROUND,
            "legend.edgecolor": COLOR_INK_SOFT,
            "legend.framealpha": 1.0,
            "legend.fontsize": 9.5,
        }
    )


_apply_dendra_style()


def load_paired(slug: str) -> tuple[dict, list[dict]]:
    path = RESULTS_DIR / f"{slug}_paired.jsonl"
    summary = None
    checkpoints = []
    with path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") == "summary":
                summary = rec
            elif rec.get("kind") == "checkpoint":
                checkpoints.append(rec)
    assert summary is not None
    return summary, checkpoints


def paired_mcnemar_p(rule_correct: list[bool], ml_correct: list[bool]) -> tuple[int, int, float]:
    r = np.array(rule_correct, dtype=bool)
    m = np.array(ml_correct, dtype=bool)
    b = int(np.sum(~r & m))
    c = int(np.sum(r & ~m))
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p_one = binom.cdf(k, n, 0.5)
    p = min(1.0, 2.0 * p_one)
    return b, c, p


def unpaired_z_p(rule_correct: list[bool], ml_correct: list[bool]) -> float:
    r = np.array(rule_correct, dtype=bool)
    m = np.array(ml_correct, dtype=bool)
    n = len(r)
    p_r = r.mean()
    p_m = m.mean()
    p_pool = (p_r + p_m) / 2.0
    se = np.sqrt(2.0 * p_pool * (1.0 - p_pool) / n)
    if se == 0:
        return 1.0 if p_m <= p_r else 0.0
    z = (p_m - p_r) / se
    p = 1.0 - norm.cdf(z)
    return float(p)


def figure_1_transition_curves() -> None:
    """8-panel transition-curve grid covering the full §5.1 benchmark suite.

    2 rows × 4 cols, sorted by descending rule baseline so regimes
    cluster visually: top row covers the "rule has fighting chance"
    end (codelangs, ATIS, TREC-6, AG News), bottom row the "rule at
    floor" end (Snips, HWU64, Banking77, CLINC150).
    """
    panels = [
        ("codelangs", "codelangs", 12),
        ("atis", "ATIS", 26),
        ("trec6", "TREC-6", 6),
        ("ag_news", "AG News", 4),
        ("snips", "Snips", 7),
        ("hwu64", "HWU64", 64),
        ("banking77", "Banking77", 77),
        ("clinc150", "CLINC150", 151),
    ]
    # Width matches Figure 2 (figsize=(10, 6)) so the two figures sit
    # column-aligned in the paper layout; height bumped to 6.5 so the
    # 2-row grid has a touch more vertical room per panel.
    fig, axes = plt.subplots(2, 4, figsize=(10, 6.5), sharey=False)
    panel_labels = ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)", "(g)", "(h)"]

    for idx, (ax, (slug, name, k)) in enumerate(zip(axes.flat, panels, strict=False)):
        path = RESULTS_DIR / f"{slug}_paired.jsonl"
        if not path.exists():
            ax.text(
                0.5, 0.5, f"{slug}\n(no data)", ha="center", va="center", transform=ax.transAxes
            )
            ax.axis("off")
            continue
        _, ckpts = load_paired(slug)
        outcomes = np.array([c["training_outcomes"] for c in ckpts])
        rule_acc = np.array([c["rule_test_accuracy"] for c in ckpts]) * 100
        ml_acc = np.array([c["ml_test_accuracy"] for c in ckpts]) * 100

        first_fire = None
        for c in ckpts:
            b, cv, p = paired_mcnemar_p(c["rule_correct"], c["ml_correct"])
            if b > cv and p < ALPHA:
                first_fire = c["training_outcomes"]
                break

        ax.fill_between(
            outcomes, rule_acc, ml_acc, where=ml_acc >= rule_acc, color=COLOR_ML, alpha=0.10
        )
        ax.plot(outcomes, rule_acc, color=COLOR_RULE, lw=1.8, label="Rule")
        ax.plot(outcomes, ml_acc, color=COLOR_ML, lw=2.0, label="ML head")
        if first_fire is not None:
            ax.axvline(
                first_fire, color=COLOR_ACCENT_DEEP, lw=1.0, ls="--", alpha=0.7, label="Gate fires"
            )

        ax.set_xscale("log")
        ax.set_xlim(left=outcomes.min() * 0.8)
        ax.set_ylim(0, 100)
        # Show major ticks at powers of 10 only; suppress minor-tick LABELS
        # that otherwise overlap on narrow x-ranges (e.g. codelangs at 100-600
        # outcomes). Keeps the minor tick marks for visual density.
        from matplotlib.ticker import LogLocator, NullFormatter

        ax.xaxis.set_major_locator(LogLocator(base=10))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Training outcomes", fontsize=9)
        if idx % 4 == 0:
            ax.set_ylabel("Test accuracy (%)", fontsize=9)
        ax.set_title(f"{panel_labels[idx]} {name} ({k} labels)", loc="left", fontsize=10)
        ax.grid(True, alpha=0.3)
        if idx == 0:
            ax.legend(loc="center right", fontsize=8, framealpha=0.92)

    fig.suptitle(
        "Figure 1. Transition curves across the eight-benchmark suite "
        "(sorted by descending rule baseline)",
        fontsize=12,
        y=1.00,
    )
    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-1-transition-curves.png"
    out_svg = RESULTS_DIR / "figure-1-transition-curves.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_2_pvalue_trajectories() -> None:
    """8-bench paired-McNemar p-value trajectories on log-log axes.

    Shows that every benchmark plummets through alpha=0.01, with the
    rate of descent revealing relative effect size.
    """
    benches_for_fig = [
        ("codelangs", "codelangs"),
        ("atis", "ATIS"),
        ("trec6", "TREC-6"),
        ("ag_news", "AG News"),
        ("snips", "Snips"),
        ("hwu64", "HWU64"),
        ("banking77", "Banking77"),
        ("clinc150", "CLINC150"),
    ]
    fig, ax = plt.subplots(figsize=(10, 6))
    for slug, name in benches_for_fig:
        path = RESULTS_DIR / f"{slug}_paired.jsonl"
        if not path.exists():
            continue
        _, ckpts = load_paired(slug)
        xs, ys = [], []
        for c in ckpts:
            _, _, p = paired_mcnemar_p(c["rule_correct"], c["ml_correct"])
            xs.append(c["training_outcomes"])
            ys.append(max(p, 1e-300))
        ax.plot(xs, ys, marker="o", lw=1.8, markersize=4, label=name)
    ax.axhline(ALPHA, color=COLOR_ACCENT_DEEP, ls="--", lw=1.4, label=f"alpha = {ALPHA}")
    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xlim(left=80)
    ax.set_xlabel("Training outcomes (log)")
    ax.set_ylabel("Paired McNemar p-value (log)")
    ax.set_title("Figure 2. Paired McNemar p-value trajectories across the eight-benchmark suite")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="lower left", fontsize=9, ncol=2)
    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-2-pvalue-trajectories.png"
    out_svg = RESULTS_DIR / "figure-2-pvalue-trajectories.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_3_two_regimes() -> None:
    """Deprecated: 4-bench bar chart with two-regime tinting. Superseded
    by ``figure_3b_extended_two_regimes`` which covers all eight
    benchmarks. Retained as a no-op for backwards-compat with old
    figure-1-through-5 reproduce scripts; the paper uses figure-3b."""
    print("figure-3 (4-bench): deprecated, superseded by figure-3b")


def figure_4_paired_vs_unpaired() -> None:
    """Per-checkpoint p-value trajectories: paired McNemar vs unpaired-z.

    Replaces the older bar-chart-of-crossing-depths view (which was
    quantized at the 250-outcome resolution and mostly showed ties)
    with a continuous comparison that visualizes the order-of-magnitude
    gap between the two tests at every checkpoint.
    """
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=False)
    panel_labels = ["(a)", "(b)", "(c)", "(d)"]

    for idx, (ax, (slug, name, k)) in enumerate(zip(axes.flat, BENCHES, strict=False)):
        _, ckpts = load_paired(slug)
        outcomes = []
        paired_ps = []
        unpaired_ps = []
        for c in ckpts:
            _, _, p_paired = paired_mcnemar_p(c["rule_correct"], c["ml_correct"])
            p_unpaired = unpaired_z_p(c["rule_correct"], c["ml_correct"])
            outcomes.append(c["training_outcomes"])
            paired_ps.append(max(p_paired, 1e-300))
            unpaired_ps.append(max(p_unpaired, 1e-300))

        ax.plot(
            outcomes,
            unpaired_ps,
            color="#aec7e8",
            lw=2,
            marker="s",
            markersize=4,
            label="Unpaired z",
        )
        ax.plot(
            outcomes,
            paired_ps,
            color=COLOR_ML,
            lw=2.2,
            marker="o",
            markersize=4,
            label="Paired McNemar",
        )
        ax.axhline(ALPHA, color=COLOR_ACCENT_DEEP, ls="--", lw=1.2, label=f"alpha = {ALPHA}")

        ax.set_yscale("log")
        ax.set_xscale("log")
        ax.set_xlim(left=200)
        ax.set_xlabel("Training outcomes (log)")
        ax.set_ylabel("p-value (log)")
        ax.set_title(f"{panel_labels[idx]} {name} ({k} labels)", loc="left", fontsize=11)
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc="lower left", fontsize=9, framealpha=0.92)

    fig.suptitle(
        "Figure 4. Paired McNemar p-value is consistently below unpaired-z at every checkpoint",
        fontsize=13,
        y=1.00,
    )
    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-4-paired-vs-unpaired.png"
    out_svg = RESULTS_DIR / "figure-4-paired-vs-unpaired.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_5_lifecycle() -> None:
    fig, ax = plt.subplots(figsize=(13, 5.0))
    ax.set_xlim(-0.2, 14.2)
    ax.set_ylim(0, 5)
    ax.axis("off")

    box_w, box_h = 1.7, 1.0
    spacing = 2.3
    x_start = 1.1
    y_box = 2.6

    phases = [
        ("P0", "RULE"),
        ("P1", "MODEL_SHADOW"),
        ("P2", "MODEL_PRIMARY"),
        ("P3", "ML_SHADOW"),
        ("P4", "ML_W_FALLBACK"),
        ("P5", "ML_PRIMARY"),
    ]
    xs = [x_start + i * spacing for i in range(len(phases))]

    for (code, name), x in zip(phases, xs, strict=False):
        box = FancyBboxPatch(
            (x - box_w / 2, y_box - box_h / 2),
            box_w,
            box_h,
            boxstyle="round,pad=0.02",
            linewidth=1.5,
            edgecolor="#333",
            facecolor="#f0f0f0",
        )
        ax.add_patch(box)
        ax.text(x, y_box + 0.18, code, ha="center", fontsize=11, fontweight="bold")
        ax.text(x, y_box - 0.22, name, ha="center", fontsize=8.5, family="monospace")

    advance_labels = ["shadow add", "McNemar gate", "shadow add", "McNemar gate", "McNemar gate"]
    y_advance = y_box + 0.82
    for i in range(5):
        x0 = xs[i] + box_w / 2 + 0.05
        x1 = xs[i + 1] - box_w / 2 - 0.05
        arrow = FancyArrowPatch(
            (x0, y_advance),
            (x1, y_advance),
            arrowstyle="->",
            mutation_scale=14,
            lw=1.6,
            color="#1f77b4",
        )
        ax.add_patch(arrow)
        ax.text(
            (x0 + x1) / 2,
            y_advance + 0.18,
            advance_labels[i],
            ha="center",
            fontsize=8.5,
            color="#1f77b4",
        )

    y_demote = y_box - 0.82
    for i in range(1, 6):
        x0 = xs[i] - box_w / 2 - 0.05
        x1 = xs[i - 1] + box_w / 2 + 0.05
        arrow = FancyArrowPatch(
            (x0, y_demote),
            (x1, y_demote),
            arrowstyle="->",
            mutation_scale=12,
            lw=1.2,
            color=COLOR_ACCENT_DEEP,
            linestyle=(0, (4, 2)),
        )
        ax.add_patch(arrow)
    mid = (xs[0] + xs[-1]) / 2
    ax.text(
        mid,
        y_demote - 0.30,
        "demote (gate fires in reverse on accumulated drift)",
        ha="center",
        fontsize=9,
        color=COLOR_ACCENT_DEEP,
        style="italic",
    )

    band_x0 = xs[0] - box_w / 2 - 0.1
    band_x1 = xs[-1] + box_w / 2 + 0.1
    ax.add_patch(
        FancyBboxPatch(
            (band_x0, 0.25),
            band_x1 - band_x0,
            0.65,
            boxstyle="round,pad=0.02",
            edgecolor="#666",
            facecolor="#fff8e1",
            linewidth=1.0,
        )
    )
    ax.text(
        (band_x0 + band_x1) / 2,
        0.58,
        (
            "Rule R is structurally preserved as the safety floor in "
            "P1–P4 and as the circuit-breaker target in P5."
        ),
        ha="center",
        fontsize=9.5,
        color="#444",
    )

    ax.text(
        mid,
        4.55,
        (
            "Figure 5. The graduated-autonomy lifecycle. Solid arrows "
            "= advance; dashed arrows = demote."
        ),
        ha="center",
        fontsize=11,
    )

    out_png = RESULTS_DIR / "figure-5-lifecycle.png"
    out_svg = RESULTS_DIR / "figure-5-lifecycle.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_3b_extended_two_regimes() -> None:
    """Expanded version of Figure 3 covering all 8 benchmarks.

    Adds Snips (the surprise low-cardinality / weak-keyword case),
    TREC-6, AG News, and codelangs to the original 4-bench rule-vs-ML
    bar chart. Color-codes by regime: A (rule strong), A* (rule
    moderate), B (rule at floor).
    """
    import json as _json

    summary_path = RESULTS_DIR / "paired_mcnemar_summary.json"
    _json.loads(summary_path.read_text()) if summary_path.exists() else {}

    rows = []
    for slug, name, k in EXTENDED_BENCHES:
        path = RESULTS_DIR / f"{slug}_paired.jsonl"
        if not path.exists():
            continue
        # Read first + last checkpoint for rule/ML accuracy.
        first_ckpt, last_ckpt = None, None
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("kind") == "checkpoint":
                    if first_ckpt is None:
                        first_ckpt = rec
                    last_ckpt = rec
        if last_ckpt is None:
            continue
        rule_acc = last_ckpt["rule_test_accuracy"] * 100
        ml_acc = last_ckpt["ml_test_accuracy"] * 100
        rows.append((slug, name, k, rule_acc, ml_acc))

    if not rows:
        print("figure-3b: no data")
        return

    # Order by rule accuracy descending so the regime sort is visual.
    rows.sort(key=lambda r: -r[3])
    names = [f"{n}\n({k} labels)" for _, n, k, _, _ in rows]
    rule_acc = [r for _, _, _, r, _ in rows]
    ml_acc = [m for _, _, _, _, m in rows]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    x = np.arange(len(rows))
    width = 0.38
    ax.bar(x - width / 2, rule_acc, width, color=COLOR_RULE, label="Rule (day 0)")
    ax.bar(x + width / 2, ml_acc, width, color=COLOR_ML, label="ML head (final)")

    for i, (r, m) in enumerate(zip(rule_acc, ml_acc, strict=False)):
        ax.text(i - width / 2, r + 1.5, f"{r:.1f}%", ha="center", fontsize=8.5, color=COLOR_INK)
        ax.text(i + width / 2, m + 1.5, f"{m:.1f}%", ha="center", fontsize=8.5, color=COLOR_INK)

    # Regime tinting: A=rule>=50, A*=20<=rule<50, B=rule<20
    for i, (_, _, _, r, _) in enumerate(rows):
        if r >= 50:
            color = COLOR_REGIME_A
        elif r >= 20:
            color = "#bcbd22"  # olive — "moderate keyword affinity"
        else:
            color = COLOR_REGIME_B
        ax.axvspan(i - 0.5, i + 0.5, color=color, alpha=0.07)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("Test accuracy (%)")
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_title(
        "Figure 3b. Rule baseline vs ML head across the extended benchmark suite",
        fontsize=12,
        loc="center",
    )
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="lower left", fontsize=10)

    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-3b-extended-regimes.png"
    out_svg = RESULTS_DIR / "figure-3b-extended-regimes.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_6_autoresearch_winners() -> None:
    """Autoresearch winner per benchmark, plotted by cardinality.

    Visualizes the §5.6 finding: empirical winner depends on data
    shape. Cardinality-axis scatter, color/shape by winning head,
    annotated with the autoresearch margin.
    """
    import json as _json

    head_color = {
        "TfidfLogReg": "#999999",
        "TfidfLinearSVC": "#1f77b4",
        "TfidfMultinomialNB": "#d62728",
        "TfidfGradientBoosting": "#2ca02c",
    }
    head_marker = {
        "TfidfLogReg": "o",
        "TfidfLinearSVC": "s",
        "TfidfMultinomialNB": "^",
        "TfidfGradientBoosting": "D",
    }

    # Per-benchmark label offsets in points. Defaults to (8, 5) (above-right
    # of the marker). Overridden for benchmarks whose markers cluster on the
    # log-x axis: HWU64 (64) and Banking77 (77) sit ~8% apart in log-space,
    # so HWU64's default label is occluded by Banking77's marker; same story
    # for TREC-6 (6) and Snips (7).
    label_offsets = {
        "HWU64": (-10, -16),
        "TREC-6": (-12, -16),
        "Snips": (8, -2),
    }

    fig, ax = plt.subplots(figsize=(11, 5.5))
    annotated_heads = set()
    for slug, name, k in EXTENDED_BENCHES:
        path = RESULTS_DIR / f"autoresearch-mlhead-{slug}.json"
        if not path.exists():
            continue
        d = _json.loads(path.read_text())
        winner = d["winner"]
        winner_acc = d["reports"][winner]["accuracy"] * 100
        color = head_color.get(winner, "#777")
        marker = head_marker.get(winner, "x")
        label = winner if winner not in annotated_heads else None
        annotated_heads.add(winner)
        ax.scatter(
            [k],
            [winner_acc],
            s=140,
            c=color,
            marker=marker,
            edgecolors="black",
            linewidths=0.6,
            label=label,
            zorder=3,
        )
        offset = label_offsets.get(name, (8, 5))
        ha = "right" if offset[0] < 0 else "left"
        ax.annotate(
            name, (k, winner_acc), textcoords="offset points", xytext=offset, fontsize=9, ha=ha
        )

    ax.set_xscale("log")
    ax.set_xlabel("Label cardinality (log)")
    ax.set_ylabel("Winning ML-head accuracy (%)")
    ax.set_title(
        "Figure 6. Autoresearch picks shape-dependent MLHead winners across benchmarks",
        fontsize=12,
    )
    ax.set_ylim(50, 102)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="lower left", title="Winning head", fontsize=10)
    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-6-autoresearch-winners.png"
    out_svg = RESULTS_DIR / "figure-6-autoresearch-winners.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def figure_7_cifar10_transition() -> None:
    """CIFAR-10 image-bench transition curve (paper §5.8).

    Demonstrates the lifecycle generalizes beyond text. Rule is the
    color-centroid heuristic; ML head is sklearn LogReg on flat
    pixels. Honest framing: pretrained embeddings would raise the
    ML ceiling but not change the curve shape.
    """
    path = RESULTS_DIR / "cifar10_paired.jsonl"
    if not path.exists():
        print("figure-7: cifar10_paired.jsonl missing; skip")
        return
    ckpts = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") == "checkpoint":
                ckpts.append(rec)
    if not ckpts:
        print("figure-7: no checkpoints; skip")
        return

    outcomes = np.array([c["training_outcomes"] for c in ckpts])
    rule_acc = np.array([c["rule_test_accuracy"] for c in ckpts]) * 100
    ml_acc = np.array([c["ml_test_accuracy"] for c in ckpts]) * 100
    # Compute paired-McNemar p-value at each checkpoint and find first fire.
    first_fire = None
    p_values = []
    for c in ckpts:
        _, _, p = paired_mcnemar_p(c["rule_correct"], c["ml_correct"])
        p_values.append(p)
        if first_fire is None and p < ALPHA:
            first_fire = c["training_outcomes"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

    ax1.fill_between(
        outcomes,
        rule_acc,
        ml_acc,
        where=ml_acc >= rule_acc,
        color=COLOR_ML,
        alpha=0.10,
        label="ML margin over rule",
    )
    ax1.plot(outcomes, rule_acc, color=COLOR_RULE, lw=2, label="Color-centroid rule")
    ax1.plot(outcomes, ml_acc, color=COLOR_ML, lw=2.2, label="Pixel LogReg head")
    if first_fire is not None:
        ax1.axvline(
            first_fire,
            color=COLOR_ACCENT_DEEP,
            lw=1.2,
            ls="--",
            alpha=0.7,
            label=f"Gate fires (p<{ALPHA})",
        )
    ax1.set_xscale("log")
    ax1.set_xlim(left=40)
    ax1.set_ylim(0, 50)
    ax1.set_xlabel("Training outcomes (log)")
    ax1.set_ylabel("Test accuracy (%)")
    ax1.set_title("(a) CIFAR-10 transition curve", loc="left", fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower right", fontsize=9)

    ax2.plot(
        outcomes, np.maximum(p_values, 1e-300), color=COLOR_ML, lw=2.2, marker="o", markersize=5
    )
    ax2.axhline(ALPHA, color=COLOR_ACCENT_DEEP, lw=1.2, ls="--", label=f"alpha = {ALPHA}")
    ax2.set_yscale("log")
    ax2.set_xscale("log")
    ax2.set_xlim(left=40)
    ax2.set_xlabel("Training outcomes (log)")
    ax2.set_ylabel("Paired McNemar p-value (log)")
    ax2.set_title("(b) p-value trajectory", loc="left", fontsize=11)
    ax2.grid(True, which="both", alpha=0.3)
    ax2.legend(loc="lower left", fontsize=9)

    fig.suptitle(
        "Figure 7. The transition curve generalizes to image classification (CIFAR-10)",
        fontsize=12,
        y=1.02,
    )
    fig.tight_layout()
    out_png = RESULTS_DIR / "figure-7-cifar10-transition.png"
    out_svg = RESULTS_DIR / "figure-7-cifar10-transition.svg"
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png.name}, {out_svg.name}")


def main() -> None:
    figure_1_transition_curves()
    figure_2_pvalue_trajectories()
    figure_3_two_regimes()
    figure_3b_extended_two_regimes()
    figure_4_paired_vs_unpaired()
    figure_5_lifecycle()
    figure_6_autoresearch_winners()
    figure_7_cifar10_transition()


if __name__ == "__main__":
    main()
