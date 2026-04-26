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

"""Tests for the ROI self-reporter."""

from __future__ import annotations

import time

import pytest

from dendra import ClassificationRecord, FileStorage
from dendra.roi import (
    ROIAssumptions,
    compute_portfolio_roi,
    compute_switch_roi,
    format_portfolio_report,
)


def _outcome(*, source="rule", outcome="correct", output="bug") -> ClassificationRecord:
    return ClassificationRecord(
        timestamp=time.time(),
        input={"x": 1},
        label=output,
        outcome=outcome,
        source=source,
        confidence=1.0,
    )


class TestSwitchROI:
    def test_direct_eng_savings_use_range(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(50):
            s.append_record("triage", _outcome())
        roi = compute_switch_roi(switch_name="triage", storage=s)
        # Low bound should be > 0 for a switch with outcomes logged.
        assert roi.direct_eng_savings_low_usd > 0
        assert roi.direct_eng_savings_high_usd >= roi.direct_eng_savings_low_usd

    def test_no_ttm_when_never_graduated(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(50):
            s.append_record("triage", _outcome(source="rule"))
        roi = compute_switch_roi(switch_name="triage", storage=s)
        assert roi.phase_ever_graduated is False
        assert roi.ttm_value_low_usd == 0.0
        assert roi.ttm_value_high_usd == 0.0

    def test_ttm_populates_when_graduated(self, tmp_path):
        s = FileStorage(tmp_path)
        s.append_record("triage", _outcome(source="rule"))
        s.append_record("triage", _outcome(source="ml"))
        roi = compute_switch_roi(switch_name="triage", storage=s)
        assert roi.phase_ever_graduated is True
        assert roi.ttm_value_low_usd > 0
        assert roi.ttm_value_high_usd > roi.ttm_value_low_usd

    def test_regression_scales_with_volume(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(1_000):
            s.append_record("big", _outcome())
        s.append_record("small", _outcome())
        big = compute_switch_roi(switch_name="big", storage=s)
        small = compute_switch_roi(switch_name="small", storage=s)
        assert big.regression_avoidance_low_usd >= small.regression_avoidance_low_usd

    def test_custom_assumptions_override(self, tmp_path):
        s = FileStorage(tmp_path)
        s.append_record("triage", _outcome(source="ml"))
        default = compute_switch_roi(switch_name="triage", storage=s)
        cheap = compute_switch_roi(
            switch_name="triage",
            storage=s,
            assumptions=ROIAssumptions(engineer_cost_per_week_usd=1_000.0),
        )
        assert cheap.direct_eng_savings_low_usd < default.direct_eng_savings_low_usd

    def test_token_savings_count_non_model_outcomes(self, tmp_path):
        s = FileStorage(tmp_path)
        # 100 rule outcomes, 20 ml outcomes, 30 llm outcomes.
        for _ in range(100):
            s.append_record("hot_path", _outcome(source="rule"))
        for _ in range(20):
            s.append_record("hot_path", _outcome(source="ml"))
        for _ in range(30):
            s.append_record("hot_path", _outcome(source="model"))
        roi = compute_switch_roi(switch_name="hot_path", storage=s)
        # 100 rule + 20 ml = 120 LLM calls avoided.
        assert roi.model_calls_avoided == 120
        # Positive range, low <= high.
        assert roi.token_savings_low_usd > 0
        assert roi.token_savings_high_usd >= roi.token_savings_low_usd

    def test_token_savings_scale_with_counterfactual_pct(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(100):
            s.append_record("a", _outcome(source="rule"))
        default = compute_switch_roi(switch_name="a", storage=s)
        halved = compute_switch_roi(
            switch_name="a",
            storage=s,
            assumptions=ROIAssumptions(pct_outcomes_that_would_use_llm_without_dendra=0.5),
        )
        # Halving the counter-factual halves the token savings.
        assert abs(halved.token_savings_low_usd - default.token_savings_low_usd / 2) < 1.0

    def test_all_model_traffic_means_zero_token_savings(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(100):
            s.append_record("a", _outcome(source="model"))
        roi = compute_switch_roi(switch_name="a", storage=s)
        assert roi.model_calls_avoided == 0
        assert roi.token_savings_low_usd == 0.0

    def test_accuracy_computed_from_outcomes(self, tmp_path):
        s = FileStorage(tmp_path)
        for _ in range(7):
            s.append_record("triage", _outcome(outcome="correct"))
        for _ in range(3):
            s.append_record("triage", _outcome(outcome="incorrect"))
        roi = compute_switch_roi(switch_name="triage", storage=s)
        assert roi.accuracy == pytest.approx(0.7)
        assert roi.outcomes_correct == 7
        assert roi.outcomes_incorrect == 3


class TestPortfolio:
    def test_reports_every_switch(self, tmp_path):
        s = FileStorage(tmp_path)
        s.append_record("a", _outcome())
        s.append_record("b", _outcome())
        rois = compute_portfolio_roi(storage=s)
        names = sorted(r.switch_name for r in rois)
        assert names == ["a", "b"]

    def test_report_contains_assumptions(self, tmp_path):
        s = FileStorage(tmp_path)
        s.append_record("a", _outcome())
        rois = compute_portfolio_roi(storage=s)
        report = format_portfolio_report(rois)
        assert "ROI report" in report
        assert "eng_cost_per_week" in report
        assert "a" in report
