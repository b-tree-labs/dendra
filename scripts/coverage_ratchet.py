#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
"""Coverage ratchet — enforce per-file floors against ``coverage_floors.json``.

Three rules, all enforced on every CI run:

  R1  no-regression. For every file in the floor snapshot, the run's
      pct must be >= the recorded floor.

  R2  buffer above floor for low-coverage files. For every file with
      a recorded floor below 70.0, the run's pct must be >= floor + 5.0.
      The 5pp buffer prevents the snapshot from silently rotting back
      down to the recorded floor; bumping the floor with ``--update``
      requires demonstrating real coverage gains, not a 1-line nudge.

  R3  new-file entry threshold. A file appearing in the run that has
      no recorded floor must be at >= 60.0% on entry. New file passes
      the bar => its actual pct is auto-recorded as the floor (no
      manual ``--update`` needed). Sub-60 => CI red.

Modes:

  scripts/coverage_ratchet.py
      Default check mode. Reads ``coverage.json`` (produced by
      pytest --cov-report=json) and ``coverage_floors.json``. Exits 0
      if all rules pass, 1 otherwise. Prints a human-readable diff.

  scripts/coverage_ratchet.py --update
      Rewrites ``coverage_floors.json`` to the current per-file pcts.
      Use after a deliberate coverage push to lock in the new floor.
      The new floor must itself satisfy R1+R2+R3 against the OLD
      floor — i.e. you cannot use --update to lower the floor.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_JSON = REPO_ROOT / "coverage.json"
FLOORS_JSON = REPO_ROOT / "coverage_floors.json"

LOW_COVERAGE_THRESHOLD = 70.0  # files below this get the +buffer rule
LOW_COVERAGE_BUFFER = 5.0  # required pp above floor for low-cov files
NEW_FILE_MINIMUM = 60.0  # required pct for a file appearing for the first time
TOTAL_KEY = "TOTAL"  # special key in floors for total project coverage

# Float comparison tolerance — coverage.py rounds to 2dp; allow tiny jitter.
EPSILON = 0.05


def load_current_pcts() -> dict[str, float]:
    """Read ``coverage.json`` produced by pytest-cov.

    Returns a mapping of file-path → percent (0–100). Includes the
    special ``TOTAL`` key for project-wide coverage.
    """
    if not COVERAGE_JSON.exists():
        sys.stderr.write(f"error: {COVERAGE_JSON} not found. Run pytest --cov-report=json first.\n")
        sys.exit(2)
    data = json.loads(COVERAGE_JSON.read_text())
    pcts: dict[str, float] = {}
    for path, payload in data.get("files", {}).items():
        pcts[path] = round(float(payload["summary"]["percent_covered"]), 2)
    pcts[TOTAL_KEY] = round(float(data["totals"]["percent_covered"]), 2)
    return pcts


def load_floors() -> dict[str, float]:
    if not FLOORS_JSON.exists():
        return {}
    return json.loads(FLOORS_JSON.read_text())


def write_floors(pcts: dict[str, float]) -> None:
    """Write floors with a stable shape: TOTAL first, then files sorted."""
    sorted_pcts = {TOTAL_KEY: pcts[TOTAL_KEY]}
    for k in sorted(pcts.keys()):
        if k == TOTAL_KEY:
            continue
        sorted_pcts[k] = pcts[k]
    FLOORS_JSON.write_text(json.dumps(sorted_pcts, indent=2) + "\n")


def check(current: dict[str, float], floors: dict[str, float]) -> list[str]:
    """Return a list of human-readable failure messages (empty == pass)."""
    failures: list[str] = []

    # R1 — no-regression on every file in the floor snapshot.
    # R2 — +buffer for files with floor < threshold.
    for path, floor in floors.items():
        if path not in current:
            failures.append(
                f"R1: {path} (floor {floor:.2f}%) is in floors but not in this run "
                "— delete from coverage_floors.json if the file was removed."
            )
            continue
        cur = current[path]
        if cur + EPSILON < floor:
            failures.append(
                f"R1: {path} regressed: {cur:.2f}% < floor {floor:.2f}% (Δ {cur - floor:+.2f}pp)."
            )
            continue
        # R2 only applies to source files with floor < threshold; skip TOTAL.
        if path == TOTAL_KEY:
            continue
        if floor < LOW_COVERAGE_THRESHOLD:
            required = floor + LOW_COVERAGE_BUFFER
            if cur + EPSILON < required:
                failures.append(
                    f"R2: {path} below {LOW_COVERAGE_THRESHOLD:.0f}% floor "
                    f"({floor:.2f}%) requires +{LOW_COVERAGE_BUFFER:.0f}pp buffer; "
                    f"got {cur:.2f}%, need ≥{required:.2f}%."
                )

    # R3 — new files must enter at >= NEW_FILE_MINIMUM.
    for path, cur in current.items():
        if path == TOTAL_KEY:
            continue
        if path in floors:
            continue
        if cur + EPSILON < NEW_FILE_MINIMUM:
            failures.append(
                f"R3: new file {path} entered at {cur:.2f}% — must be "
                f"≥{NEW_FILE_MINIMUM:.0f}% on first appearance."
            )

    return failures


def floor_value_for(current_pct: float) -> float:
    """Map a current run pct to the floor value that should be recorded.

    For low-cov files, the floor lags actual coverage by the buffer so that
    R2 (current >= floor + buffer) can be satisfied right after --update.
    For files at or above the threshold, the floor IS the current pct —
    R2 doesn't apply, so no lag is needed.
    """
    if current_pct < LOW_COVERAGE_THRESHOLD:
        return round(max(0.0, current_pct - LOW_COVERAGE_BUFFER), 2)
    return round(current_pct, 2)


def cmd_check() -> int:
    current = load_current_pcts()
    floors = load_floors()
    failures = check(current, floors)
    if failures:
        sys.stderr.write("coverage ratchet RED:\n\n")
        for msg in failures:
            sys.stderr.write(f"  - {msg}\n")
        sys.stderr.write(
            "\nFix the regression / add tests, then re-run pytest --cov-report=json. "
            "If the floor is genuinely wrong, fix it explicitly via "
            "scripts/coverage_ratchet.py --update.\n"
        )
        return 1

    # Auto-seed new files that cleared R3. We only WRITE the snapshot if
    # we're in --update mode — in check mode we just report what would
    # be seeded so reviewers see it in CI logs.
    new_passes = [p for p, v in current.items() if p not in floors and p != TOTAL_KEY]
    if new_passes:
        sys.stdout.write(
            f"note: {len(new_passes)} new file(s) cleared the {NEW_FILE_MINIMUM:.0f}% bar. "
            "Run scripts/coverage_ratchet.py --update to seed them in coverage_floors.json:\n"
        )
        for p in sorted(new_passes):
            sys.stdout.write(f"  + {p} = {current[p]:.2f}%\n")
        sys.stdout.write("(check mode does not modify the snapshot; CI passes regardless.)\n")

    sys.stdout.write(
        f"coverage ratchet GREEN: {len(floors)} files at floor, "
        f"TOTAL {current[TOTAL_KEY]:.2f}% ≥ {floors.get(TOTAL_KEY, 0):.2f}%.\n"
    )
    return 0


def cmd_update(bootstrap: bool = False) -> int:
    current = load_current_pcts()
    floors = load_floors()
    if bootstrap:
        if floors:
            sys.stderr.write(
                "Refusing to --bootstrap: coverage_floors.json already exists. "
                "Use --update for normal floor bumps.\n"
            )
            return 1
    else:
        # Validate the OLD floor against the current run before bumping.
        # This prevents --update from being used to silently lower a
        # regressed floor or seed a new file below the entry threshold.
        failures = check(current, floors)
        if failures:
            sys.stderr.write(
                "Refusing to --update: the current run violates the existing floors. "
                "Fix the regression first.\n\n"
            )
            for msg in failures:
                sys.stderr.write(f"  - {msg}\n")
            return 1

    new_floors = {
        k: (round(v, 2) if k == TOTAL_KEY else floor_value_for(v)) for k, v in current.items()
    }
    write_floors(new_floors)
    diffs = []
    for path in sorted(set(floors) | set(new_floors)):
        old = floors.get(path)
        new = new_floors.get(path)
        if old is None:
            diffs.append(f"  + {path} = {new:.2f}% (new)")
        elif new is None:
            diffs.append(f"  - {path} (was {old:.2f}%, now removed)")
        elif abs(new - old) >= 0.01:
            diffs.append(f"    {path}: {old:.2f}% → {new:.2f}% ({new - old:+.2f}pp)")
    if diffs:
        sys.stdout.write("Snapshot updated:\n")
        for d in diffs:
            sys.stdout.write(d + "\n")
    sys.stdout.write(
        f"\ncoverage_floors.json now reflects the current run "
        f"(TOTAL {new_floors[TOTAL_KEY]:.2f}%).\n"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--update",
        action="store_true",
        help="rewrite coverage_floors.json to the current run (after rule check passes).",
    )
    ap.add_argument(
        "--bootstrap",
        action="store_true",
        help="seed coverage_floors.json from scratch, bypassing R3. "
        "Refuses to overwrite an existing snapshot.",
    )
    args = ap.parse_args()
    if args.bootstrap:
        return cmd_update(bootstrap=True)
    if args.update:
        return cmd_update()
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
