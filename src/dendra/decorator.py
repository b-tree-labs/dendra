# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""The ``@ml_switch`` decorator — generic, brand-neutral public API.

Wraps a user function (the rule) as a :class:`LearnedSwitch` while
keeping the decorated name callable exactly like the original function.

    @ml_switch(labels=["bug", "feature"], author="alice")
    def triage(ticket):
        if "crash" in ticket.get("title", ""):
            return "bug"
        return "feature"

    # Still a regular call:
    label = triage({"title": "app crashes"})   # → "bug"

    # Plus LearnedSwitch affordances:
    triage.record_outcome(input={...}, output="bug", outcome="correct")
    triage.status()
    triage.switch   # the underlying LearnedSwitch instance
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from dendra.core import LearnedSwitch, SwitchConfig


class _MLSwitchWrapper:
    """Callable + proxy for a decorated function.

    Exists as a class (not a closure) so introspection tools see a
    stable object with predictable attribute access.
    """

    def __init__(self, fn: Callable[..., Any], switch: LearnedSwitch) -> None:
        self.switch = switch
        self._fn = fn
        # Preserve wrapped function metadata so reflection / help()
        # / docstrings work as if the user had called the bare fn.
        functools.update_wrapper(self, fn)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._fn(*args, **kwargs)

    # Proxy convenience methods onto the wrapped switch.

    @property
    def name(self) -> str:
        return self.switch.name

    def record_outcome(
        self,
        *,
        input: Any,
        output: Any,
        outcome: str,
        source: str = "rule",
        confidence: float = 1.0,
    ) -> None:
        self.switch.record_outcome(
            input=input,
            output=output,
            outcome=outcome,
            source=source,
            confidence=confidence,
        )

    def status(self):  # → SwitchStatus
        return self.switch.status()

    def phase(self):  # → Phase
        return self.switch.phase()


def ml_switch(
    *,
    labels: Optional[list[str]] = None,
    author: str,
    name: Optional[str] = None,
    config: Optional[SwitchConfig] = None,
    storage: Optional[Any] = None,
) -> Callable[[Callable[..., Any]], _MLSwitchWrapper]:
    """Wrap a classification rule function as a :class:`LearnedSwitch`.

    Args:
        labels: Exhaustive list of valid output labels. Unused in
            Phase 0; required at Phase 1+ for ML head configuration.
        author: Principal associated with the switch (opaque string).
        name: Stable switch identifier. Defaults to the wrapped
            function's ``__name__``.
        config: Optional :class:`SwitchConfig`.
        storage: Optional :class:`Storage` backend.

    Returns a wrapper callable that forwards to the decorated function
    and exposes the LearnedSwitch affordances (``record_outcome``,
    ``status``, ``phase``, ``switch``).
    """

    def decorate(fn: Callable[..., Any]) -> _MLSwitchWrapper:
        switch_name = name or fn.__name__
        switch = LearnedSwitch(
            name=switch_name,
            rule=fn,
            author=author,
            config=config,
            storage=storage,
        )
        # ``labels`` is informational in v0.1.0; stash on the switch for
        # later phases to consume during ML head construction.
        switch.labels = list(labels or [])  # type: ignore[attr-defined]
        return _MLSwitchWrapper(fn, switch)

    return decorate
