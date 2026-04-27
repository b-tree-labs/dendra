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

"""Tests for the Dendra MCP server.

The MCP server exposes Dendra's CLI surface as Model Context Protocol
tools so Claude Code (and other MCP-aware agents) can drive Dendra
inside a user's codebase. v1 ships exactly four tools:

- ``dendra_analyze``
- ``dendra_init``
- ``dendra_refresh``
- ``dendra_doctor``

These tests run in-process (no stdio transport). They confirm tool
registration shape and that each tool handler returns the expected
JSON-serializable dict against fixture projects on disk.
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path

import pytest

# Skip the entire module if mcp isn't installed. The server module is
# expected to fail-import gracefully with a helpful error in that case,
# but these tests need the real package.
mcp = pytest.importorskip("mcp")

from dendra import mcp_server  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in a fresh event loop for in-process tests."""
    return asyncio.run(coro)


def _make_simple_classifier(tmp_path: Path) -> Path:
    """Write a tiny Python file with one return-string classification site."""
    f = tmp_path / "triage.py"
    f.write_text(
        textwrap.dedent(
            """\
            def triage_ticket(text):
                if "billing" in text:
                    return "billing"
                if "outage" in text:
                    return "outage"
                return "general"
            """
        )
    )
    return f


# ---------------------------------------------------------------------------
# Tool registration shape
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """All four tools must be registered with valid JSON-Schema input."""

    def test_list_tools_returns_exactly_four(self):
        tools = _run(mcp_server.list_tools())
        names = sorted(t.name for t in tools)
        assert names == [
            "dendra_analyze",
            "dendra_doctor",
            "dendra_init",
            "dendra_refresh",
        ]

    def test_each_tool_has_description_and_schema(self):
        tools = _run(mcp_server.list_tools())
        for t in tools:
            assert t.description, f"{t.name} missing description"
            assert isinstance(t.inputSchema, dict)
            assert t.inputSchema.get("type") == "object"
            assert "properties" in t.inputSchema

    def test_analyze_schema_requires_path(self):
        tools = {t.name: t for t in _run(mcp_server.list_tools())}
        schema = tools["dendra_analyze"].inputSchema
        assert "path" in schema["properties"]
        assert "path" in schema.get("required", [])

    def test_init_schema_has_dry_run_default_true(self):
        tools = {t.name: t for t in _run(mcp_server.list_tools())}
        schema = tools["dendra_init"].inputSchema
        props = schema["properties"]
        assert "file" in props
        assert "function_name" in props
        assert "dry_run" in props
        # v1: dry_run defaults to True so MCP can't silently write files.
        assert props["dry_run"].get("default") is True


# ---------------------------------------------------------------------------
# dendra_analyze
# ---------------------------------------------------------------------------


class TestAnalyzeTool:
    def test_analyze_file_returns_dict_with_sites(self, tmp_path):
        f = _make_simple_classifier(tmp_path)
        result = _run(mcp_server.call_tool("dendra_analyze", {"path": str(f)}))
        assert isinstance(result, dict)
        assert result["files_scanned"] == 1
        assert result["total_sites"] >= 1
        assert any(s["function_name"] == "triage_ticket" for s in result["sites"])

    def test_analyze_directory_walks_recursively(self, tmp_path):
        _make_simple_classifier(tmp_path)
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "more.py").write_text(
            textwrap.dedent(
                """\
                def kind(x):
                    if x > 0:
                        return "pos"
                    return "neg"
                """
            )
        )
        result = _run(mcp_server.call_tool("dendra_analyze", {"path": str(tmp_path)}))
        assert result["files_scanned"] >= 2
        names = {s["function_name"] for s in result["sites"]}
        assert "triage_ticket" in names

    def test_analyze_missing_path_returns_structured_error(self, tmp_path):
        result = _run(
            mcp_server.call_tool(
                "dendra_analyze", {"path": str(tmp_path / "does-not-exist.py")}
            )
        )
        # The analyzer reports the missing path via its `errors` list.
        assert result["files_scanned"] == 0
        assert result["errors"]

    def test_analyze_result_is_json_serializable(self, tmp_path):
        f = _make_simple_classifier(tmp_path)
        result = _run(mcp_server.call_tool("dendra_analyze", {"path": str(f)}))
        # If it round-trips through json, downstream agents can consume it.
        json.dumps(result)


# ---------------------------------------------------------------------------
# dendra_init
# ---------------------------------------------------------------------------


class TestInitTool:
    def test_init_dry_run_returns_diff(self, tmp_path):
        f = _make_simple_classifier(tmp_path)
        original = f.read_text()
        result = _run(
            mcp_server.call_tool(
                "dendra_init",
                {"file": str(f), "function_name": "triage_ticket"},
            )
        )
        assert isinstance(result, dict)
        assert "diff" in result
        assert "@ml_switch" in result["diff"]
        assert isinstance(result["files_to_create"], list)
        assert isinstance(result["files_to_modify"], list)
        # dry-run default: file on disk must be untouched.
        assert f.read_text() == original
        assert str(f) in result["files_to_modify"]

    def test_init_non_existent_file_returns_structured_error(self, tmp_path):
        result = _run(
            mcp_server.call_tool(
                "dendra_init",
                {"file": str(tmp_path / "missing.py"), "function_name": "foo"},
            )
        )
        assert isinstance(result, dict)
        assert result.get("error")
        # Don't crash; no diff.
        assert result.get("diff") in (None, "")

    def test_init_unknown_function_returns_structured_error(self, tmp_path):
        f = _make_simple_classifier(tmp_path)
        result = _run(
            mcp_server.call_tool(
                "dendra_init",
                {"file": str(f), "function_name": "does_not_exist"},
            )
        )
        assert result.get("error")


# ---------------------------------------------------------------------------
# dendra_refresh: walks __dendra_generated__ dirs and reports drift.
# ---------------------------------------------------------------------------


class TestRefreshTool:
    def _seed_generated(self, tmp_path: Path) -> Path:
        """Create one source file + one matching generated file (up-to-date)."""
        from dendra.refresh import ast_hash, write_generated_file

        proj = tmp_path / "proj"
        proj.mkdir()
        src = proj / "myapp" / "routing.py"
        src.parent.mkdir(parents=True)
        src.write_text("def route_user(text):\n    return 'standard'\n")
        gen = proj / "myapp" / "__dendra_generated__" / "routing__route_user.py"
        write_generated_file(
            gen,
            source_module="myapp.routing",
            source_function="route_user",
            source_ast_hash=ast_hash(src.read_text()),
            content="class RouteUserSwitch:\n    pass\n",
            dendra_version="1.0.0",
        )
        return proj

    def test_refresh_reports_up_to_date(self, tmp_path):
        proj = self._seed_generated(tmp_path)
        result = _run(
            mcp_server.call_tool("dendra_refresh", {"path": str(proj)})
        )
        assert result["up_to_date"] == 1
        assert result["source_drift"] == 0
        assert result["user_edited"] == 0
        assert result["missing"] == 0
        assert result["orphaned"] == 0
        assert isinstance(result["details"], list)
        assert len(result["details"]) == 1

    def test_refresh_detects_source_drift(self, tmp_path):
        proj = self._seed_generated(tmp_path)
        # User edits source.
        src = proj / "myapp" / "routing.py"
        src.write_text("def route_user(text):\n    return 'premium'\n")
        result = _run(
            mcp_server.call_tool("dendra_refresh", {"path": str(proj)})
        )
        assert result["source_drift"] == 1
        assert result["up_to_date"] == 0

    def test_refresh_detects_orphaned(self, tmp_path):
        proj = self._seed_generated(tmp_path)
        src = proj / "myapp" / "routing.py"
        src.write_text("def something_else(): pass\n")
        result = _run(
            mcp_server.call_tool("dendra_refresh", {"path": str(proj)})
        )
        assert result["orphaned"] == 1

    def test_refresh_check_only_does_not_write(self, tmp_path):
        proj = self._seed_generated(tmp_path)
        before = sorted(p.name for p in proj.rglob("*.py"))
        _run(
            mcp_server.call_tool(
                "dendra_refresh", {"path": str(proj), "check_only": True}
            )
        )
        after = sorted(p.name for p in proj.rglob("*.py"))
        assert before == after


# ---------------------------------------------------------------------------
# dendra_doctor: same shape as refresh, with severity + suggestions.
# ---------------------------------------------------------------------------


class TestDoctorTool:
    def test_doctor_returns_severity_tags(self, tmp_path):
        from dendra.refresh import ast_hash, write_generated_file

        proj = tmp_path / "proj"
        proj.mkdir()
        src = proj / "myapp" / "routing.py"
        src.parent.mkdir(parents=True)
        src.write_text("def route_user(text):\n    return 'standard'\n")
        gen = proj / "myapp" / "__dendra_generated__" / "routing__route_user.py"
        write_generated_file(
            gen,
            source_module="myapp.routing",
            source_function="route_user",
            source_ast_hash=ast_hash(src.read_text()),
            content="class RouteUserSwitch:\n    pass\n",
            dendra_version="1.0.0",
        )
        # Make this drift.
        src.write_text("def route_user(text):\n    return 'premium'\n")

        result = _run(mcp_server.call_tool("dendra_doctor", {"path": str(proj)}))
        assert "details" in result
        assert result["source_drift"] == 1
        # doctor adds severity + suggestion per detail.
        d = result["details"][0]
        assert "severity" in d
        assert "suggestion" in d
        assert "dendra refresh" in d["suggestion"]


# ---------------------------------------------------------------------------
# Unknown tool name -> structured error (not a crash).
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="unknown tool"):
            _run(mcp_server.call_tool("dendra_nope", {}))
