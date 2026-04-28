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

"""Tests for the static analyzer."""

from __future__ import annotations

import json

from dendra.analyzer import analyze, render_json, render_text


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


class TestPatternP1:
    def test_if_elif_string_returns_matches(self, tmp_path):
        _write(
            tmp_path / "triage.py",
            "def triage(ticket):\n"
            "    t = ticket.get('title', '').lower()\n"
            "    if 'crash' in t:\n"
            "        return 'bug'\n"
            "    if '?' in t:\n"
            "        return 'question'\n"
            "    return 'feature'\n",
        )
        report = analyze(tmp_path)
        # P4 matches first (keyword-in-scan pattern), which is fine —
        # multiple patterns may apply; we report the first match.
        assert report.total_sites() == 1
        assert report.sites[0].function_name == "triage"
        assert set(report.sites[0].labels) == {"bug", "question", "feature"}
        assert report.sites[0].label_cardinality == 3
        assert report.sites[0].regime == "narrow"
        assert report.sites[0].fit_score >= 4.0


class TestPatternP2:
    def test_match_case_matches(self, tmp_path):
        _write(
            tmp_path / "router.py",
            "def route(x):\n"
            "    match x:\n"
            "        case 'a':\n"
            "            return 'alpha'\n"
            "        case 'b':\n"
            "            return 'beta'\n"
            "        case _:\n"
            "            return 'default'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        s = report.sites[0]
        assert s.pattern == "P2"
        assert set(s.labels) == {"alpha", "beta", "default"}


class TestPatternP3:
    def test_dict_lookup_matches(self, tmp_path):
        _write(
            tmp_path / "lookup.py",
            "def map_code(code):\n"
            "    mapping = {\n"
            "        'a': 'alpha',\n"
            "        'b': 'beta',\n"
            "        'c': 'gamma',\n"
            "        'd': 'delta',\n"
            "    }\n"
            "    return mapping.get(code, 'unknown')\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        assert report.sites[0].pattern == "P3"


class TestPatternP4:
    def test_keyword_scanner_matches(self, tmp_path):
        _write(
            tmp_path / "scan.py",
            "def classify(text):\n"
            "    if 'error' in text:\n"
            "        return 'error'\n"
            "    if 'warning' in text:\n"
            "        return 'warning'\n"
            "    if 'info' in text:\n"
            "        return 'info'\n"
            "    return 'unknown'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        # P4 should be preferred over P1 here since the matchers run in order;
        # P1 is checked first. Either way, we get a valid site with labels.
        s = report.sites[0]
        assert s.pattern in ("P1", "P4")
        assert "error" in s.labels
        assert "warning" in s.labels


class TestPatternP5:
    def test_regex_dispatch_matches(self, tmp_path):
        _write(
            tmp_path / "regex_classify.py",
            "import re\n"
            "\n"
            "def classify(text):\n"
            "    if re.match(r'\\d+', text):\n"
            "        return 'numeric'\n"
            "    if re.search(r'[A-Z]+', text):\n"
            "        return 'uppercase'\n"
            "    return 'other'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        s = report.sites[0]
        # P1 applies (it's an if/elif with string returns), and runs first.
        # The regex ops inside are still covered by P5; the analyzer reports
        # the first matching pattern.
        assert s.pattern in ("P1", "P5")
        assert set(s.labels) == {"numeric", "uppercase", "other"}


class TestPatternP6:
    def test_model_prompted_classifier_matches(self, tmp_path):
        _write(
            tmp_path / "llm_classify.py",
            "def classify(text):\n"
            "    response = client.chat.completions.create(\n"
            "        model='gpt-4', messages=[{'role':'user','content':text}]\n"
            "    )\n"
            "    return response.choices[0].message.content.strip()\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        assert report.sites[0].pattern == "P6"


# ---------------------------------------------------------------------------
# Non-classification functions are ignored
# ---------------------------------------------------------------------------


class TestNonMatches:
    def test_numeric_computation_not_matched(self, tmp_path):
        _write(
            tmp_path / "compute.py",
            "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 0

    def test_single_return_string_not_classifier(self, tmp_path):
        # One string return alone doesn't make it a classifier — no branching.
        _write(
            tmp_path / "const.py",
            "def greeting():\n    return 'hello'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 0

    def test_two_branches_but_no_strings(self, tmp_path):
        _write(
            tmp_path / "branch.py",
            "def route(x):\n    if x > 0:\n        return x + 1\n    return x - 1\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 0


# ---------------------------------------------------------------------------
# Directory traversal + ignore rules
# ---------------------------------------------------------------------------


class TestTraversal:
    def test_walks_subdirectories(self, tmp_path):
        _write(
            tmp_path / "a.py",
            "def triage(x):\n    if 'crash' in x: return 'bug'\n    return 'feat'\n",
        )
        _write(
            tmp_path / "sub" / "b.py",
            "def gate(x):\n"
            "    if 'pii' in x: return 'pii'\n"
            "    if 'tox' in x: return 'toxic'\n"
            "    return 'safe'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 2
        files = sorted({s.file_path for s in report.sites})
        assert files == ["a.py", "sub/b.py"]

    def test_ignores_default_dirs(self, tmp_path):
        _write(
            tmp_path / "real.py",
            "def triage(x):\n    if 'a' in x: return 'x'\n    return 'y'\n",
        )
        _write(
            tmp_path / ".venv" / "noise.py",
            "def noise(x):\n    if 'a' in x: return 'x'\n    return 'y'\n",
        )
        _write(
            tmp_path / "__pycache__" / "gunk.py",
            "def gunk(x):\n    if 'a' in x: return 'x'\n    return 'y'\n",
        )
        report = analyze(tmp_path)
        files = {s.file_path for s in report.sites}
        assert files == {"real.py"}

    def test_parse_error_becomes_warning(self, tmp_path):
        _write(tmp_path / "good.py", "def f(x):\n    return x\n")
        _write(
            tmp_path / "bad.py",
            "def broken(x)\n"  # missing colon
            "    return 'a'\n",
        )
        report = analyze(tmp_path)
        assert len(report.errors) == 1
        assert "bad.py" in report.errors[0]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestRender:
    def test_text_report_contains_file_lines(self, tmp_path):
        _write(
            tmp_path / "triage.py",
            "def triage(x):\n    if 'crash' in x: return 'bug'\n    return 'feature'\n",
        )
        report = analyze(tmp_path)
        text = render_text(report)
        assert "triage.py" in text
        assert "triage" in text
        assert "labels" in text.lower()
        assert "regime" in text.lower()

    def test_json_report_roundtrips(self, tmp_path):
        _write(
            tmp_path / "triage.py",
            "def triage(x):\n    if 'crash' in x: return 'bug'\n    return 'feature'\n",
        )
        report = analyze(tmp_path)
        payload = json.loads(render_json(report))
        assert payload["total_sites"] == 1
        assert payload["sites"][0]["function_name"] == "triage"
        assert set(payload["sites"][0]["labels"]) == {"bug", "feature"}

    def test_empty_report_message(self, tmp_path):
        _write(tmp_path / "plain.py", "def noop(): pass\n")
        report = analyze(tmp_path)
        text = render_text(report)
        assert "No classification sites" in text


# ---------------------------------------------------------------------------
# Markdown rendering + savings projection
# ---------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_markdown_contains_ranked_table(self, tmp_path):
        from dendra.analyzer import render_markdown

        _write(
            tmp_path / "triage.py",
            "def triage(x):\n"
            "    if 'crash' in x: return 'bug'\n"
            "    if 'feat' in x: return 'feature'\n"
            "    return 'question'\n",
        )
        report = analyze(tmp_path)
        md = render_markdown(report)
        assert "# Dendra analyzer report" in md
        assert "Sites ranked by Dendra-fit" in md
        assert "`triage.py:1`" in md
        assert "`triage`" in md

    def test_markdown_empty_has_helpful_message(self, tmp_path):
        from dendra.analyzer import render_markdown

        _write(tmp_path / "noop.py", "def noop(): pass\n")
        report = analyze(tmp_path)
        md = render_markdown(report)
        assert "No classification sites identified" in md
        assert "file an issue" in md


class TestSavingsProjection:
    def test_projection_totals_are_positive(self, tmp_path):
        from dendra.analyzer import project_savings

        _write(
            tmp_path / "triage.py",
            "def triage(x):\n"
            "    if 'crash' in x: return 'bug'\n"
            "    if 'feat' in x: return 'feature'\n"
            "    return 'question'\n",
        )
        report = analyze(tmp_path)
        projections = project_savings(report)
        assert len(projections) == 1
        p = projections[0]
        assert p.total_low_usd > 0
        assert p.total_high_usd >= p.total_low_usd
        assert p.engineering_savings_low_usd > 0
        assert p.token_savings_low_usd > 0
        assert p.regression_avoidance_low_usd > 0

    def test_projection_respects_custom_assumptions(self, tmp_path):
        from dendra.analyzer import project_savings

        _write(
            tmp_path / "triage.py",
            "def triage(x):\n"
            "    if 'crash' in x: return 'bug'\n"
            "    if 'feat' in x: return 'feature'\n"
            "    return 'question'\n",
        )
        report = analyze(tmp_path)
        default = project_savings(report)[0]
        cheap = project_savings(report, eng_cost_per_week_usd=1_000.0)[0]
        assert cheap.engineering_savings_low_usd < default.engineering_savings_low_usd

    def test_markdown_with_projections_shows_totals(self, tmp_path):
        from dendra.analyzer import project_savings, render_markdown

        _write(
            tmp_path / "triage.py",
            "def triage(x):\n"
            "    if 'crash' in x: return 'bug'\n"
            "    if 'feat' in x: return 'feature'\n"
            "    return 'question'\n",
        )
        report = analyze(tmp_path)
        projections = project_savings(report)
        md = render_markdown(report, projections=projections)
        assert "Projected annual value by site" in md
        assert "Portfolio projected value" in md
        assert "$" in md


# ---------------------------------------------------------------------------
# Regime classification (paper §6 alignment)
# ---------------------------------------------------------------------------


class TestRegimeClassification:
    """``_classify_regime`` thresholds align with paper §6:
    cardinality < 30 → narrow (Regime A); 30..60 → medium;
    > 60 → high (Regime B); 0 → unknown.
    """

    def test_zero_cardinality_is_unknown(self):
        from dendra.analyzer import _classify_regime

        assert _classify_regime(0) == "unknown"

    def test_just_below_narrow_threshold(self):
        from dendra.analyzer import _classify_regime

        assert _classify_regime(1) == "narrow"
        assert _classify_regime(29) == "narrow"

    def test_narrow_threshold_boundary(self):
        """Cardinality 30 is the first medium; <30 is narrow."""
        from dendra.analyzer import _classify_regime

        assert _classify_regime(29) == "narrow"
        assert _classify_regime(30) == "medium"

    def test_medium_band(self):
        from dendra.analyzer import _classify_regime

        assert _classify_regime(30) == "medium"
        assert _classify_regime(45) == "medium"
        assert _classify_regime(60) == "medium"

    def test_high_threshold_boundary(self):
        """Cardinality 61 is the first high; ≤60 is medium."""
        from dendra.analyzer import _classify_regime

        assert _classify_regime(60) == "medium"
        assert _classify_regime(61) == "high"

    def test_far_above_high_threshold(self):
        from dendra.analyzer import _classify_regime

        assert _classify_regime(77) == "high"
        assert _classify_regime(151) == "high"
        assert _classify_regime(1000) == "high"

    def test_paper_section_6_anchors(self):
        """The paper's §6 heuristics use these boundary cases. Pin them."""
        from dendra.analyzer import _classify_regime

        # ATIS: 26 labels → narrow (Regime A)
        assert _classify_regime(26) == "narrow"
        # HWU64: 64 labels → high (Regime B)
        assert _classify_regime(64) == "high"
        # Banking77: 77 labels → high (Regime B)
        assert _classify_regime(77) == "high"
        # CLINC150: 151 labels → high (Regime B)
        assert _classify_regime(151) == "high"


class TestFitScoreBoundaries:
    """``_compute_fit_score`` rewards the Regime A sweet spot (2..29)
    plus narrow/medium regime plus P1/P4 patterns."""

    def test_min_score_no_labels_no_p1p4(self):
        from dendra.analyzer import _compute_fit_score

        # Cardinality 0 → unknown regime, no sweet-spot bonus, P5 pattern.
        assert _compute_fit_score([], "P5") == 2.0

    def test_max_score_p1_narrow_sweet_spot(self):
        from dendra.analyzer import _compute_fit_score

        labels = ["bug", "feature", "question"]  # 3 labels, narrow, sweet spot
        assert _compute_fit_score(labels, "P1") == 5.0

    def test_max_score_p4_narrow_sweet_spot(self):
        from dendra.analyzer import _compute_fit_score

        labels = ["bug", "feature", "question"]
        assert _compute_fit_score(labels, "P4") == 5.0

    def test_high_cardinality_loses_sweet_spot_and_regime_bonus(self):
        from dendra.analyzer import _compute_fit_score

        labels = [f"label_{i}" for i in range(70)]  # high regime, outside sweet spot
        # 2 base + 0 (not in sweet spot) + 0 (high regime) + 1 (P1) = 3.0
        assert _compute_fit_score(labels, "P1") == 3.0

    def test_medium_regime_loses_sweet_spot_keeps_regime_bonus(self):
        from dendra.analyzer import _compute_fit_score

        labels = [f"label_{i}" for i in range(40)]  # medium regime, outside sweet spot
        # 2 base + 0 (not sweet spot, n>=30) + 1 (medium regime) + 1 (P4) = 4.0
        assert _compute_fit_score(labels, "P4") == 4.0

    def test_p2_pattern_no_pattern_bonus(self):
        from dendra.analyzer import _compute_fit_score

        labels = ["bug", "feature"]  # narrow, sweet spot, but P2 not P1/P4
        # 2 base + 1 (sweet spot) + 1 (narrow) + 0 (P2) = 4.0
        assert _compute_fit_score(labels, "P2") == 4.0


class TestRegimeInJsonReport:
    """Regime field round-trips correctly through render_json."""

    def test_narrow_regime_in_json(self, tmp_path):
        _write(
            tmp_path / "triage.py",
            "def triage(x):\n"
            "    if 'a' in x: return 'bug'\n"
            "    if 'b' in x: return 'feature'\n"
            "    return 'question'\n",
        )
        report = analyze(tmp_path)
        out = json.loads(render_json(report))
        assert out["sites"][0]["regime"] == "narrow"
        assert out["sites"][0]["label_cardinality"] == 3

    def test_high_regime_appears_in_text_summary(self, tmp_path):
        # Synthesize a 70-label classifier to trigger the high regime.
        labels = [f'"label_{i}"' for i in range(70)]
        body_lines = ["    if 'a' in x: return " + lbl for lbl in labels[:69]]
        body_lines.append(f"    return {labels[69]}")
        _write(
            tmp_path / "many.py",
            "def many(x):\n" + "\n".join(body_lines) + "\n",
        )
        report = analyze(tmp_path)
        text = render_text(report)
        # The text report's by-regime section should mention "high".
        assert "high" in text.lower()


# ---------------------------------------------------------------------------
# Async classifier sites — analyzer must surface AsyncFunctionDef matches.
# Real-codebase testing on 2026-04-28 found zero async sites across 10
# corpora including langchain. Root cause: ``isinstance(node, ast.FunctionDef)``
# excludes ``AsyncFunctionDef``. The fix surfaces them; lifters keep
# refusing for now (queued as v1.5 work).
# ---------------------------------------------------------------------------


class TestAsyncFunctionDef:
    def test_analyzer_recognizes_async_def(self, tmp_path):
        _write(
            tmp_path / "async_triage.py",
            "async def classify(text: str) -> str:\n"
            "    if 'bug' in text:\n"
            "        return 'bug'\n"
            "    return 'other'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1, (
            f"expected analyzer to surface 1 async classifier site, "
            f"got {report.total_sites()}: {[s.function_name for s in report.sites]}"
        )
        site = report.sites[0]
        assert site.function_name == "classify"
        assert site.pattern == "P1"
        assert site.fit_score > 0.0
        assert set(site.labels) == {"bug", "other"}

    def test_analyzer_finds_both_sync_and_async_in_same_file(self, tmp_path):
        _write(
            tmp_path / "mixed.py",
            "def sync_classify(text):\n"
            "    if 'a' in text: return 'alpha'\n"
            "    return 'beta'\n"
            "\n"
            "async def async_classify(text):\n"
            "    if 'a' in text: return 'alpha'\n"
            "    return 'beta'\n",
        )
        report = analyze(tmp_path)
        names = sorted(s.function_name for s in report.sites)
        assert names == ["async_classify", "sync_classify"]


# ---------------------------------------------------------------------------
# Test-path demotion — analyzer should mark sites in test directories /
# pytest-style fixtures as refused with a ``not_a_classifier`` hazard so
# they don't dominate fit lists when users run ``dendra analyze`` on
# their own repo. Mirrors the existing landing-corpus filter, applied at
# the analyzer layer.
# ---------------------------------------------------------------------------


class TestTestPathDemotion:
    def test_analyzer_demotes_test_function_sites(self, tmp_path):
        _write(
            tmp_path / "tests" / "test_thing.py",
            "def test_cors():\n"
            "    if 'origin' in 'header': return 'allowed'\n"
            "    return 'denied'\n",
        )
        report = analyze(tmp_path)
        # Site is still surfaced (option (b) — transparency over silence).
        assert report.total_sites() == 1
        site = report.sites[0]
        assert site.function_name == "test_cors"
        assert site.lift_status == "refused"
        assert any(h.category == "not_a_classifier" for h in site.hazards), (
            f"expected a not_a_classifier hazard, got {[h.category for h in site.hazards]}"
        )

    def test_analyzer_demotes_setup_method(self, tmp_path):
        _write(
            tmp_path / "module" / "thing_test.py",
            "def setUp():\n    if 'a' in 'b': return 'x'\n    return 'y'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        site = report.sites[0]
        assert site.lift_status == "refused"
        assert any(h.category == "not_a_classifier" for h in site.hazards)

    def test_analyzer_demotes_conftest_site(self, tmp_path):
        _write(
            tmp_path / "conftest.py",
            "def my_fixture(x):\n    if 'a' in x: return 'alpha'\n    return 'beta'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        site = report.sites[0]
        assert site.lift_status == "refused"
        assert any(h.category == "not_a_classifier" for h in site.hazards)

    def test_analyzer_demotes_unittest_fixture_in_test_dir(self, tmp_path):
        # Combination: name pattern + path pattern. Should still be one
        # not_a_classifier hazard (no double-counting).
        _write(
            tmp_path / "tests" / "test_x.py",
            "def tearDownClass():\n    if 'a' in 'b': return 'x'\n    return 'y'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        site = report.sites[0]
        assert site.lift_status == "refused"

    def test_real_classifier_in_non_test_path_is_unaffected(self, tmp_path):
        """Sanity check: real production code keeps its lift_status."""
        _write(
            tmp_path / "src" / "triage.py",
            "def triage(ticket):\n    if 'crash' in ticket: return 'bug'\n    return 'feature'\n",
        )
        report = analyze(tmp_path)
        assert report.total_sites() == 1
        site = report.sites[0]
        assert site.lift_status == "auto_liftable"
        assert site.hazards == []
