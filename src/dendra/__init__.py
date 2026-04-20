# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Dendra — graduated-autonomy classification primitive.

v0.1.0 — Phase 0 (rule mode + outcome logging). See README.md.
"""

__version__ = "0.1.0"

from dendra.core import (
    LearnedSwitch,
    Outcome,
    OutcomeRecord,
    Phase,
    SwitchConfig,
    SwitchResult,
    SwitchStatus,
)
from dendra.decorator import ml_switch
from dendra.storage import FileStorage, InMemoryStorage, Storage

__all__ = [
    "FileStorage",
    "InMemoryStorage",
    "LearnedSwitch",
    "Outcome",
    "OutcomeRecord",
    "Phase",
    "Storage",
    "SwitchConfig",
    "SwitchResult",
    "SwitchStatus",
    "__version__",
    "ml_switch",
]
