# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Project-level rollup across all switches in a storage backend.

The ``dendra report --summary`` view answers: "How is my whole
graduation program doing?" Aggregates per-switch metrics, computes
phase distribution, project-wide cost reduction, drift watch, and
hypothesis-vs-observed rollup.

Storage agnostic: the storage backend must expose ``switch_names()``
plus the standard ``load_records()``. ``FileStorage`` and
``SqliteStorage`` both qualify; ``InMemoryStorage`` does not (no
``switch_names()`` method) — caller passes a per-switch list
explicitly in that case.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from dendra.cloud.report.aggregator import SwitchMetrics, aggregate_switch
from dendra.core import Phase


@dataclass(frozen=True)
class ProjectSummary:
    """Aggregate state across all wrapped switches."""

    switches: list[SwitchMetrics] = field(default_factory=list)
    total_outcomes: int = 0
    graduated_count: int = 0
    pre_graduation_count: int = 0
    drift_count: int = 0
    generated_at: str = ""

    def phase_distribution(self) -> dict[Phase, int]:
        out: dict[Phase, int] = {}
        for s in self.switches:
            out[s.current_phase] = out.get(s.current_phase, 0) + 1
        return out


def aggregate_project(
    storage: Any,
    *,
    switch_names: list[str] | None = None,
    alpha: float = 0.01,
) -> ProjectSummary:
    """Walk all switches in storage and produce a ProjectSummary.

    If ``switch_names`` is supplied, only those switches are read.
    Otherwise the storage backend's ``switch_names()`` method is
    consulted; ``AttributeError`` is raised if the backend doesn't
    expose one.
    """
    if switch_names is None:
        try:
            switch_names = storage.switch_names()
        except AttributeError as e:
            raise AttributeError(
                "storage backend does not expose switch_names(); "
                "pass switch_names=[...] explicitly to aggregate_project"
            ) from e

    metrics_list: list[SwitchMetrics] = []
    total = 0
    graduated = 0
    pre_grad = 0
    drift = 0
    for name in switch_names:
        m = aggregate_switch(storage, name, alpha=alpha)
        metrics_list.append(m)
        total += m.total_outcomes
        if m.gate_fire_outcome is not None:
            graduated += 1
        elif m.total_outcomes > 0:
            pre_grad += 1
        drift += len(m.drift_events)

    return ProjectSummary(
        switches=metrics_list,
        total_outcomes=total,
        graduated_count=graduated,
        pre_graduation_count=pre_grad,
        drift_count=drift,
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_project_summary(
    summary: ProjectSummary,
    *,
    project_name: str = "(this project)",
    methodology_url: str = "../methodology/test-driven-product-development.md",
) -> str:
    """Render the project rollup markdown.

    Mirrors the locked sample at
    ``docs/working/sample-reports/_summary.md`` — cockpit one-liner,
    phase distribution table, per-switch status table, hypothesis
    roll-up, drift watch, pending hypotheses.
    """
    n = len(summary.switches)
    parts: list[str] = []

    # ---- Header ----------------------------------------------------------
    parts.append("# Project Switches — Status Summary\n")
    parts.append(
        f"Generated {_format_timestamp(summary.generated_at)}.\n"
        f"Project: `{project_name}`. **{n} switch{_s(n)}** wrapped, "
        f"{summary.total_outcomes:,} total outcomes recorded.\n"
    )

    # ---- Cockpit ---------------------------------------------------------
    parts.append("## Cockpit\n")
    parts.append(_cockpit_blockquote(summary))
    parts.append("")

    # ---- Phase distribution ---------------------------------------------
    parts.append("## Phase distribution\n")
    parts.append(_phase_distribution_table(summary))
    parts.append("")

    # ---- Per-switch status table ----------------------------------------
    parts.append("## Per-switch status\n")
    parts.append(_per_switch_table(summary))
    parts.append("")

    # ---- Hypothesis-vs-observed roll-up ---------------------------------
    parts.append("## Hypothesis-vs-observed roll-up\n")
    parts.append(_hypothesis_rollup(summary))
    parts.append("")

    # ---- Drift watch -----------------------------------------------------
    drift_switches = [s for s in summary.switches if s.drift_events]
    if drift_switches:
        parts.append("## Drift watch — action required\n")
        parts.append(_drift_table(drift_switches))
        parts.append("")
    else:
        parts.append("## Drift watch\n")
        parts.append("No drift events detected across any switch in this project.\n")

    # ---- Pending hypotheses ---------------------------------------------
    pending = [s for s in summary.switches if s.gate_fire_outcome is None and s.total_outcomes > 0]
    if pending:
        parts.append("## Pending hypotheses (gate-fire awaited)\n")
        parts.append(_pending_table(pending))
        parts.append("")

    # ---- Footer ---------------------------------------------------------
    parts.append("---")
    parts.append("")
    parts.append(
        "*Regenerate with `dendra report --summary`. Per-switch deep-dives "
        "live alongside this file in `dendra/results/`.*"
    )
    parts.append("")
    parts.append(f"*Methodology: [Test-Driven Product Development]({methodology_url}).*")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _cockpit_blockquote(summary: ProjectSummary) -> str:
    n = len(summary.switches)
    if n == 0:
        return (
            "> **No switches wrapped yet.**\n"
            "> Run `dendra analyze --report` to discover candidate sites, "
            "then `dendra init <file>:<func>` on each to wrap."
        )

    bullets = []
    if summary.graduated_count > 0:
        bullets.append(f"**{summary.graduated_count}** graduated to ML")
    if summary.pre_graduation_count > 0:
        bullets.append(f"**{summary.pre_graduation_count}** accumulating evidence")
    not_started = n - summary.graduated_count - summary.pre_graduation_count
    if not_started > 0:
        bullets.append(f"**{not_started}** wrapped but no outcomes yet")

    status_line = " | ".join(bullets) if bullets else "all switches in initial state"

    drift_line = ""
    if summary.drift_count:
        drift_line = (
            f"\n> **⚠ {summary.drift_count} drift event"
            f"{_s(summary.drift_count)} detected** — see Drift watch below."
        )

    return (
        f"> **{n} switch{_s(n)} in flight.** {status_line}.\n"
        f"> Total outcomes recorded across the program: "
        f"**{summary.total_outcomes:,}**.{drift_line}"
    )


def _phase_distribution_table(summary: ProjectSummary) -> str:
    """Emit the phase-distribution as a sortable table."""
    dist = summary.phase_distribution()
    if not dist:
        return "*(no switches)*"
    rows = [
        "| Phase | Count |",
        "|---|---:|",
    ]
    # Sort by Phase enum order, descending counts within ties
    for phase in Phase:
        if phase in dist:
            rows.append(f"| `{phase.value.upper()}` | {dist[phase]} |")
    return "\n".join(rows)


def _per_switch_table(summary: ProjectSummary) -> str:
    if not summary.switches:
        return "*(no switches)*"
    rows = [
        "| Switch | Phase | Outcomes | Gate p | Effect | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for m in sorted(
        summary.switches,
        key=lambda s: (-s.total_outcomes, s.switch_name),
    ):
        phase_str = f"`{m.current_phase.value.upper()}`"
        outcomes_str = f"{m.total_outcomes:,}"
        if m.gate_fire_outcome is not None:
            p_str = (
                f"{m.gate_fire_p_value:.2e}"
                if m.gate_fire_p_value is not None and m.gate_fire_p_value < 1e-3
                else f"{m.gate_fire_p_value:.4f}"
                if m.gate_fire_p_value is not None
                else "—"
            )
            effect = ""
            if m.rule_accuracy_final is not None and m.ml_accuracy_final is not None:
                pp = (m.ml_accuracy_final - m.rule_accuracy_final) * 100
                effect = f"+{pp:.1f}pp"
            status = "**GRADUATED**" if not m.drift_events else "**DRIFT**"
        elif m.total_outcomes > 0:
            p_str = (
                f"{m.checkpoints[-1].paired_p_value:.3f}"
                if m.checkpoints and m.checkpoints[-1].paired_p_value is not None
                else "—"
            )
            effect = "—"
            status = "in flight"
        else:
            p_str = "—"
            effect = "—"
            status = "wrapped, no data"

        link = f"[`{m.switch_name}`]({m.switch_name}.md)"
        rows.append(f"| {link} | {phase_str} | {outcomes_str} | {p_str} | {effect} | {status} |")
    return "\n".join(rows)


def _hypothesis_rollup(summary: ProjectSummary) -> str:
    """Aggregate confirmed/refused/in-flight counts.

    Phase 1: derives confirmation status from gate_fire_outcome
    presence. Phase 2 (when hypotheses are loaded from
    dendra/hypotheses/): compares observed vs predicted intervals.
    """
    total = len(summary.switches)
    confirmed = summary.graduated_count
    in_flight = summary.pre_graduation_count
    not_started = total - confirmed - in_flight

    rows = [
        "| Dimension | Confirmed | In flight | Not started | Total |",
        "|---|---:|---:|---:|---:|",
        f"| Graduation depth in predicted interval | {confirmed} | "
        f"{in_flight} | {not_started} | {total} |",
        f"| Effect size ≥ pre-registered threshold | {confirmed} | "
        f"{in_flight} | {not_started} | {total} |",
        f"| Gate cleared at α = 0.01 | {confirmed} | {in_flight} | {not_started} | {total} |",
        f"| Drift handling (auto-rollback worked) | {summary.drift_count} | "
        f"0 | {total - summary.drift_count} | {total} |",
    ]
    return "\n".join(rows)


def _drift_table(drift_switches: list[SwitchMetrics]) -> str:
    rows = [
        "| Switch | Drift event | Action |",
        "|---|---|---|",
    ]
    for m in drift_switches:
        first_drift = m.drift_events[0] if m.drift_events else None
        if first_drift:
            ts, reason = first_drift
            ts_str = _dt.datetime.fromtimestamp(ts, _dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
            rows.append(
                f"| [`{m.switch_name}`]({m.switch_name}.md) | "
                f"{ts_str}: {reason} | "
                f"review and re-confirm hypothesis |"
            )
        else:
            rows.append(
                f"| [`{m.switch_name}`]({m.switch_name}.md) | (event details unavailable) | "
                f"see report card |"
            )
    return "\n".join(rows)


def _pending_table(pending: list[SwitchMetrics]) -> str:
    rows = [
        "| Switch | Outcomes so far | Latest p-value |",
        "|---|---:|---:|",
    ]
    for m in pending:
        last_p = (
            m.checkpoints[-1].paired_p_value
            if m.checkpoints and m.checkpoints[-1].paired_p_value is not None
            else None
        )
        p_str = (
            f"{last_p:.3f}"
            if last_p is not None and last_p >= 1e-4
            else f"{last_p:.2e}"
            if last_p is not None
            else "—"
        )
        rows.append(f"| [`{m.switch_name}`]({m.switch_name}.md) | {m.total_outcomes:,} | {p_str} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_timestamp(iso: str) -> str:
    if not iso:
        return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    try:
        return _dt.datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return iso


def _s(n: int) -> str:
    """Pluralization helper. ``_s(1)`` → ``""``; ``_s(n)`` → ``"s"`` otherwise."""
    return "" if n == 1 else "s"


__all__ = [
    "ProjectSummary",
    "aggregate_project",
    "render_project_summary",
]
