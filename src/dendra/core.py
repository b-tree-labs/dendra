# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Core types and the LearnedSwitch class.

v0.2.0 extends v0.1.0 with Phase 1 (MODEL_SHADOW). The six-phase
lifecycle follows the paper outline (§3.1):

    RULE → MODEL_SHADOW → MODEL_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK → ML_PRIMARY

In RULE the rule is the decision-maker. In MODEL_SHADOW the rule still
decides; an LLM runs alongside, its prediction captured on every
outcome for later analysis. Phases 2+ add their own routing rules.
"""

from __future__ import annotations

import contextlib
import inspect
import threading
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dendra.ml import MLHead
    from dendra.models import ModelClassifier
    from dendra.storage import Storage
    from dendra.telemetry import TelemetryEmitter

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    """Lifecycle phase — see paper §3.1 Table 1."""

    RULE = "RULE"
    MODEL_SHADOW = "MODEL_SHADOW"
    MODEL_PRIMARY = "MODEL_PRIMARY"
    ML_SHADOW = "ML_SHADOW"
    ML_WITH_FALLBACK = "ML_WITH_FALLBACK"
    ML_PRIMARY = "ML_PRIMARY"


class Verdict(str, Enum):
    """Label for an observed classification decision."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Labels + action dispatch
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Label:
    """A classification output, optionally paired with an action.

    A :class:`Label` is a **label-based conditional expression**:
    ``name`` is the label (the classifier's possible output); ``on``
    is the consequent — the callable invoked when the switch's
    chosen output equals ``name``. Conceptually::

        if classify(input) == label.name:
            label.on(input)

    The "label" framing is the standard ML term for a classifier's
    output category. The "conditional-expression" framing is
    Dendra's: every label carries an optional *consequent* that
    Dendra evaluates on a match, so a single ``classify()`` call
    produces both a decision and (when configured) the action that
    the decision implies.

    Failures inside ``on`` are captured, not propagated; the caller
    sees ``action_raised`` populated on the result and record.
    """

    name: str
    on: Callable[[Any], Any] | None = None


# Forms accepted for the decorator/switch ``labels=`` argument.
LabelLike = str | Label
LabelsArg = list[LabelLike] | dict[str, Callable[[Any], Any]]


def _normalize_labels(labels: LabelsArg | None) -> list[Label]:
    """Coerce list[str] | list[Label] | dict[str, Callable] → list[Label]."""
    if labels is None:
        return []
    if isinstance(labels, dict):
        return [Label(name=k, on=v) for k, v in labels.items()]
    out: list[Label] = []
    for item in labels:
        if isinstance(item, Label):
            out.append(item)
        elif isinstance(item, str):
            out.append(Label(name=item))
        else:
            raise TypeError(
                f"labels entries must be str or Label; got {type(item).__name__}"
            )
    return out


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """The return value of ``classify`` / ``dispatch``.

    ``label`` is the switch's chosen classification output. Named
    ``label`` (not ``output``) to match the rest of the API's
    vocabulary — the same word appears in ``labels=``, :class:`Label`,
    and the "label-based conditional expression" framing.

    Includes fluent verdict shortcuts (``mark_correct``,
    ``mark_incorrect``, ``mark_unknown``) that append a verdict
    record to the originating switch's storage. When the result
    was produced by a detached construction (tests, manual instantiation),
    the shortcuts raise :class:`RuntimeError` instead of silently
    no-op'ing.

    **Shadow observations travel on the result**, not on the
    switch. Each :class:`ClassificationResult` carries the
    per-source predictions captured during its own classify call —
    so calling ``.mark_correct()`` minutes later (or from a
    different thread, or after many intervening calls) still
    attaches the CORRECT shadow data to the verdict record. This
    is the fix for the shadow-stash cross-contamination race
    (v1-readiness.md §2 finding #3).
    """

    label: Any
    source: str  # "rule" | "model" | "ml" | "rule_fallback"
    confidence: float
    phase: Phase
    # Populated when the chosen label has an ``on=`` callable.
    action_result: Any = None
    action_raised: str | None = None
    action_elapsed_ms: float | None = None
    # Private back-references so ``.mark_*()`` methods can record a
    # verdict without the caller re-threading the switch and input.
    # Per-call shadow observations travel on the result so
    # concurrent classifies can't cross-contaminate each other's
    # verdict records. None of these private fields participate in
    # equality or repr; none are serialized.
    _switch: Any = field(default=None, repr=False, compare=False)
    _input: Any = field(default=None, repr=False, compare=False)
    _rule_output: Any = field(default=None, repr=False, compare=False)
    _model_output: Any = field(default=None, repr=False, compare=False)
    _model_confidence: float | None = field(default=None, repr=False, compare=False)
    _ml_output: Any = field(default=None, repr=False, compare=False)
    _ml_confidence: float | None = field(default=None, repr=False, compare=False)

    def mark_correct(self) -> None:
        """Record that this classification matched ground truth."""
        self._mark(Verdict.CORRECT)

    def mark_incorrect(self) -> None:
        """Record that this classification did not match ground truth."""
        self._mark(Verdict.INCORRECT)

    def mark_unknown(self) -> None:
        """Record that ground truth is unknown / still pending."""
        self._mark(Verdict.UNKNOWN)

    def _mark(self, verdict: Verdict) -> None:
        if self._switch is None:
            raise RuntimeError(
                "ClassificationResult.mark_*() requires the result to "
                "come from a live switch's classify() or dispatch(); "
                "this result has no switch back-reference."
            )
        self._switch.record_verdict(
            input=self._input,
            label=self.label,
            outcome=verdict.value,
            source=self.source,
            confidence=self.confidence,
            _result_ctx=self,
        )


@dataclass(frozen=True)
class ClassificationRecord:
    """One ``(input, label, outcome)`` row in the outcome log.

    ``label`` is the decision that was actually returned by the
    switch at classify time. Per-source raw predictions live in
    ``rule_output`` / ``model_output`` / ``ml_output`` (the word
    "output" is reserved for those raw per-source predictions;
    the final decision is the ``label``).
    """

    timestamp: float
    input: Any
    label: Any
    outcome: str  # Verdict value
    source: str  # which path produced `label` at classify time
    confidence: float
    # Phase 1+ shadow observations (optional; omitted at Phase 0).
    rule_output: Any | None = None
    model_output: Any | None = None
    model_confidence: float | None = None
    # Phase 3+ ML shadow observations.
    ml_output: Any | None = None
    ml_confidence: float | None = None
    # Action-dispatch observations (populated when the chosen label has
    # ``on=`` set and dispatch() fired it).
    action_result: Any | None = None
    action_raised: str | None = None
    action_elapsed_ms: float | None = None


@dataclass
class SwitchStatus:
    """Observable state of a switch at a point in time."""

    name: str
    phase: Phase
    outcomes_total: int
    outcomes_correct: int
    outcomes_incorrect: int
    model_version: str | None = None
    # Phase 1 observability — fraction of outcomes where the LLM agreed
    # with the rule. ``None`` when no shadow observations are recorded.
    shadow_agreement_rate: float | None = None
    # Phase 3 observability — fraction where ML shadow matched the primary.
    ml_agreement_rate: float | None = None
    # Phase 5 circuit-breaker state.
    circuit_breaker_tripped: bool = False


# Phase ordering for <= / >= comparisons. RULE = 0, ML_PRIMARY = 5.
_PHASE_ORDER: dict[Phase, int] = {
    Phase.RULE: 0,
    Phase.MODEL_SHADOW: 1,
    Phase.MODEL_PRIMARY: 2,
    Phase.ML_SHADOW: 3,
    Phase.ML_WITH_FALLBACK: 4,
    Phase.ML_PRIMARY: 5,
}


@dataclass
class SwitchConfig:
    """Runtime configuration for a switch.

    Two phase-related axes are tracked separately:

    - ``starting_phase`` — the phase the switch begins in. Default
      :data:`Phase.RULE` (safety-first). Set to a higher phase for
      LLM-as-teacher bootstrap (``MODEL_PRIMARY``), porting an
      existing LLM classifier, or hybrid steady-state designs.
    - ``phase_limit`` — the ceiling. ``advance()`` refuses to cross
      it. Default :data:`Phase.ML_PRIMARY` (no cap — full autonomy
      permitted when evidence earns it). Set lower to constrain
      how far the switch is allowed to graduate.

    ``safety_critical=True`` is a convenience flag that implies
    ``phase_limit = ML_WITH_FALLBACK`` and refuses construction in
    ``ML_PRIMARY``. It's kept for backward-compat and readability;
    new code can use ``phase_limit=Phase.ML_WITH_FALLBACK`` directly
    for the same effect (or any other ceiling).

    The legacy ``phase=...`` keyword is accepted as an alias for
    ``starting_phase=...`` and emits a ``DeprecationWarning``. It
    will be removed in a future major release.
    """

    confidence_threshold: float = 0.85
    starting_phase: Phase = Phase.RULE
    phase_limit: Phase = Phase.ML_PRIMARY
    safety_critical: bool = False
    # Gate used by ``LearnedSwitch.advance()`` to decide whether the
    # switch has earned its next phase. Defaults to None → resolved
    # to the default McNemarGate at switch construction time.
    gate: Any = None
    # Automatic verdict-free logging: every ``classify``/``dispatch``
    # call auto-appends a ClassificationRecord with
    # ``outcome=Verdict.UNKNOWN`` and all captured shadow observations.
    # Later ``record_verdict`` calls append verdict-bearing rows that
    # the gate prefers for paired-correctness math. Set
    # ``auto_record=False`` to suppress the UNKNOWN rows.
    auto_record: bool = True
    # Automatic graduation: every ``auto_advance_interval`` calls to
    # ``record_verdict``, the switch asks the gate whether it's
    # earned the next phase. Set ``auto_advance=False`` for
    # operator-only workflows.
    auto_advance: bool = True
    auto_advance_interval: int = 100
    # Optional hook fired after every successful ``record_verdict``.
    # Receives the persisted :class:`ClassificationRecord`. Useful
    # for mirroring verdicts to an external audit store, triggering
    # metrics, sending webhooks.
    on_verdict: Callable[[Any], None] | None = None
    # Deprecated alias for starting_phase. None means "not supplied"
    # and the dataclass falls back to starting_phase's default.
    phase: Phase | None = None

    def __post_init__(self) -> None:
        if self.phase is not None:
            import warnings

            warnings.warn(
                "SwitchConfig(phase=...) is deprecated; use "
                "starting_phase=... instead. The phase parameter will "
                "be removed in a future major release.",
                DeprecationWarning,
                stacklevel=3,
            )
            # Alias wins over the default starting_phase; explicit
            # starting_phase (non-default) takes precedence if both set.
            if self.starting_phase is Phase.RULE:
                self.starting_phase = self.phase

        # safety_critical refuses ML_PRIMARY as either starting_phase
        # or as a permitted ceiling — gives the paper-§7.1 guarantee
        # its own explicit error message rather than the generic
        # starting_phase/phase_limit mismatch.
        if self.safety_critical and self.starting_phase is Phase.ML_PRIMARY:
            raise ValueError(
                "safety_critical switches cannot start in ML_PRIMARY; "
                "cap at ML_WITH_FALLBACK (paper §7.1)."
            )

        # safety_critical caps the ceiling at ML_WITH_FALLBACK.
        if (
            self.safety_critical
            and _PHASE_ORDER[self.phase_limit] > _PHASE_ORDER[Phase.ML_WITH_FALLBACK]
        ):
            self.phase_limit = Phase.ML_WITH_FALLBACK

        # starting_phase cannot exceed phase_limit.
        if _PHASE_ORDER[self.starting_phase] > _PHASE_ORDER[self.phase_limit]:
            raise ValueError(
                f"starting_phase={self.starting_phase.name} exceeds "
                f"phase_limit={self.phase_limit.name}. The switch cannot "
                f"start above its own ceiling."
            )


# ---------------------------------------------------------------------------
# LearnedSwitch
# ---------------------------------------------------------------------------


RuleFunc = Callable[[Any], Any]


class _VerdictHolder:
    """Yielded by :meth:`LearnedSwitch.verdict_for` — stores the in-flight
    classification and exposes methods that record the verdict.
    """

    def __init__(self, *, switch: Any, input: Any, result: ClassificationResult) -> None:
        self._switch = switch
        self._input = input
        self.result = result
        self._recorded = False

    def correct(self) -> None:
        """Record that the classification matched ground truth."""
        self._mark(Verdict.CORRECT)

    def incorrect(self) -> None:
        """Record that the classification did not match ground truth."""
        self._mark(Verdict.INCORRECT)

    def unknown(self) -> None:
        """Record that ground truth is unknown / pending."""
        self._mark(Verdict.UNKNOWN)

    def _mark(self, verdict: Verdict) -> None:
        if self._recorded:
            return
        self._recorded = True
        self._switch.record_verdict(
            input=self._input,
            label=self.result.label,
            outcome=verdict.value,
            source=self.result.source,
            confidence=self.result.confidence,
        )


def _derive_author(switch_name: str, rule: RuleFunc) -> str:
    """Derive a stable author ID from the caller's code location.

    Strategy: prefer the rule function's module (that's where the
    switch semantically lives), falling back to a walk up the call
    stack until we leave the ``dendra`` package. The returned
    string has the shape ``"@<module>:<switch_name>"`` — stable
    per-deployment, unique per-switch-per-module, and unspoofable
    without editing the source that defines the switch.

    Users who want a different provenance scheme pass ``author=...``
    explicitly; the explicit value always wins.
    """
    module = getattr(rule, "__module__", None)
    if module and module != "__main__" and not module.startswith("dendra."):
        return f"@{module}:{switch_name}"

    # Rule has no useful __module__ (lambda, __main__, or dendra-internal).
    # Walk the stack to find the first caller outside of dendra.
    frame = inspect.currentframe()
    try:
        while frame is not None:
            caller_module = frame.f_globals.get("__name__", "")
            if caller_module and not caller_module.startswith("dendra."):
                return f"@{caller_module}:{switch_name}"
            frame = frame.f_back
    finally:
        del frame  # Avoid cyclic references.

    # Last-resort fallback — should be unreachable in practice.
    return f"@unknown:{switch_name}"


# Process-level registry of active switches keyed by (id(storage), name).
# Used to detect collisions when two LearnedSwitches would share a storage
# backend AND a name — a silent shared outcome log is almost always a bug.
# Entries auto-expire when a switch is garbage-collected.
_SWITCH_REGISTRY: weakref.WeakValueDictionary[tuple[int, str], LearnedSwitch] = (
    weakref.WeakValueDictionary()
)
_SWITCH_REGISTRY_LOCK = threading.Lock()


def _derive_name_from_rule(rule: RuleFunc) -> str:
    """Derive a switch name from the rule function's ``__name__``.

    Raises :class:`ValueError` for lambdas and other rules with no
    stable name — those cannot be auto-named safely because the
    storage key must survive process restarts.
    """
    rule_name = getattr(rule, "__name__", None)
    if not rule_name or rule_name == "<lambda>":
        raise ValueError(
            "name is required when rule has no stable __name__ "
            "(e.g., lambda, partial, or wrapped callable). Pass "
            "name=... explicitly."
        )
    return rule_name


class LearnedSwitch:
    """Graduated-autonomy classification primitive.

    Args:
        rule: Pure function ``input → output`` that produces the
            safety-floor decision. Never modified by the library.
        name: Stable identifier used in logs, audit records, and
            storage keys. Optional — when omitted, auto-derived from
            ``rule.__name__``. Rules with no stable name (lambdas,
            wrapped callables) must pass ``name`` explicitly. If two
            switches would share the same storage backend AND the
            same name, construction raises :class:`ValueError` —
            silent shared outcome logs are almost always a bug.
        author: Principal associated with the switch (opaque
            provenance string; logged, surfaced in audit output,
            used by the regulated-tier audit chain). Optional —
            when omitted, auto-derived from the rule's module plus
            the switch name as ``"@<module>:<name>"``. Pass an
            explicit value to use a custom provenance scheme (team
            handle, service account, compliance ID, etc.); the
            explicit value always wins. Cannot be an empty string.
        labels: The switch's label-based conditional expressions —
            each label names a possible classifier output; pairing a
            label with an ``on=`` action turns the label into a
            dispatch clause. Accepted forms: ``list[str]``,
            ``list[Label]``, or ``dict[str, Callable]``.
        starting_phase: Lifecycle phase the switch begins in.
            Default :data:`Phase.RULE`. Convenience shortcut for
            ``config=SwitchConfig(starting_phase=...)``.
        phase_limit: Upper bound on phase advancement. Default
            :data:`Phase.ML_PRIMARY` (no cap). Convenience shortcut
            for ``config=SwitchConfig(phase_limit=...)``.
        safety_critical: Shorthand for a switch that must never drop
            its rule floor — caps ``phase_limit`` at
            ``ML_WITH_FALLBACK`` and refuses construction in
            ``ML_PRIMARY``. See example 03.
        confidence_threshold: Minimum model/ML confidence for the
            switch to adopt their decision over the rule floor.
            Default 0.85.
        config: Optional :class:`SwitchConfig`. Power-user escape
            hatch when you need full control. **Mutually exclusive**
            with ``starting_phase`` / ``phase_limit`` /
            ``safety_critical`` / ``confidence_threshold`` — pass
            one shape or the other, not both.
        storage: Optional :class:`Storage` backend. When omitted, a
            :class:`BoundedInMemoryStorage` is installed so a bare
            switch cannot leak memory from unbounded outcome logging.
            Pass ``persist=True`` to derive a :class:`FileStorage`
            under ``./runtime/dendra/<name>/`` instead (wrapped in a
            :class:`ResilientStorage` so a transient disk failure
            does not take down classification).
        persist: When ``True`` and ``storage`` is not explicitly
            supplied, use a :class:`FileStorage` rooted at
            ``./runtime/dendra/`` wrapped in :class:`ResilientStorage`
            — transient I/O failures spill to an in-memory buffer
            that drains back when the primary recovers. Mutually
            exclusive with an explicit ``storage=`` argument. For
            hard-fail-on-IO-error semantics, pass
            ``storage=FileStorage(...)`` directly.
        model: Optional :class:`ModelClassifier` used in MODEL_SHADOW and
            MODEL_PRIMARY phases.
    """

    def __init__(
        self,
        *,
        rule: RuleFunc,
        name: str | None = None,
        author: str | None = None,
        labels: LabelsArg | None = None,
        # Hoisted SwitchConfig fields — the common case. These build a
        # SwitchConfig internally. Passing ``config=`` directly is the
        # power-user escape hatch; mixing the two forms raises.
        starting_phase: Phase | None = None,
        phase_limit: Phase | None = None,
        safety_critical: bool | None = None,
        confidence_threshold: float | None = None,
        gate: Any | None = None,
        auto_record: bool | None = None,
        auto_advance: bool | None = None,
        auto_advance_interval: int | None = None,
        on_verdict: Callable[[Any], None] | None = None,
        config: SwitchConfig | None = None,
        storage: Storage | None = None,
        persist: bool = False,
        model: ModelClassifier | None = None,
        ml_head: MLHead | None = None,
        telemetry: TelemetryEmitter | None = None,
    ) -> None:
        if rule is None or not callable(rule):
            raise ValueError("rule must be a callable")

        # ---- Name: autogen from rule.__name__ when absent -----------------
        name_was_autoderived = name is None
        if name is None:
            name = _derive_name_from_rule(rule)
        elif not name:
            raise ValueError("name cannot be empty; omit the argument for autogen")

        # ---- Author: autogen provenance ID when absent --------------------
        if author is None:
            author = _derive_author(name, rule)
        elif not author:
            raise ValueError(
                "author cannot be empty; omit the argument for autogen, "
                "or pass a non-empty provenance string."
            )

        # ---- Config: either the hoisted kwargs or an explicit config ------
        hoisted_config_kwargs = {
            "starting_phase": starting_phase,
            "phase_limit": phase_limit,
            "safety_critical": safety_critical,
            "confidence_threshold": confidence_threshold,
            "gate": gate,
            "auto_record": auto_record,
            "auto_advance": auto_advance,
            "auto_advance_interval": auto_advance_interval,
            "on_verdict": on_verdict,
        }
        supplied_hoisted = {k: v for k, v in hoisted_config_kwargs.items() if v is not None}
        if config is not None and supplied_hoisted:
            raise ValueError(
                "config=... is mutually exclusive with the hoisted shortcuts "
                f"({', '.join(sorted(supplied_hoisted))}). Pass one shape or "
                "the other, not both."
            )
        if config is None:
            # Build a SwitchConfig from the hoisted kwargs (or defaults).
            config = SwitchConfig(**supplied_hoisted) if supplied_hoisted else SwitchConfig()
        resolved_config = config

        # Resolve the gate lazily — keeps core's import graph free of
        # the viz/math dependencies that McNemarGate needs.
        if resolved_config.gate is None:
            from dendra.gates import McNemarGate

            resolved_config.gate = McNemarGate()

        # safety_critical refuses ML_PRIMARY even as a ceiling; this
        # is stricter than SwitchConfig's post_init (which only caps
        # the ceiling). Keeps the paper §7.1 architectural guarantee.
        if resolved_config.safety_critical and resolved_config.starting_phase is Phase.ML_PRIMARY:
            raise ValueError(
                "safety_critical switches cannot start in ML_PRIMARY; "
                "cap at ML_WITH_FALLBACK (paper §7.1)."
            )

        self.name = name
        self._rule = rule
        self.author = author
        self.config = resolved_config
        if storage is not None and persist:
            raise ValueError(
                "persist=True is incompatible with an explicit storage= "
                "argument. Pass one or the other."
            )
        if storage is None:
            if persist:
                # persist=True wraps a FileStorage in ResilientStorage so a
                # transient disk failure (full disk, permission glitch,
                # rotated directory) does NOT take down classification.
                # Fallback lives in an in-memory buffer that drains back
                # to FileStorage when primary recovers. Users who want
                # hard-fail-on-IO-error semantics should pass an explicit
                # ``storage=FileStorage(...)`` and skip the wrapper.
                from dendra.storage import FileStorage, ResilientStorage

                storage = ResilientStorage(FileStorage("runtime/dendra"))
            else:
                from dendra.storage import BoundedInMemoryStorage

                storage = BoundedInMemoryStorage()
        self._storage = storage

        # ---- Collision detection ------------------------------------------
        # If a LIVE switch already holds this (storage, name) pair, the new
        # one would silently share an outcome log. Fail loud. Auto-named
        # switches get a more informative error since the user didn't
        # pick the name and may not realize it collided.
        registry_key = (id(self._storage), name)
        with _SWITCH_REGISTRY_LOCK:
            existing = _SWITCH_REGISTRY.get(registry_key)
            if existing is not None and existing is not self:
                hint = (
                    f"A LearnedSwitch named {name!r} is already using this "
                    f"storage backend."
                )
                if name_was_autoderived:
                    hint += (
                        " The name was auto-derived from rule.__name__; "
                        "pass an explicit name=... to the second switch "
                        "to disambiguate."
                    )
                else:
                    hint += " Use a different name= or a different storage."
                raise ValueError(hint)
            _SWITCH_REGISTRY[registry_key] = self

        self._model = model
        self._ml_head = ml_head
        if telemetry is None:
            from dendra.telemetry import NullEmitter

            telemetry = NullEmitter()
        self._telemetry = telemetry
        # Single RLock serializing all mutations to per-switch state
        # (breaker, auto-advance counter, config.starting_phase,
        # rotation-style bookkeeping). Classify calls take it while
        # checking the breaker and updating its state; record_verdict
        # takes it around the auto-advance counter; advance() takes it
        # across the read-log / evaluate-gate / mutate-phase sequence.
        # RLock (not Lock) because advance() invoked from within a
        # locked record_verdict re-enters.
        self._lock = threading.RLock()
        self._circuit_tripped: bool = False
        # Counter driving auto-advance — incremented by record_verdict
        # under the lock, reset when the gate is asked (whether it
        # said yes or no).
        self._records_since_advance_check: int = 0
        # Canonical labels list (Label objects). Assignment via the setter
        # normalizes strings / dicts.
        self._labels_raw: list[Label] = _normalize_labels(labels)
        # Rehydrate persisted breaker state (paper §7.1 promise must
        # survive a process restart when durable storage is configured).
        self._persist: bool = bool(persist)
        if self._persist:
            self._load_breaker_state()

    # --- Labels ------------------------------------------------------------

    @property
    def labels(self) -> list[Label]:
        """Canonical label list (as :class:`Label` objects)."""
        return list(self._labels_raw)

    @labels.setter
    def labels(self, value: LabelsArg | None) -> None:
        self._labels_raw = _normalize_labels(value)

    def _label_names(self) -> list[str]:
        return [label.name for label in self._labels_raw]

    def _find_label(self, name: Any) -> Label | None:
        if not isinstance(name, str):
            return None
        for label in self._labels_raw:
            if label.name == name:
                return label
        return None

    # --- Public API --------------------------------------------------------

    def classify(self, input: Any) -> ClassificationResult:
        """Classify ``input`` — **pure**. Returns the decision; fires no actions.

        Routing depends on ``config.starting_phase``. Any ``Label.on=``
        callables registered on matching labels are **not** invoked
        here — that's :meth:`dispatch`'s job. ``classify()`` is safe to
        call from tests, benchmarks, dashboards, and other read-only
        observers that need the decision without the side effects.

        When ``config.auto_record`` is ``True`` (the default), this
        also appends a ``ClassificationRecord`` with
        ``outcome=Verdict.UNKNOWN`` to the outcome log, preserving the
        shadow observations captured during this call. Pass
        ``auto_record=False`` to suppress.
        """
        result = self._classify_impl(input)
        result._switch = self
        result._input = input
        if self.config.auto_record:
            self._auto_log(input, result)
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

    def dispatch(self, input: Any) -> ClassificationResult:
        """Classify ``input`` and fire the matched label's ``on=`` action.

        The production verb: decide *and* act. Returns a
        :class:`ClassificationResult` with ``action_result`` /
        ``action_raised`` / ``action_elapsed_ms`` populated when the
        chosen label has an ``on=`` callable. Exceptions inside the
        action are captured (stringified into ``action_raised``), not
        propagated — the classification decision itself is never lost
        to a handler bug.

        When no label matches or the matched label has no ``on=``
        callable, behaves exactly like :meth:`classify` (but still
        emits a ``dispatch`` telemetry event so consumers can
        distinguish the two call sites). When ``config.auto_record``
        is ``True``, appends an UNKNOWN outcome record including the
        dispatched action's result.
        """
        result = self._classify_impl(input)
        result = self._maybe_dispatch(input, result)
        result._switch = self
        result._input = input
        if self.config.auto_record:
            self._auto_log(input, result)
        try:
            self._telemetry.emit(
                "dispatch",
                {
                    "switch": self.name,
                    "phase": result.phase.value,
                    "source": result.source,
                    "confidence": result.confidence,
                    "action_raised": result.action_raised,
                },
            )
        except Exception:
            pass
        return result

    def _auto_log(self, input: Any, result: ClassificationResult) -> None:
        """Append an UNKNOWN-outcome record from the just-completed call.

        Pulls shadow observations from the result itself (populated
        by ``_classify_impl``), not from any per-switch instance
        stash — which is what keeps concurrent classifies from
        cross-contaminating each other's records.
        """
        record = ClassificationRecord(
            timestamp=time.time(),
            input=input,
            label=result.label,
            outcome=Verdict.UNKNOWN.value,
            source=result.source,
            confidence=result.confidence,
            rule_output=result._rule_output,
            model_output=result._model_output,
            model_confidence=result._model_confidence,
            ml_output=result._ml_output,
            ml_confidence=result._ml_confidence,
            action_result=result.action_result,
            action_raised=result.action_raised,
            action_elapsed_ms=result.action_elapsed_ms,
        )
        try:
            self._storage.append_record(self.name, record)
        except Exception:
            # Storage failure must not break classification.
            pass

    @contextlib.contextmanager
    def verdict_for(self, input: Any):
        """Context manager yielding a verdict holder for ``input``.

        Classifies ``input`` on entry and yields an object with
        ``.result`` (the :class:`ClassificationResult`) plus
        ``.correct()`` / ``.incorrect()`` / ``.unknown()`` methods.
        If the block exits without a verdict being marked, defaults
        to UNKNOWN so an incident log always has a trailing state.

        Usage::

            with rule.verdict_for(ticket) as v:
                try:
                    do_downstream(v.result.label)
                    v.correct()
                except HandlerError:
                    v.incorrect()
        """
        result = self.classify(input)
        holder = _VerdictHolder(switch=self, input=input, result=result)
        try:
            yield holder
        finally:
            if not holder._recorded:
                holder.unknown()

    def _maybe_dispatch(self, input: Any, result: ClassificationResult) -> ClassificationResult:
        """Fire the chosen label's ``on=`` action, if any.

        Captures failures rather than propagating; the caller sees
        ``action_raised`` populated. Timing is recorded on success and
        failure. The shadow observations threaded on ``result`` are
        preserved through to the new result so ``_auto_log`` still
        sees them.
        """
        label = self._find_label(result.label)
        if label is None or label.on is None:
            return result

        start = time.perf_counter()
        action_result: Any = None
        action_raised: str | None = None
        try:
            action_result = label.on(input)
        except Exception as e:
            action_raised = f"{type(e).__name__}: {e}"
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        new_result = ClassificationResult(
            label=result.label,
            source=result.source,
            confidence=result.confidence,
            phase=result.phase,
            action_result=action_result,
            action_raised=action_raised,
            action_elapsed_ms=elapsed_ms,
        )
        # Re-thread shadow observations through the dispatch-returned
        # result so record_verdict / auto_log still sees them.
        new_result._rule_output = result._rule_output
        new_result._model_output = result._model_output
        new_result._model_confidence = result._model_confidence
        new_result._ml_output = result._ml_output
        new_result._ml_confidence = result._ml_confidence
        return new_result

    def _classify_impl(self, input: Any) -> ClassificationResult:
        phase = self.phase()
        # Runtime re-check of the paper §7.1 architectural guarantee.
        # Construction-time checks catch the common case, but
        # ``config`` is a mutable dataclass — users (or bugs) can
        # raise the phase after construction. The rule-floor promise
        # must survive that. Refuse to serve ML_PRIMARY when
        # safety_critical is set, regardless of how the phase got here.
        if self.config.safety_critical and phase is Phase.ML_PRIMARY:
            raise RuntimeError(
                f"switch {self.name!r} is safety_critical=True but phase "
                f"is ML_PRIMARY. The rule floor cannot be removed "
                f"architecturally (paper §7.1); this state should be "
                f"unreachable. Check for direct mutation of "
                f"config.starting_phase."
            )
        rule_output = self._rule(input)

        def _result(
            label: Any,
            source: str,
            confidence: float,
            *,
            model_output: Any = None,
            model_confidence: float | None = None,
            ml_output: Any = None,
            ml_confidence: float | None = None,
        ) -> ClassificationResult:
            r = ClassificationResult(
                label=label,
                source=source,
                confidence=confidence,
                phase=phase,
            )
            r._rule_output = rule_output
            r._model_output = model_output
            r._model_confidence = model_confidence
            r._ml_output = ml_output
            r._ml_confidence = ml_confidence
            return r

        if phase is Phase.RULE:
            return _result(rule_output, "rule", 1.0)

        if phase is Phase.MODEL_SHADOW:
            if self._model is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "model classifier was provided"
                )
            # Shadow: run the LLM for observation but never let failure
            # propagate — the rule is the user-visible decision.
            model_output: Any = None
            model_confidence: float | None = None
            try:
                pred = self._model.classify(input, self._label_names())
                model_output = pred.label
                model_confidence = float(pred.confidence)
            except Exception:
                pass
            return _result(
                rule_output, "rule", 1.0,
                model_output=model_output, model_confidence=model_confidence,
            )

        if phase is Phase.MODEL_PRIMARY:
            if self._model is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no "
                    "model classifier was provided"
                )
            try:
                pred = self._model.classify(input, self._label_names())
            except Exception:
                return _result(rule_output, "rule_fallback", 1.0)
            if float(pred.confidence) < self.config.confidence_threshold:
                return _result(
                    rule_output, "rule_fallback", 1.0,
                    model_output=pred.label,
                    model_confidence=float(pred.confidence),
                )
            return _result(
                pred.label, "model", float(pred.confidence),
                model_output=pred.label,
                model_confidence=float(pred.confidence),
            )

        if phase is Phase.ML_SHADOW:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no ml_head was provided"
                )
            # Primary decision path at Phase 3 mirrors MODEL_PRIMARY when an
            # LLM is configured, else falls to rule. ML runs only in shadow.
            primary = self._phase_primary_decision(input, rule_output, phase)
            ml_output: Any = None
            ml_confidence: float | None = None
            try:
                ml_pred = self._ml_head.predict(input, self._label_names())
                ml_output = ml_pred.label
                ml_confidence = float(ml_pred.confidence)
            except Exception:
                pass
            primary._ml_output = ml_output
            primary._ml_confidence = ml_confidence
            return primary

        if phase is Phase.ML_WITH_FALLBACK:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no ml_head was provided"
                )
            try:
                ml_pred = self._ml_head.predict(input, self._label_names())
            except Exception:
                return _result(rule_output, "rule_fallback", 1.0)
            if float(ml_pred.confidence) < self.config.confidence_threshold:
                return _result(
                    rule_output, "rule_fallback", 1.0,
                    ml_output=ml_pred.label,
                    ml_confidence=float(ml_pred.confidence),
                )
            return _result(
                ml_pred.label, "ml", float(ml_pred.confidence),
                ml_output=ml_pred.label,
                ml_confidence=float(ml_pred.confidence),
            )

        if phase is Phase.ML_PRIMARY:
            if self._ml_head is None:
                raise ValueError(
                    f"switch {self.name!r} is in phase {phase.value} but no ml_head was provided"
                )
            # Lock the breaker check-and-call sequence so the first
            # failure trips the circuit and subsequent callers
            # short-circuit to the rule rather than stampeding the
            # broken ML head (v1-readiness.md §2 finding #16, F2).
            with self._lock:
                if self._circuit_tripped:
                    return _result(rule_output, "rule_fallback", 1.0)
                try:
                    ml_pred = self._ml_head.predict(input, self._label_names())
                except Exception:
                    self._circuit_tripped = True
                    self._save_breaker_state()
                    return _result(rule_output, "rule_fallback", 1.0)
                return _result(
                    ml_pred.label, "ml", float(ml_pred.confidence),
                    ml_output=ml_pred.label,
                    ml_confidence=float(ml_pred.confidence),
                )

        # Unreachable — exhaustive enum handled above.
        return _result(rule_output, "rule", 1.0)

    def _phase_primary_decision(
        self, input: Any, rule_output: Any, phase: Phase
    ) -> ClassificationResult:
        """Primary decision for phases where an ML head runs in shadow.

        Routes through the LLM when configured (MODEL_PRIMARY semantics),
        otherwise falls back to the rule. Never touches the ML head —
        that's the shadow layer's job.
        """
        def _r(
            label: Any, source: str, confidence: float,
            *,
            model_output: Any = None,
            model_confidence: float | None = None,
        ) -> ClassificationResult:
            r = ClassificationResult(
                label=label, source=source, confidence=confidence, phase=phase,
            )
            r._rule_output = rule_output
            r._model_output = model_output
            r._model_confidence = model_confidence
            return r

        if self._model is None:
            return _r(rule_output, "rule", 1.0)
        try:
            pred = self._model.classify(input, self._label_names())
        except Exception:
            return _r(rule_output, "rule_fallback", 1.0)
        if float(pred.confidence) < self.config.confidence_threshold:
            return _r(
                rule_output, "rule_fallback", 1.0,
                model_output=pred.label,
                model_confidence=float(pred.confidence),
            )
        return _r(
            pred.label, "model", float(pred.confidence),
            model_output=pred.label,
            model_confidence=float(pred.confidence),
        )

    def record_verdict(
        self,
        *,
        input: Any,
        label: Any,
        outcome: str,
        source: str = "rule",
        confidence: float = 1.0,
        _result_ctx: ClassificationResult | None = None,
    ) -> None:
        """Append a labeled outcome to the storage log.

        ``label`` is the decision the switch returned (or that the
        caller assigned). ``outcome`` is the :class:`Verdict` — did
        that decision match ground truth?

        When this is called via a :class:`ClassificationResult`'s
        ``mark_*()`` / ``verdict_for`` path, the result's captured
        shadow observations (rule output, model prediction, ML
        prediction) are threaded through to the persisted record
        automatically. When called directly on the switch (e.g.
        from a webhook with ``record_verdict(input=..., label=...,
        outcome=...)``), the switch has no reliable way to pair the
        verdict with its originating classify — so no shadow
        observations are attached. Use the result-aware path when
        per-call paired data is load-bearing.
        """
        if outcome not in {o.value for o in Verdict}:
            raise ValueError(
                f"outcome must be one of {[o.value for o in Verdict]}; got {outcome!r}"
            )
        # Pull shadow observations from the paired result when
        # available; otherwise fall back to a minimal record with
        # just the user-supplied fields. No instance-level stash —
        # that was the source of the cross-contamination bug.
        if _result_ctx is not None:
            rule_output = _result_ctx._rule_output
            if rule_output is None and source == "rule":
                rule_output = label
            model_output = _result_ctx._model_output
            model_confidence = _result_ctx._model_confidence
            ml_output = _result_ctx._ml_output
            ml_confidence = _result_ctx._ml_confidence
            action_result = _result_ctx.action_result
            action_raised = _result_ctx.action_raised
            action_elapsed_ms = _result_ctx.action_elapsed_ms
        else:
            rule_output = label if source == "rule" else None
            model_output = None
            model_confidence = None
            ml_output = None
            ml_confidence = None
            action_result = None
            action_raised = None
            action_elapsed_ms = None

        record = ClassificationRecord(
            timestamp=time.time(),
            input=input,
            label=label,
            outcome=outcome,
            source=source,
            confidence=confidence,
            rule_output=rule_output,
            model_output=model_output,
            model_confidence=model_confidence,
            ml_output=ml_output,
            ml_confidence=ml_confidence,
            action_result=action_result,
            action_raised=action_raised,
            action_elapsed_ms=action_elapsed_ms,
        )
        self._storage.append_record(self.name, record)
        if self.config.on_verdict is not None:
            # User-supplied hook for mirroring verdicts (webhooks,
            # external audit stores, metrics). Failures never break
            # record_verdict.
            try:
                self.config.on_verdict(record)
            except Exception:
                pass
        try:
            self._telemetry.emit(
                "outcome",
                {
                    "switch": self.name,
                    "outcome": outcome,
                    "source": source,
                    "rule_output": rule_output,
                    "model_output": model_output,
                    "ml_output": ml_output,
                },
            )
        except Exception:
            pass

        # Auto-advance: every ``auto_advance_interval`` recorded
        # predictions, ask the gate whether we've earned the next
        # phase. The counter increment is locked so concurrent
        # record_verdicts can't race on read-modify-write (v1
        # finding #16). Gate refusals and exceptions never break
        # record_verdict.
        if self.config.auto_advance:
            should_advance = False
            with self._lock:
                self._records_since_advance_check += 1
                if self._records_since_advance_check >= self.config.auto_advance_interval:
                    self._records_since_advance_check = 0
                    should_advance = True
            if should_advance:
                try:
                    self.advance(_auto=True)
                except Exception:
                    pass

    def phase(self) -> Phase:
        """Current lifecycle phase.

        Reads ``config.starting_phase``. :meth:`advance` mutates this
        state when the configured gate says the next phase is earned.
        """
        return self.config.starting_phase

    def phase_limit(self) -> Phase:
        """Ceiling on this switch's phase. :meth:`advance` refuses to exceed."""
        return self.config.phase_limit

    def advance(self, *, _auto: bool = False) -> Any:
        """Evaluate the configured gate and advance the phase on pass.

        Returns a :class:`dendra.gates.GateDecision` regardless of
        whether the phase moved — operators and audit trails want to
        see the rationale either way. When ``decision.advance`` is
        ``True``, ``config.starting_phase`` is mutated up by one
        phase in the lifecycle and an ``advance`` telemetry event is
        emitted.

        The gate is ``config.gate`` (defaults to
        :class:`dendra.gates.McNemarGate`). Construction-time
        invariants still hold: ``advance`` refuses to exceed
        ``phase_limit`` and never touches a terminal phase.

        **Automatic scheduling.** By default,
        :meth:`record_verdict` calls ``advance`` every
        ``config.auto_advance_interval`` records. Set
        ``auto_advance=False`` on the switch to disable and call
        this method from your own cron / ops workflow. Manual calls
        still work when auto-advance is on — use them for on-demand
        probes or to force an evaluation ahead of schedule.

        ``_auto`` is an internal flag tagging the telemetry event;
        it is not part of the stable API.
        """
        from dendra.gates import GateDecision, next_phase

        # Serialize the read-log / evaluate-gate / mutate-phase
        # sequence against concurrent classifies (which read
        # starting_phase) and other advance() callers.
        with self._lock:
            current = self.config.starting_phase
            target = next_phase(current)
            if target is None:
                return GateDecision(
                    advance=False,
                    rationale=f"already at terminal phase {current.name}",
                )
            if _PHASE_ORDER[target] > _PHASE_ORDER[self.config.phase_limit]:
                return GateDecision(
                    advance=False,
                    rationale=(
                        f"target phase {target.name} exceeds phase_limit "
                        f"{self.config.phase_limit.name}"
                    ),
                )
            if (
                self.config.safety_critical
                and target is Phase.ML_PRIMARY
            ):
                # safety_critical refuses ML_PRIMARY on the hot path per
                # paper §7.1, regardless of gate evidence. Belt + suspenders
                # on top of phase_limit — if anyone ever widens that cap,
                # this check still enforces the architectural guarantee.
                return GateDecision(
                    advance=False,
                    rationale=(
                        "safety_critical=True refuses advancement to "
                        "ML_PRIMARY (paper §7.1)"
                    ),
                )

            records = self._storage.load_records(self.name)
            decision = self.config.gate.evaluate(records, current, target)

            if decision.advance:
                self.config.starting_phase = target

        if decision.advance:
            try:
                self._telemetry.emit(
                    "advance",
                    {
                        "switch": self.name,
                        "from": current.value,
                        "to": target.value,
                        "rationale": decision.rationale,
                        "p_value": decision.p_value,
                        "paired_sample_size": decision.paired_sample_size,
                        "current_accuracy": decision.current_accuracy,
                        "target_accuracy": decision.target_accuracy,
                        "auto": _auto,
                    },
                )
            except Exception:
                pass

        return decision

    def status(self) -> SwitchStatus:
        """Return a :class:`SwitchStatus` snapshot."""
        outcomes = self._storage.load_records(self.name)
        total = len(outcomes)
        correct = sum(1 for r in outcomes if r.outcome == Verdict.CORRECT.value)
        incorrect = sum(1 for r in outcomes if r.outcome == Verdict.INCORRECT.value)

        shadow_rate: float | None = None
        shadow_obs = [
            r for r in outcomes if r.model_output is not None and r.rule_output is not None
        ]
        if shadow_obs:
            agreements = sum(1 for r in shadow_obs if r.model_output == r.rule_output)
            shadow_rate = agreements / len(shadow_obs)

        ml_rate: float | None = None
        ml_obs = [r for r in outcomes if r.ml_output is not None]
        if ml_obs:
            # Compare ML against whatever the user-visible decision was
            # (output), which is the most load-bearing definition of
            # "agreement" for Phase 3+ transition math.
            ml_agreements = sum(1 for r in ml_obs if r.ml_output == r.label)
            ml_rate = ml_agreements / len(ml_obs)

        version = self._ml_head.model_version() if self._ml_head is not None else None

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
        with self._lock:
            self._circuit_tripped = False
            self._save_breaker_state()

    # --- Breaker-state persistence (paper §7.1 survives restart) ---------

    def _breaker_path(self) -> Path | None:
        """Path to the breaker-state sidecar file, or ``None`` if unsupported.

        Breaker persistence is enabled when ``persist=True`` was
        passed at construction — see v1-readiness.md §5 D2.
        """
        if not getattr(self, "_persist", False):
            return None
        return Path("runtime") / "dendra" / self.name / ".breaker"

    def _save_breaker_state(self) -> None:
        """Persist ``_circuit_tripped`` to disk when configured.

        Called from the lock holders that mutate the breaker
        (``_classify_impl`` ML_PRIMARY branch, ``reset_circuit_breaker``).
        A failure here never propagates — persistence is best-effort;
        crashing the classifier over a sidecar-file write is a worse
        outcome than losing a restart-survival on one trip.
        """
        path = self._breaker_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("1" if self._circuit_tripped else "0")
        except OSError:
            pass

    def _load_breaker_state(self) -> None:
        """Rehydrate ``_circuit_tripped`` from disk at construction.

        Called from ``__init__`` only when ``persist=True``. A
        missing or unreadable file leaves the breaker untripped
        (the safe default).
        """
        path = self._breaker_path()
        if path is None:
            return
        try:
            raw = path.read_text().strip()
        except (OSError, FileNotFoundError):
            return
        if raw == "1":
            self._circuit_tripped = True

    # --- Diagnostics -------------------------------------------------------

    @property
    def storage(self) -> Storage:
        """Public accessor — useful for tests and advanced wiring."""
        return self._storage
