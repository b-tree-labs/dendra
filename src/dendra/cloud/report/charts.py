# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Matplotlib chart rendering for per-switch report cards.

Three chart types match the locked sample at
``docs/working/sample-reports/triage_rule.md``:

- ``transition_curve(metrics, out_path)`` — Rule vs ML accuracy over
  outcomes with the gate-fire moment marked.
- ``pvalue_trajectory(metrics, out_path)`` — Paired-McNemar p-value
  over outcomes (log-y), with α threshold dashed.
- ``cost_trajectory(metrics, out_path, cost_per_call, ...)`` — Per-call
  cost over time with the graduation moment annotated.

All chart generators import matplotlib lazily so the rest of the
report module works without the ``dendra[viz]`` extra installed.
Callers should catch :class:`ImportError` and fall back to the
text-only "Chart rendering pending — install dendra[viz]" placeholder.

Color palette mirrors ``scripts/figures/build_paper_figures.py`` so
customer report cards visually match the published research.
"""

from __future__ import annotations

from pathlib import Path

from dendra.cloud.report.aggregator import SwitchMetrics

# Brand palette — same constants as the paper figures + the sample-
# report generator. Keeping these in sync is a manual discipline; if
# the paper palette evolves, mirror the change here.
_COLOR_INK = "#1a1a1f"
_COLOR_INK_SOFT = "#6a6a72"
_COLOR_ACCENT = "#bf5700"
_COLOR_ACCENT_DEEP = "#8a3f00"
_COLOR_GROUND = "#f8f6f1"
_COLOR_RULE = _COLOR_INK_SOFT
_COLOR_ML = _COLOR_ACCENT
_COLOR_GATE = _COLOR_ACCENT_DEEP


def _apply_brand_style(plt) -> None:
    """Configure matplotlib once per render with Dendra's brand palette."""
    plt.rcParams.update(
        {
            "figure.facecolor": _COLOR_GROUND,
            "axes.facecolor": _COLOR_GROUND,
            "savefig.facecolor": _COLOR_GROUND,
            "axes.edgecolor": _COLOR_INK,
            "axes.labelcolor": _COLOR_INK,
            "axes.titlecolor": _COLOR_INK,
            "grid.color": _COLOR_INK_SOFT,
            "grid.alpha": 0.2,
            "xtick.color": _COLOR_INK,
            "ytick.color": _COLOR_INK,
            "text.color": _COLOR_INK,
            "legend.facecolor": _COLOR_GROUND,
            "legend.edgecolor": _COLOR_INK_SOFT,
            "font.family": "sans-serif",
            "font.size": 10,
        }
    )


# ---------------------------------------------------------------------------
# Public chart generators
# ---------------------------------------------------------------------------


def transition_curve(
    metrics: SwitchMetrics,
    out_path: Path | str,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (9, 4.5),
    dpi: int = 140,
) -> Path:
    """Render the rule-vs-ML accuracy curve to ``out_path``.

    Returns the absolute output path. Raises :class:`ImportError`
    if ``dendra[viz]`` is not installed.

    The chart shows two series across all checkpoints:
    rule accuracy (gray dashed) and ML accuracy (accent solid).
    If the gate has fired, a vertical line marks the gate-fire
    outcome with the p-value annotated. If a crossover (where ML
    first overtakes rule) is detected and is distinct from the
    gate-fire, it's marked separately with a dotted line.

    Pre-graduation switches still produce a chart (showing the
    accumulating curves so far). Day-zero switches with zero
    checkpoints raise :class:`ValueError` — caller should skip
    chart rendering for those and let the markdown placeholder
    handle the empty state.
    """
    if not metrics.checkpoints:
        raise ValueError(
            "transition_curve requires at least one checkpoint; "
            "metrics has 0 — caller should skip chart rendering for "
            "day-zero switches"
        )

    import matplotlib.pyplot as plt

    _apply_brand_style(plt)
    fig, ax = plt.subplots(figsize=figsize)

    outcomes = [cp.outcome_count for cp in metrics.checkpoints]
    rule_acc = [
        cp.rule_accuracy * 100 if cp.rule_accuracy is not None else None
        for cp in metrics.checkpoints
    ]
    ml_acc = [
        cp.ml_accuracy * 100 if cp.ml_accuracy is not None else None for cp in metrics.checkpoints
    ]

    if any(a is not None for a in rule_acc):
        ax.plot(
            outcomes,
            [a if a is not None else float("nan") for a in rule_acc],
            color=_COLOR_RULE,
            linestyle="--",
            linewidth=1.5,
            marker="o",
            markersize=4,
            label="Rule",
        )
    if any(a is not None for a in ml_acc):
        ax.plot(
            outcomes,
            [a if a is not None else float("nan") for a in ml_acc],
            color=_COLOR_ML,
            linewidth=2.0,
            marker="o",
            markersize=4,
            label="ML head",
        )

    if metrics.gate_fire_outcome is not None:
        ax.axvline(
            metrics.gate_fire_outcome,
            color=_COLOR_GATE,
            linewidth=1.5,
            alpha=0.7,
        )
        if metrics.gate_fire_p_value is not None:
            p = metrics.gate_fire_p_value
            p_str = f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"
            ax.text(
                metrics.gate_fire_outcome,
                ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.05,
                f" gate fires (n={metrics.gate_fire_outcome})\n p = {p_str}",
                fontsize=9,
                color=_COLOR_GATE,
                verticalalignment="bottom",
            )

    if (
        metrics.crossover_outcome is not None
        and metrics.crossover_outcome != metrics.gate_fire_outcome
    ):
        ax.axvline(
            metrics.crossover_outcome,
            color=_COLOR_INK_SOFT,
            linewidth=1.0,
            alpha=0.4,
            linestyle=":",
        )

    ax.set_xlabel("Outcomes")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title(title or f"Transition curve — {metrics.switch_name}")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    if any(outcomes) and outcomes[-1] >= 200:
        ax.set_xscale("log")
    ax.legend(loc="lower right", framealpha=0.95)

    plt.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out.resolve()


def pvalue_trajectory(
    metrics: SwitchMetrics,
    out_path: Path | str,
    *,
    alpha: float = 0.01,
    figsize: tuple[float, float] = (9, 3.8),
    dpi: int = 140,
) -> Path:
    """Render the paired-McNemar p-value trajectory to ``out_path``.

    Log-y axis, inverted so smaller p-values are visually higher
    (matches paper figure 2 convention). Horizontal dashed line at
    α. Vertical line at gate-fire outcome (if cleared).
    """
    if not metrics.checkpoints:
        raise ValueError("pvalue_trajectory requires at least one checkpoint")

    import matplotlib.pyplot as plt

    _apply_brand_style(plt)
    fig, ax = plt.subplots(figsize=figsize)

    outcomes = [cp.outcome_count for cp in metrics.checkpoints]
    pvalues = [cp.paired_p_value for cp in metrics.checkpoints]
    valid_pairs = [(o, p) for o, p in zip(outcomes, pvalues, strict=False) if p is not None]
    if not valid_pairs:
        raise ValueError("no checkpoint has a finite p-value")

    xs, ys = zip(*valid_pairs, strict=False)
    ax.plot(
        xs,
        ys,
        color=_COLOR_ML,
        linewidth=2.0,
        marker="o",
        markersize=5,
    )
    ax.axhline(
        alpha,
        color=_COLOR_INK,
        linewidth=1.0,
        linestyle="--",
        alpha=0.6,
    )
    ax.text(
        xs[0],
        alpha * 1.5,
        f"α = {alpha}",
        fontsize=9,
        color=_COLOR_INK,
        verticalalignment="bottom",
    )
    if metrics.gate_fire_outcome is not None:
        ax.axvline(
            metrics.gate_fire_outcome,
            color=_COLOR_GATE,
            linewidth=1.5,
            alpha=0.7,
        )

    ax.set_yscale("log")
    ax.set_xlabel("Outcomes")
    ax.set_ylabel("Paired-McNemar p-value")
    ax.set_title(f"p-value trajectory — {metrics.switch_name}")
    ax.grid(True, alpha=0.3, which="both")
    ax.invert_yaxis()
    plt.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out.resolve()


def cost_trajectory(
    metrics: SwitchMetrics,
    out_path: Path | str,
    *,
    cost_per_call: float,
    cost_post_graduation: float = 3e-6,
    estimated_calls_per_day: int | None = None,
    figsize: tuple[float, float] = (9, 3.5),
    dpi: int = 140,
) -> Path:
    """Render the per-call cost trajectory to ``out_path``.

    Pre-graduation cost is the configured per-call rate (LLM round-
    trip). Post-graduation drops to ``cost_post_graduation`` (default
    matches in-process inference at ~3 microdollars/call).

    For graduated switches: x-axis is "days since wrap", with a
    vertical line at the graduation moment. Pre-graduation switches:
    flat line at the pre-graduation rate (no graduation event yet).
    """
    if not metrics.checkpoints:
        raise ValueError("cost_trajectory requires at least one checkpoint")

    import matplotlib.pyplot as plt

    _apply_brand_style(plt)
    fig, ax = plt.subplots(figsize=figsize)

    # Approximate days since wrap from checkpoint cadence + estimated traffic.
    # If we have phase_history with timestamps, use those; otherwise just
    # plot outcome count on the x-axis labeled accordingly.
    use_days = bool(metrics.phase_history) and estimated_calls_per_day
    if use_days:
        x_label = "Days since switch wrapped"
        xs = [
            (cp.outcome_count / max(1, estimated_calls_per_day or 1)) for cp in metrics.checkpoints
        ]
        graduation_x = (
            metrics.gate_fire_outcome / max(1, estimated_calls_per_day or 1)
            if metrics.gate_fire_outcome
            else None
        )
    else:
        x_label = "Outcomes"
        xs = [cp.outcome_count for cp in metrics.checkpoints]
        graduation_x = metrics.gate_fire_outcome

    if metrics.gate_fire_outcome is not None:
        # Cost was pre-graduation up through the gate-fire checkpoint,
        # post-graduation after.
        costs = [
            cost_per_call if cp.outcome_count <= metrics.gate_fire_outcome else cost_post_graduation
            for cp in metrics.checkpoints
        ]
    else:
        costs = [cost_per_call] * len(metrics.checkpoints)

    ax.plot(xs, costs, color=_COLOR_ML, linewidth=2.0, marker="o", markersize=4)

    if graduation_x is not None:
        ax.axvline(graduation_x, color=_COLOR_GATE, linewidth=1.5, alpha=0.7)
        ax.text(
            graduation_x,
            cost_post_graduation * 100,
            " graduation\n → in-process",
            fontsize=9,
            color=_COLOR_GATE,
            verticalalignment="bottom",
        )

    ax.set_yscale("log")
    ax.set_xlabel(x_label)
    ax.set_ylabel("$ per call (log)")
    ax.set_title(f"Cost trajectory — {metrics.switch_name}")
    ax.grid(True, alpha=0.3, which="both")
    plt.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out.resolve()


__all__ = ["transition_curve", "pvalue_trajectory", "cost_trajectory"]
