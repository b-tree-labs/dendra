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
    LLMPrediction,
    Phase,
    SwitchConfig,
)
from dendra.research import BenchmarkExample, Checkpoint, run_transition_curve


def _rule(ticket: dict) -> str:
    if "crash" in (ticket.get("title", "") or "").lower():
        return "bug"
    return "feature_request"


@dataclass
class AgreesWithRuleLLM:
    """LLM that mirrors the rule — drives 100% agreement for tests."""

    def classify(self, input, labels):
        label = _rule(input)
        return LLMPrediction(label=label, confidence=0.95)


class TestTransitionCurve:
    def test_runs_checkpoints(self):
        s = LearnedSwitch(name="t", rule=_rule, author="alice")
        examples = [BenchmarkExample(input={"title": f"crash {i}"}, label="bug") for i in range(10)]
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        assert len(checkpoints) == 2
        assert all(isinstance(c, Checkpoint) for c in checkpoints)
        assert checkpoints[-1].outcomes == 10
        # Every example matched the rule.
        assert checkpoints[-1].rule_accuracy == pytest.approx(1.0)
        assert checkpoints[-1].decision_accuracy == pytest.approx(1.0)

    def test_captures_llm_shadow_accuracy(self):
        s = LearnedSwitch(
            name="t",
            rule=_rule,
            author="alice",
            llm=AgreesWithRuleLLM(),
            config=SwitchConfig(phase=Phase.LLM_SHADOW),
        )
        examples = [
            BenchmarkExample(input={"title": "crash"}, label="bug"),
            BenchmarkExample(input={"title": "add feature"}, label="feature_request"),
        ] * 5
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        last = checkpoints[-1]
        assert last.llm_accuracy == pytest.approx(1.0)
        assert last.ml_accuracy is None  # no ML head at Phase 1

    def test_tail_checkpoint_appended(self):
        s = LearnedSwitch(name="t", rule=_rule, author="alice")
        examples = [BenchmarkExample(input={"title": "crash"}, label="bug") for _ in range(7)]
        # 5-step checkpoint gives one at t=5; tail fires at t=7.
        checkpoints = run_transition_curve(s, examples, checkpoint_every=5)
        assert [c.outcomes for c in checkpoints] == [5, 7]
