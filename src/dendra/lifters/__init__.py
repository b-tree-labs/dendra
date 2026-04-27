# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
"""Auto-lift transforms.

Public entry points for ``dendra init --auto-lift``. Each lifter
consumes Python source plus a function name and returns refactored
source that targets the :class:`dendra.Switch` native authoring form.
On any safe-subset violation, the lifter raises :class:`LiftRefused`
with a structured ``reason`` and source ``line`` for diagnostics.

Phase 2 (this module) ships the branch-body lifter: it splits each
``if``/``elif``/``else`` branch's side effects into ``_on_<label>``
methods while preserving the branch chain inside ``_rule``. Phase 3
adds evidence lifting on top.

This module also exports two opt-in annotation decorators consumed by
the evidence lifter (v1.1):

- :func:`evidence_via_probe` declares a dry-run probe expression for a
  side-effect-bearing bind, overriding the analyzer's
  ``side_effect_evidence`` refusal.
- :func:`evidence_inputs` declares per-field gatherer callables for
  cases where static analysis cannot trace the evidence (dynamic
  dispatch, ``getattr`` of computed attribute names), overriding the
  ``dynamic_dispatch`` refusal.

Both decorators are runtime no-ops that attach metadata. The lifter
inspects the wrapped function's decorator list at the AST level, so the
decorators carry no runtime cost beyond a single attribute set.
"""

from typing import Any, Callable

from dendra.lifters.branch import LiftRefused, lift_branches
from dendra.lifters.evidence import lift_evidence


def evidence_via_probe(**fields: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as having a dry-run probe for side-effect-bearing
    evidence.

    Each kwarg maps a generated evidence field name to a probe-call
    source string the lifter splices into the generated ``_evidence_*``
    method. Example:

    .. code-block:: python

        @evidence_via_probe(charge_status="api.charge_probe(req)")
        def maybe_charge(req):
            response = api.charge(req)
            if response.ok:
                notify(req)
                return "charged"
            return "skipped"

    The lifter sees the decorator, generates ``_evidence_charge_status``
    calling ``api.charge_probe(req)`` (NOT ``api.charge``), and the
    branch-lifter (Phase 2) lifts ``api.charge(req)`` into the chosen
    label's ``_on_charged`` handler so the real charge fires only on
    that path.
    """

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn._dendra_evidence_probes = dict(fields)  # type: ignore[attr-defined]
        return fn

    return wrapper


def evidence_inputs(**fields: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare evidence inputs explicitly when static lift cannot infer
    them (dynamic dispatch, ``getattr``, etc.).

    Each kwarg maps an evidence field name to a callable that produces
    that field from the function's inputs. Example:

    .. code-block:: python

        @evidence_inputs(handler_priority=lambda self, text, kind:
            getattr(self, f"handle_{kind}").priority)
        def route(self, text, kind):
            handler = getattr(self, f"handle_{kind}")
            if handler.priority > 5:
                return "high"
            return "low"

    The lifter sees the decorator, ignores the function body's
    ``getattr`` detection for the annotated fields, and uses the
    supplied callables (parsed at AST level) as the generated gatherers.
    """

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn._dendra_evidence_inputs = dict(fields)  # type: ignore[attr-defined]
        return fn

    return wrapper


__all__ = [
    "LiftRefused",
    "evidence_inputs",
    "evidence_via_probe",
    "lift_branches",
    "lift_evidence",
]
