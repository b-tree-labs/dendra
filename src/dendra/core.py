# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Core types and the LearnedSwitch class — v0.1.0 (Phase 0).

v0.1.0 supports only Phase 0 (RULE). The rule function is always the
decision-maker; ``classify`` returns the rule's output with
``source="rule"`` and ``confidence=1.0``. Outcomes are recorded for
later ML training (Phase 1+).

The data types shipped here are the stable v1 API — Phase 1/2/3
implementations add behavior, not new types.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    """Lifecycle phase. v0.1.0 ships RULE only."""

    RULE = "RULE"
    SHADOW = "SHADOW"
    ML_WITH_FALLBACK = "ML_WITH_FALLBACK"
    ML_PRIMARY = "ML_PRIMARY"


class Outcome(str, Enum):
    """Label for an observed classification decision."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwitchResult:
    """The return value of ``classify``."""

    output: Any
    source: str  # "rule" | "ml" | "rule_fallback"
    confidence: float
    phase: Phase


@dataclass(frozen=True)
class OutcomeRecord:
    """One ``(input, output, outcome)`` row in the outcome log."""

    timestamp: float
    input: Any
    output: Any
    outcome: str  # Outcome value
    source: str  # which path produced `output` at classify time
    confidence: float


@dataclass
class SwitchStatus:
    """Observable state of a switch at a point in time."""

    name: str
    phase: Phase
    outcomes_total: int
    outcomes_correct: int
    outcomes_incorrect: int
    model_version: Optional[str] = None


@dataclass
class SwitchConfig:
    """Runtime configuration for a switch (mostly Phase 1+ concerns)."""

    confidence_threshold: float = 0.85
    safety_critical: bool = False


# ---------------------------------------------------------------------------
# LearnedSwitch
# ---------------------------------------------------------------------------


RuleFunc = Callable[[Any], Any]


class LearnedSwitch:
    """Graduated-autonomy classification primitive.

    v0.1.0 (Phase 0): every classification call goes through the rule.
    Outcomes are logged for later training; the ML path is not active
    yet.

    Args:
        name: Stable identifier used in logs, audit records, storage
            directory naming. Not user-visible.
        rule: Pure function ``input → output`` that produces the
            decision. Never modified by the library; stays code.
        author: Principal associated with the switch (e.g. an email or
            Matrix-style ``@name:ctx``). Stored for future approval
            flows; opaque string to the library.
        config: Optional :class:`SwitchConfig` overrides.
        storage: Optional :class:`Storage` backend. Defaults to
            ``InMemoryStorage`` so a caller who never passes one still
            has a working switch (but loses outcomes on process exit).
    """

    def __init__(
        self,
        *,
        name: str,
        rule: RuleFunc,
        author: str,
        config: Optional[SwitchConfig] = None,
        storage: Optional["Storage"] = None,
    ) -> None:
        if not name:
            raise ValueError("name is required")
        if rule is None or not callable(rule):
            raise ValueError("rule must be a callable")
        if not author:
            raise ValueError("author is required")

        self.name = name
        self._rule = rule
        self.author = author
        self.config = config or SwitchConfig()
        # Lazy import to avoid a circular reference through __init__.
        if storage is None:
            from learned_switch.storage import InMemoryStorage

            storage = InMemoryStorage()
        self._storage = storage

    # --- Public API --------------------------------------------------------

    def classify(self, input: Any) -> SwitchResult:
        """Classify ``input`` — Phase 0 always routes through the rule."""
        output = self._rule(input)
        return SwitchResult(
            output=output,
            source="rule",
            confidence=1.0,
            phase=self.phase(),
        )

    def record_outcome(
        self,
        *,
        input: Any,
        output: Any,
        outcome: str,
        source: str = "rule",
        confidence: float = 1.0,
    ) -> None:
        """Append a labeled outcome to the storage log."""
        if outcome not in {o.value for o in Outcome}:
            raise ValueError(
                f"outcome must be one of {[o.value for o in Outcome]}; "
                f"got {outcome!r}"
            )
        record = OutcomeRecord(
            timestamp=time.time(),
            input=input,
            output=output,
            outcome=outcome,
            source=source,
            confidence=confidence,
        )
        self._storage.append_outcome(self.name, record)

    def phase(self) -> Phase:
        """Current lifecycle phase. v0.1.0 is always Phase.RULE."""
        return Phase.RULE

    def status(self) -> SwitchStatus:
        """Return a :class:`SwitchStatus` snapshot."""
        outcomes = self._storage.load_outcomes(self.name)
        total = len(outcomes)
        correct = sum(1 for r in outcomes if r.outcome == Outcome.CORRECT.value)
        incorrect = sum(1 for r in outcomes if r.outcome == Outcome.INCORRECT.value)
        return SwitchStatus(
            name=self.name,
            phase=self.phase(),
            outcomes_total=total,
            outcomes_correct=correct,
            outcomes_incorrect=incorrect,
            model_version=None,
        )

    # --- Diagnostics -------------------------------------------------------

    @property
    def storage(self) -> "Storage":
        """Public accessor — useful for tests and advanced wiring."""
        return self._storage
