# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Filesystem paths shared across the insights package.

All insights state lives under ``~/.dendra/``. The directory is created
lazily on first write; reads against missing files return safe defaults
(no enrollment, empty queue, no cached defaults).
"""

from __future__ import annotations

import os
from pathlib import Path


def dendra_home() -> Path:
    """Return the dendra state directory.

    Honors ``$DENDRA_HOME`` for tests and CI. Defaults to ``~/.dendra``.
    """
    override = os.environ.get("DENDRA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".dendra"


def enrollment_path() -> Path:
    return dendra_home() / "insights-enroll"


def queue_path() -> Path:
    return dendra_home() / "insights-queue.jsonl"


def tuned_defaults_cache_path() -> Path:
    return dendra_home() / "tuned-defaults.json"


def ensure_dendra_home() -> Path:
    """Create ``~/.dendra/`` if missing. Safe to call repeatedly."""
    home = dendra_home()
    home.mkdir(parents=True, exist_ok=True)
    return home
