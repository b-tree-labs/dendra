# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Auto-generate pre-registered hypothesis files at `dendra init` time.

Every wrapped switch gets a markdown file at
``dendra/hypotheses/<switch>.md`` populated from cohort-tuned
defaults plus analyzer fit data. The customer reviews and commits
the file before evidence accumulates; subsequent edits change its
content hash, which is recorded in the audit chain at every gate
evaluation. This is the pre-registration discipline that makes
TDPD evidence auditor-grade rather than "we said so afterwards".

Idempotent: if the file already exists, this function does NOT
overwrite it. Customers who edited their hypothesis keep their
edits; second `dendra init` runs print a notice and skip.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path
from typing import Any

# Customer-facing defaults — used when cohort data isn't available.
# Mirror BAKED_IN_DEFAULTS in dendra.insights.tuned_defaults; we don't
# import the insights module to keep the report layer non-circular.
_DEFAULT_REGIME_GRADUATION_INTERVAL: dict[str, tuple[int, int]] = {
    "narrow": (200, 400),
    "medium": (400, 800),
    "high": (800, 1500),
    "unknown": (300, 700),
}
_DEFAULT_EFFECT_SIZE_PP: float = 5.0
_DEFAULT_ALPHA: float = 0.01


def hypothesis_path(switch_name: str, root: Path | str = "dendra/hypotheses") -> Path:
    return Path(root) / f"{switch_name}.md"


def generate_hypothesis_file(
    switch_name: str,
    *,
    file_location: str | None = None,
    function_name: str | None = None,
    site_fingerprint: str | None = None,
    regime: str = "unknown",
    pattern: str | None = None,
    label_cardinality: int | None = None,
    priority_score: float | None = None,
    cohort_size: int = 0,
    cohort_predicted_low: int | None = None,
    cohort_predicted_high: int | None = None,
    effect_size_pp: float | None = None,
    alpha: float | None = None,
    root: Path | str = "dendra/hypotheses",
    overwrite: bool = False,
) -> tuple[Path, str, bool]:
    """Render and write the pre-registered hypothesis markdown.

    Returns ``(output_path, content_sha256, was_created)``. When the
    file already exists and ``overwrite=False``, returns the existing
    file's path and hash with ``was_created=False`` (no write
    attempted; existing content preserved).

    Cohort-prediction interval comes from explicit ``cohort_predicted_*``
    args if supplied; otherwise from a regime-keyed default. Effect-
    size threshold defaults to 5pp; α defaults to 0.01.
    """
    out_path = hypothesis_path(switch_name, root=root)

    if out_path.exists() and not overwrite:
        existing = out_path.read_text(encoding="utf-8")
        return out_path, _content_hash(existing), False

    pred_low, pred_high = _resolve_predicted_interval(
        cohort_predicted_low, cohort_predicted_high, regime
    )
    effect = effect_size_pp if effect_size_pp is not None else _DEFAULT_EFFECT_SIZE_PP
    a = alpha if alpha is not None else _DEFAULT_ALPHA

    body = _render_template(
        switch_name=switch_name,
        file_location=file_location,
        function_name=function_name,
        site_fingerprint=site_fingerprint,
        regime=regime,
        pattern=pattern,
        label_cardinality=label_cardinality,
        priority_score=priority_score,
        cohort_size=cohort_size,
        pred_low=pred_low,
        pred_high=pred_high,
        effect_size_pp=effect,
        alpha=a,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path, _content_hash(body), True


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_template(
    *,
    switch_name: str,
    file_location: str | None,
    function_name: str | None,
    site_fingerprint: str | None,
    regime: str,
    pattern: str | None,
    label_cardinality: int | None,
    priority_score: float | None,
    cohort_size: int,
    pred_low: int,
    pred_high: int,
    effect_size_pp: float,
    alpha: float,
) -> str:
    today = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d")
    site_line = ""
    if file_location and function_name:
        site_line = f"`{file_location}:{function_name}`"
    elif file_location:
        site_line = f"`{file_location}`"
    fp_line = f"Fingerprint: `{site_fingerprint}`" if site_fingerprint else "Fingerprint: (not yet computed)"

    cohort_basis = (
        f"Cohort model, regime={regime}, n={cohort_size} deployments"
        if cohort_size
        else f"Default for regime={regime} (no cohort data yet — install will pull when available)"
    )

    lines = [
        f"# Pre-registered hypothesis — {_humanize(switch_name)}",
        "",
        f"Pre-registered: **{today}**.",
    ]
    if site_line:
        lines.append(f"Site: {site_line}.")
    lines.append(fp_line + ".")
    lines.append("")
    lines.append(
        "*This file is part of the audit chain for the wrapped switch. "
        "Edits change its content hash; the hash is recorded in every "
        "subsequent gate evaluation. Edit deliberately; commit before "
        "evidence accumulates.*"
    )
    lines.append("")

    # Six-question pre-registration template
    lines.append("## 1. Unit of decision")
    lines.append("")
    lines.append(
        f"This single classification call site, identified by the "
        f"fingerprint above. The site fingerprint is a blake2b digest "
        f"over the function's normalized AST (with identifiers and "
        f"literals stripped); refactors that don't change shape "
        f"preserve the fingerprint, so this hypothesis survives "
        f"variable renames and reformatting."
    )
    lines.append("")

    lines.append("## 2. Gate criterion")
    lines.append("")
    lines.append(
        f"`McNemarGate` with α = **{alpha}** and minimum 30 paired-"
        f"correctness samples. The gate evaluates at every checkpoint "
        f"(default: every 50 outcomes). First-clear is treated as the "
        f"graduation event; subsequent checkpoints continue to "
        f"validate the decision."
    )
    lines.append("")

    lines.append("## 3. Expected n at graduation")
    lines.append("")
    lines.append(
        f"**{pred_low}–{pred_high} outcomes** (90% CI). Source: {cohort_basis}."
    )
    if pattern or label_cardinality is not None or priority_score is not None:
        lines.append("")
        lines.append("Site-shape inputs to the prediction:")
        if pattern:
            lines.append(f"- Pattern: `{pattern}`")
        if label_cardinality is not None:
            lines.append(f"- Label cardinality: {label_cardinality}")
        if priority_score is not None:
            lines.append(f"- Analyzer priority score: {priority_score:.2f}")
        lines.append(f"- Regime: {regime}")
    lines.append("")

    lines.append("## 4. Expected effect size")
    lines.append("")
    lines.append(
        f"At graduation, ML accuracy must exceed Rule accuracy by "
        f"**≥ {effect_size_pp:.1f} percentage points**. This is the "
        f"lower bound below which we don't consider the graduation "
        f"worth the operational complexity, regardless of statistical "
        f"significance. Edit if your domain has a different floor."
    )
    lines.append("")

    lines.append("## 5. Truth source")
    lines.append("")
    lines.append(
        "**Primary truth source:** *(to be filled in)*. Suggestions:"
    )
    lines.append("")
    lines.append("- Synchronous callable (Python function returning correct/incorrect)")
    lines.append("- LLM judge with self-judgment-bias guardrail")
    lines.append("- Human reviewer queue (best for safety-critical)")
    lines.append("- Webhook to a downstream system that has ground truth")
    lines.append("")
    lines.append(
        "**Secondary (cross-validation):** *(optional; recommended for "
        "high-stakes sites)*. Use a different source than primary so "
        "agreement is informative."
    )
    lines.append("")
    lines.append(
        "**Tie-breaker:** *(optional)*. The source consulted when "
        "primary and secondary disagree."
    )
    lines.append("")

    lines.append("## 6. Rollback rule")
    lines.append("")
    lines.append(
        "Drift detector fires when the wrapped function's AST hash no "
        "longer matches the hash recorded at graduation. Circuit "
        "breaker auto-rolls back to MODEL_PRIMARY when ML accuracy "
        "falls ≥ 10 pp below the rule baseline sustained over 20 "
        "verdicts. Both behaviors are default; override per the "
        "`SwitchConfig` documentation."
    )
    lines.append("")

    lines.append("## Verdict (filled in by `dendra report`)")
    lines.append("")
    lines.append(
        "*Once the gate fires (or the timeout at outcome "
        f"{pred_high * 3} triggers a 'did not graduate within "
        "budget' outcome), `dendra report` populates this section "
        "with the observed-vs-predicted comparison. Until then it "
        "reads `(in flight)` for each row.*"
    )
    lines.append("")
    lines.append("| Predicted | Observed | Verdict |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Graduation depth: {pred_low}–{pred_high} outcomes | (in flight) | (in flight) |"
    )
    lines.append(
        f"| Effect size: ≥ {effect_size_pp:.1f} pp | (in flight) | (in flight) |"
    )
    lines.append(f"| p < {alpha} at first clear | (in flight) | (in flight) |")
    lines.append(
        "| Drift handling: auto-rollback on AST mismatch | (no events yet) | (in flight) |"
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Methodology: [Test-Driven Product Development]"
        "(../../methodology/test-driven-product-development.md). "
        "Auto-generated by `dendra init`; review and commit before "
        "evidence accumulates. Subsequent edits change the content "
        "hash; the hash is recorded in the audit chain at every "
        "gate evaluation.*"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_predicted_interval(
    explicit_low: int | None,
    explicit_high: int | None,
    regime: str,
) -> tuple[int, int]:
    """Pick the prediction interval, with explicit args overriding defaults."""
    if explicit_low is not None and explicit_high is not None:
        return explicit_low, explicit_high
    return _DEFAULT_REGIME_GRADUATION_INTERVAL.get(
        regime, _DEFAULT_REGIME_GRADUATION_INTERVAL["unknown"]
    )


def _content_hash(text: str) -> str:
    """SHA-256 hex digest. Used as the pre-registration audit anchor."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _humanize(switch_name: str) -> str:
    return " ".join(p.capitalize() for p in switch_name.replace("-", "_").split("_"))


__all__ = [
    "generate_hypothesis_file",
    "hypothesis_path",
]
