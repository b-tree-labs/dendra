# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Telemetry hooks — zero-dep, opt-in.

Every :class:`~dendra.core.LearnedSwitch` can be configured with a
:class:`TelemetryEmitter`. The switch emits two event kinds:

- ``classify``  — one per :meth:`~dendra.core.LearnedSwitch.classify`
- ``outcome``   — one per :meth:`~dendra.core.LearnedSwitch.record_outcome`

An emitter is just a callable ``emit(event_name, payload_dict)``. The
library never blocks on telemetry and swallows exceptions so a broken
emitter can't degrade the decision path.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TelemetryEmitter(Protocol):
    """Anything callable ``(event, payload)`` satisfies this."""

    def emit(self, event: str, payload: dict[str, Any]) -> None: ...


class NullEmitter:
    """Default — swallows events. Zero overhead."""

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        return


class StdoutEmitter:
    """JSON-lines emitter to stdout (or any file handle).

    Useful for CLI smoke tests, shell pipelines, and when sibling tools
    like ``jq`` should slice the event stream.
    """

    def __init__(self, stream: Any = sys.stdout) -> None:
        self._stream = stream

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"event": event, **payload}, default=str)
        self._stream.write(line + "\n")
        self._stream.flush()


class ListEmitter:
    """In-memory emitter — captures events for tests + replay."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append((event, dict(payload)))


__all__ = ["ListEmitter", "NullEmitter", "StdoutEmitter", "TelemetryEmitter"]
