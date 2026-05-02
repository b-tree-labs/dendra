# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.
# See LICENSE-BSL in the repository root.

"""Aggregate per-switch storage records into report-card metrics.

The aggregator is the read-only view: walk a switch's
:class:`~dendra.core.ClassificationRecord` log, bucket into
checkpoints, compute rule + ML accuracy at each, identify the
gate-fire moment, and stamp the current phase. Output is a plain
dataclass that the markdown renderer consumes.

Storage agnostic by construction — accepts any object with a
``load_records(switch_name)`` method. Never writes; never mutates;
no side effects beyond CPU.

Cost trajectory deliberately excluded from this module — cost
estimation requires the configured LLM adapter pricing, which is
caller context. The renderer accepts an optional ``cost_per_call``
parameter and builds the cost section from that.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from dendra.core import ClassificationRecord, Phase
from dendra.gates import GateDecision, McNemarGate

#: Number of outcomes per checkpoint. Matches the v1 paper's default
#: checkpoint cadence (every 50 outcomes; coarser cadences are
#: possible but produce noisy transition curves).
DEFAULT_CHECKPOINT_EVERY: int = 50


@dataclass(frozen=True)
class Checkpoint:
    """One row in the report card's "Raw checkpoints" table.

    Computed from the record window ending at this checkpoint's
    outcome count. ``rule_acc`` and ``ml_acc`` are over the *full*
    history-to-date (not just this 50-outcome window) — the report
    card shows the running estimate, not the windowed estimate, to
    match how the gate evaluates.
    """

    outcome_count: int
    rule_correct: int
    rule_total: int
    ml_correct: int
    ml_total: int
    paired_p_value: float | None  # None if too few paired samples
    paired_n: int  # number of paired-correctness rows
    phase_at_checkpoint: Phase

    @property
    def rule_accuracy(self) -> float | None:
        return self.rule_correct / self.rule_total if self.rule_total else None

    @property
    def ml_accuracy(self) -> float | None:
        return self.ml_correct / self.ml_total if self.ml_total else None


@dataclass(frozen=True)
class HypothesisVerdict:
    """Comparison between a pre-registered hypothesis and observed evidence.

    Populated when the caller passes the hypothesis claims (loaded
    from ``dendra/hypotheses/<switch>.md``). Fields are ``None`` when
    the hypothesis isn't supplied — renderer skips the section.
    """

    predicted_graduation_low: int | None = None
    predicted_graduation_high: int | None = None
    predicted_effect_size_pp: float | None = None
    observed_graduation_outcome: int | None = None  # None if not graduated
    observed_effect_size_pp: float | None = None
    observed_p_at_first_clear: float | None = None

    def graduation_within_predicted_interval(self) -> bool | None:
        if self.observed_graduation_outcome is None:
            return None
        if self.predicted_graduation_low is None or self.predicted_graduation_high is None:
            return None
        return (
            self.predicted_graduation_low
            <= self.observed_graduation_outcome
            <= self.predicted_graduation_high
        )

    def effect_size_meets_threshold(self) -> bool | None:
        if self.observed_effect_size_pp is None:
            return None
        if self.predicted_effect_size_pp is None:
            return None
        return self.observed_effect_size_pp >= self.predicted_effect_size_pp


@dataclass(frozen=True)
class SwitchMetrics:
    """Everything the renderer needs about one switch.

    Produced by :func:`aggregate_switch`. Fields with no data are
    represented by safe defaults (empty list, ``None``, ``Phase.RULE``)
    so the renderer can produce a "day-zero, no outcomes yet" report
    without special-casing.
    """

    switch_name: str
    site_fingerprint: str | None
    current_phase: Phase
    total_outcomes: int
    checkpoints: list[Checkpoint] = field(default_factory=list)
    gate_fire_outcome: int | None = None  # first checkpoint where p < alpha
    gate_fire_p_value: float | None = None
    rule_accuracy_final: float | None = None
    ml_accuracy_final: float | None = None
    crossover_outcome: int | None = None  # first outcome where ML > Rule
    phase_history: list[tuple[Phase, float]] = field(default_factory=list)  # (phase, ts)
    drift_events: list[tuple[float, str]] = field(default_factory=list)  # (ts, reason)
    last_record_timestamp: float | None = None
    generated_at: str = ""  # ISO timestamp of report generation


def aggregate_switch(
    storage: Any,
    switch_name: str,
    *,
    site_fingerprint: str | None = None,
    current_phase: Phase | None = None,
    checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY,
    alpha: float = 0.01,
    min_paired: int = 30,
) -> SwitchMetrics:
    """Read storage for ``switch_name`` and compute report-card metrics.

    Parameters
    ----------
    storage
        Anything with a ``load_records(switch_name)`` method —
        a :class:`~dendra.storage.Storage` instance, but duck-typed.
    switch_name
        The name passed to ``LearnedSwitch(name=...)`` at construction.
    site_fingerprint
        Optional blake2b shape-fingerprint for the wrapped function.
        Surfaced in the report card header. ``None`` skips it.
    current_phase
        The switch's current phase. The renderer uses this for the
        "Status" banner. ``None`` falls back to the last phase
        observed in the records (``Phase.RULE`` if no records).
    checkpoint_every
        Outcomes per checkpoint. Default 50 matches paper §4.
    alpha
        Gate threshold for the first-clear detection. Default 0.01
        matches the default :class:`~dendra.gates.McNemarGate` config.
    min_paired
        Minimum paired-correctness rows before the gate evaluates.
        Default 30 matches McNemar's stable-approximation threshold.
    """
    records: list[ClassificationRecord] = storage.load_records(switch_name)
    total = len(records)

    if not records:
        # No data yet — return a day-zero metrics object the renderer
        # can still produce a valid card from.
        return SwitchMetrics(
            switch_name=switch_name,
            site_fingerprint=site_fingerprint,
            current_phase=current_phase or Phase.RULE,
            total_outcomes=0,
            generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        )

    # ---- Final accuracies -------------------------------------------------
    rule_correct, rule_total = 0, 0
    ml_correct, ml_total = 0, 0
    for r in records:
        if r.rule_output is not None and r.outcome != "unknown":
            rule_total += 1
            if _is_correct(r, r.rule_output):
                rule_correct += 1
        if r.ml_output is not None and r.outcome != "unknown":
            ml_total += 1
            if _is_correct(r, r.ml_output):
                ml_correct += 1

    rule_acc_final = rule_correct / rule_total if rule_total else None
    ml_acc_final = ml_correct / ml_total if ml_total else None

    # ---- Checkpoints ------------------------------------------------------
    checkpoints: list[Checkpoint] = []
    gate = McNemarGate(alpha=alpha, min_paired=min_paired)
    seen_phases: set[Phase] = set()
    phase_history: list[tuple[Phase, float]] = []
    drift_events: list[tuple[float, str]] = []

    for i in range(checkpoint_every, total + 1, checkpoint_every):
        window = records[:i]
        cp = _compute_checkpoint(window, gate)
        checkpoints.append(cp)
    # Always include the final partial-window checkpoint if total isn't
    # a multiple of checkpoint_every (so the table includes the most
    # recent state, not just the last full bucket).
    if total % checkpoint_every != 0:
        cp = _compute_checkpoint(records, gate)
        checkpoints.append(cp)

    # Track phase history (each new phase observed in source field)
    for r in records:
        # `source` strings on records mirror Phase values in v1 (e.g.
        # "rule", "model", "ml") but customers can wire their own.
        # Phase tracking here is best-effort.
        phase_str = r.source.lower() if isinstance(r.source, str) else ""
        for p in Phase:
            if p.value in phase_str and p not in seen_phases:
                seen_phases.add(p)
                phase_history.append((p, r.timestamp))
                break

    # ---- Gate-fire detection ---------------------------------------------
    gate_fire_outcome: int | None = None
    gate_fire_p: float | None = None
    for cp in checkpoints:
        if cp.paired_p_value is not None and cp.paired_p_value < alpha:
            gate_fire_outcome = cp.outcome_count
            gate_fire_p = cp.paired_p_value
            break

    # ---- Crossover detection (first outcome where ML > Rule) -------------
    crossover: int | None = None
    for cp in checkpoints:
        if (
            cp.rule_accuracy is not None
            and cp.ml_accuracy is not None
            and cp.ml_accuracy > cp.rule_accuracy
        ):
            crossover = cp.outcome_count
            break

    # ---- Phase resolution ------------------------------------------------
    phase = current_phase
    if phase is None:
        # Best-effort: take the last record's source as a hint
        last_src = records[-1].source.lower() if isinstance(records[-1].source, str) else ""
        for p in Phase:
            if p.value in last_src:
                phase = p
                break
        if phase is None:
            phase = Phase.RULE

    return SwitchMetrics(
        switch_name=switch_name,
        site_fingerprint=site_fingerprint,
        current_phase=phase,
        total_outcomes=total,
        checkpoints=checkpoints,
        gate_fire_outcome=gate_fire_outcome,
        gate_fire_p_value=gate_fire_p,
        rule_accuracy_final=rule_acc_final,
        ml_accuracy_final=ml_acc_final,
        crossover_outcome=crossover,
        phase_history=phase_history,
        drift_events=drift_events,
        last_record_timestamp=records[-1].timestamp,
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_correct(record: ClassificationRecord, prediction: Any) -> bool:
    """True iff this record's outcome confirms the prediction was correct.

    Outcome semantics (matching :data:`~dendra.verdicts.Verdict`):

    - ``"correct"``: the chosen ``label`` was right; rule/ml output
      is ``correct`` iff it equals the chosen label.
    - ``"incorrect"``: the chosen ``label`` was wrong; rule/ml
      output is ``correct`` iff it differs from the chosen label
      (the label that was right wasn't the one chosen, so a
      shadow that picked something other than ``label`` *might*
      have been right — but with only a binary outcome we can't
      tell). Convention from the paper: shadow outputs that
      differ from the chosen label are credited as correct in
      ``incorrect`` rows.
    - ``"unknown"``: no signal; row excluded from accuracy.

    See ``dendra/gates.py:_paired_correctness`` for the matching
    gate-side logic; the two must stay aligned.
    """
    if record.outcome == "correct":
        return prediction == record.label
    if record.outcome == "incorrect":
        return prediction != record.label
    return False  # "unknown" — caller filters these out by checking outcome first


def _compute_checkpoint(records: list[ClassificationRecord], gate: McNemarGate) -> Checkpoint:
    """Compute one checkpoint's worth of metrics from a record window."""
    rule_c, rule_t = 0, 0
    ml_c, ml_t = 0, 0
    for r in records:
        if r.outcome == "unknown":
            continue
        if r.rule_output is not None:
            rule_t += 1
            if _is_correct(r, r.rule_output):
                rule_c += 1
        if r.ml_output is not None:
            ml_t += 1
            if _is_correct(r, r.ml_output):
                ml_c += 1

    # Run the gate to get a paired McNemar p-value. The gate compares
    # rule_output (RULE phase) vs ml_output (ML_PRIMARY phase) — i.e.
    # "should the rule graduate to ML?", which is the question every
    # report card answers.
    decision: GateDecision | None = None
    try:
        decision = gate.evaluate(records, Phase.RULE, Phase.ML_PRIMARY)
    except Exception:  # noqa: BLE001 — never let gate failure abort report rendering
        decision = None

    p_value = decision.p_value if decision and decision.p_value is not None else None
    paired_n = decision.paired_sample_size if decision else 0

    # Phase at this checkpoint = the source of the last record in the window
    last_src = records[-1].source.lower() if records and isinstance(records[-1].source, str) else ""
    phase_at = Phase.RULE
    for p in Phase:
        if p.value in last_src:
            phase_at = p
            break

    return Checkpoint(
        outcome_count=len(records),
        rule_correct=rule_c,
        rule_total=rule_t,
        ml_correct=ml_c,
        ml_total=ml_t,
        paired_p_value=p_value,
        paired_n=paired_n,
        phase_at_checkpoint=phase_at,
    )
