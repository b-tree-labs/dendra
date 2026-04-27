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

"""Model Context Protocol (MCP) server for Dendra.

Exposes Dendra's CLI surface as MCP tools so Claude Code (and other
MCP-aware agents) can drive Dendra directly inside a user's codebase
without shelling out.

v1 ships exactly four tools:

- ``dendra_analyze`` (path, format) -> dict
- ``dendra_init`` (file, function_name, dry_run=True) -> dict
- ``dendra_refresh`` (path, check_only=False) -> dict
- ``dendra_doctor`` (path) -> dict

All tools return JSON-serializable dicts. ``dendra_init`` defaults to
``dry_run=True`` so the agent never writes files via MCP unless the
caller is explicit. The handlers call into Dendra's existing modules
in-process (no subprocess hop).

Run as a stdio server:

    python -m dendra.mcp_server

Or via the CLI subcommand:

    dendra mcp

The mcp Python package is an optional dependency. Install with:

    pip install dendra[mcp]
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Fail-import gracefully if the user installed dendra without the mcp extra.
try:
    from mcp import types
    from mcp.server import Server
except ImportError as e:  # pragma: no cover - exercised manually
    raise ImportError(
        "The Dendra MCP server requires the optional 'mcp' dependency. "
        "Install it with: pip install dendra[mcp]"
    ) from e


# ---------------------------------------------------------------------------
# Tool registry. Defined as plain data so the server module is importable
# without spinning up a real Server, and so tests can introspect schemas.
# ---------------------------------------------------------------------------


_TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="dendra_analyze",
        description=(
            "Run the Dendra static analyzer over a file or directory. "
            "Identifies classification sites (return-string dispatch, dict "
            "lookups, regex routers, model prompts) and returns a "
            "structured report identical to `dendra analyze --json`."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to scan.",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "text", "markdown"],
                    "default": "json",
                    "description": "Output format. Default: json.",
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="dendra_init",
        description=(
            "Generate the wrapped form of a single function (insert "
            "@ml_switch decorator + import). Returns the unified diff "
            "and the lists of files that would be created or modified. "
            "v1 default is dry_run=True so the MCP server never writes "
            "files silently."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Path to the source file containing the function.",
                },
                "function_name": {
                    "type": "string",
                    "description": "Top-level function to wrap.",
                },
                "author": {
                    "type": "string",
                    "default": "@agent:mcp",
                    "description": (
                        "Matrix-style principal identifier baked into the "
                        "decorator. Default: @agent:mcp."
                    ),
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Explicit labels. If omitted, Dendra infers them "
                        "from string-literal returns."
                    ),
                },
                "phase": {
                    "type": "string",
                    "default": "RULE",
                    "description": "Initial phase (default: RULE).",
                },
                "safety_critical": {
                    "type": "boolean",
                    "default": False,
                    "description": "Cap graduation at Phase 4.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "When true (the default), do not write files; only "
                        "return the diff. Set false to actually modify the "
                        "file on disk."
                    ),
                },
            },
            "required": ["file", "function_name"],
        },
    ),
    types.Tool(
        name="dendra_refresh",
        description=(
            "Walk the project for __dendra_generated__/ files and report "
            "drift. Returns counts per DriftStatus (up_to_date, "
            "source_drift, user_edited, missing, orphaned) plus a per-file "
            "details list. With check_only=True, behaves as a CI gate: it "
            "never writes files (the v1 server is read-only either way)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Project root to scan. Default: cwd.",
                },
                "check_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, never modify files (CI-gate mode).",
                },
            },
        },
    ),
    types.Tool(
        name="dendra_doctor",
        description=(
            "Diagnostic-only walk of __dendra_generated__/ files. Same "
            "counts as dendra_refresh, plus per-detail severity tags "
            "(info / warning / error) and suggested CLI commands the "
            "user (or agent) should run next."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Project root to scan. Default: cwd.",
                },
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool implementations. Each returns a JSON-serializable dict.
# ---------------------------------------------------------------------------


def _tool_analyze(args: Mapping[str, Any]) -> dict[str, Any]:
    from dendra.analyzer import analyze, render_json

    path = args["path"]
    fmt = args.get("format", "json")
    report = analyze(path)
    # Always return a structured dict. For non-JSON formats we still
    # provide the structured payload alongside the rendered text, since
    # MCP clients consume structured data.
    payload = json.loads(render_json(report))
    if fmt != "json":
        from dendra.analyzer import render_markdown, render_text

        payload["rendered"] = (
            render_markdown(report) if fmt == "markdown" else render_text(report)
        )
        payload["format"] = fmt
    return payload


def _tool_init(args: Mapping[str, Any]) -> dict[str, Any]:
    from dendra.wrap import WrapError, wrap_function

    file = args["file"]
    function_name = args["function_name"]
    author = args.get("author", "@agent:mcp")
    labels = args.get("labels")
    phase = args.get("phase", "RULE")
    safety_critical = bool(args.get("safety_critical", False))
    dry_run = bool(args.get("dry_run", True))

    path = Path(file)
    if not path.exists():
        return {
            "error": f"file not found: {file}",
            "diff": "",
            "files_to_create": [],
            "files_to_modify": [],
        }

    try:
        source = path.read_text(encoding="utf-8")
        result = wrap_function(
            source,
            function_name,
            author=author,
            labels=labels,
            phase=phase,
            safety_critical=safety_critical,
        )
    except WrapError as e:
        return {
            "error": str(e),
            "diff": "",
            "files_to_create": [],
            "files_to_modify": [],
        }
    except SyntaxError as e:
        return {
            "error": f"syntax error in {file}: {e}",
            "diff": "",
            "files_to_create": [],
            "files_to_modify": [],
        }

    diff = result.diff(filename=file)
    files_to_modify = [str(path)]
    files_to_create: list[str] = []

    if not dry_run:
        path.write_text(result.modified_source, encoding="utf-8")

    return {
        "diff": diff,
        "files_to_create": files_to_create,
        "files_to_modify": files_to_modify,
        "labels": list(result.labels),
        "inferred_labels": result.inferred_labels,
        "dry_run": dry_run,
        "wrote_file": (not dry_run),
    }


def _walk_drift(root: Path) -> list[dict[str, Any]]:
    """Walk ``root`` for __dendra_generated__/ files, return per-file rows.

    Each row is a dict with keys: ``generated_path``, ``source_path``,
    ``function_name``, ``status`` (DriftStatus.value). Source files are
    discovered by parsing the generated header and resolving the source
    module to a file under ``root``.
    """
    from dendra.refresh import (
        DriftStatus,
        detect_drift,
        parse_generated_header,
    )

    rows: list[dict[str, Any]] = []
    for gen_path in root.rglob("__dendra_generated__/*.py"):
        try:
            header = parse_generated_header(gen_path.read_text())
        except (ValueError, OSError) as e:
            rows.append(
                {
                    "generated_path": str(gen_path),
                    "source_path": None,
                    "function_name": None,
                    "status": "malformed",
                    "error": str(e),
                }
            )
            continue

        # Resolve source module name to a path under root. We try a
        # straight conversion first ("a.b.c" -> a/b/c.py); if that doesn't
        # exist we fall back to scanning rglob for the basename, which
        # handles unusual layouts without a sys.path lookup.
        candidate = root / Path(*header.source_module.split(".")).with_suffix(".py")
        if not candidate.exists():
            short = header.source_module.split(".")[-1] + ".py"
            matches = [
                p for p in root.rglob(short) if "__dendra_generated__" not in p.parts
            ]
            candidate = matches[0] if matches else candidate

        if not candidate.exists():
            rows.append(
                {
                    "generated_path": str(gen_path),
                    "source_path": None,
                    "function_name": header.source_function,
                    "status": DriftStatus.ORPHANED.value,
                }
            )
            continue

        status = detect_drift(candidate, header.source_function, gen_path)
        rows.append(
            {
                "generated_path": str(gen_path),
                "source_path": str(candidate),
                "function_name": header.source_function,
                "status": status.value,
            }
        )
    return rows


def _summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Tally rows into per-status counts."""
    counts = {
        "up_to_date": 0,
        "source_drift": 0,
        "user_edited": 0,
        "missing": 0,
        "orphaned": 0,
    }
    for r in rows:
        status = r["status"]
        if status in counts:
            counts[status] += 1
    return counts


def _tool_refresh(args: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(args.get("path", "."))
    check_only = bool(args.get("check_only", False))
    rows = _walk_drift(path.resolve())
    counts = _summarize(rows)
    return {
        **counts,
        "details": rows,
        "check_only": check_only,
    }


_SEVERITY = {
    "up_to_date": "info",
    "source_drift": "warning",
    "user_edited": "warning",
    "missing": "warning",
    "orphaned": "error",
    "malformed": "error",
}

_SUGGESTIONS = {
    "up_to_date": "no action needed",
    "source_drift": "run `dendra refresh` to regenerate",
    "user_edited": "run `dendra refresh --force` to overwrite manual edits, or revert them",
    "missing": "run `dendra refresh` to regenerate the missing file",
    "orphaned": "delete the generated file; the source function is gone (or run `dendra refresh --prune`)",
    "malformed": "delete the generated file and re-run `dendra init` for the source function",
}


def _tool_doctor(args: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(args.get("path", "."))
    rows = _walk_drift(path.resolve())
    annotated = []
    for r in rows:
        status = r["status"]
        annotated.append(
            {
                **r,
                "severity": _SEVERITY.get(status, "warning"),
                "suggestion": _SUGGESTIONS.get(
                    status, "run `dendra refresh` for guidance"
                ),
            }
        )
    counts = _summarize(annotated)
    return {**counts, "details": annotated}


_HANDLERS = {
    "dendra_analyze": _tool_analyze,
    "dendra_init": _tool_init,
    "dendra_refresh": _tool_refresh,
    "dendra_doctor": _tool_doctor,
}


# ---------------------------------------------------------------------------
# In-process API used by tests and any embedder. The async surface mirrors
# how the MCP server dispatches; tests can drive it without stdio.
# ---------------------------------------------------------------------------


async def list_tools() -> list[types.Tool]:
    """Return the registered MCP tool definitions."""
    return list(_TOOL_DEFINITIONS)


async def call_tool(name: str, arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    """Invoke a registered tool by name. Returns a JSON-serializable dict."""
    if name not in _HANDLERS:
        raise ValueError(f"unknown tool: {name!r}")
    args = arguments or {}
    return _HANDLERS[name](args)


# ---------------------------------------------------------------------------
# Server wiring + stdio entry point.
# ---------------------------------------------------------------------------


def build_server() -> Server:
    """Construct the MCP Server and register the four tool handlers."""
    server: Server = Server("dendra", version=_dendra_version())

    @server.list_tools()
    async def _handle_list_tools() -> list[types.Tool]:
        return await list_tools()

    @server.call_tool()
    async def _handle_call_tool(name: str, arguments: dict[str, Any]):
        result = await call_tool(name, arguments)
        # Returning a dict surfaces it as structuredContent in the
        # CallToolResult (and is also serialized as text content for
        # clients that don't support structured results).
        return result

    return server


def _dendra_version() -> str:
    try:
        from importlib.metadata import version

        return version("dendra")
    except Exception:  # pragma: no cover
        return "0.0.0"


def serve_stdio() -> None:
    """Run the MCP server over stdio. Blocks until the client disconnects."""
    import anyio

    from mcp.server.stdio import stdio_server

    server = build_server()

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    anyio.run(_run)


def main() -> int:
    """Entry point for ``python -m dendra.mcp_server``."""
    # Sanity guard: the server is silent on stdout (stdio is reserved for
    # the MCP transport). Diagnostic output goes to stderr.
    if os.environ.get("DENDRA_MCP_DEBUG"):
        import sys

        print("Dendra MCP server starting on stdio", file=sys.stderr)
    serve_stdio()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
