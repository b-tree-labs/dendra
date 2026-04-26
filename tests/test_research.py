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

"""Tests for the transition-curve runner and research instrumentation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from dendra import (
    LearnedSwitch,
    ModelPrediction,
    Phase,
    SwitchConfig,
)
from dendra.research import BenchmarkExample, Checkpoint, run_transition_curve


def _rule(ticket: dict) -> str:
    if "crash" in (ticket.get("title", "") or "").lower():
        return "bug"
    return "feature_request"


@dataclass
class AgreesWithRuleLM:
    """LLM that mirrors the rule — drives 100% agreement for tests."""

    def classify(self, input, labels):
        label = _rule(input)
        return ModelPrediction(label=label, confidence=0.95)


class TestTransitionCurve:
    def test_runs_checkpoints(self):
        s = LearnedSwitch(name="t", rule=_rule, author="alice", auto_record=False)
        examples = [BenchmarkExample(input={"title": f"crash {i}"}, label="bug") for i in range(10)]
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        assert len(checkpoints) == 2
        assert all(isinstance(c, Checkpoint) for c in checkpoints)
        assert checkpoints[-1].outcomes == 10
        # Every example matched the rule.
        assert checkpoints[-1].rule_accuracy == pytest.approx(1.0)
        assert checkpoints[-1].decision_accuracy == pytest.approx(1.0)

    def test_captures_model_shadow_accuracy(self):
        s = LearnedSwitch(
            name="t",
            rule=_rule,
            author="alice",
            model=AgreesWithRuleLM(),
            config=SwitchConfig(auto_record=False, phase=Phase.MODEL_SHADOW),
        )
        examples = [
            BenchmarkExample(input={"title": "crash"}, label="bug"),
            BenchmarkExample(input={"title": "add feature"}, label="feature_request"),
        ] * 5
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        last = checkpoints[-1]
        assert last.lm_accuracy == pytest.approx(1.0)
        assert last.ml_accuracy is None  # no ML head at Phase 1

    def test_tail_checkpoint_appended(self):
        s = LearnedSwitch(name="t", rule=_rule, author="alice", auto_record=False)
        examples = [BenchmarkExample(input={"title": "crash"}, label="bug") for _ in range(7)]
        # 5-step checkpoint gives one at t=5; tail fires at t=7.
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        assert [c.outcomes for c in checkpoints] == [5, 7]


class TestBenchmarkExperimentStorage:
    """Regression: the benchmark harness must not silently drop training
    examples to its own storage cap. v1 CLINC150 divergence root cause —
    default ``BoundedInMemoryStorage(10_000)`` FIFO-evicted at outcome
    10,500 on a label-blocked stream, erasing ~50 label classes from the
    ML head's fit-view."""

    def test_run_benchmark_experiment_uses_unbounded_storage(self):
        """Every training outcome must be addressable at evaluation time.

        Pathological setup: 12 000 training rows (above the default
        10 000 bounded cap), each a distinct (text, label) pair with
        label-blocked ordering — exactly the shape that bit the
        original CLINC150 run. Run the benchmark past the cap and
        assert the final outcome log holds every example.
        """
        from dendra.ml import MLHead
        from dendra.research import run_benchmark_experiment

        # Minimal ML head — no-op, just satisfies the protocol.
        class _NoopHead(MLHead):
            def fit(self, records):
                pass

            def predict(self, input, labels):
                return ModelPrediction(label="x", confidence=0.1)

            def model_version(self):
                return "noop"

        def _rule_fn(text: str) -> str:
            return "x"

        # 12 000 rows, 10 distinct labels feeding in 1 200-sized blocks.
        train = [(f"ex-{i}", f"label-{i // 1200}") for i in range(12_000)]
        test = [("ex-t", "label-0")]

        run_benchmark_experiment(
            train=train,
            test=test,
            rule=_rule_fn,
            ml_head=_NoopHead(),
            checkpoint_every=2_000,
        )

        # Verify: the switch the runner built internally must have
        # retained every training outcome. We can't grab it directly,
        # but we can assert the runner's *contract* by calling it and
        # checking the behaviour — with unbounded storage the ML head
        # would have been offered all 12 000 records at the final
        # checkpoint. Under the old bug it would have seen only
        # 10 000. The simpler assertion: a capture-all ML head counts
        # records and surfaces the count via model_version.
        class _CountingHead(MLHead):
            def __init__(self):
                self.max_seen = 0

            def fit(self, records):
                records = list(records)
                self.max_seen = max(self.max_seen, len(records))

            def predict(self, input, labels):
                return ModelPrediction(label="x", confidence=0.1)

            def model_version(self):
                return f"count-{self.max_seen}"

        counting = _CountingHead()
        run_benchmark_experiment(
            train=train,
            test=test,
            rule=_rule_fn,
            ml_head=counting,
            checkpoint_every=2_000,
        )
        assert counting.max_seen == 12_000, (
            f"benchmark harness must expose every training outcome to "
            f"the ML head; got max_seen={counting.max_seen} of 12 000. "
            "Check that run_benchmark_experiment uses unbounded "
            "InMemoryStorage, not the default BoundedInMemoryStorage."
        )
