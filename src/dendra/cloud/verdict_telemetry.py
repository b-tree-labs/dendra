# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at LICENSE-BSL in the
# repository root, or at https://mariadb.com/bsl11/.
#
# Change Date:    2030-05-01
# Change License: Apache License, Version 2.0

"""Hosted-API verdict telemetry pipe.

Bridges the in-process ``outcome`` telemetry stream produced by
:meth:`dendra.core.LearnedSwitch.record_verdict` to
``POST /v1/verdicts`` on the hosted API. Default-on for signed-in
users (those with ``~/.dendra/credentials``); inert for everyone else.

Design constraints:

- **Async + non-blocking.** ``emit()`` returns immediately. A single
  daemon thread per process consumes a bounded queue.
- **Fails silent.** Network errors, server errors, 5xx, malformed
  responses — all absorbed. The decision path is never degraded by
  a telemetry hiccup.
- **Burst-limited.** Token-bucket caps the producer at ~100 events/sec
  per process; the bucket fills at 100 tokens/sec up to a 200-token
  burst window. Over-budget events are dropped (counted in
  ``CloudVerdictEmitter.dropped``).
- **Bounded memory.** Queue size capped at 1024 events; on overflow we
  drop the OLDEST event, preserving the most recent activity for the
  dashboard while bounding worst-case memory.
- **Honors opt-outs at every level.** Process: ``DENDRA_NO_TELEMETRY=1``
  short-circuits at default-emitter resolution (see
  :mod:`dendra.telemetry`). Per-switch: ``telemetry=NullEmitter()`` on
  the decorator. Per-call: not currently plumbed (no public hook on
  ``record_verdict``); the per-switch knob is the documented opt-out.

This module installs itself as the default emitter at import time iff
``dendra.auth.is_logged_in()`` returns True. The trigger is the
import from :mod:`dendra` — :func:`maybe_install` is invoked from
``dendra/__init__.py`` so simple ``import dendra`` is enough.

What ships over the wire (one POST per record_verdict call):

    {
      "switch_name": "<name>",         # operator-chosen
      "phase":       "P0".."P5"|None,  # lifecycle phase at emit time
      "rule_correct":   bool|None,
      "model_correct":  bool|None,
      "ml_correct":     bool|None,
      "request_id":  "<uuid4>",        # idempotency on retries
    }

What does NOT ship: inputs, ground-truth labels, payloads, machine ID,
IP. The server attaches ``account_hash`` (from the bearer-key lookup),
so the SDK never has to compute it.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any, Final

from dendra import auth as _auth
from dendra.telemetry import (
    TelemetryEmitter,
    register_default_emitter,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables. Public-ish so tests can override.
# ---------------------------------------------------------------------------

#: Default hosted-API base URL. Override with ``$DENDRA_API_URL``.
DEFAULT_API_URL: Final[str] = "https://api.dendra.run"

#: Bounded queue capacity. Drop-OLDEST on overflow.
QUEUE_CAPACITY: Final[int] = 1024

#: Token bucket size (max burst).
RATE_LIMIT_BURST: Final[int] = 200

#: Token refill rate (events per second).
RATE_LIMIT_PER_SECOND: Final[float] = 100.0

#: Per-request HTTP timeout (seconds).
REQUEST_TIMEOUT_SECONDS: Final[float] = 5.0

#: Phases that always get null for a given classifier — used by the
#: server-side validator. We mirror the contract here.
_PHASES: Final[frozenset[str]] = frozenset({"P0", "P1", "P2", "P3", "P4", "P5"})


# ---------------------------------------------------------------------------
# Tiny stdlib HTTP sender — kept dependency-free so adding the cloud pipe
# doesn't bloat ``pip install dendra``.
# ---------------------------------------------------------------------------


class _UrllibSender:
    """POST a JSON body with a bearer token. Returns True on 2xx.

    Failures are logged at debug-level and reported as ``False``. The
    caller (sender thread) treats any failure mode as silent drop.
    """

    def __init__(self, url: str, bearer: str, timeout: float) -> None:
        self._url = url.rstrip("/") + "/v1/verdicts"
        self._bearer = bearer
        self._timeout = timeout

    def post(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._bearer}",
                "User-Agent": "dendra-sdk-verdicts/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 — HTTPS to a configured host
                req, timeout=self._timeout
            ) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            # 4xx is interesting (key revoked, validation drift, 429
            # over-cap). 5xx is transient. We don't retry — losing the
            # occasional record is acceptable for a metering feed.
            _log.debug("verdict POST failed http=%s url=%s", e.code, self._url)
            return False
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _log.debug("verdict POST failed transport=%s url=%s", e, self._url)
            return False


# ---------------------------------------------------------------------------
# Token-bucket rate limiter — pure-stdlib, lockless via monotonic-clock math.
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Simple token bucket. Thread-safe via a single lock on take()."""

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._refill_per_sec = refill_per_sec
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> bool:
        """Try to consume one token. Returns True if consumed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_sec)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


# ---------------------------------------------------------------------------
# CloudVerdictEmitter — public class. Implements TelemetryEmitter.
# ---------------------------------------------------------------------------


class CloudVerdictEmitter:
    """Default-on emitter that streams record_verdict outcomes to the
    hosted API.

    Construct directly for explicit control (tests, dev backends):

        from dendra.cloud.verdict_telemetry import CloudVerdictEmitter

        em = CloudVerdictEmitter(
            api_url="http://localhost:8787",
            bearer_token="dndr_live_…",  # pragma: allowlist secret
        )
        decorate(..., telemetry=em)

    Or rely on :func:`maybe_install` which the package init invokes
    automatically — signed-in users get one per process for free.

    The emitter listens for ``outcome`` events; ``classify`` /
    ``dispatch`` / ``advance`` / ``demote`` events are dropped on the
    floor (they don't contribute to the dashboard's verdict count).
    """

    def __init__(
        self,
        *,
        api_url: str,
        bearer_token: str,
        sender: _UrllibSender | None = None,
        queue_capacity: int = QUEUE_CAPACITY,
        rate_limit_burst: int = RATE_LIMIT_BURST,
        rate_limit_per_second: float = RATE_LIMIT_PER_SECOND,
        request_timeout: float = REQUEST_TIMEOUT_SECONDS,
        start_thread: bool = True,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._bearer = bearer_token
        self._sender: _UrllibSender = sender or _UrllibSender(
            self._api_url, self._bearer, request_timeout
        )
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_capacity)
        self._bucket = _TokenBucket(rate_limit_burst, rate_limit_per_second)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Observability counters — exposed as attributes so callers
        # (and tests) can sample without poking internals.
        self.queued: int = 0
        self.sent: int = 0
        self.dropped_rate_limited: int = 0
        self.dropped_queue_full: int = 0
        self.failed: int = 0

        if start_thread:
            self._start_sender()

    # -- public emitter surface --------------------------------------------

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        """TelemetryEmitter.emit — non-blocking, never raises."""
        try:
            if event != "outcome":
                return
            if not self._bucket.take():
                self.dropped_rate_limited += 1
                return
            wire = self._build_payload(payload)
            if wire is None:
                return
            self._enqueue(wire)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            # Belt-and-suspenders: emit() never propagates. The whole
            # point of this module is that the dispatch path is
            # observability-unaware.
            return

    # -- introspection helpers ---------------------------------------------

    def flush(self, timeout: float = 2.0) -> None:
        """Block (up to ``timeout`` seconds) until the queue drains.

        Test-only convenience; production code should not call this.
        Returns whether the queue went empty before the timeout fired.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.empty():
                return
            time.sleep(0.01)

    def close(self, timeout: float = 2.0) -> None:
        """Signal the sender thread to stop and join it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # -- internal: payload shape --------------------------------------------

    def _build_payload(self, ev: dict[str, Any]) -> dict[str, Any] | None:
        """Convert an ``outcome`` event payload into the wire shape.

        The wire payload intentionally OMITS:

        - rule_output / model_output / ml_output (the raw predictions)
        - label, ground_truth (the labels themselves)
        - source, switch internals beyond the name
        - any operator metadata

        What ships is the metering / paired-correctness summary.
        """
        switch_name = ev.get("switch")
        if not isinstance(switch_name, str) or not switch_name:
            return None
        phase = ev.get("phase")
        if phase is not None and (not isinstance(phase, str) or phase not in _PHASES):
            phase = None
        payload: dict[str, Any] = {
            "switch_name": switch_name,
            # uuid4 + the SDK's send-once semantic gives the server a
            # cheap idempotency token. The server treats a retry with
            # the same request_id as a no-op (HTTP 200 + duplicate=True).
            "request_id": uuid.uuid4().hex,
        }
        if phase is not None:
            payload["phase"] = phase
        # Each is bool | None. Honour None faithfully — the server
        # treats absent and None equivalently.
        for key in ("rule_correct", "model_correct", "ml_correct"):
            v = ev.get(key)
            if v is None:
                continue
            if isinstance(v, bool):
                payload[key] = v
        return payload

    def _enqueue(self, payload: dict[str, Any]) -> None:
        """Place a wire payload onto the queue.

        On overflow, drop the oldest queued item (which represents the
        least-fresh data) and try again. The single bounded retry keeps
        the producer wait-free.
        """
        try:
            self._queue.put_nowait(payload)
            self.queued += 1
            return
        except queue.Full:
            pass
        # Drop-oldest pass.
        try:
            self._queue.get_nowait()
            self.dropped_queue_full += 1
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(payload)
            self.queued += 1
        except queue.Full:
            # Producer raced with another producer. Drop this event,
            # not the queue's; queue is full of more-recent activity
            # written between our two .put_nowait() calls.
            self.dropped_queue_full += 1

    # -- internal: sender loop ----------------------------------------------

    def _start_sender(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="dendra-verdict-sender",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                payload = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            ok = False
            try:
                ok = self._sender.post(payload)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                ok = False
            if ok:
                self.sent += 1
            else:
                self.failed += 1
            try:
                self._queue.task_done()
            except ValueError:
                # task_done() called more times than items put — should
                # never happen given the get/put pairing, but defending
                # the daemon thread is cheap.
                pass


# ---------------------------------------------------------------------------
# One-shot install hook called from dendra/__init__.py.
# ---------------------------------------------------------------------------


def maybe_install(
    *,
    api_url: str | None = None,
    auth_lookup: Callable[[], dict | None] | None = None,
) -> CloudVerdictEmitter | None:
    """Register :class:`CloudVerdictEmitter` as the default emitter iff
    the user is signed in AND has not opted out via env var.

    Returns the installed emitter (for tests / introspection) or
    ``None`` when not installed. This function is idempotent in the
    sense that a second call just registers a new emitter — the old
    one becomes unreferenced and its daemon thread terminates on
    process exit.

    The single ``DENDRA_API_URL`` env var overrides the hosted endpoint
    (used by the local-dev Worker on ``http://localhost:8787``); falls
    back to :data:`DEFAULT_API_URL` in production.
    """
    if os.environ.get("DENDRA_NO_TELEMETRY", "").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    ):
        # The env-var opt-out wins. Don't register anything — the
        # default-emitter resolver will return NullEmitter() directly.
        return None
    lookup = auth_lookup or _auth.load_credentials
    try:
        creds = lookup()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        creds = None
    if not creds or not creds.get("api_key"):
        # Not signed in. Stay quiet — the OSS path remains
        # telemetry-free.
        return None

    resolved_url = (api_url or os.environ.get("DENDRA_API_URL") or DEFAULT_API_URL).rstrip("/")
    emitter = CloudVerdictEmitter(
        api_url=resolved_url,
        bearer_token=str(creds["api_key"]),
    )
    register_default_emitter(lambda: emitter)
    return emitter


# Convenience: tests want a "no telemetry, please" reset.
def uninstall() -> None:
    """Reset the default emitter to NullEmitter. Tests + opt-out path."""
    from dendra.telemetry import reset_default_emitter

    reset_default_emitter()


__all__ = [
    "DEFAULT_API_URL",
    "QUEUE_CAPACITY",
    "RATE_LIMIT_BURST",
    "RATE_LIMIT_PER_SECOND",
    "REQUEST_TIMEOUT_SECONDS",
    "CloudVerdictEmitter",
    "TelemetryEmitter",
    "maybe_install",
    "uninstall",
]
