# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Core types and the LearnedSwitch class.

v0.2.0 extends v0.1.0 with Phase 1 (LLM_SHADOW). The six-phase
lifecycle follows the paper outline (§3.1):

    RULE → LLM_SHADOW → LLM_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK → ML_PRIMARY

In RULE the rule is the decision-maker. In LLM_SHADOW the rule still
decides; an LLM runs alongside, its prediction captured on every
outcome for later analysis. Phases 2+ add their own routing rules.
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
    """Lifecycle phase — see paper §3.1 Table 1."""

    RULE = "RULE"
    LLM_SHADOW = "LLM_SHADOW"
    LLM_PRIMARY = "LLM_PRIMARY"
    ML_SHADOW = "ML_SHADOW"
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
    source: str  # "rule" | "llm" | "ml" | "rule_fallback"
    confidence: float
    phase: Phase


@dataclass(frozen=True)
class OutcomeRecord:
    """One ``(input, output, outcome)`` row in the outcome log.

    Extra fields capture shadow predictions so later phase-transition
    math can run on a single source of truth.
    """

    timestamp: float
    input: Any
    output: Any
    outcome: str  # Outcome value
    source: str  # which path produced `output` at classify time
    confidence: float
    # Phase 1+ shadow observations (optional; omitted at Phase 0).
    rule_output: Optional[Any] = None
    llm_output: Optional[Any] = None
    llm_confidence: Optional[float] = None
    # Phase 3+ ML shadow observations.
    ml_output: Optional[Any] = None
    ml_confidence: Optional[float] = None


@dataclass
class SwitchStatus:
    """Observable state of a switch at a point in time."""

    name: str
    phase: Phase
    outcomes_total: int
    outcomes_correct: int
    outcomes_incorrect: int
    model_version: Optional[str] = None
    # Phase 1 observability — fraction of outcomes where the LLM agreed
    # with the rule. ``None`` when no shadow observations are recorded.
    shadow_agreement_rate: Optional[float] = None
    # Phase 3 observability — fraction where ML shadow matched the primary.
    ml_agreement_rate: Optional[float] = None
    # Phase 5 circuit-breaker state.
    circuit_breaker_tripped: bool = False


@dataclass
class SwitchConfig:
    """Runtime configuration for a switch."""

    confidence_threshold: float = 0.85
    safety_critical: bool = False
    phase: Phase = Phase.RULE


# ---------------------------------------------------------------------------
# LearnedSwitch
# ---------------------------------------------------------------------------


RuleFunc = Callable[[Any], Any]


class LearnedSwitch:
    """Graduated-autonomy classification primitive.

    Args:
        name: Stable identifier used in logs, audit records, storage
            directory naming.
        rule: Pure function ``input → output`` that produces the
            safety-floor decision. Never modified by the library.
        author: Principal associated with the switch (opaque string).
        config: Optional :class:`SwitchConfig`. The ``phase`` field
            drives classify()'s routing.
        storage: Optional :class:`Storage` backend. Defaults to
            :class:`InMemoryStorage`.
        llm: Optional :class:`LLMClassifier` used in LLM_SHADOW and
            LLM_PRIMARY phases.
    """

    def __init__(
        self,
        *,
        name: str,
        rule: RuleFunc,
        author: str,
        config: Optional[SwitchConfig] = None,
        storage: Optional["Storage"] = None,
        llm: Optional["LLMClassifier"] = None,
        ml_head: Optional["MLHead"] = None,
        telemetry: Optional["TelemetryEmitter"] = None,
    ) -> None:
        if not name:
            raise ValueError("name is required")
        if rule is None or not callable(rule):
            raise ValueError("rule must be a callable")
        if not author:
            raise ValueError("author is required")

        resolved_config = config or SwitchConfig()
        if (
            resolved_config.safety_critical
            and resolved_config.phase is Phase.ML_PRIMARY
        ):
            raise ValueError(
                "safety_critical switches cannot start in ML_PRIMARY; "
                "cap at ML_WITH_FALLBACK (paper §7.1)."
            )

        self.name = name
        self._rule = rule
        self.author = author
        self.config = resolved_config
        if storage is None:
            from dendra.storage import InMemoryStorage

            storage = InMemoryStorage()
        self._storage = storage
        self._llm = llm
        self._ml_head = ml_head
        if telemetry is None:
            from dendra.telemetry import NullEmitter

            telemetry = NullEmitter()
        self._telemetry = telemetry
        # Track the last LLM/ML observations so record_outcome can attach them
        # to the outcome row without the caller passing them through.
        self._last_shadow: Optional[tuple[Any, float]] = None
        self._last_ml: Optional[tuple[Any, float]] = None
        self._last_rule_output: Optional[Any] = None
        self._circuit_tripped: bool = False
        # Labels are set by the decorator; bare construction leaves them empty.
        self.labels: list[str] = []

    # --- Public API --------------------------------------------------------

    def classify(self, input: Any) -> SwitchResult:
        """Classify ``input`` — routing depends on ``config.phase``."""
        result = self._classify_impl(input)
        try:
            self._telemetry.emit(
                "classify",
                {
                    "switch": self.name,
                    "phase": result.phase.value,
                    "source": result.source,
                    "confidence": result.confidence,
                },
            )
        except Exception:
            pass
        return result

    def _classify_impl(self, input: Any) -> SwitchResult:
        phase = self.phase()
        rule_output = self._rule(input)

        if phase is Phase.RULE:
            self._last_shadow = None
            self._last_rule_output = rule_output
            return SwitchResult(
                output=rule_output,
                source="rule",
                confidence=1.0,
                phase=phase,
            )

        if phase is Phase.LLM_SHADOW:
            if self._llm is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "llm classifier was provided"
                )
            # Shadow: run the LLM for observation but never let failure
            # propagate — the rule is the user-visible decision.
            try:
                pred = self._llm.classify(input, self.labels)
                self._last_shadow = (pred.label, float(pred.confidence))
            except Exception:
                self._last_shadow = None
            self._last_rule_output = rule_output
            return SwitchResult(
                output=rule_output,
                source="rule",
                confidence=1.0,
                phase=phase,
            )

        if phase is Phase.LLM_PRIMARY:
            if self._llm is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "llm classifier was provided"
                )
            self._last_rule_output = rule_output
            try:
                pred = self._llm.classify(input, self.labels)
            except Exception:
                self._last_shadow = None
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            self._last_shadow = (pred.label, float(pred.confidence))
            if float(pred.confidence) < self.config.confidence_threshold:
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            return SwitchResult(
                output=pred.label,
                source="llm",
                confidence=float(pred.confidence),
                phase=phase,
            )

        if phase is Phase.ML_SHADOW:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "ml_head was provided"
                )
            self._last_rule_output = rule_output

            # Primary decision path at Phase 3 mirrors LLM_PRIMARY when an
            # LLM is configured, else falls to rule. ML runs only in shadow.
            primary = self._phase_primary_decision(input, rule_output, phase)

            try:
                ml_pred = self._ml_head.predict(input, self.labels)
                self._last_ml = (ml_pred.label, float(ml_pred.confidence))
            except Exception:
                self._last_ml = None
            return primary

        if phase is Phase.ML_WITH_FALLBACK:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "ml_head was provided"
                )
            self._last_rule_output = rule_output
            try:
                ml_pred = self._ml_head.predict(input, self.labels)
            except Exception:
                self._last_ml = None
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            self._last_ml = (ml_pred.label, float(ml_pred.confidence))
            if float(ml_pred.confidence) < self.config.confidence_threshold:
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            return SwitchResult(
                output=ml_pred.label,
                source="ml",
                confidence=float(ml_pred.confidence),
                phase=phase,
            )

        if phase is Phase.ML_PRIMARY:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "ml_head was provided"
                )
            self._last_rule_output = rule_output
            if self._circuit_tripped:
                # Safety floor: rule takes over until the breaker is reset.
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            try:
                ml_pred = self._ml_head.predict(input, self.labels)
            except Exception:
                self._last_ml = None
                self._circuit_tripped = True
                return SwitchResult(
                    output=rule_output,
                    source="rule_fallback",
                    confidence=1.0,
                    phase=phase,
                )
            self._last_ml = (ml_pred.label, float(ml_pred.confidence))
            return SwitchResult(
                output=ml_pred.label,
                source="ml",
                confidence=float(ml_pred.confidence),
                phase=phase,
            )

        # Unreachable — exhaustive enum handled above.
        self._last_shadow = None
        self._last_rule_output = rule_output
        return SwitchResult(
            output=rule_output,
            source="rule",
            confidence=1.0,
            phase=phase,
        )

    def _phase_primary_decision(
        self, input: Any, rule_output: Any, phase: Phase
    ) -> SwitchResult:
        """Primary decision for phases where an ML head runs in shadow.

        Routes through the LLM when configured (LLM_PRIMARY semantics),
        otherwise falls back to the rule. Never touches the ML head —
        that's the shadow layer's job.
        """
        if self._llm is None:
            return SwitchResult(
                output=rule_output,
                source="rule",
                confidence=1.0,
                phase=phase,
            )
        try:
            pred = self._llm.classify(input, self.labels)
        except Exception:
            self._last_shadow = None
            return SwitchResult(
                output=rule_output,
                source="rule_fallback",
                confidence=1.0,
                phase=phase,
            )
        self._last_shadow = (pred.label, float(pred.confidence))
        if float(pred.confidence) < self.config.confidence_threshold:
            return SwitchResult(
                output=rule_output,
                source="rule_fallback",
                confidence=1.0,
                phase=phase,
            )
        return SwitchResult(
            output=pred.label,
            source="llm",
            confidence=float(pred.confidence),
            phase=phase,
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
        """Append a labeled outcome to the storage log.

        If the most recent ``classify()`` invocation produced a shadow
        prediction, it is attached to this record automatically.
        """
        if outcome not in {o.value for o in Outcome}:
            raise ValueError(
                f"outcome must be one of {[o.value for o in Outcome]}; "
                f"got {outcome!r}"
            )
        llm_output: Optional[Any] = None
        llm_confidence: Optional[float] = None
        if self._last_shadow is not None:
            llm_output, llm_confidence = self._last_shadow
            self._last_shadow = None

        ml_output: Optional[Any] = None
        ml_confidence: Optional[float] = None
        if self._last_ml is not None:
            ml_output, ml_confidence = self._last_ml
            self._last_ml = None

        # Always capture the rule output when classify() produced one, so
        # transition-curve analysis can compare all three (rule, llm, ml).
        rule_output = self._last_rule_output
        if rule_output is None and source == "rule":
            rule_output = output
        self._last_rule_output = None

        record = OutcomeRecord(
            timestamp=time.time(),
            input=input,
            output=output,
            outcome=outcome,
            source=source,
            confidence=confidence,
            rule_output=rule_output,
            llm_output=llm_output,
            llm_confidence=llm_confidence,
            ml_output=ml_output,
            ml_confidence=ml_confidence,
        )
        self._storage.append_outcome(self.name, record)
        try:
            self._telemetry.emit(
                "outcome",
                {
                    "switch": self.name,
                    "outcome": outcome,
                    "source": source,
                    "rule_output": rule_output,
                    "llm_output": llm_output,
                    "ml_output": ml_output,
                },
            )
        except Exception:
            pass

    def phase(self) -> Phase:
        """Current lifecycle phase (from :class:`SwitchConfig`)."""
        return self.config.phase

    def status(self) -> SwitchStatus:
        """Return a :class:`SwitchStatus` snapshot."""
        outcomes = self._storage.load_outcomes(self.name)
        total = len(outcomes)
        correct = sum(1 for r in outcomes if r.outcome == Outcome.CORRECT.value)
        incorrect = sum(1 for r in outcomes if r.outcome == Outcome.INCORRECT.value)

        shadow_rate: Optional[float] = None
        shadow_obs = [
            r for r in outcomes
            if r.llm_output is not None and r.rule_output is not None
        ]
        if shadow_obs:
            agreements = sum(1 for r in shadow_obs if r.llm_output == r.rule_output)
            shadow_rate = agreements / len(shadow_obs)

        ml_rate: Optional[float] = None
        ml_obs = [r for r in outcomes if r.ml_output is not None]
        if ml_obs:
            # Compare ML against whatever the user-visible decision was
            # (output), which is the most load-bearing definition of
            # "agreement" for Phase 3+ transition math.
            ml_agreements = sum(1 for r in ml_obs if r.ml_output == r.output)
            ml_rate = ml_agreements / len(ml_obs)

        version = (
            self._ml_head.model_version()
            if self._ml_head is not None
            else None
        )

        return SwitchStatus(
            name=self.name,
            phase=self.phase(),
            outcomes_total=total,
            outcomes_correct=correct,
            outcomes_incorrect=incorrect,
            model_version=version,
            shadow_agreement_rate=shadow_rate,
            ml_agreement_rate=ml_rate,
            circuit_breaker_tripped=self._circuit_tripped,
        )

    def reset_circuit_breaker(self) -> None:
        """Clear a tripped circuit breaker and allow ML decisions again.

        The breaker trips automatically on ML failures in Phase 5
        (ML_PRIMARY); calling this signals that the operator has
        investigated and is ready to resume ML-primary decisions.
        """
        self._circuit_tripped = False

    # --- Diagnostics -------------------------------------------------------

    @property
    def storage(self) -> "Storage":
        """Public accessor — useful for tests and advanced wiring."""
        return self._storage
