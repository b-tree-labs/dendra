# Chaos / failure-mode audit (v1 readiness)

Audit date: 2026-04-24. Scope: `src/dendra/{storage,core,gates,models,decorator}.py`
and the existing test suite under `tests/`.

## Summary

Dendra's failure posture is **strong on the hot path** (breaker + ResilientStorage
give classification real liveness under adverse I/O), but has **three classes of
silent-failure bugs** that will bite v1 users: (1) the `ResilientStorage` fallback
buffer silently evicts records on overflow with no audit signal, (2) successful
drains that later re-fail can **duplicate records** in the primary, and (3) the
circuit breaker state is process-local with no persistence, so a crashloop silently
un-trips the breaker on every restart. Several adapter/edge-case failures
propagate as uncaught exceptions through `classify()`, violating the documented
"rule floor never lost to an ML-head failure" guarantee. Graduation math does
not validate paired-record availability for the *target* phase before firing the
gate, which can produce a confident "advance" decision on no data.

## Failure modes discovered

### 1. ResilientStorage fallback overflow is silent (CRITICAL)
- **Scenario**: Primary fails, fallback is `BoundedInMemoryStorage` (default
  `max_records=100_000`). Records exceed cap → `deque.append` silently evicts
  oldest.
- **Current behavior**: Silent drop. `degraded_writes` counter keeps incrementing
  as if nothing was lost. No warning, no callback, no distinction in
  `load_records` output.
- **Severity**: CRITICAL
- **Impact**: Operator thinks "we didn't lose any outcomes, they're buffered" —
  actually the *oldest* (often the most interesting, the ones around the
  degradation start) are gone.
- **Fix**: Track fallback high-water-mark vs. capacity; emit a second
  `UserWarning` + fire an `on_overflow` callback when eviction begins; expose
  `fallback_evicted_count` property.

### 2. Drain-then-fail can duplicate records (CRITICAL)
- **Scenario** (`ResilientStorage._try_recover`, storage.py:918-956): The drain
  loop `append_record`s each fallback record into primary, then
  `_clear_fallback_for(switch)` *only after the whole switch drains*. If a later
  switch's drain raises, the earlier switches are already in primary **and**
  still in fallback. Next classify() reads `primary + fallback` → duplicates.
- **Current behavior**: Silent duplication on every degraded read between the
  partial-drain and the next successful drain.
- **Severity**: CRITICAL (corrupts the outcome log McNemar gate reads from)
- **Impact**: Gate statistics skewed; advance() can fire on duplicated pairs;
  ROI/status counts double-counted outcomes.
- **Fix**: Clear fallback entries *per-record* as they drain (with a rollback
  on primary failure), or use idempotent record IDs so dedup is possible on read.

### 3. Circuit-breaker state is not persisted across restart (HIGH)
- **Scenario** (`core.py:552, 793-811, 1078-1085`): `self._circuit_tripped: bool`
  lives only in the process. A crashloop or a routine restart silently un-trips
  the breaker.
- **Current behavior**: Each restart starts in `_circuit_tripped=False` →
  immediately tries the ML head → breaker trips → another outcome burst leaks
  through → repeat.
- **Severity**: HIGH
- **Impact**: In production a flapping ML head combined with a supervisor that
  restarts on crash will show as "breaker works" in a single-process test, but
  in reality thrashes classification between ML and rule on every restart.
- **Fix**: Persist breaker state in storage (a sentinel record or a sidecar
  file) and re-hydrate on construction; OR document explicitly and add a
  `persist_breaker=True` option.

### 4. ML-head exception in non-ML_PRIMARY phases propagates (HIGH)
- **Scenario** (`core.py:749-753, 762-771`): In `ML_SHADOW` and
  `ML_WITH_FALLBACK`, exceptions from `self._ml_head.predict()` are caught with
  bare `except Exception`. But a `BaseException` subclass
  (`KeyboardInterrupt`, `SystemExit`, `asyncio.CancelledError` in 3.8+) is NOT
  caught — it propagates through `classify()`, breaking the "rule floor is
  always a safe answer" guarantee.
- **Current behavior**: `classify()` raises; caller's control flow breaks.
- **Severity**: HIGH (especially for async callers where `CancelledError` is
  routine)
- **Impact**: Async callers cancelling a request see the cancellation escape
  into the rule path.
- **Fix**: Catch `BaseException` explicitly around the ML head call, or
  whitelist (re-raise `KeyboardInterrupt`/`SystemExit`, catch everything else).

### 5. Adapter output never validated against configured labels (HIGH)
- **Scenario** (`models.py:_normalize_label` lines 70-99): If the LLM returns
  text matching no label, `_normalize_label` returns `label_list[0]` as a
  fallback with whatever confidence the logprob math produced (can be high).
  The switch then records an outcome with a label that was not actually
  predicted.
- **Current behavior**: Silent mis-attribution. No way to tell "model guessed
  default" from "model said label 0 confidently".
- **Severity**: HIGH
- **Impact**: Training data for Phase 4/5 is contaminated; gates advance on
  fictitious agreement.
- **Fix**: Flag normalized fallbacks (return `confidence=0.0` and/or a
  `normalized_from` field on `ModelPrediction`); surface as a telemetry event.

### 6. Adapter confidence is not clamped to [0, 1] (MEDIUM)
- **Scenario** (`models.py:_logprob_to_confidence` line 250-265): Returns
  `math.exp(logprob)`. For logprob > 0 (should be impossible but provider bugs
  exist), returns > 1.0.  `OpenAIAdapter` passes this straight through.
- **Current behavior**: `confidence_threshold` comparison still works
  (`> 1.0 >= 0.85`), but dashboards and McNemarGate see nonsense confidences.
- **Severity**: MEDIUM
- **Impact**: Cosmetic in normal operation; masks upstream provider bugs.
- **Fix**: `min(1.0, max(0.0, value))` in `_logprob_to_confidence` and in
  `ModelPrediction` / `MLPrediction` post_init.

### 7. Network-timeout is hardcoded / unbounded (MEDIUM/HIGH)
- **Scenario** (`models.py`): `OllamaAdapter` hardcodes `timeout=60.0`.
  `OpenAIAdapter` and `AnthropicAdapter` pass NO timeout — rely on the SDK
  default (can be 600s+). `classify()` blocks for that long.
- **Current behavior**: `classify()` can block a request thread for up to 10
  minutes on a hung provider. In `ML_WITH_FALLBACK`/`ML_PRIMARY`, breaker only
  trips *after* the timeout returns.
- **Severity**: HIGH for latency-sensitive callers
- **Impact**: p99 latency unbounded by Dendra's contract; circuit breaker is
  slow to engage.
- **Fix**: Accept a `timeout` kwarg on all adapters, default to something sane
  (e.g., 10s); document the hot-path blocking guarantee.

### 8. Graduation gate fires on zero target-phase paired records (MEDIUM)
- **Scenario** (`gates.py:_paired_correctness` + `McNemarGate.evaluate`): When
  the target phase has recorded zero predictions (e.g., advancing RULE →
  MODEL_SHADOW with no model observations yet), `_paired_correctness` returns
  `([], [])`, `n=0 < min_paired=200` → refuses. OK. But when the target has
  `model_output=None` on most records and a few stray observations that happen
  to match, n can be small and statistically meaningless even if nominally
  above `min_paired`. More importantly, `_source_correct_for` only admits
  `outcome == "correct"` rows, making `n` deceptive: the gate's `min_paired`
  counts the subset that's already paired, which can be dominated by a
  single-label distribution.
- **Current behavior**: Gate can fire `advance=True` on degenerate data if
  `min_paired` is met in the correct-outcome subset.
- **Severity**: MEDIUM
- **Impact**: Premature advancement on small-N switches.
- **Fix**: Require a minimum total outcome count separate from paired count;
  add a label-diversity check (reject if paired data contains only one label).

### 9. `load_records()` raising during `advance()` propagates (MEDIUM)
- **Scenario** (`core.py:1016`): `records = self._storage.load_records(self.name)`
  — if the storage raises (corrupt SQLite, permission glitch on FileStorage
  read path), the exception propagates out of `advance()`.
- **Current behavior**: `advance()` raises. Callers that run advance() in a
  background loop (example 07) crash the loop.
- **Severity**: MEDIUM
- **Impact**: Operator tooling that calls advance() on a timer crashes;
  requires ops intervention.
- **Fix**: Wrap in `try/except`, return a `GateDecision(advance=False,
  rationale="storage unreachable: ...")`.

### 10. Non-serializable input silently fallback-stringified (MEDIUM)
- **Scenario** (`storage.py:serialize_record` line 173): Uses
  `json.dumps(asdict(record), default=str)`. An open file handle or a thread
  lock stringifies to `"<_io.TextIOWrapper ...>"` — the outcome log will "work"
  but the `input` field is useless for reconstruction and correlation.
- **Current behavior**: Silent, lossy serialization.
- **Severity**: MEDIUM
- **Impact**: Audit trail unreliable; research / viz layer sees garbage
  inputs.
- **Fix**: Emit a `UserWarning` when `default=str` is invoked; document
  input-serializability contract prominently.

### 11. Large input (10MB dict) writes a 10MB outcome row (LOW/MEDIUM)
- **Scenario** (`storage.py:474`): `serialize_record` encodes the full input.
  A 10MB input writes 10MB to the JSONL file, blowing segment-size budgets
  in a single record (defaults: 64MB segment cap → ~6 such records before
  rotation).
- **Current behavior**: Works, but disk budget calculations assume ~100 bytes
  per row.
- **Severity**: LOW (hard for users to hit accidentally but easy to forget)
- **Impact**: "10 years on any reasonable disk" guarantee in the FileStorage
  docstring becomes wildly wrong.
- **Fix**: Optional `max_input_bytes` on storage — truncate with a marker past
  that, or emit a warning when a single record exceeds (say) 256KB.

### 12. FileStorage construction can crash on read-only mount (LOW)
- **Scenario** (`storage.py:410`): `self._base.mkdir(parents=True,
  exist_ok=True)` — raises `PermissionError` / `OSError` on RO mount.
- **Current behavior**: Constructor raises. No graceful downgrade.
- **Severity**: LOW (construction-time; loud failure is fine here)
- **Impact**: App startup fails with a raw `PermissionError`. ResilientStorage
  cannot wrap this because construction of primary happens before ResilientStorage
  wraps it.
- **Fix**: Document that `persist=True` on a RO FS fails at construction; add
  a `ResilientStorage.from_config()` factory that lazy-constructs the primary.

### 13. SQLite BEGIN IMMEDIATE + INSERT fails under ENOSPC (LOW)
- **Scenario** (`storage.py:717-730`): If INSERT fails on disk-full, the
  `conn.execute("ROLLBACK")` inside `except` can ALSO fail (same disk). The
  `raise` still propagates, but the connection is left in an undefined
  transaction state (closed by `_connect`'s finally → next connection starts
  fresh, so actually OK). Worth verifying.
- **Current behavior**: Raises. ResilientStorage catches and falls back.
- **Severity**: LOW (the fallback wrapper handles it)
- **Impact**: Noisy stderr when BEGIN IMMEDIATE runs on a read-only WAL after
  disk-full, but does not lose data.
- **Fix**: Test explicitly; document that ResilientStorage is required for
  ENOSPC tolerance.

### 14. Decorator does not handle async / generator / classmethod rules (LOW)
- **Scenario** (`decorator.py`): `ml_switch` wraps `fn` with
  `functools.update_wrapper`. An `async def` rule returns a coroutine that the
  switch stores as the "classification" — `_classify_impl` does
  `self._rule(input)` and returns the coroutine as the label. No
  `iscoroutinefunction` check.
- **Current behavior**: Async rule → coroutine label → serialization warning
  (via `default=str`) → useless outcome log.
- **Severity**: LOW (documented async support doesn't exist; but users will
  try).
- **Impact**: Confusing silent failure for users who reach for async rules.
- **Fix**: Reject async/generator rules at decorator time with a clear error;
  OR add first-class async support.

### 15. Breaker flap has no hysteresis / backoff (LOW)
- **Scenario** (`core.py:787-811`): Each time the operator calls
  `reset_circuit_breaker()`, the next call goes straight to ML head. No
  half-open state, no exponential backoff. If the ML head is intermittently
  failing, an automated reset script oscillates the breaker.
- **Current behavior**: Trip → reset → trip → reset — each cycle leaks one
  classification into the rule-fallback path.
- **Severity**: LOW (requires user error — an aggressive auto-reset)
- **Impact**: Routing integrity is preserved (rule path is always safe), but
  telemetry is noisy.
- **Fix**: Document the "operator-driven reset" intent; add an optional
  `half_open_after_s` parameter for auto-reset workflows.

## Recommended chaos tests to add

Concrete, Python-level injection tests to write before v1:

1. **`test_resilient_fallback_overflow_audited`** — fill a 5-record
   `BoundedInMemoryStorage` fallback with 20 records under a failing primary;
   assert `degraded_writes == 20`, assert eviction was signalled (fails today).
2. **`test_resilient_drain_partial_failure_no_duplication`** — primary
   recovers, drain starts, primary fails mid-drain on switch #2; recover again;
   assert no record appears twice in `load_records()`.
3. **`test_breaker_state_across_fresh_switch_construction`** — trip breaker,
   discard switch, construct a new one with the same storage; document
   whether breaker re-trips or starts clean (either is OK; behavior must be
   documented).
4. **`test_ml_head_raises_baseexception`** — use `FakeMLHead` that raises
   `asyncio.CancelledError`; assert `classify()` either catches it (rule
   fallback) or re-raises a specific documented subset.
5. **`test_model_adapter_returns_out_of_label`** — stub adapter returning
   `"not-a-label"`; assert the prediction is flagged (confidence or a
   `normalized_from` field), not silently mapped to `labels[0]`.
6. **`test_adapter_confidence_clamped`** — stub adapter returning
   `ModelPrediction(label="a", confidence=1.7)`; assert downstream usage is
   bounded / rejected.
7. **`test_adapter_network_timeout_bounded`** — monkeypatch `httpx.post`
   to sleep 30s; assert `classify()` returns within adapter's timeout + ε.
8. **`test_advance_storage_unreachable`** — storage whose `load_records`
   raises `OSError`; call `advance()`; assert returns `GateDecision(advance=False,
   rationale=...)` rather than raising.
9. **`test_advance_with_single_label_paired_data`** — feed the gate 200 paired
   records where every label is the same; assert it refuses to advance on
   degenerate data.
10. **`test_serialize_non_jsonable_input_warns`** — pass an open file handle
    as input; assert a `UserWarning` is emitted.
11. **`test_filestorage_enospc_via_monkeypatch`** — monkeypatch `os.write`
    to raise `OSError(errno.ENOSPC)`; assert the raw `FileStorage` raises and
    that ResilientStorage wraps it into fallback mode.
12. **`test_rotation_interrupted_by_sigkill_equivalent`** — manually leave a
    partial rename state (`outcomes.jsonl.1` exists but `outcomes.jsonl` also
    exists with content); assert `load_records()` returns everything in order
    and does not crash.
13. **`test_decorator_rejects_async_rule`** — `@ml_switch(...)` on an
    `async def`; expect a clear `TypeError` at decoration time.

## Already-handled failure modes

Genuine strengths worth keeping:

- **Multi-process writer contention on FileStorage** — covered by
  `tests/test_storage_hardening.py::TestMultiProcessWriters` (including
  rotation under contention, `test_no_data_loss_with_frequent_rotation`).
- **Concurrent SQLite writers** — covered by
  `tests/test_sqlite_storage.py::TestConcurrentWriters::test_no_data_loss_under_contention`.
- **FileStorage malformed-line tolerance** — covered by
  `tests/test_storage.py::test_skips_malformed_lines_gracefully` and
  matching `_parse_line` returning `None`.
- **SQLite corrupt-row tolerance** — covered by
  `tests/test_sqlite_storage.py::TestGracefulDegradation::test_skips_corrupt_rows`.
- **ResilientStorage degrade → drain → recover cycle** — well covered by
  `tests/test_resilient_storage.py::TestDegradationCycle`, including the
  callback contract and the probe-failure-keeps-us-degraded path.
- **Primary permission errors fall back without propagating** —
  `tests/test_resilient_storage.py::TestWithFileStoragePrimary::test_filestorage_permission_failure_falls_back`.
- **Callback exceptions are swallowed** —
  `test_callback_exceptions_are_swallowed` ensures operator-hook bugs can't
  brick classification.
- **Circuit breaker: trip → stays tripped until reset** — explicitly tested in
  `tests/test_ml_primary.py::TestMLPrimary::{test_circuit_trips_on_ml_error,
  test_subsequent_calls_stay_in_fallback_until_reset, test_breaker_reset_restores_ml}`.
- **Action dispatch exceptions captured, not propagated** — handled in
  `LearnedSwitch._maybe_dispatch` (core.py:639-669).
- **Switch name collision detection** — `core.py:520-537` refuses two live
  switches sharing (storage, name) with an informative message.
- **Windows flock-absent warning** — one-shot `UserWarning` on first
  FileStorage instance; no silent race exposure.

## Prioritized for v1 launch (noisiness proxy)

If v1 ships today, the top three user-visible pain points would be:

1. **Silent fallback overflow** (#1) — the most common production complaint
   waiting to happen.
2. **Un-bounded adapter timeouts** (#7) — makes p99 latency claims unverifiable.
3. **ML-head `BaseException` propagation** (#4) — async users will hit this on
   day 1 cancellation semantics.

These three can each be fixed in < 50 LOC; the audit tests in the list above
prove the fixes.
