#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
"""Validate ``tests/integration/manifest.yaml``.

Fails CI if any named scenario in the manifest doesn't map to a real,
discoverable test. The manifest is the contract — every public-facing
user journey listed there must have a passing test in this build.

Two checks today:

  1. ``kind: pytest`` entries — the node-id must be discoverable by
     ``pytest --collect-only``. Test must exist; this script does NOT
     run it (the regular pytest job does that).

  2. ``kind: github-workflow`` entries — the named .yml file must
     exist under .github/workflows/.

When the manifest grows we may add:
  - kind: e2e          (a tagged pytest marker that runs nightly)
  - kind: dashboard-e2e (Playwright/Cypress against a live preview)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "tests" / "integration" / "manifest.yaml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        sys.stderr.write(f"error: {MANIFEST} not found\n")
        sys.exit(2)
    data = yaml.safe_load(MANIFEST.read_text())
    return data.get("scenarios", [])


def pytest_collection() -> set[str]:
    """Collect all test node-ids known to pytest.

    We use ``--collect-only -q`` and parse the simple-listing output.
    Each line is a node-id; blank lines and the trailing summary are
    skipped.
    """
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "--co", "--no-header"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if res.returncode not in (0, 5):  # 5 = no tests collected; we still parse
        sys.stderr.write("pytest --collect-only failed:\n")
        sys.stderr.write(res.stdout + "\n" + res.stderr)
        sys.exit(2)
    nodes = set()
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\d+ tests? collected", line):
            break
        if "::" in line:
            nodes.add(line)
    return nodes


def matches_pytest(target: str, collected: set[str]) -> bool:
    """A target matches if it's an exact node-id OR a prefix that catches
    at least one collected node (so users can name a class without
    listing every method)."""
    if target in collected:
        return True
    return any(node.startswith(target + "::") or node.startswith(target) for node in collected)


def main() -> int:
    scenarios = load_manifest()
    if not scenarios:
        sys.stderr.write("manifest is empty — add at least one scenario\n")
        return 1

    failures: list[str] = []

    # Defer pytest collection until we know we have pytest entries.
    needs_pytest = any(s.get("kind") == "pytest" for s in scenarios)
    collected: set[str] = pytest_collection() if needs_pytest else set()

    for s in scenarios:
        name = s.get("name", "<unnamed>")
        kind = s.get("kind")
        target = s.get("test")
        if not kind or not target:
            failures.append(f"{name}: missing 'kind' or 'test' field")
            continue
        if kind == "pytest":
            if not matches_pytest(target, collected):
                failures.append(
                    f"{name}: pytest target '{target}' did not match any collected test"
                )
        elif kind == "github-workflow":
            wf = WORKFLOWS_DIR / target
            if not wf.exists():
                failures.append(
                    f"{name}: github-workflow target '{target}' not found under .github/workflows/"
                )
        else:
            failures.append(f"{name}: unknown kind '{kind}'")

    if failures:
        sys.stderr.write("integration manifest INVALID:\n\n")
        for msg in failures:
            sys.stderr.write(f"  - {msg}\n")
        sys.stderr.write(
            "\nFix: add the missing test/workflow, or update the manifest "
            "entry to point at the real target.\n"
        )
        return 1

    pytest_count = sum(1 for s in scenarios if s.get("kind") == "pytest")
    wf_count = sum(1 for s in scenarios if s.get("kind") == "github-workflow")
    sys.stdout.write(
        f"integration manifest OK: {len(scenarios)} scenario(s) "
        f"({pytest_count} pytest, {wf_count} workflow).\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
