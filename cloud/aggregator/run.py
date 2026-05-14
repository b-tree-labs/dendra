#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Business Source License 1.1; Change Date 2030-05-01 → Apache 2.0.

"""Postrule Insights aggregator — turns raw events into tuned-defaults.json.

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
        --database postrule-events-staging \\
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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Baked-in default values — same as src/postrule/insights/tuned_defaults.py
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


def aggregate(database: str, env_flag: str, *, version: int) -> dict[str, Any]:
    """Read D1 + assemble the tuned-defaults JSON document."""

    # --- cohort size: distinct account_hash (excluding NULLs) ---
    cohort_rows = query_d1(
        database,
        "SELECT COUNT(DISTINCT account_hash) AS n FROM events WHERE account_hash IS NOT NULL",
        env_flag=env_flag,
    )
    cohort_size = int(cohort_rows[0].get("n", 0)) if cohort_rows else 0

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

    document = {
        "version": version,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
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


def _next_version(previous: int) -> int:
    """Monotonic +1 over the previously-published version."""
    return previous + 1


def _previous_version_from_file(path: Path) -> int:
    """Read `version` from a previously-written tuned-defaults file, or 0."""
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            return int(existing.get("version", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return 0


# ---------------------------------------------------------------------------
# Cloudflare KV write path. Used in production to publish the cohort
# JSON without committing to git — the API Worker reads the value and
# serves it from /insights/tuned-defaults.json. Kept dependency-free
# (urllib only) because the nightly workflow runs bare CPython without
# `pip install`.
# ---------------------------------------------------------------------------

_KV_API_BASE = "https://api.cloudflare.com/client/v4"


def _kv_put_url(account_id: str, namespace_id: str, key: str) -> str:
    return f"{_KV_API_BASE}/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key}"


def _kv_get_url(account_id: str, namespace_id: str, key: str) -> str:
    # Same endpoint shape; GET vs PUT is the verb difference.
    return _kv_put_url(account_id, namespace_id, key)


def _put_to_kv(account_id: str, namespace_id: str, key: str, body: bytes, token: str) -> None:
    req = urllib.request.Request(
        _kv_put_url(account_id, namespace_id, key),
        method="PUT",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"KV PUT failed: status {resp.status}")


def _previous_version_kv(account_id: str, namespace_id: str, key: str, token: str) -> int:
    """GET the existing value, return its `version` field, or 0 if absent."""
    req = urllib.request.Request(
        _kv_get_url(account_id, namespace_id, key),
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return int(payload.get("version", 0))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 0
        raise
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        # Garbage value in KV — treat as "no prior version".
        return 0


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


_KV_KEY = "tuned-defaults.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--database",
        default="postrule-events-staging",
        help="D1 database name (default: postrule-events-staging).",
    )
    parser.add_argument(
        "--env",
        default="",
        choices=["", "production"],
        help="Wrangler env flag (default: staging-equivalent empty).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional file path to write the JSON to. Useful for staging "
            "artifacts and local dev. Production uses --kv-namespace-id."
        ),
    )
    parser.add_argument(
        "--kv-namespace-id",
        default=None,
        help=(
            "Cloudflare KV namespace ID to PUT the JSON into. Requires "
            "CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID in env."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the document to stdout instead of writing.",
    )
    args = parser.parse_args(argv)

    env_flag = "--env production" if args.env == "production" else ""

    # --- Resolve previous version for monotonic bump ---
    if args.kv_namespace_id:
        token = os.environ.get("CLOUDFLARE_API_TOKEN")
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not token or not account_id:
            print(
                "--kv-namespace-id requires CLOUDFLARE_API_TOKEN + "
                "CLOUDFLARE_ACCOUNT_ID environment variables",
                file=sys.stderr,
            )
            return 2
        previous = _previous_version_kv(account_id, args.kv_namespace_id, _KV_KEY, token)
    elif args.output:
        previous = _previous_version_from_file(Path(args.output))
    else:
        previous = 0

    version = _next_version(previous)
    document = aggregate(args.database, env_flag, version=version)
    body = json.dumps(document, indent=2) + "\n"

    if args.dry_run:
        print(body)
        return 0

    if not args.output and not args.kv_namespace_id:
        print(
            "Refusing to run with neither --output nor --kv-namespace-id "
            "(would compute the document and discard it). Pass --dry-run "
            "to inspect.",
            file=sys.stderr,
        )
        return 2

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"Wrote {output}")

    if args.kv_namespace_id:
        # Re-resolve in case the file path branch above ran.
        token = os.environ["CLOUDFLARE_API_TOKEN"]
        account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        _put_to_kv(
            account_id,
            args.kv_namespace_id,
            _KV_KEY,
            body.encode("utf-8"),
            token,
        )
        print(f"Wrote KV namespace {args.kv_namespace_id} key {_KV_KEY}")

    print(
        f"  cohort_size:    {document['cohort_size']}\n"
        f"  events_total:   {document['_meta']['events_total']}\n"
        f"  events_by_type: {document['_meta']['events_by_type']}\n"
        f"  version:        {document['version']}\n"
        f"  generated_at:   {document['generated_at']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
