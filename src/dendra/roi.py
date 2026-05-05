# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at LICENSE-BSL in the
# repository root, or at https://mariadb.com/bsl11/.
#
# Change Date:    2030-05-01
# Change License: Apache License, Version 2.0
#
# Additional Use Grant: see LICENSE-BSL. Production use is
# permitted; offering a competing hosted service is not.

"""Self-measuring ROI reporter.

Reads outcome logs produced by :class:`dendra.storage.FileStorage` and
computes a grounded ROI estimate per switch. Every dollar figure
decomposes back to a ratio × a per-unit assumption, so adopters can
reproduce or adjust the calculation.

The assumption ranges are documented inline as attributes of
:class:`ROIAssumptions` so an AI coding assistant can reason about
them when suggesting tuning. Adjust them to match your workload's
real economics rather than relying on the shipped defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from dendra.storage import FileStorage


@dataclass
class ROIAssumptions:
    """Calibration knobs for ROI estimates. Defaults = §6.3 of
    ``industry-applicability.md`` (mid-market US, AI-assisted 2026)."""

    engineer_cost_per_week_usd: float = 4_000.0
    # Baseline cost to go from hand-rolled rule → shipped ML + monitoring,
    # assuming AI coding assistance. §4.1.2 modern column.
    baseline_weeks_per_graduation_low: float = 1.6
    baseline_weeks_per_graduation_high: float = 3.5
    # With Dendra: first site is ~0.5 weeks, subsequent sites ~0.1 weeks.
    dendra_first_site_weeks: float = 0.5
    dendra_subsequent_site_weeks: float = 0.1
    # Time-to-ML value acceleration (months earlier).
    months_accelerated_low: float = 2.0
    months_accelerated_high: float = 6.0
    # Monthly value per production-ready classifier (partial revenue uplift
    # or cost avoidance). Deliberately wide — reader can tighten.
    monthly_value_per_site_low_usd: float = 2_000.0
    monthly_value_per_site_high_usd: float = 12_000.0
    # Regression-event cost and frequency (per site per year).
    regressions_per_site_per_year: float = 0.25  # 1 per quarter per site
    regression_cost_low_usd: float = 50_000.0
    regression_cost_high_usd: float = 300_000.0

    # --- Token-cost dimension (2026 language model-era) --------------------------------
    # Typical per-classification token shape: prompt (system + labels + input)
    # + completion (just the label). Real measurements from our tests:
    # ~50-100 input, ~3-8 output for a short-input classifier.
    llm_input_tokens_per_call: int = 80
    llm_output_tokens_per_call: int = 5
    # Pricing bands cover Haiku/Mini-class (low) through Sonnet-class (high).
    # Units: USD per 1M tokens. April 2026 public rates.
    llm_input_usd_per_1m_tokens_low: float = 0.15  # GPT-4o-mini / Haiku 4.5
    llm_input_usd_per_1m_tokens_high: float = 3.00  # Claude Sonnet 4.6
    llm_output_usd_per_1m_tokens_low: float = 0.60
    llm_output_usd_per_1m_tokens_high: float = 15.00
    # Counter-factual: if the team had shipped model-only instead of
    # Dendra-graduated, what fraction of outcomes would have gone to the
    # language model? Default: 100% (Dendra's rule/ML paths save all of them).
    pct_outcomes_that_would_use_llm_without_dendra: float = 1.0


@dataclass
class SwitchROI:
    """Per-switch ROI summary."""

    switch_name: str
    outcomes_total: int
    outcomes_correct: int
    outcomes_incorrect: int
    accuracy: float
    bytes_on_disk: int
    phase_ever_graduated: bool
    # Savings projections (low, high).
    direct_eng_savings_low_usd: float
    direct_eng_savings_high_usd: float
    ttm_value_low_usd: float
    ttm_value_high_usd: float
    regression_avoidance_low_usd: float
    regression_avoidance_high_usd: float
    # Token savings — model calls Dendra routed away from.
    model_calls_avoided: int
    token_savings_low_usd: float
    token_savings_high_usd: float
    total_savings_low_usd: float
    total_savings_high_usd: float


def compute_switch_roi(
    *,
    switch_name: str,
    storage: FileStorage,
    assumptions: ROIAssumptions | None = None,
) -> SwitchROI:
    """Compute ROI for one switch from its outcome log."""
    a = assumptions or ROIAssumptions()
    outcomes = storage.load_records(switch_name)
    total = len(outcomes)
    correct = sum(1 for r in outcomes if r.outcome == "correct")
    incorrect = sum(1 for r in outcomes if r.outcome == "incorrect")
    acc = correct / total if total else 0.0

    graduated = any(
        getattr(r, "source", "rule") in {"model", "ml", "rule_fallback"} for r in outcomes
    )

    # Direct engineering savings: (baseline - dendra) weeks × cost.
    # For a SINGLE site already instrumented in Dendra, the savings are
    # "baseline - dendra-subsequent" (assumed amortized across sites).
    eng_low = (
        a.baseline_weeks_per_graduation_low - a.dendra_subsequent_site_weeks
    ) * a.engineer_cost_per_week_usd
    eng_high = (
        a.baseline_weeks_per_graduation_high - a.dendra_subsequent_site_weeks
    ) * a.engineer_cost_per_week_usd
    eng_low = max(0.0, eng_low)
    eng_high = max(0.0, eng_high)

    # Time-to-ML value: months_earlier × monthly_value. Only accrues if
    # the switch has actually progressed beyond Phase 0 (someone's
    # using the graduated path).
    if graduated:
        ttm_low = a.months_accelerated_low * a.monthly_value_per_site_low_usd
        ttm_high = a.months_accelerated_high * a.monthly_value_per_site_high_usd
    else:
        ttm_low = 0.0
        ttm_high = 0.0

    # Regression avoidance scales with outcome volume — more traffic =
    # more chances for a silent regression that Dendra's breaker catches.
    # Normalize to "regressions per year" assuming total outcomes arrived
    # over 1 year (overestimates if faster, underestimates if slower —
    # we cap at 1 to stay conservative).
    regression_year_fraction = min(1.0, max(0.1, total / 100_000.0))
    reg_low = a.regressions_per_site_per_year * regression_year_fraction * a.regression_cost_low_usd
    reg_high = (
        a.regressions_per_site_per_year * regression_year_fraction * a.regression_cost_high_usd
    )

    # Token-cost savings: every outcome that Dendra routed through
    # rule/ML is a model call the counter-factual design would have paid
    # for. We count outcomes whose source is NOT "model" (i.e., handled
    # without calling the model) and multiply by per-call token cost.
    model_calls_avoided = sum(1 for r in outcomes if getattr(r, "source", "rule") != "model")
    # Scale by the "what fraction would have gone to language model in the counter-
    # factual" knob. Default 1.0 = "team would have shipped model-only".
    counterfactual_llm_calls = (
        model_calls_avoided * a.pct_outcomes_that_would_use_llm_without_dendra
    )
    cost_per_call_low = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_low / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_low / 1e6
    )
    cost_per_call_high = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_high / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_high / 1e6
    )
    # Annualize — if the log represents less than a year of traffic, we
    # extrapolate. If more, we keep the actual count (conservative).
    year_scale = 1.0 / regression_year_fraction
    tok_low = counterfactual_llm_calls * cost_per_call_low * year_scale
    tok_high = counterfactual_llm_calls * cost_per_call_high * year_scale

    return SwitchROI(
        switch_name=switch_name,
        outcomes_total=total,
        outcomes_correct=correct,
        outcomes_incorrect=incorrect,
        accuracy=acc,
        bytes_on_disk=storage.bytes_on_disk(switch_name),
        phase_ever_graduated=graduated,
        direct_eng_savings_low_usd=eng_low,
        direct_eng_savings_high_usd=eng_high,
        ttm_value_low_usd=ttm_low,
        ttm_value_high_usd=ttm_high,
        regression_avoidance_low_usd=reg_low,
        regression_avoidance_high_usd=reg_high,
        model_calls_avoided=model_calls_avoided,
        token_savings_low_usd=tok_low,
        token_savings_high_usd=tok_high,
        total_savings_low_usd=eng_low + ttm_low + reg_low + tok_low,
        total_savings_high_usd=eng_high + ttm_high + reg_high + tok_high,
    )


def compute_portfolio_roi(
    *,
    storage: FileStorage,
    assumptions: ROIAssumptions | None = None,
) -> list[SwitchROI]:
    """Compute ROI for every switch in the storage root."""
    a = assumptions or ROIAssumptions()
    return [
        compute_switch_roi(switch_name=name, storage=storage, assumptions=a)
        for name in storage.switch_names()
    ]


def format_portfolio_report(
    rois: list[SwitchROI], *, assumptions: ROIAssumptions | None = None
) -> str:
    """Render a human-readable ROI report."""
    a = assumptions or ROIAssumptions()
    total_low = sum(r.total_savings_low_usd for r in rois)
    total_high = sum(r.total_savings_high_usd for r in rois)
    total_outcomes = sum(r.outcomes_total for r in rois)
    total_bytes = sum(r.bytes_on_disk for r in rois)

    total_llm_avoided = sum(r.model_calls_avoided for r in rois)
    total_tok_low = sum(r.token_savings_low_usd for r in rois)
    total_tok_high = sum(r.token_savings_high_usd for r in rois)

    lines = [
        "Dendra self-measured ROI report",
        "=" * 60,
        f"Switches tracked:     {len(rois)}",
        f"Total outcomes:       {total_outcomes:,}",
        f"model calls avoided:    {total_llm_avoided:,}",
        f"Disk usage:           {total_bytes / 1024:,.1f} KB",
        "",
        f"{'switch':<26} {'outcomes':>9} {'acc':>6} {'eng+ttm+reg (USD)':>20} {'tokens (USD)':>18}",
        "-" * 86,
    ]
    for r in rois:
        non_tok_low = (
            r.direct_eng_savings_low_usd + r.ttm_value_low_usd + r.regression_avoidance_low_usd
        )
        non_tok_high = (
            r.direct_eng_savings_high_usd + r.ttm_value_high_usd + r.regression_avoidance_high_usd
        )
        lines.append(
            f"{r.switch_name:<26} "
            f"{r.outcomes_total:>9,} "
            f"{r.accuracy:>5.0%} "
            f"{f'${non_tok_low:>7,.0f}–${non_tok_high:>7,.0f}':>20} "
            f"{f'${r.token_savings_low_usd:>6,.0f}–${r.token_savings_high_usd:>6,.0f}':>18}"
        )
    lines += [
        "-" * 86,
        f"Portfolio savings range:  ${total_low:,.0f} – ${total_high:,.0f} / year",
        f"  of which token savings: ${total_tok_low:,.0f} – ${total_tok_high:,.0f}",
        "",
        "Assumptions (adjust via ROIAssumptions):",
        f"  eng_cost_per_week=${a.engineer_cost_per_week_usd:,.0f}",
        f"  baseline_weeks={a.baseline_weeks_per_graduation_low}-"
        f"{a.baseline_weeks_per_graduation_high}",
        f"  dendra_subsequent_site={a.dendra_subsequent_site_weeks}w",
        f"  months_accelerated={a.months_accelerated_low}-{a.months_accelerated_high}",
        f"  monthly_value_per_site=${a.monthly_value_per_site_low_usd:,.0f}-"
        f"${a.monthly_value_per_site_high_usd:,.0f}",
        f"  tokens_per_call={a.llm_input_tokens_per_call}in/{a.llm_output_tokens_per_call}out",
        f"  llm_price_per_1M={a.llm_input_usd_per_1m_tokens_low}-"
        f"${a.llm_input_usd_per_1m_tokens_high}in / "
        f"${a.llm_output_usd_per_1m_tokens_low}-"
        f"${a.llm_output_usd_per_1m_tokens_high}out",
        f"  counter_factual_llm_pct={a.pct_outcomes_that_would_use_llm_without_dendra:.0%}",
        "",
        "Every dollar figure = ratio × per-unit assumption. "
        "Tune ROIAssumptions to your workload before relying on totals.",
    ]
    return "\n".join(lines)


__all__ = [
    "ROIAssumptions",
    "SwitchROI",
    "compute_portfolio_roi",
    "compute_switch_roi",
    "format_portfolio_report",
]
