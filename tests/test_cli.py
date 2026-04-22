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

"""Tests for the `dendra` CLI surface."""

from __future__ import annotations

import json
import time

import pytest

from dendra import FileStorage, OutcomeRecord
from dendra.cli import main


def _run_cli(argv, capsys):
    """Invoke the CLI main() and capture stdout/stderr."""
    try:
        code = main(argv)
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 0
    out = capsys.readouterr()
    return code, out.out, out.err


# ---------------------------------------------------------------------------
# dendra init
# ---------------------------------------------------------------------------


class TestCliInit:
    def test_init_dry_run_shows_diff(self, tmp_path, capsys):
        src = tmp_path / "triage.py"
        src.write_text(
            "def triage(ticket):\n"
            "    t = ticket.get('title', '').lower()\n"
            "    if 'crash' in t:\n"
            "        return 'bug'\n"
            "    return 'feature'\n"
        )
        code, out, err = _run_cli(
            [
                "init",
                f"{src}:triage",
                "--author",
                "@triage:support",
                "--dry-run",
            ],
            capsys,
        )
        assert code == 0
        assert "@ml_switch(" in out
        assert "from dendra import ml_switch" in out

    def test_init_rejects_nonexistent_file(self, tmp_path, capsys):
        code, out, err = _run_cli(
            ["init", f"{tmp_path}/missing.py:foo", "--author", "@a:b"],
            capsys,
        )
        assert code == 2
        assert "file not found" in err

    def test_init_rejects_malformed_target(self, capsys):
        code, out, err = _run_cli(
            ["init", "no-colon-in-target", "--author", "@a:b"],
            capsys,
        )
        assert code == 2
        assert "FILE:FUNCTION" in err

    def test_init_writes_file_without_dry_run(self, tmp_path, capsys):
        src = tmp_path / "triage.py"
        src.write_text("def triage(x):\n    if 'a' in x: return 'label_a'\n    return 'label_b'\n")
        code, out, err = _run_cli(
            ["init", f"{src}:triage", "--author", "@triage:team"],
            capsys,
        )
        assert code == 0
        modified = src.read_text()
        assert "@ml_switch(" in modified
        assert "from dendra import ml_switch" in modified

    def test_init_with_safety_critical_flag(self, tmp_path, capsys):
        src = tmp_path / "gate.py"
        src.write_text("def gate(x):\n    if 'pii' in x: return 'pii'\n    return 'safe'\n")
        code, out, err = _run_cli(
            [
                "init",
                f"{src}:gate",
                "--author",
                "@safety:gate",
                "--safety-critical",
                "--dry-run",
            ],
            capsys,
        )
        assert code == 0
        assert "safety_critical=True" in out

    def test_init_reports_wrap_errors(self, tmp_path, capsys):
        src = tmp_path / "already.py"
        src.write_text(
            "from dendra import ml_switch\n"
            "\n"
            "@ml_switch(labels=['a'], author='@x:y')\n"
            "def triage(x):\n"
            "    return 'a'\n"
        )
        code, out, err = _run_cli(
            ["init", f"{src}:triage", "--author", "@x:y", "--dry-run"],
            capsys,
        )
        assert code == 1
        assert "already decorated" in err


# ---------------------------------------------------------------------------
# dendra analyze
# ---------------------------------------------------------------------------


class TestCliAnalyze:
    def _write_sample(self, tmp_path):
        (tmp_path / "src.py").write_text(
            "def triage(x):\n"
            "    if 'crash' in x: return 'bug'\n"
            "    if '?' in x: return 'question'\n"
            "    return 'feature'\n"
        )

    def test_analyze_text_default(self, tmp_path, capsys):
        self._write_sample(tmp_path)
        code, out, err = _run_cli(["analyze", str(tmp_path)], capsys)
        assert code == 0
        assert "Dendra static analyzer" in out
        assert "triage" in out

    def test_analyze_json_format(self, tmp_path, capsys):
        self._write_sample(tmp_path)
        code, out, err = _run_cli(
            ["analyze", str(tmp_path), "--format", "json"],
            capsys,
        )
        assert code == 0
        payload = json.loads(out)
        assert payload["total_sites"] == 1
        assert payload["sites"][0]["function_name"] == "triage"

    def test_analyze_legacy_json_flag(self, tmp_path, capsys):
        self._write_sample(tmp_path)
        code, out, err = _run_cli(
            ["analyze", str(tmp_path), "--json"],
            capsys,
        )
        assert code == 0
        json.loads(out)  # validates JSON

    def test_analyze_markdown_with_projection(self, tmp_path, capsys):
        self._write_sample(tmp_path)
        code, out, err = _run_cli(
            [
                "analyze",
                str(tmp_path),
                "--format",
                "markdown",
                "--project-savings",
            ],
            capsys,
        )
        assert code == 0
        assert "# Dendra analyzer report" in out
        assert "Projected annual value" in out
        assert "Portfolio projected value" in out


# ---------------------------------------------------------------------------
# dendra roi
# ---------------------------------------------------------------------------


class TestCliRoi:
    def _seed_storage(self, tmp_path):
        s = FileStorage(tmp_path)
        for i in range(20):
            s.append_outcome(
                "triage",
                OutcomeRecord(
                    timestamp=time.time(),
                    input=f"in {i}",
                    output="bug",
                    outcome="correct" if i % 3 else "incorrect",
                    source="rule",
                    confidence=1.0,
                ),
            )

    def test_roi_text_report(self, tmp_path, capsys):
        self._seed_storage(tmp_path)
        code, out, err = _run_cli(["roi", str(tmp_path)], capsys)
        assert code == 0
        assert "ROI report" in out
        assert "triage" in out

    def test_roi_json_output(self, tmp_path, capsys):
        self._seed_storage(tmp_path)
        code, out, err = _run_cli(["roi", str(tmp_path), "--json"], capsys)
        assert code == 0
        payload = json.loads(out)
        assert "assumptions" in payload
        assert "switches" in payload
        assert len(payload["switches"]) == 1

    def test_roi_override_engineer_cost(self, tmp_path, capsys):
        self._seed_storage(tmp_path)
        code, out, err = _run_cli(
            [
                "roi",
                str(tmp_path),
                "--json",
                "--engineer-cost-per-week",
                "1000",
            ],
            capsys,
        )
        assert code == 0
        payload = json.loads(out)
        assert payload["assumptions"]["engineer_cost_per_week_usd"] == 1000.0


# ---------------------------------------------------------------------------
# dendra plot (smoke test — full render requires matplotlib)
# ---------------------------------------------------------------------------


class TestCliPlot:
    def test_plot_writes_output_file(self, tmp_path, capsys):
        pytest.importorskip("matplotlib")
        jsonl = tmp_path / "run.jsonl"
        jsonl.write_text(
            '{"kind": "summary", "benchmark": "atis", "labels": 26,'
            ' "train_rows": 4978, "test_rows": 893, "seed_size": 100}\n'
            '{"kind": "checkpoint", "training_outcomes": 500,'
            ' "rule_test_accuracy": 0.7, "ml_test_accuracy": 0.79,'
            ' "ml_trained": true, "ml_version": "v1"}\n'
            '{"kind": "checkpoint", "training_outcomes": 1000,'
            ' "rule_test_accuracy": 0.7, "ml_test_accuracy": 0.82,'
            ' "ml_trained": true, "ml_version": "v1"}\n'
        )
        out_png = tmp_path / "fig.png"
        code, _, err = _run_cli(
            ["plot", str(jsonl), "-o", str(out_png)],
            capsys,
        )
        assert code == 0
        assert out_png.exists()
        assert out_png.stat().st_size > 0


# ---------------------------------------------------------------------------
# Error routing
# ---------------------------------------------------------------------------


class TestCliErrorPaths:
    def test_unknown_subcommand_rejected(self, capsys):
        with pytest.raises(SystemExit):
            main(["not-a-real-subcommand"])
