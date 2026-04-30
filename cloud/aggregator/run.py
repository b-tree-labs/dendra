#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Dendra Insights aggregator — turns raw events into tuned-defaults.json.

Reads from the D1 events database (via wrangler d1 execute) and writes
to landing/insights/tuned-defaults.json. Triggered nightly by
.github/workflows/aggregator.yml.

v1 ships a TRIVIAL aggregator: it republishes the baked-in defaults
with cohort_size + generated_at refreshed, plus event_type histograms
for transparency. No regime-keyed parameter tuning yet — that's the
Phase B "real signal extraction" enhancement once we have ≥100
graduation events to learn from.

Schema of the output JSON (kept stable; clients tolerate forward-
compatible additions):

  {
    "version": <monotonic int>,
    "generated_at": <ISO-8601 UTC>,
    "cohort_size": <distinct account_hash count>,
    "defaults": {
      "median_outcomes_to_graduation": {"narrow": 250, ...},
      "suggested_min_outcomes": {"narrow": 250, ...},
      "suggested_alpha": null,
      "pattern_frequencies": {"P1": 0.42, ...},
      "top_refusal_categories": [...]
    },
    "signature": null,        // Phase B: Ed25519 over canonical JSON
    "_meta": {
      "events_total": <int>,
      "events_by_type": {"analyze": <int>, ...},
      "aggregator_version": "<git sha>"
    }
  }

Run locally (against the staging D1):

    python cloud/aggregator/run.py \\
        --database dendra-events-staging \\
        --output landing/insights/tuned-defaults.json

Run via GitHub Action (see .github/workflows/aggregator.yml) — uses
wrangler with CLOUDFLARE_API_TOKEN to query D1 remotely.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# Baked-in default values — same as src/dendra/insights/tuned_defaults.py
# BAKED_IN_DEFAULTS. The aggregator MAY override these in v1.1+ once we
# have signal-extraction logic; for v1.0 they pass through unchanged
# with cohort_size + generated_at refreshed.
_BAKED_IN_DEFAULTS = {
    "median_outcomes_to_graduation": {
        "narrow": 250,
        "medium": 500,
        "high": 1000,
    },
    "suggested_min_outcomes": {
        "narrow": 250,
        "medium": 500,
        "high": 1000,
    },
    "suggested_alpha": None,
    "pattern_frequencies": {},
    "top_refusal_categories": [],
}


def query_d1(database: str, sql: str, *, env_flag: str = "") -> list[dict[str, Any]]:
    """Run a SELECT against D1 via wrangler and return rows as dicts.

    ``env_flag`` should be ``"--env production"`` for the prod database
    or ``""`` (default) for staging.
    """
    cmd = [
        "wrangler",
        "d1",
        "execute",
        database,
        "--remote",
        "--json",
        "--command",
        sql,
    ]
    if env_flag:
        cmd.extend(env_flag.split())

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"wrangler d1 execute failed (rc={result.returncode}):\n"
            f"  stderr: {result.stderr.strip()}",
            file=sys.stderr,
        )
        # On failure, return an empty result rather than abort. The
        # aggregator's job is "best-effort republish"; if D1 is
        # unreachable we still want to refresh the timestamp so
        # client caches don't go stale unnecessarily.
        return []

    try:
        # wrangler returns a list of result objects; each has a `results` array
        # of rows. We always do single-statement queries so take the first.
        parsed = json.loads(result.stdout)
        if isinstance(parsed, list) and parsed:
            rows = parsed[0].get("results", [])
            return rows if isinstance(rows, list) else []
    except json.JSONDecodeError as e:
        print(f"failed to parse wrangler JSON output: {e}", file=sys.stderr)
        return []
    return []


def aggregate(database: str, env_flag: str) -> dict[str, Any]:
    """Read D1 + assemble the tuned-defaults JSON document."""

    # --- cohort size: distinct account_hash (excluding NULLs) ---
    cohort_rows = query_d1(
        database,
        "SELECT COUNT(DISTINCT account_hash) AS n FROM events "
        "WHERE account_hash IS NOT NULL",
        env_flag=env_flag,
    )
    cohort_size = (
        int(cohort_rows[0].get("n", 0)) if cohort_rows else 0
    )

    # --- event totals + by-type breakdown ---
    total_rows = query_d1(
        database,
        "SELECT COUNT(*) AS n FROM events",
        env_flag=env_flag,
    )
    events_total = int(total_rows[0].get("n", 0)) if total_rows else 0

    by_type_rows = query_d1(
        database,
        "SELECT event_type, COUNT(*) AS n FROM events GROUP BY event_type",
        env_flag=env_flag,
    )
    events_by_type = {row["event_type"]: int(row["n"]) for row in by_type_rows}

    # --- pattern frequencies (extracted from analyze event payloads) ---
    # v1.0: trivial — leave as empty dict. Phase B will SELECT
    # json_extract(payload_json, '$.pattern_histogram') and aggregate
    # across the cohort.
    pattern_frequencies: dict[str, float] = {}

    # --- top refusal categories ---
    # Same: Phase B; v1.0 leaves empty.
    top_refusal_categories: list[str] = []

    # --- assemble + bump version ---
    version = _next_version()

    document = {
        "version": version,
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "cohort_size": cohort_size,
        "defaults": {
            **_BAKED_IN_DEFAULTS,
            "pattern_frequencies": pattern_frequencies,
            "top_refusal_categories": top_refusal_categories,
        },
        "signature": None,  # Phase B
        "_meta": {
            "events_total": events_total,
            "events_by_type": events_by_type,
            "aggregator_version": _git_sha(),
            "source_database": database,
        },
    }
    return document


def _next_version() -> int:
    """Monotonically-increasing version counter persisted in the output file.

    Reads the previous version from the existing file (if any) and adds 1.
    The version field gates client-side cache invalidation; bumping it
    every aggregator run ensures clients with stale caches re-fetch at
    least once per cycle.
    """
    output = os.environ.get("DENDRA_AGGREGATOR_OUTPUT", "landing/insights/tuned-defaults.json")
    path = Path(output)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            return int(existing.get("version", 0)) + 1
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return 1


def _git_sha() -> str:
    """Short git SHA of the aggregator's source. Used for traceability."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--database",
        default="dendra-events-staging",
        help="D1 database name (default: dendra-events-staging).",
    )
    parser.add_argument(
        "--env",
        default="",
        choices=["", "production"],
        help="Wrangler env flag (default: staging-equivalent empty).",
    )
    parser.add_argument(
        "--output",
        default="landing/insights/tuned-defaults.json",
        help="Output path (default: landing/insights/tuned-defaults.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the document to stdout instead of writing.",
    )
    args = parser.parse_args()

    env_flag = "--env production" if args.env == "production" else ""
    document = aggregate(args.database, env_flag)

    if args.dry_run:
        print(json.dumps(document, indent=2))
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {output}\n"
        f"  cohort_size:    {document['cohort_size']}\n"
        f"  events_total:   {document['_meta']['events_total']}\n"
        f"  events_by_type: {document['_meta']['events_by_type']}\n"
        f"  version:        {document['version']}\n"
        f"  generated_at:   {document['generated_at']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
