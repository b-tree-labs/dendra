#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Build a self-contained browser bundle of the analyzer.

The static analyzer (``src/dendra/analyzer.py``) is pure-stdlib except
for two dendra-internal imports used by the @ml_switch wraps:

    from dendra.core import Phase
    from dendra.decorator import ml_switch

For browser-side use via Pyodide we don't need real switches — those
wraps add observability for the local CLI invocation, not for a one-
shot in-browser analyze. We strip the two imports and substitute
inline no-op stubs so the bundle is a single self-contained .py file
Pyodide can load directly without micropip / wheel infra.

Run:
    python3 scripts/build_browser_analyzer.py

Writes:
    landing/wasm/dendra_analyzer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "src" / "dendra" / "analyzer.py"
OUTPUT = REPO_ROOT / "landing" / "wasm" / "dendra_analyzer.py"

_STUBS = """\
# ----- Inlined stubs (browser-only) ---------------------------------------
# The browser bundle doesn't need real LearnedSwitch behavior — these
# stubs make ``@ml_switch(...)`` a no-op decorator and ``Phase.RULE`` a
# trivial constant, so the analyzer module imports + runs without the
# rest of the dendra package.


class Phase:
    RULE = "RULE"
    SHADOW_LM = "SHADOW_LM"
    LM_PRIMARY = "LM_PRIMARY"
    SHADOW_ML = "SHADOW_ML"
    ML_PRIMARY = "ML_PRIMARY"


def ml_switch(**_kwargs):
    def _decorate(fn):
        return fn

    return _decorate


# --------------------------------------------------------------------------
"""


def build() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source not found at {SOURCE}", file=sys.stderr)
        return 1

    src_text = SOURCE.read_text(encoding="utf-8")
    lines = src_text.splitlines(keepends=True)

    out_lines: list[str] = []
    stubs_inserted = False
    for line in lines:
        stripped = line.lstrip()
        # Strip the two dendra-internal imports added in the @ml_switch
        # wrap commit (358b502).
        if stripped.startswith("from dendra.core import Phase") or stripped.startswith(
            "from dendra.decorator import ml_switch"
        ):
            if not stubs_inserted:
                out_lines.append(_STUBS)
                stubs_inserted = True
            continue
        # Drop the explanatory comment block that introduces the strip
        # imports — it references "dendra-internal" which is misleading
        # in the browser bundle context.
        if "Internal-switch wrapping (Dendra-on-Dendra dogfood)." in stripped:
            # Skip this comment line + the next 3 follow-up comment lines.
            continue
        if "Direct imports" in stripped and "going through" in stripped:
            continue
        if "circular import since the package init imports analyzer." in stripped:
            continue
        out_lines.append(line)

    if not stubs_inserted:
        # Fallback: source no longer contains those imports — write the
        # stubs near the top after the stdlib imports anyway, so the
        # build keeps working if the imports get removed.
        out_lines.insert(20, _STUBS)

    header = (
        "# Copyright (c) 2026 B-Tree Ventures, LLC\n"
        "# SPDX-License-Identifier: LicenseRef-BSL-1.1\n"
        "# AUTO-GENERATED — DO NOT EDIT.\n"
        "# Generated from src/dendra/analyzer.py by scripts/build_browser_analyzer.py.\n"
        "# Loaded into Pyodide at runtime by landing/scripts/paste-analyzer.js so\n"
        "# visitors can analyze pasted Python without installing anything locally.\n"
        "# Two dendra-internal imports stripped + replaced with inline no-op stubs\n"
        "# so this is a single self-contained .py file.\n"
        "\n"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(header + "".join(out_lines), encoding="utf-8")

    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
