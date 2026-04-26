# Copyright (c) 2026 B-Tree Ventures, LLC
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

"""Research instrumentation — transition-curve runner.

Implements the experiment described in the Dendra paper §4.3:

    1. Start a switch at Phase.RULE.
    2. Stream labeled examples through the switch.
    3. Every ``checkpoint_every`` outcomes, record accuracy per source
       (rule, model, ml) over the outcomes observed so far.
    4. Return a list of :class:`Checkpoint` rows — the raw data for
       the paper's Figure 1 transition curves.

Zero hard dependencies. If a caller wants to train the ML head between
checkpoints, they pass ``fit_each_checkpoint=True`` and the runner
calls ``ml_head.fit(outcomes)`` at every checkpoint.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from dendra.core import LearnedSwitch, Verdict


def train_ml_from_model_outcomes(
    switch: LearnedSwitch,
    ml_head: Any,
    *,
    min_llm_outcomes: int = 200,
    outcome_label_filter: tuple[str, ...] = ("correct",),
) -> int:
    """Bootstrap an ML head from model-labeled outcomes.

    **The LLM-as-teacher pattern.** When a switch has been running at
    ``Phase.MODEL_PRIMARY`` (or any phase where ``source="model"`` outcomes
    accumulate), the language model has been acting as a production labeler. This
    helper filters the outcome log down to model-labeled records whose
    downstream signal matched (outcome="correct" by default), then
    calls ``ml_head.fit(...)`` on those records.

    Returns the count of records used for fitting. If fewer than
    ``min_llm_outcomes`` qualify, the fit is SKIPPED and 0 is returned
    — training on too few labels produces an ML head that underperforms
    the language model and stalls phase graduation.

    Typical usage::

        from dendra import SklearnTextHead
        from dendra.research import train_ml_from_model_outcomes

        head = SklearnTextHead(min_outcomes=200)
        used = train_ml_from_model_outcomes(
            switch=my_switch, ml_head=head, min_llm_outcomes=500,
        )
        if used >= 500:
            my_switch._ml_head = head
            my_switch.config.starting_phase = Phase.ML_WITH_FALLBACK

    The LLM-as-teacher pattern: start at MODEL_PRIMARY with no
    labeled data, let the language model decide + label production traffic,
    then train a local ML head on the accumulated language model labels and
    graduate to ML_WITH_FALLBACK. This retires the language model from the
    hot path once the cheaper ML head is trained.

    See ``examples/07_llm_as_teacher.py`` for a runnable
    demonstration.
    """
    all_outcomes = switch.storage.load_records(switch.name)
    usable = [
        r
        for r in all_outcomes
        if getattr(r, "source", None) == "model"
        and getattr(r, "outcome", None) in outcome_label_filter
    ]
    if len(usable) < min_llm_outcomes:
        return 0
    ml_head.fit(usable)
    return len(usable)


@dataclass(frozen=True)
class BenchmarkExample:
    """One labeled example streamed through a switch during benchmarking."""

    input: Any
    label: str


@dataclass(frozen=True)
class Checkpoint:
    """Accuracy snapshot at a given outcome count."""

    outcomes: int
    rule_accuracy: float
    lm_accuracy: float | None
    ml_accuracy: float | None
    decision_accuracy: float  # accuracy of whatever the switch actually returned


def run_transition_curve(
    switch: LearnedSwitch,
    examples: Iterable[BenchmarkExample],
    *,
    checkpoint_every: int = 100,
    fit_each_checkpoint: bool = False,
) -> list[Checkpoint]:
    """Stream ``examples`` through ``switch`` and measure transition curves.

    Records one :class:`Checkpoint` per ``checkpoint_every`` outcomes.
    ``rule_accuracy`` is always populated; ``lm_accuracy`` and
    ``ml_accuracy`` appear when the switch's current phase is
    producing shadow observations for them.
    """
    checkpoints: list[Checkpoint] = []
    total = 0
    for ex in examples:
        result = switch.classify(ex.input)
        if result.label == ex.label:
            result.mark_correct()
        else:
            result.mark_incorrect()
        total += 1

        if total % checkpoint_every == 0:
            if fit_each_checkpoint and switch._ml_head is not None:
                switch._ml_head.fit(switch.storage.load_records(switch.name))
            checkpoints.append(_snapshot(switch, total))

    # Tail snapshot if we have outcomes beyond the last checkpoint.
    if total and (not checkpoints or checkpoints[-1].outcomes < total):
        checkpoints.append(_snapshot(switch, total))

    return checkpoints


def _snapshot(switch: LearnedSwitch, total: int) -> Checkpoint:
    outcomes = switch.storage.load_records(switch.name)
    correct = sum(1 for r in outcomes if r.outcome == Verdict.CORRECT.value)
    decision_acc = correct / len(outcomes) if outcomes else 0.0

    rule_rows = [r for r in outcomes if r.rule_output is not None]
    # Accuracy here means: did the SHADOW (or primary) match the ground-
    # truth label? We use the recorded outcome as ground truth: a row is
    # "correct" when output == ground truth. Rule accuracy is how often
    # the rule's output matched the recorded ground truth; we reconstruct
    # ground truth as `output if outcome==correct else something_else`.
    # Simpler: rule accuracy = fraction where rule_output == output when
    # outcome==correct, OR rule_output != output when outcome==incorrect
    # collapses to "rule matched the real label" — equivalent to:
    #     rule_output matches the actual ground truth label
    # and we recover ground truth from whichever source was correct.
    rule_correct = _source_accuracy(rule_rows, "rule_output")
    model_rows = [r for r in outcomes if r.model_output is not None]
    model_acc = _source_accuracy(model_rows, "model_output") if model_rows else None
    ml_rows = [r for r in outcomes if r.ml_output is not None]
    ml_acc = _source_accuracy(ml_rows, "ml_output") if ml_rows else None

    return Checkpoint(
        outcomes=total,
        rule_accuracy=rule_correct or 0.0,
        lm_accuracy=model_acc,
        ml_accuracy=ml_acc,
        decision_accuracy=decision_acc,
    )


def _source_accuracy(rows: list[Any], field_name: str) -> float:
    """Fraction of rows where the named source matched the ground-truth label.

    Ground truth is reconstructed from the outcome: if outcome=="correct",
    the actual ``output`` is the label. If outcome=="incorrect", we don't
    know the correct label from this row alone — those rows drop out.
    """
    usable = [r for r in rows if r.outcome == Verdict.CORRECT.value]
    if not usable:
        return 0.0
    matches = sum(1 for r in usable if getattr(r, field_name) == r.label)
    return matches / len(usable)


@dataclass(frozen=True)
class BenchmarkCheckpoint:
    """Accuracy snapshot evaluated against a held-out test set.

    Distinct from :class:`Checkpoint` — this is the paper's Figure 1
    shape: rule vs ML accuracy against a FIXED evaluation set, measured
    at growing training-outcome counts. The earlier :class:`Checkpoint`
    scores each source over the historical stream.

    ``model_test_accuracy`` is flat across checkpoints when the language model runs
    in pure shadow mode (no fine-tuning / context-accumulation between
    outcomes) — it reflects the zero-shot ceiling under §9.3's
    "model-as-shadow-labeler" regime.

    ``rule_correct`` / ``ml_correct`` are per-example booleans (test-row
    order) when paired-test reporting is enabled. They let callers
    compute McNemar's test and error-analysis stats. Stored as
    ``list[bool]`` rather than full predictions to keep JSONL size
    tractable (~1 bit × test_n × checkpoints).
    """

    training_outcomes: int
    rule_test_accuracy: float
    ml_test_accuracy: float
    ml_trained: bool
    ml_version: str
    model_test_accuracy: float | None = None
    lm_test_sample: int | None = None
    rule_correct: list[bool] | None = None
    ml_correct: list[bool] | None = None


def run_benchmark_experiment(
    *,
    train: Iterable[tuple[str, str]],
    test: Iterable[tuple[str, str]],
    rule: Callable[[str], str],
    ml_head: MLHeadT,
    checkpoint_every: int = 250,
    min_train_for_ml: int = 100,
    max_train: int | None = None,
    model: LLMClassifierT | None = None,
    lm_labels: list[str] | None = None,
    lm_test_sample_size: int | None = None,
    record_per_example: bool = True,
    shuffle_seed: int | None = None,
) -> list[BenchmarkCheckpoint]:
    """Streaming training + held-out evaluation — the paper's core experiment.

    Feeds training pairs one at a time; the rule is constant, and the
    ML head is retrained on accumulated "correct" outcomes at each
    checkpoint. Both the rule and the ML head are then evaluated
    against the fixed test set, producing one :class:`BenchmarkCheckpoint`
    per checkpoint.

    ``ml_head`` must satisfy :class:`dendra.ml.MLHead`. The runner
    doesn't assume any particular backend — swap in a fake for tests.
    """
    from dendra.core import LearnedSwitch, Phase, SwitchConfig, Verdict

    train_list = list(train)
    test_list = list(test)
    if shuffle_seed is not None:
        import random as _random

        rng = _random.Random(shuffle_seed)
        rng.shuffle(train_list)
    if max_train is not None:
        train_list = train_list[:max_train]

    # One-time language model evaluation — constant across checkpoints since the language model
    # isn't updated between outcomes. Matches the paper §9.3 shadow regime.
    model_acc: float | None = None
    model_sample: int | None = None
    if model is not None:
        eval_rows = test_list
        if lm_test_sample_size is not None:
            eval_rows = eval_rows[:lm_test_sample_size]
        model_sample = len(eval_rows)
        labels_for_llm = (
            list(lm_labels) if lm_labels is not None else sorted({lbl for _, lbl in test_list})
        )
        correct = 0
        for text, lbl in eval_rows:
            try:
                pred = model.classify(text, labels_for_llm)
            except Exception:
                continue
            if pred.label == lbl:
                correct += 1
        model_acc = correct / model_sample if model_sample else 0.0

    def _rule_fn(text: str) -> str:
        return rule(text)

    # A single switch carries the outcome log; ML head retrains from it.
    # auto_record=False: benchmark records verdicts explicitly per example;
    # UNKNOWN auto-rows would double-count in transition-curve math.
    #
    # Unbounded storage: the benchmark harness OWNS the full training
    # set and bounds its own lifetime. The default
    # ``BoundedInMemoryStorage(10_000)`` is correct for production
    # switches (prevents unbounded memory growth) but FIFO-evicts at
    # cap — catastrophic when the benchmark stream is label-blocked
    # (e.g. CLINC150 feeds 10 labels per 1,000-example window; at
    # outcome 10,500 the first 500 records are evicted, meaning ~5
    # entire label classes drop out of the ML head's training view).
    # Using the explicit unbounded ``InMemoryStorage`` keeps the full
    # stream addressable. See
    # docs/papers/2026-when-should-a-rule-learn/results/findings.md
    # "CLINC150 divergence" for the investigation log.
    from dendra.storage import InMemoryStorage

    switch = LearnedSwitch(
        name="bench",
        rule=_rule_fn,
        author="bench",
        ml_head=ml_head,
        storage=InMemoryStorage(),
        config=SwitchConfig(phase=Phase.RULE, auto_record=False),
    )

    checkpoints: list[BenchmarkCheckpoint] = []
    for i, (text, label) in enumerate(train_list, start=1):
        # Route through the switch so phase-specific shadow observations
        # are recorded. We override ``label`` / ``source`` with the
        # oracle truth for training, but thread the classify result
        # (_result_ctx) so the per-call shadow observations still
        # attach to the persisted record.
        # See §6.1 "direct human label" assumption in the paper.
        result = switch.classify(text)
        switch.record_verdict(
            input=text,
            label=label,
            outcome=Verdict.CORRECT.value,
            source="oracle",
            confidence=1.0,
            _result_ctx=result,
        )

        if i % checkpoint_every == 0:
            checkpoints.append(
                _eval_checkpoint(
                    switch=switch,
                    rule=rule,
                    ml_head=ml_head,
                    test_list=test_list,
                    training_outcomes=i,
                    min_train_for_ml=min_train_for_ml,
                    model_acc=model_acc,
                    model_sample=model_sample,
                    record_per_example=record_per_example,
                )
            )

    # Tail checkpoint if last batch was partial.
    if train_list and (not checkpoints or checkpoints[-1].training_outcomes < len(train_list)):
        checkpoints.append(
            _eval_checkpoint(
                switch=switch,
                rule=rule,
                ml_head=ml_head,
                test_list=test_list,
                training_outcomes=len(train_list),
                min_train_for_ml=min_train_for_ml,
                model_acc=model_acc,
                model_sample=model_sample,
                record_per_example=record_per_example,
            )
        )

    return checkpoints


def _eval_checkpoint(
    *,
    switch: LearnedSwitchT,
    rule: Callable[[str], str],
    ml_head: MLHeadT,
    test_list: list[tuple[str, str]],
    training_outcomes: int,
    min_train_for_ml: int,
    model_acc: float | None = None,
    model_sample: int | None = None,
    record_per_example: bool = True,
) -> BenchmarkCheckpoint:
    # Per-example rule correctness — constant across checkpoints (rule is
    # fixed) but recorded at every checkpoint so paired analysis lines up.
    rule_hits = [rule(text) == lbl for text, lbl in test_list]
    rule_acc = sum(rule_hits) / len(test_list) if test_list else 0.0

    ml_trained = False
    ml_acc = 0.0
    ml_hits: list[bool] | None = None
    if training_outcomes >= min_train_for_ml:
        ml_head.fit(switch.storage.load_records(switch.name))
        ml_trained = True
        labels = sorted({lbl for _, lbl in test_list})
        ml_hits = []
        for text, lbl in test_list:
            pred = ml_head.predict(text, labels)
            ml_hits.append(pred.label == lbl)
        ml_acc = sum(ml_hits) / len(test_list) if test_list else 0.0

    return BenchmarkCheckpoint(
        training_outcomes=training_outcomes,
        rule_test_accuracy=rule_acc,
        ml_test_accuracy=ml_acc,
        ml_trained=ml_trained,
        ml_version=ml_head.model_version() if ml_trained else "untrained",
        model_test_accuracy=model_acc,
        lm_test_sample=model_sample,
        rule_correct=rule_hits if record_per_example else None,
        ml_correct=ml_hits if record_per_example else None,
    )


# Type-aliases used only for Protocol annotations above.
MLHeadT = Any
LearnedSwitchT = Any
LLMClassifierT = Any


__all__ = [
    "BenchmarkCheckpoint",
    "BenchmarkExample",
    "Checkpoint",
    "run_benchmark_experiment",
    "run_transition_curve",
]
