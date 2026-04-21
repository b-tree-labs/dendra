# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Storage backends for outcome records.

Two backends ship with v0.2.0:

- :class:`InMemoryStorage` — process-local, volatile. Zero dependencies.
  Useful for tests and embedded deployments where outcome persistence
  is owned by the host.
- :class:`FileStorage` — JSONL append-log at
  ``<base>/<switch_name>/outcomes.jsonl``. Durable across process
  restarts. Zero dependencies. Self-managing: rotates at a configurable
  size cap, prunes rotated segments past a configurable retention count,
  and never grows unbounded.

SQLite and Postgres backends share the :class:`Storage` protocol.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, runtime_checkable

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


# Defaults chosen so *zero-config usage never blows up a disk*:
# - 64 MB per active segment is ~600k outcomes at ~100 bytes each.
# - 8 segments × 64 MB = 512 MB cap per switch before compaction drops
#   oldest rows. A decade of operation at 10 outcomes/sec sits inside this.
_DEFAULT_MAX_BYTES_PER_SEGMENT = 64 * 1024 * 1024
_DEFAULT_MAX_ROTATED_SEGMENTS = 8


class FileStorage:
    """JSONL append-log on disk with self-managing rotation.

    Layout::

        <base_path>/<switch_name>/
            outcomes.jsonl         # active segment (appended to)
            outcomes.jsonl.1       # most-recent rotated segment
            outcomes.jsonl.2
            ...

    When the active segment crosses ``max_bytes_per_segment``, the
    writer renames it to ``outcomes.jsonl.1`` (shifting existing
    segments up) and starts a fresh active file. Segments beyond
    ``max_rotated_segments`` are deleted — old outcomes age out
    **automatically**, no cron required.

    ``load_outcomes`` returns every segment in chronological order.
    Malformed lines are silently skipped ("some data beats no data").

    The defaults (64 MB / 8 segments = ~512 MB cap per switch) are
    chosen so a Dendra install can be left running for years without
    operator touch on any reasonable disk. Shrink them for embedded
    deployments; grow them for data-science workflows that need full
    history.
    """

    def __init__(
        self,
        base_path: str | Path,
        *,
        max_bytes_per_segment: int = _DEFAULT_MAX_BYTES_PER_SEGMENT,
        max_rotated_segments: int = _DEFAULT_MAX_ROTATED_SEGMENTS,
    ) -> None:
        if max_bytes_per_segment <= 0:
            raise ValueError("max_bytes_per_segment must be positive")
        if max_rotated_segments < 0:
            raise ValueError("max_rotated_segments must be >= 0")
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max_bytes_per_segment
        self._max_rotated = max_rotated_segments

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _switch_dir(self, switch_name: str) -> Path:
        return self._base / switch_name

    def _active_path(self, switch_name: str) -> Path:
        return self._switch_dir(switch_name) / "outcomes.jsonl"

    def _rotated_path(self, switch_name: str, idx: int) -> Path:
        return self._switch_dir(switch_name) / f"outcomes.jsonl.{idx}"

    # ------------------------------------------------------------------
    # Append path
    # ------------------------------------------------------------------

    def append_outcome(self, switch_name: str, record: OutcomeRecord) -> None:
        path = self._active_path(switch_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(record), default=str) + os.linesep

        # Rotate BEFORE writing if the new line would put us over the cap.
        # This keeps the size bound strict — segments never exceed cap.
        if path.exists():
            try:
                current = path.stat().st_size
            except OSError:
                current = 0
            if current + len(line) > self._max_bytes:
                self._rotate(switch_name)

        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def _rotate(self, switch_name: str) -> None:
        """Shift segments up and drop anything beyond the retention cap."""
        # Drop segments beyond retention first (from oldest to newest so
        # we never clobber one we'd still be renaming into).
        for idx in range(self._max_rotated + 1, 1000):
            old = self._rotated_path(switch_name, idx)
            if not old.exists():
                break
            with contextlib.suppress(OSError):
                old.unlink()

        # Shift rotated segments up by one slot (N → N+1).
        for idx in range(self._max_rotated, 0, -1):
            src = self._rotated_path(switch_name, idx)
            dst = self._rotated_path(switch_name, idx + 1)
            if src.exists():
                if idx + 1 > self._max_rotated:
                    # Drop if shifting would push us past retention.
                    with contextlib.suppress(OSError):
                        src.unlink()
                    continue
                with contextlib.suppress(OSError):
                    src.replace(dst)

        # Move active → .1.
        active = self._active_path(switch_name)
        if active.exists():
            with contextlib.suppress(OSError):
                active.replace(self._rotated_path(switch_name, 1))

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def load_outcomes(self, switch_name: str) -> list[OutcomeRecord]:
        records: list[OutcomeRecord] = []
        # Walk rotated segments oldest→newest, then the active segment.
        for idx in range(self._max_rotated, 0, -1):
            records.extend(self._read_segment(self._rotated_path(switch_name, idx)))
        records.extend(self._read_segment(self._active_path(switch_name)))
        return records

    @staticmethod
    def _read_segment(path: Path) -> list[OutcomeRecord]:
        if not path.exists():
            return []
        out: list[OutcomeRecord] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    out.append(OutcomeRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    # ------------------------------------------------------------------
    # Operator-facing utilities (also fuel the `dendra roi` reporter)
    # ------------------------------------------------------------------

    def switch_names(self) -> list[str]:
        """Return every switch name that has an outcome directory on disk."""
        if not self._base.exists():
            return []
        return sorted(p.name for p in self._base.iterdir() if p.is_dir())

    def bytes_on_disk(self, switch_name: str) -> int:
        """Total bytes used by this switch across all segments."""
        total = 0
        d = self._switch_dir(switch_name)
        if not d.exists():
            return 0
        for p in d.iterdir():
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    def compact(self, switch_name: str) -> None:
        """Force a rotation pass now, useful before archiving."""
        self._rotate(switch_name)
