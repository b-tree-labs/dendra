# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Storage backends for outcome records.

Two backends ship with v0.1.0:

- :class:`InMemoryStorage` — process-local, volatile. Zero dependencies.
  Useful for tests and embedded deployments where outcome persistence
  is owned by the host.
- :class:`FileStorage` — JSONL append-log at
  ``<base>/<switch_name>/outcomes.jsonl``. Durable across process
  restarts. Zero dependencies.

SQLite and Postgres backends are deferred to later releases and will
share the :class:`Storage` protocol so swapping them in is a config
change, not a code change.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from dendra.core import OutcomeRecord


@runtime_checkable
class Storage(Protocol):
    """Contract every outcome-log backend implements."""

    def append_outcome(self, switch_name: str, record: OutcomeRecord) -> None: ...

    def load_outcomes(self, switch_name: str) -> list[OutcomeRecord]: ...


# ---------------------------------------------------------------------------
# InMemoryStorage
# ---------------------------------------------------------------------------


class InMemoryStorage:
    """Process-local append log. Fast, volatile, zero-dep.

    Useful for tests, embedded deployments where the host owns
    persistence, and for non-durable scratch workflows.
    """

    def __init__(self) -> None:
        self._log: dict[str, list[OutcomeRecord]] = {}

    def append_outcome(self, switch_name: str, record: OutcomeRecord) -> None:
        self._log.setdefault(switch_name, []).append(record)

    def load_outcomes(self, switch_name: str) -> list[OutcomeRecord]:
        return list(self._log.get(switch_name, []))


# ---------------------------------------------------------------------------
# FileStorage
# ---------------------------------------------------------------------------


class FileStorage:
    """JSONL append-log on disk.

    Layout: ``<base_path>/<switch_name>/outcomes.jsonl``. One record
    per line. Append-only; never rewrites existing lines.

    Malformed lines (corruption, interrupted writes) are skipped during
    load — the library prefers "some data" over "no data" for a switch
    whose log is mostly intact.
    """

    def __init__(self, base_path: "str | Path") -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def _log_path(self, switch_name: str) -> Path:
        return self._base / switch_name / "outcomes.jsonl"

    def append_outcome(self, switch_name: str, record: OutcomeRecord) -> None:
        path = self._log_path(switch_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Open in line-buffered append mode; one JSON object per line.
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), default=str))
            f.write(os.linesep)

    def load_outcomes(self, switch_name: str) -> list[OutcomeRecord]:
        path = self._log_path(switch_name)
        if not path.exists():
            return []

        records: list[OutcomeRecord] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(OutcomeRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    # Skip corrupted lines — the rest of the log is
                    # still useful.
                    continue
        return records
