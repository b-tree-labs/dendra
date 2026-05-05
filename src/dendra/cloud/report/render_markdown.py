# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Markdown renderer for per-switch report cards.

Output mirrors the locked sample at
``docs/working/sample-reports/triage_rule.md`` — heading, status
banner, transition-curve placeholder, p-value placeholder, Mermaid
phase timeline, cost trajectory (when ``cost_per_call`` is supplied),
hypothesis-vs-observed verdict (when hypothesis claims supplied), and
raw checkpoints table.

PNG chart embedding lives in a separate ``charts`` module (Phase 2);
when matplotlib is available and a chart path is provided, the
``{transition_chart}`` slot in the template fills with an image
reference. Without it, the slot stays as a "(no chart yet)" line and
the markdown still reads cleanly.
"""

from __future__ import annotations

import datetime as _dt

from dendra.cloud.report.aggregator import HypothesisVerdict, SwitchMetrics

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_switch_card(
    metrics: SwitchMetrics,
    *,
    file_location: str | None = None,
    site_function: str | None = None,
    gate_name: str = "McNemarGate",
    alpha: float = 0.01,
    cost_per_call: float | None = None,
    estimated_calls_per_month: int | None = None,
    cost_post_graduation: float = 3e-6,
    hypothesis: HypothesisVerdict | None = None,
    methodology_url: str = "../../methodology/test-driven-product-development.md",
    transition_chart_path: str | None = None,
    pvalue_chart_path: str | None = None,
    cost_chart_path: str | None = None,
) -> str:
    """Render the per-switch report card markdown.

    Required: ``metrics`` (from :func:`aggregate_switch`). Everything
    else is optional context that fills in additional sections —
    callers without that context get a card that still reads cleanly,
    just with fewer sections populated.
    """
    parts: list[str] = []

    # ---- Header ----------------------------------------------------------
    title_name = _humanize(metrics.switch_name)
    parts.append(f"# {title_name} — Graduation Report Card\n")
    parts.append(f"Generated {_format_timestamp(metrics.generated_at)}.")
    if file_location and site_function:
        parts.append(f"Site: `{file_location}:{site_function}`.")
    elif file_location:
        parts.append(f"Site: `{file_location}`.")
    if metrics.site_fingerprint:
        parts.append(f"Fingerprint: `{metrics.site_fingerprint}`.")
    parts.append("")

    # ---- Status banner ---------------------------------------------------
    parts.append("## Status\n")
    parts.append(_status_banner(metrics, gate_name=gate_name, alpha=alpha))
    parts.append("")

    # ---- Transition curve ------------------------------------------------
    parts.append("## Transition curve\n")
    if transition_chart_path:
        parts.append(f"![Rule vs ML accuracy over outcomes]({transition_chart_path})\n")
    else:
        parts.append("> *Chart rendering pending — install `dendra[viz]` to generate the PNG.*\n")

    if metrics.crossover_outcome and metrics.gate_fire_outcome:
        parts.append(
            f"The crossover (where ML first overtakes the rule) was at outcome "
            f"{metrics.crossover_outcome}. The gate fires at "
            f"{metrics.gate_fire_outcome} — the gate measures *evidence sufficiency*, "
            f"not crossover; the lag is the cost of paired-McNemar at α = {alpha}. "
            f"See [methodology]({methodology_url}).\n"
        )
    elif metrics.crossover_outcome:
        parts.append(
            f"Crossover (ML first overtakes Rule) at outcome "
            f"{metrics.crossover_outcome}. Gate has not yet fired.\n"
        )

    # ---- p-value trajectory ---------------------------------------------
    parts.append("## p-value trajectory\n")
    if pvalue_chart_path:
        parts.append(f"![Gate p-value over outcomes]({pvalue_chart_path})\n")
    else:
        parts.append(f"> *p-value at each checkpoint shown in the table below; α = {alpha}.*\n")

    # ---- Phase timeline (Mermaid) ---------------------------------------
    parts.append("## Phase timeline\n")
    parts.append(_render_phase_timeline_mermaid(metrics))
    parts.append("")

    # ---- Cost trajectory ------------------------------------------------
    if cost_per_call is not None:
        parts.append("## Cost trajectory\n")
        if cost_chart_path:
            parts.append(f"![Per-call cost over time]({cost_chart_path})\n")
        parts.append(
            _render_cost_table(
                cost_per_call=cost_per_call,
                cost_post_graduation=cost_post_graduation,
                estimated_calls_per_month=estimated_calls_per_month,
            )
        )
        parts.append(
            "\n> **Pro-forma: model substitution.** Run "
            f"`dendra report {metrics.switch_name} --model claude-haiku-4.5` to "
            f"see this site's pre-graduation cost on a different LLM. Useful as a "
            f"pro-forma when sizing your AI budget *before* graduation.\n"
        )

    # ---- Hypothesis evidence --------------------------------------------
    if hypothesis is not None:
        parts.append("## Hypothesis evidence\n")
        parts.append(_render_hypothesis_table(hypothesis, switch_name=metrics.switch_name))

    # ---- Raw checkpoints ------------------------------------------------
    parts.append("## Raw checkpoints\n")
    parts.append(_render_checkpoint_table(metrics))

    # ---- Footer ---------------------------------------------------------
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(
        f"*Regenerate with `dendra report {metrics.switch_name}`. "
        f"Last drift check: "
        f"{'see drift events above' if metrics.drift_events else 'no drift detected'}.*"
    )
    parts.append("")
    parts.append(f"*Methodology: [Test-Driven Product Development]({methodology_url}).*")
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _status_banner(metrics: SwitchMetrics, *, gate_name: str, alpha: float) -> str:
    """The blockquote at the top of the card. Adapts to phase + data."""
    phase_str = f"`{metrics.current_phase.value.upper()}`"

    if metrics.total_outcomes == 0:
        return (
            f"> **Phase: {phase_str}** — wrapped, **0 outcomes recorded**.\n"
            f"> Gate (`{gate_name}`, α = {alpha}) is configured and waiting for verdicts.\n"
            f"> No graduation evidence yet — this report card will fill in as outcomes accumulate."
        )

    if metrics.gate_fire_outcome is not None:
        # Graduated
        rule_pct = (
            f"{metrics.rule_accuracy_final * 100:.1f}%"
            if metrics.rule_accuracy_final is not None
            else "—"
        )
        ml_pct = (
            f"{metrics.ml_accuracy_final * 100:.1f}%"
            if metrics.ml_accuracy_final is not None
            else "—"
        )
        effect_pp = None
        if metrics.rule_accuracy_final is not None and metrics.ml_accuracy_final is not None:
            effect_pp = (metrics.ml_accuracy_final - metrics.rule_accuracy_final) * 100
        effect_str = f"+{effect_pp:.1f} pp" if effect_pp else "—"
        p_str = (
            _format_p(metrics.gate_fire_p_value) if metrics.gate_fire_p_value is not None else "—"
        )
        return (
            f"> **Phase: {phase_str}** — graduated at outcome {metrics.gate_fire_outcome}.\n"
            f"> Gate (`{gate_name}`, α = {alpha}) fired with p = **{p_str}**.\n"
            f"> Effect size: rule {rule_pct} → ML {ml_pct} (**{effect_str}**)."
        )

    # Pre-graduation (records exist but gate hasn't cleared)
    last_p = None
    last_n = 0
    if metrics.checkpoints:
        last = metrics.checkpoints[-1]
        last_p = last.paired_p_value
        last_n = last.paired_n
    p_str = _format_p(last_p) if last_p is not None else "(insufficient paired data)"

    rule_pct_str = "—"
    ml_pct_str = "—"
    if metrics.checkpoints:
        last = metrics.checkpoints[-1]
        if last.rule_accuracy is not None:
            rule_pct_str = f"{last.rule_accuracy * 100:.1f}%"
        if last.ml_accuracy is not None:
            ml_pct_str = f"{last.ml_accuracy * 100:.1f}%"

    return (
        f"> **Phase: {phase_str}** — accumulating evidence.\n"
        f"> {metrics.total_outcomes} outcomes recorded "
        f"(paired n = {last_n}). Gate (`{gate_name}`, α = {alpha}) "
        f"currently at p = **{p_str}**.\n"
        f"> Rule {rule_pct_str} vs ML {ml_pct_str} — gate has not yet fired."
    )


def _render_phase_timeline_mermaid(metrics: SwitchMetrics) -> str:
    """Render the phase progression as a Mermaid Gantt chart.

    Renders inline on GitHub / GitLab / VS Code preview without any
    image generation. If we have phase-history timestamps, use them;
    otherwise emit a "phase only, no dates" simplified version.
    """
    if not metrics.phase_history:
        # No phase history — emit a minimal current-state diagram
        return (
            "```mermaid\n"
            "flowchart LR\n"
            f"    A[Current phase: {metrics.current_phase.value.upper()}]\n"
            "```"
        )

    lines = [
        "```mermaid",
        "gantt",
        "    dateFormat YYYY-MM-DD",
        f"    title {_humanize(metrics.switch_name)} lifecycle",
        "    section Production",
    ]
    sorted_phases = sorted(metrics.phase_history, key=lambda x: x[1])
    for i, (phase, ts) in enumerate(sorted_phases):
        date_str = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d")
        if i + 1 < len(sorted_phases):
            next_ts = sorted_phases[i + 1][1]
            duration_days = max(1, int((next_ts - ts) / 86400))
            lines.append(f"    {phase.value.upper():<24}:done, p{i}, {date_str}, {duration_days}d")
        else:
            # Last phase is currently-active
            now_ts = metrics.last_record_timestamp or _dt.datetime.now(_dt.timezone.utc).timestamp()
            duration_days = max(1, int((now_ts - ts) / 86400))
            lines.append(
                f"    {phase.value.upper():<24}:active, p{i}, {date_str}, {duration_days}d"
            )
    lines.append("```")
    return "\n".join(lines)


def _render_cost_table(
    *,
    cost_per_call: float,
    cost_post_graduation: float,
    estimated_calls_per_month: int | None,
) -> str:
    """Cost-savings table. ``estimated_calls_per_month`` populates per-month rows."""
    reduction_pct = (1 - cost_post_graduation / cost_per_call) * 100 if cost_per_call else 0
    rows = [
        "| | Pre-graduation | Post-graduation | Reduction |",
        "|---|---:|---:|---:|",
        f"| Per call | ${cost_per_call:.6f} | ${cost_post_graduation:.6f} | {reduction_pct:.2f}% |",
    ]
    if estimated_calls_per_month:
        pre_month = cost_per_call * estimated_calls_per_month
        post_month = cost_post_graduation * estimated_calls_per_month
        rows.append(
            f"| Per month ({estimated_calls_per_month:,} calls) | ${pre_month:,.2f} | "
            f"${post_month:,.2f} | ${pre_month - post_month:,.2f} |"
        )
    return "\n".join(rows)


def _render_hypothesis_table(verdict: HypothesisVerdict, *, switch_name: str) -> str:
    """Pre-registered claims vs observed evidence."""
    rows = [
        f"The pre-registered hypothesis at "
        f"[`dendra/hypotheses/{switch_name}.md`](../hypotheses/{switch_name}.md) "
        f"is summarized below:\n",
        "| Predicted | Observed | Verdict |",
        "|---|---|---|",
    ]
    grad_within = verdict.graduation_within_predicted_interval()
    if (
        verdict.predicted_graduation_low is not None
        and verdict.predicted_graduation_high is not None
    ):
        observed_str = (
            f"{verdict.observed_graduation_outcome} outcomes"
            if verdict.observed_graduation_outcome is not None
            else "(in flight)"
        )
        verdict_str = (
            "✓ Within interval"
            if grad_within is True
            else "✗ Outside interval"
            if grad_within is False
            else "(in flight)"
        )
        rows.append(
            f"| Graduation depth: "
            f"{verdict.predicted_graduation_low}–{verdict.predicted_graduation_high} outcomes "
            f"| {observed_str} | {verdict_str} |"
        )
    if verdict.predicted_effect_size_pp is not None:
        observed = (
            f"{verdict.observed_effect_size_pp:.1f} pp"
            if verdict.observed_effect_size_pp is not None
            else "(insufficient data)"
        )
        meets = verdict.effect_size_meets_threshold()
        verdict_str = (
            "✓ Met" if meets is True else "✗ Below threshold" if meets is False else "(in flight)"
        )
        rows.append(
            f"| Effect size: ≥ {verdict.predicted_effect_size_pp:.1f} pp "
            f"| {observed} | {verdict_str} |"
        )
    if verdict.observed_p_at_first_clear is not None:
        rows.append(
            f"| p < 0.01 at first clear | "
            f"{_format_p(verdict.observed_p_at_first_clear)} | ✓ Cleared |"
        )
    return "\n".join(rows)


def _render_checkpoint_table(metrics: SwitchMetrics) -> str:
    """Tabular dump of every checkpoint computed by the aggregator."""
    if not metrics.checkpoints:
        return "> *No checkpoints yet. The first checkpoint runs at outcome 50.*"
    rows = [
        "| Outcome | Rule acc | ML acc | McNemar p | Phase |",
        "|---:|---:|---:|---:|---|",
    ]
    for cp in metrics.checkpoints:
        rule_str = f"{cp.rule_accuracy * 100:.1f}%" if cp.rule_accuracy is not None else "—"
        ml_str = f"{cp.ml_accuracy * 100:.1f}%" if cp.ml_accuracy is not None else "—"
        p_str = _format_p(cp.paired_p_value) if cp.paired_p_value is not None else "—"
        phase_str = cp.phase_at_checkpoint.value.upper()

        # Bold the gate-fire row so the eye lands on it
        is_gate_fire = (
            metrics.gate_fire_outcome is not None and cp.outcome_count == metrics.gate_fire_outcome
        )
        if is_gate_fire:
            rows.append(
                f"| **{cp.outcome_count}** | **{rule_str}** | **{ml_str}** | "
                f"**{p_str}** | **{phase_str}** ← gate |"
            )
        else:
            rows.append(f"| {cp.outcome_count} | {rule_str} | {ml_str} | {p_str} | {phase_str} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _humanize(switch_name: str) -> str:
    """``triage_rule`` → ``Triage Rule``."""
    return " ".join(part.capitalize() for part in switch_name.replace("-", "_").split("_"))


def _format_timestamp(iso: str) -> str:
    """ISO-8601 → human-readable UTC stamp like ``2026-04-29 22:15 UTC``."""
    if not iso:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        ts = _dt.datetime.fromisoformat(iso)
        return ts.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return iso


def _format_p(p: float | None) -> str:
    """Render p-values: scientific for tiny, fixed for normal-range."""
    if p is None:
        return "—"
    if p < 1e-4:
        return f"{p:.2e}"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"
