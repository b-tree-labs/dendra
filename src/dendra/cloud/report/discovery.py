# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Initial-analysis discovery report — the conversion artifact.

When a customer first runs ``dendra analyze --report``, this module
turns the analyzer's site list into a markdown opportunity assessment:
ranked top-fit sites, cohort-predicted time to graduation per site,
projected $/mo savings, recommended graduation sequence, refused-with-
reason breakdown.

This is a different artifact from per-switch and project-summary —
it's the *opportunity view* a new customer sees before they've wrapped
anything. Drives the conversion funnel from `dendra analyze` to
`dendra init`.

Mirrors the locked sample at
``docs/working/sample-reports/_initial-analysis.md``. Phase 1 ships
the markdown table + cohort comparison; Phase 2 adds the
opportunity-bubble PNG chart.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

# Default cost-per-call estimate by LLM family. Used when the user
# hasn't passed --cost-per-call. Conservative midpoint pricing as of
# Q2 2026; falls back to a generic "frontier-LLM" rate when the
# configured adapter is unknown.
_DEFAULT_COST_PER_CALL: dict[str, float] = {
    "openai": 0.0042,  # ~ Sonnet/GPT-equivalent at 500 token avg
    "anthropic": 0.0042,
    "haiku": 0.0006,
    "ollama": 0.0,  # local; functionally free
    "default": 0.0042,
}

# Heuristic: at production traffic, sites in these volume buckets see
# this many monthly calls on average. Volume bucket comes from the
# analyzer's static AST signals (route decorators, file-path hints).
# Tunable post-launch from real cohort data.
_DEFAULT_MONTHLY_CALLS_BY_VOLUME: dict[str, int] = {
    "cold": 300_000,
    "warm": 1_300_000,
    "hot": 3_000_000,
}


@dataclass(frozen=True)
class OpportunitySite:
    """One ranked site in the initial-analysis report.

    Built from the analyzer's :class:`~dendra.analyzer.ClassificationSite`
    plus cohort projections.
    """

    file_path: str
    function_name: str
    line_start: int
    pattern: str
    regime: str
    label_cardinality: int
    volume_estimate: str
    priority_score: float
    lift_status: str
    hazard_categories: list[str]
    predicted_graduation_low: int
    predicted_graduation_high: int
    estimated_monthly_savings_usd: float


def render_discovery_report(
    analyze_report: Any,
    *,
    cost_per_call: float | None = None,
    llm_provider_hint: str = "default",
    cohort_size: int = 0,
    cohort_predicted_low_per_regime: dict[str, int] | None = None,
    cohort_predicted_high_per_regime: dict[str, int] | None = None,
    methodology_url: str = "../methodology/test-driven-product-development.md",
) -> str:
    """Render the initial-analysis markdown report.

    Parameters
    ----------
    analyze_report
        An :class:`~dendra.analyzer.AnalyzerReport` instance from a
        recent ``dendra.analyzer.analyze(path)`` call.
    cost_per_call
        Estimated $/call for the configured LLM. If ``None``, looks
        up by ``llm_provider_hint`` in the default table.
    llm_provider_hint
        ``"openai"`` / ``"anthropic"`` / ``"haiku"`` / ``"ollama"`` /
        ``"default"``. Used to pick a default cost when
        ``cost_per_call`` is None.
    cohort_size
        Cohort size (from insights tuned defaults). Surfaced in the
        report as evidence basis.
    cohort_predicted_low_per_regime, cohort_predicted_high_per_regime
        Override the default regime-keyed graduation intervals. Used
        for the Insights-cohort path.
    """
    cost = cost_per_call if cost_per_call is not None else _DEFAULT_COST_PER_CALL.get(
        llm_provider_hint, _DEFAULT_COST_PER_CALL["default"]
    )

    sites = _rank_sites(
        analyze_report,
        cost_per_call=cost,
        cohort_low=cohort_predicted_low_per_regime,
        cohort_high=cohort_predicted_high_per_regime,
    )

    auto_liftable = [s for s in sites if s.lift_status == "auto_liftable"]
    needs_annotation = [s for s in sites if s.lift_status == "needs_annotation"]
    refused = [s for s in sites if s.lift_status == "refused"]
    already = getattr(analyze_report, "already_dendrified", []) or []
    total_savings = sum(s.estimated_monthly_savings_usd for s in auto_liftable)
    annual_savings = total_savings * 12

    parts: list[str] = []

    # ---- Header ----------------------------------------------------------
    parts.append("# Initial Analysis — what `dendra analyze` found in this codebase\n")
    parts.append(
        f"Generated {_dt.datetime.now(_dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}. "
        f"**No switches wrapped yet.**\n"
        f"Project root: `{analyze_report.root}`. "
        f"{analyze_report.files_scanned:,} Python file"
        f"{'' if analyze_report.files_scanned == 1 else 's'} scanned.\n"
    )

    # ---- Cockpit ---------------------------------------------------------
    parts.append("## Cockpit\n")
    if not sites and not already:
        parts.append(
            "> **No classification sites discovered.**\n"
            f"> The analyzer scanned {analyze_report.files_scanned:,} files "
            "and didn't find any patterns matching its detectors (P1–P6). "
            "If you expected hits, your code may be using a pattern shape we "
            "don't yet recognize — `dendra analyze --verbose` prints the "
            "shapes considered.\n"
        )
    else:
        first_action = ""
        if auto_liftable:
            top = auto_liftable[0]
            first_action = (
                f"\n>\n> **Recommended first wrap**: `{top.function_name}` "
                f"at `{top.file_path}:{top.line_start}` — "
                f"highest fit, {top.regime} regime ({top.label_cardinality} labels), "
                f"cohort-predicted graduation in "
                f"~{(top.predicted_graduation_low + top.predicted_graduation_high) // 2} outcomes.\n"
                f">\n> Run `dendra init "
                f"{top.file_path}:{top.function_name}` to wrap your first site."
            )
        parts.append(
            f"> **{len(sites)} classification site"
            f"{'' if len(sites) == 1 else 's'} discovered.** "
            f"{len(auto_liftable)} auto-liftable today, "
            f"{len(needs_annotation)} need annotation (1-line fixes), "
            f"{len(refused)} refused (review required).\n"
            f">\n"
            f"> **Estimated annual LLM cost reduction** "
            f"if all auto-liftable sites graduate: "
            f"**~${annual_savings:,.0f}**.{first_action}\n"
        )

    # ---- Top opportunities table -----------------------------------------
    if auto_liftable or needs_annotation:
        parts.append("## Top opportunities (ranked)\n")
        parts.append(_opportunities_table(auto_liftable + needs_annotation, cost))
        parts.append("")

    # ---- Already wrapped section ----------------------------------------
    if already:
        parts.append("## Already wrapped\n")
        parts.append(
            f"> **{len(already)} site"
            f"{'' if len(already) == 1 else 's'} already-dendrified** "
            f"(decorator-wrapped or `Switch` subclass). The analyzer "
            f"correctly recognizes these and skips them.\n"
        )

    # ---- Refused with reasons -------------------------------------------
    if refused:
        parts.append("## Refused — why and how to fix\n")
        parts.append(_refused_table(refused))
        parts.append("")

    # ---- Recommended sequence -------------------------------------------
    if len(auto_liftable) >= 2:
        parts.append("## Recommended sequence (meta-experiment design)\n")
        parts.append(_recommended_sequence(auto_liftable))
        parts.append("")

    # ---- Cohort comparison ----------------------------------------------
    if cohort_size > 0 and sites:
        parts.append("## Cohort comparison\n")
        parts.append(_cohort_comparison(sites, cohort_size))
        parts.append("")

    # ---- What you'll see next -------------------------------------------
    parts.append("## What you'll see here as switches graduate\n")
    parts.append(
        "After `dendra init` on the first site, this discovery report "
        "is replaced by `dendra/results/_summary.md` (the cockpit view "
        "across all wrapped switches). Each wrapped switch gets its own "
        "report card at `dendra/results/<switch>.md` that fills in over "
        "time:\n\n"
        "- **Day 0–1**: pre-registered hypothesis recorded; transition curve empty.\n"
        "- **Day 1–14**: shadow phase; rule + ML head accumulate evidence.\n"
        "- **~Day 14–28**: gate fires; switch graduates to ML; cost trajectory drops.\n"
        "- **Continuous**: drift detector watches; report card stays current.\n"
    )

    # ---- Footer ---------------------------------------------------------
    parts.append("---")
    parts.append("")
    parts.append(
        "*Regenerate with `dendra analyze --report`. This file is a "
        "snapshot of what was found at scan time; it doesn't update as "
        "your code changes. For ongoing status, use "
        "`dendra report --summary`.*"
    )
    parts.append("")
    parts.append(f"*Methodology: [Test-Driven Product Development]({methodology_url}).*")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rank_sites(
    analyze_report: Any,
    *,
    cost_per_call: float,
    cohort_low: dict[str, int] | None,
    cohort_high: dict[str, int] | None,
) -> list[OpportunitySite]:
    """Convert AnalyzerReport sites into ranked OpportunitySite list."""
    out: list[OpportunitySite] = []
    for site in getattr(analyze_report, "sites", []):
        regime = site.regime if site.regime else "unknown"
        volume = getattr(site, "volume_estimate", "warm")
        low, high = _resolve_predicted_interval(regime, cohort_low, cohort_high)
        verdicts_per_month = _DEFAULT_MONTHLY_CALLS_BY_VOLUME.get(volume, 1_300_000)
        # Pre-graduation cost = cost_per_call * verdicts/month
        # Post-graduation cost ≈ 0 (in-process inference)
        savings_per_month = cost_per_call * verdicts_per_month
        out.append(
            OpportunitySite(
                file_path=site.file_path,
                function_name=site.function_name,
                line_start=site.line_start,
                pattern=site.pattern,
                regime=regime,
                label_cardinality=site.label_cardinality,
                volume_estimate=volume,
                priority_score=site.priority_score,
                lift_status=site.lift_status,
                hazard_categories=[h.category for h in site.hazards],
                predicted_graduation_low=low,
                predicted_graduation_high=high,
                estimated_monthly_savings_usd=savings_per_month,
            )
        )
    # Rank by (priority_score desc, savings desc)
    return sorted(
        out,
        key=lambda s: (-s.priority_score, -s.estimated_monthly_savings_usd),
    )


def _resolve_predicted_interval(
    regime: str,
    explicit_low: dict[str, int] | None,
    explicit_high: dict[str, int] | None,
) -> tuple[int, int]:
    if explicit_low and explicit_high:
        if regime in explicit_low and regime in explicit_high:
            return explicit_low[regime], explicit_high[regime]
    defaults = {
        "narrow": (200, 400),
        "medium": (400, 800),
        "high": (800, 1500),
        "unknown": (300, 700),
    }
    return defaults.get(regime, defaults["unknown"])


def _opportunities_table(sites: list[OpportunitySite], cost_per_call: float) -> str:
    """The ranked-sites table — the centerpiece of the discovery report."""
    rows = [
        "| # | Site | Pattern | Regime | Vol | Priority | Cohort grad time | Est. $/mo savings | Action |",
        "|---:|---|---|---|---|---:|---|---:|---|",
    ]
    for i, s in enumerate(sites[:15], start=1):  # cap top-15 for readability
        regime_str = (
            f"{s.regime} ({s.label_cardinality})" if s.label_cardinality else s.regime
        )
        grad_str = f"~{(s.predicted_graduation_low + s.predicted_graduation_high) // 2} outcomes"
        savings_str = (
            f"**${s.estimated_monthly_savings_usd:,.0f}**"
            if s.lift_status == "auto_liftable"
            else f"${s.estimated_monthly_savings_usd:,.0f}"
        )
        if s.lift_status == "auto_liftable":
            action = f"`dendra init {s.file_path}:{s.function_name}`"
        else:
            primary_hazard = s.hazard_categories[0] if s.hazard_categories else "—"
            action = f"needs `@evidence_*` annotation ({primary_hazard})"
        site_label = f"`{s.file_path}:{s.line_start} {s.function_name}`"
        rows.append(
            f"| {i} | {site_label} | {s.pattern} | {regime_str} | "
            f"{s.volume_estimate} | **{s.priority_score:.2f}** | "
            f"{grad_str} | {savings_str} | {action} |"
        )
    if len(sites) > 15:
        rows.append(
            f"\n*({len(sites) - 15} more sites below the top-15 cutoff; "
            "see the full JSON report for the long tail.)*"
        )
    rows.append(
        f"\nEstimated savings use ~${cost_per_call:.4f}/call (your configured LLM). "
        f"Switch with `dendra report --pro-forma --model claude-haiku-4.5` to see "
        f"how the picture changes under different pricing."
    )
    return "\n".join(rows)


def _refused_table(refused: list[OpportunitySite]) -> str:
    rows = [
        "| Site | Reason | Remediation |",
        "|---|---|---|",
    ]
    remediation_map = {
        "side_effect_evidence": (
            "Refactor to make state-mutation explicit, then re-analyze"
        ),
        "dynamic_dispatch": "Add `@evidence_inputs(...)` annotation",
        "not_a_classifier": "Confirm this isn't really a classifier; if it is, rename out of test path",
        "not_top_level": "v1.5 lifters reach class methods; defer or refactor to module-level",
        "multi_arg_no_annotation": "Add `@evidence_inputs(...)` to bind args",
    }
    for s in refused:
        primary = s.hazard_categories[0] if s.hazard_categories else "(unspecified)"
        fix = remediation_map.get(primary, "See report card details")
        rows.append(
            f"| `{s.file_path}:{s.line_start} {s.function_name}` | "
            f"{primary} | {fix} |"
        )
    return "\n".join(rows)


def _recommended_sequence(auto_liftable: list[OpportunitySite]) -> str:
    """The meta-experiment ordering. Wrap simple sites first."""
    # Sort by graduation depth ascending (shorter time = wrap first)
    ordered = sorted(
        auto_liftable,
        key=lambda s: (s.predicted_graduation_low, -s.priority_score),
    )
    lines = [
        "To maximize *learning per graduation*, wrap in approximately this order:\n"
    ]
    for i, s in enumerate(ordered[:5], start=1):
        if i == 1:
            rationale = (
                f"highest-priority. Narrow regime, lowest risk; use it to "
                f"validate the methodology on your codebase + traffic shape."
            )
        elif i == 2:
            rationale = "reinforces the pattern from #1."
        elif i == 3:
            rationale = "adds a different shape; verifies the methodology generalizes."
        else:
            rationale = f"after #{i-1} graduates, the discipline is dialed in."
        lines.append(
            f"{i}. **`{s.function_name}`** at `{s.file_path}:{s.line_start}` — {rationale} "
            f"Predicted graduation: ~"
            f"{(s.predicted_graduation_low + s.predicted_graduation_high) // 2} outcomes."
        )
    if len(ordered) > 5:
        lines.append(
            f"{len(ordered)-5} additional auto-liftable sites can ship in parallel "
            "after the first three graduate."
        )
    return "\n".join(lines)


def _cohort_comparison(
    sites: list[OpportunitySite],
    cohort_size: int,
) -> str:
    n_sites = len(sites)
    n_high = sum(1 for s in sites if s.priority_score >= 4.0)
    high_pct = (n_high / n_sites) * 100 if n_sites else 0
    return (
        f"> **Insights enrolled.** Cohort size: **{cohort_size}** deployments.\n\n"
        f"| Metric | This codebase | Cohort median |\n"
        f"|---|---:|---:|\n"
        f"| Total classification sites | {n_sites} | (depends on codebase size) |\n"
        f"| High-priority (≥ 4.0) | {n_high}/{n_sites} ({high_pct:.0f}%) | ~30% typical |\n\n"
        f"You're {'above' if high_pct > 30 else 'at or below'} cohort median on "
        f"high-priority-site density. Translation: the methodology should pay off "
        f"{'faster' if high_pct > 30 else 'in line with median timelines'} here."
    )


__all__ = ["OpportunitySite", "render_discovery_report"]
