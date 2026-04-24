# Concurrency audit (v1 readiness)

## Summary

**Posture: bugs found — the library is implicitly single-threaded and will silently misbehave under even modest in-process concurrency.**

The storage layer's cross-process story is solid (fcntl exclusive lock around append+rotate on `FileStorage`, WAL mode + fresh-connection-per-call on `SqliteStorage`, collision-detection registry under a `threading.Lock`). But the `LearnedSwitch` hot path itself is unprotected:

- The single-slot "shadow stash" (`_last_shadow`, `_last_ml`, `_last_rule_output`, `_last_action`) is a textbook check-and-act race: interleaved `classify()` / `record_verdict()` calls from two threads will cross-contaminate outcome records. This is the load-bearing bug — the outcome log is the data the paper's phase-transition math is built on.
- The circuit breaker `_circuit_tripped` flag is a plain `bool` with check-then-act semantics and no lock, so multiple threads can all trip it in parallel, race a `reset_circuit_breaker()` against an in-flight failure, and (most harmfully) the "test, then call ML, then store" sequence has no atomicity.
- `advance()` mutates `config.starting_phase` live; a classify() call that reads the phase, starts executing one phase's branch, and is interrupted by an `advance()` gets an inconsistent mix.
- `ResilientStorage` degraded-mode state machine (`_degraded`, `_degraded_writes`, `_writes_since_probe`, `_tracked_switches`) has zero synchronization — `_try_recover()` can drain and clear fallback while another thread is simultaneously appending to it, and two threads can both call `_enter_degraded()`.
- The in-memory storage backends explicitly document "not thread-safe" but the default `BoundedInMemoryStorage` is installed silently whenever a user omits `storage=`, so users will not know.

Good news: none of the bugs are hard to fix. A single `threading.RLock` on `LearnedSwitch` (guarding classify/record/advance/reset/breaker), a lock on `ResilientStorage` state transitions, and locks on the in-memory backends would close the majority of findings. The fcntl / WAL stories for cross-process use are already correct.

## Findings

### F1. Shadow-stash cross-contamination under thread interleave
- **Location**: `src/dendra/core.py:548-552` (stash fields), `core.py:671-828` (populated in `_classify_impl`), `core.py:871-935` (consumed in `record_verdict`)
- **Severity**: **CRITICAL**
- **Scenario**: Thread A calls `classify(input_A)` — populates `_last_shadow = (pred_A, conf_A)` and `_last_rule_output = rule_A`. Before A calls `record_verdict`, Thread B runs `classify(input_B)`, overwriting `_last_shadow = (pred_B, conf_B)` and `_last_rule_output = rule_B`. A then calls `record_verdict(input=input_A, label=label_A, ...)` — and the `model_output` / `rule_output` attached to A's record are actually from input B. `_last_shadow` is then set to None (A's consumer clears it), so B's subsequent `record_verdict` loses *its* shadow observation entirely.
- **Impact**: The outcome log becomes statistically poisoned. McNemar gate evaluates `rule_output == label` pairs that never co-occurred in reality; `shadow_agreement_rate` in `status()` is wrong; `advance()` fires (or refuses) based on fiction. This is not a rare edge — any web server / worker pool that dispatches classify calls across threads will hit it on day one.
- **Fix**: Three options, in decreasing order of user-friendliness:
  1. **Preferred**: Return the shadow state inline on `ClassificationResult` (add optional `_shadow`, `_ml`, `_rule_output` fields or a `_stash` token) and have `record_verdict` accept the stash as an argument. Eliminates the shared mutable state entirely; safe for threads, processes, async, serialization — everything. Ship a deprecation path for the argless `record_verdict`.
  2. **Minimal**: Replace the four single-slot stashes with a `threading.local()` attribute so each thread gets its own slot. Keeps the API, loses the cross-thread leak. Still broken for async coroutines (shared event-loop thread) and for "classify in worker, record in main" patterns.
  3. **Expedient**: Wrap classify+record in a single `RLock` and document that calls must be paired-without-interleave. Does NOT fix correctness if user does `for x in batch: results.append(s.classify(x))` then later records — would need a keyed stash.
- Option 1 is the only one that is correct under all threat-model rows (threads, processes, async). Ship it.

### F2. `_circuit_tripped` is a lock-free bool with check-then-act races
- **Location**: `src/dendra/core.py:552` (declaration), `core.py:793-811` (trip on ML failure in ML_PRIMARY), `core.py:1078-1085` (reset)
- **Severity**: **HIGH**
- **Scenario A (double-trip is benign, but the read is racy)**: Two threads enter Phase.ML_PRIMARY branch, both read `_circuit_tripped=False`, both call `ml_head.predict()`, both fail, both set `_circuit_tripped=True`. Harmless in isolation, but the `_last_ml` writes race — one of them wins, and if one succeeded and one failed we get the wrong `_last_ml`.
- **Scenario B (reset race)**: Operator calls `reset_circuit_breaker()` — sets `_circuit_tripped=False`. Simultaneously a classify call reads `_circuit_tripped=False` (before the reset even happens), then ML fails mid-call, then the classify handler sets `_circuit_tripped=True`. Operator thinks the breaker is reset; it's not.
- **Scenario C (stale read on first classify after reset)**: Breaker trips. Operator investigates, calls `reset_circuit_breaker()`. A request-handler thread already inside the `if self._circuit_tripped:` check (having read `True` microseconds earlier) returns rule_fallback even though the breaker is now reset. Minor — just a one-extra-fallback — but worth noting.
- **Impact**: Breaker state becomes decoupled from operator intent; reset becomes unreliable under any concurrent classify load. Safety-critical deployments can't trust the reset semantics.
- **Fix**: Add a `self._lock = threading.RLock()` on `LearnedSwitch.__init__`. Guard the Phase.ML_PRIMARY branch (and the other phases that mutate stash state) under that lock. Same lock covers `reset_circuit_breaker()`. This closes F1 option 3 and F2 in one move. Recommend RLock over Lock because `_classify_impl` may want to call into other switch methods in future refactors; RLock is cheap on Python's GIL. If the user-supplied rule/model/ml_head are themselves slow, consider taking the lock only around the stash reads/writes, not around the rule call itself — but start with the coarse lock, measure, then narrow.

### F3. `advance()` mutates `config.starting_phase` mid-classify
- **Location**: `src/dendra/core.py:963-1038` (advance), `core.py:951-957` (phase() read), `core.py:671-828` (phase-branched classify)
- **Severity**: **HIGH**
- **Scenario**: Thread A enters `_classify_impl`, reads `phase = self.phase()` → `MODEL_PRIMARY`, executes the MODEL_PRIMARY branch. Simultaneously thread B calls `advance()` and mutates `config.starting_phase = ML_SHADOW`. A's result is returned with `phase=MODEL_PRIMARY` (matches the branch it ran) but subsequent classify calls jump to ML_SHADOW. That by itself is fine. But A's stashed `_last_shadow` / `_last_ml` state is written under one phase, and a subsequent `record_verdict` on that same thread reads it under the next phase — mixing MODEL_PRIMARY shadow evidence into a ML_SHADOW-era outcome record. Gate math then pairs records across a phase boundary it shouldn't.
- **Impact**: Subtle corruption of the record-phase provenance. Also: `config` is a `@dataclass` (not frozen), so `config.starting_phase = target` is not atomic on CPython across threads in theory — in practice CPython attribute assignment is atomic under the GIL, but multi-field updates are not. Worse, `advance()` calls `self._storage.load_records()` then mutates phase based on a snapshot — if another thread appends records between the load and the mutation, the decision is on stale data. Not a correctness bug (the gate will re-evaluate next call) but an auditability one: telemetry fires with `from=current, to=target, paired_sample_size=n` where `n` is now stale.
- **Impact**: Surfaces in any operator workflow that runs `advance()` on a periodic background job while classify() is live.
- **Fix**: Serialize `advance()` and `_classify_impl` under the same `self._lock`. Document that `advance()` is a synchronization point.

### F4. `ResilientStorage` degraded-mode state is entirely unlocked
- **Location**: `src/dendra/storage.py:822-968`
- **Severity**: **HIGH**
- **Scenario A (double-enter)**: Two threads call `append_record` concurrently while primary is failing. Both see `_degraded=False`, both hit the `except`, both call `_enter_degraded()`. First one sets `_degraded=True` and fires `on_degrade`; second one returns early via the `if self._degraded: return` guard. BUT between the two `self._degraded` reads, both have already passed the outer `if not self._degraded:` and both will fall through to the fallback append. First alert fires; second is lost.
- **Scenario B (drain-vs-append)**: `_try_recover()` is called from one thread during an append; it iterates `self._tracked_switches` and for each switch it (a) loads fallback records, (b) re-appends them to primary, (c) calls `_clear_fallback_for(switch_name)` which `del log[switch_name]`. Meanwhile, Thread B calls `append_record` for the same switch, sees the (stale) `_degraded=True`, writes to fallback. Three bad outcomes are possible:
    1. B's write lands in fallback *after* (a) loaded it and *before* (c) cleared it → the write is silently deleted.
    2. B's write lands between (c) clearing the dict and `_degraded=False` → the write stays in fallback but `load_records` will still return it (OK), but the next `_try_recover` won't re-enter because `_degraded=False` → fallback record is orphaned until the next degraded episode.
    3. Mid-drain failure leaves fallback partially cleared; on retry, records are replayed to primary twice (no dedup) → duplicated outcomes in the log, which silently inflate gate statistics.
- **Scenario C (recovery-vs-degrade flip-flop)**: `_try_recover` completes, sets `_degraded=False`, but before the writes_since_probe reset, a new append fails. The next thread sees `_degraded=False`, tries primary, fails, calls `_enter_degraded`. Two warnings fire in rapid succession; the `degraded_since` timestamp bounces.
- **Impact**: This is the "classification hot path durability" primitive. Silent record loss here defeats its entire purpose. And the duplicate-replay on partial-drain failure is a real correctness bug for the downstream gate math.
- **Fix**:
  1. Add `self._lock = threading.Lock()` to `ResilientStorage.__init__`. Guard every state mutation (`_degraded`, `_degraded_since`, `_degraded_writes`, `_writes_since_probe`, `_tracked_switches`) under it.
  2. `append_record` should take the lock, decide the target (primary or fallback), release the lock, do the IO. If IO fails, re-acquire and update state.
  3. `_try_recover` should snapshot tracked_switches under the lock, then drain without the lock (to avoid holding it during IO), then re-acquire to clear fallback and flip `_degraded`.
  4. Dedup: track which records have been re-appended within a drain attempt, so partial-failure retry doesn't double-write. Easiest is to drain all-or-nothing per switch (current code already does this for the `_clear_fallback_for` step — the gap is between load and clear).

### F5. In-memory storage backends are not thread-safe, but are the default
- **Location**: `src/dendra/storage.py:194-260` (`InMemoryStorage`, `BoundedInMemoryStorage`)
- **Severity**: **MEDIUM**
- **Scenario**: `BoundedInMemoryStorage` is installed automatically when the user omits `storage=` (`core.py:510-512`). Its `append_record` does `buf = self._log.get(switch_name); if buf is None: buf = deque(...); self._log[switch_name] = buf; buf.append(record)`. Two threads concurrently calling `append_record` for a brand-new switch can both see `buf=None`, both create deques, both assign → one deque and its record are silently lost. `deque.append` is atomic on CPython so same-deque contention is safe, but the lazy-init is not. Similarly, `_log.setdefault(...).append(...)` in `InMemoryStorage` is safe for the setdefault but the append to an already-existing list is not atomic for list mutations at the level that matters for iteration (load_records snapshots into a new list — race is that the snapshot can capture a partially-appended record? On CPython, list.append is atomic but iteration concurrent with mutation can still raise).
- **Impact**: First-N-records-per-switch can be lost under concurrent append, especially in bursty-startup workloads. Medium-severity because the storage docstrings do say "not thread-safe" — but the default install is implicit, so users won't see that warning.
- **Fix**: Add `threading.Lock()` to both in-memory backends. Cost is negligible (single hash lookup + append is microseconds). Keep the docstring note as "thread-safe by internal lock; multi-process requires an external backend."

### F6. `_SWITCH_REGISTRY` lock scope is correct, but the collision check has a TOCTOU window
- **Location**: `src/dendra/core.py:325-328, 520-537`
- **Severity**: **LOW**
- **Scenario**: The existing code does `with _SWITCH_REGISTRY_LOCK: existing = registry.get(key); ... registry[key] = self` inside the same `with` block — this IS correctly scoped. HOWEVER: it's a `WeakValueDictionary`, which means a switch that's been GC'd but not yet cleared from the dict can cause a transient false-positive collision, or more subtly: thread A checks and finds no existing entry, B checks and finds no existing entry (A hasn't added yet), … wait, no, the `with` block covers both the check and the insert, so that's fine. The real sub-issue: `id(self._storage)` is only unique for *live* objects. If a storage object is GC'd and its id is reused for a new one, a stale registry key could ghost-collide. In practice this is vanishingly rare and the WeakValueDictionary clears on GC of the switch (not the storage).
- **Impact**: Essentially none in normal operation. Could surface as flaky test failures if tests recreate many switches without explicit storage= and the GC replays ids.
- **Fix**: None required for v1. Note in a comment that `id()` may collide post-GC and the WeakValueDictionary handles the switch lifetime. Optionally: key the registry by `weakref(storage)` instead of `id(storage)` — but only if this becomes a real pain point.

### F7. Telemetry emission outside `_classify_impl` can observe stash state that's about to be clobbered
- **Location**: `src/dendra/core.py:590-604` (classify), `606-637` (dispatch)
- **Severity**: **LOW**
- **Scenario**: `classify()` calls `_classify_impl`, then sets `self._last_action = None`, then emits telemetry reading `result.*`. If another thread runs `classify` between the impl and the telemetry, `self._last_*` is clobbered — but telemetry only reads `result.*` (local), so this is fine. The real risk is if a subclass or user telemetry emitter reads `switch._last_*` in its `emit()` callback. Currently no shipped emitters do this.
- **Impact**: None in v1 shipped code. Worth flagging in developer docs if we ever document the telemetry contract as "don't read stash state from emit()".
- **Fix**: Document that telemetry emitters must be pure / read-only w.r.t. switch state.

### F8. FileStorage / SqliteStorage cross-process locking — correctness review
- **Location**: `src/dendra/storage.py:474-497` (FileStorage append), `src/dendra/storage.py:717-730` (SqliteStorage append)
- **Severity**: **LOW (informational)** — existing design is correct.
- **Review findings**:
  1. `FileStorage.append_record` takes the exclusive flock, does the stat-then-rotate-then-open+write+fsync under the lock. Correct. The `os.open` + `os.write` + `os.fsync` + `os.close` sequence is atomic within the lock.
  2. `_rotate` is called only under the exclusive lock or via `compact()` which takes the lock itself. Correct.
  3. `load_records` takes the shared flock, walks segments. Correct for multi-reader-single-writer; a reader can race with a rotation that's about to happen next, but since rotation happens under exclusive (which blocks shared), this is correctly serialized.
  4. Gap: `_FileLock.__enter__` does `self._path.parent.mkdir(...)` then `os.open(..., O_RDWR|O_CREAT)` then `flock`. If the directory is deleted between the mkdir and the open (another process doing cleanup) you get EACCES. Theoretical; not worth fixing.
  5. `SqliteStorage._connect` opens a fresh connection per call. This is the standard idiom for thread-safe SQLite + WAL. Correct. The `PRAGMA journal_mode=WAL` is re-issued per connection; that's idempotent. `PRAGMA busy_timeout=30000` is set — good, eliminates `database is locked` errors under contention. `BEGIN IMMEDIATE` correctly serializes writers.
  6. Gap: `SqliteStorage.__init__` calls `_init_schema()` which opens a connection; if two processes init simultaneously on a fresh DB, both will `CREATE TABLE IF NOT EXISTS`. SQLite handles this (WAL + BEGIN IMMEDIATE), so it's fine.
- **Conclusion**: Cross-process storage primitives are sound. Ship them. Only gaps are the in-process `_LearnedSwitch` layer (F1–F5).

### F9. Telemetry emitter `ListEmitter` is not thread-safe
- **Location**: `src/dendra/telemetry.py:54-62`
- **Severity**: **LOW**
- **Scenario**: `ListEmitter.emit` does `self._events.append(...)`. `list.append` is atomic on CPython, so concurrent appends are safe in practice. However, if anything reads `ListEmitter.events` while another thread is mid-append, iteration may observe an inconsistent state.
- **Impact**: Test-only use.
- **Fix**: Document "test-only, not thread-safe for concurrent read+append." Add a lock if it becomes a real issue.

### F10. `advance()` read-then-mutate is not serialized against `record_verdict()`
- **Location**: `src/dendra/core.py:1016-1020`
- **Severity**: **MEDIUM**
- **Scenario**: `advance()` loads records via `self._storage.load_records(self.name)`, gate evaluates, then sets `config.starting_phase = target`. Between the load and the mutation, another thread may call `record_verdict()` — the new record was observed under the old phase but the switch is now in the new phase. This is *correct* in the sense that the record's `phase` isn't stored on the record (good) — but the gate decision's `paired_sample_size` and `p_value` in telemetry are already stale by microseconds. Operator drilling into the telemetry event may find `n+1` records when the event says `n`. Auditability issue, not correctness.
- **Impact**: Auditor confusion.
- **Fix**: Either hold the lock across load+evaluate+mutate+emit (simple, safe), or include a record-log snapshot hash in the telemetry payload so operators can replay the exact evaluation. Start with option 1.

## Test-coverage gaps

The tests exercise **cross-process** storage concurrency well (`TestMultiProcessWriters`, `test_concurrent_reads_during_writes`). They do **not** exercise:

1. **Multi-threaded classify on a single switch**. Zero tests spin up threads calling `classify()` or `dispatch()` in parallel.
2. **Interleaved classify + record_verdict across threads**. This is the F1 killer scenario and is entirely uncovered.
3. **advance() racing classify()**. No test calls `advance()` on one thread while another is classifying.
4. **Circuit-breaker race**. No test trips and resets the breaker concurrently with classify calls.
5. **ResilientStorage under threads**. `test_resilient_storage.py` is all single-threaded. No test covers: two threads hitting degraded-mode transition simultaneously; `_try_recover` draining while another thread appends; partial-drain retry dedup.
6. **Shadow stash contamination**. No test calls classify on input A, classify on input B, then record_verdict(input=A, ...) and asserts the stash semantics (will the record carry A's or B's shadow?).
7. **BoundedInMemoryStorage concurrent append**. No test covers the lazy-init race for a fresh switch name.
8. **Multi-switch, shared-storage**. The registry prevents same-name collisions, but no test runs two *different-named* switches against the same SqliteStorage concurrently to confirm schema isolation.
9. **Async compatibility**. No test wraps `classify` in `asyncio.to_thread`, runs N concurrent coroutines, and verifies outcome-log integrity. Given the library ships no async adapters, this is a future concern — but the docs should explicitly say "use `asyncio.to_thread(switch.classify, input)` and ensure classify+record_verdict happen in the same thread-bound coroutine until F1 is fixed."

## Recommended chaos tests

Add to `tests/test_concurrency.py` (new file):

```python
# 1. Shadow-stash contamination (would fail today)
def test_classify_record_interleave_does_not_cross_contaminate(...):
    """Fixture: MODEL_SHADOW switch with a deterministic rule that maps
    input i → f'r{i}' and a model that maps input i → f'm{i}'. Two
    threads each run 1000 iterations of (classify(i), record(i, f'r{i}',
    correct)). Assert: every record's rule_output matches its input's
    expected r{i} and model_output matches its expected m{i}. Failure
    would prove F1."""

# 2. Breaker reset race
def test_breaker_reset_races_with_classify_ml_failure(...):
    """ML_PRIMARY switch, ml_head.predict always raises after the 100th
    call. Thread A: loop classify. Thread B: after seeing circuit
    trip, call reset_circuit_breaker(). Assert: status().circuit_breaker_tripped
    faithfully reflects whether a classify call observes ML failures
    after a reset. Currently racy."""

# 3. advance() during classify
def test_advance_concurrent_with_classify_preserves_record_integrity(...):
    """Seed a switch with 500 paired correct-outcome records meeting
    McNemarGate's min_paired. Thread A: classify+record in a tight
    loop. Thread B: sleep(0.01); advance(); sleep(0.01); advance().
    Assert: every record's source+phase fields are consistent with
    some linearization of classify and advance calls. No record has
    phase=MODEL_PRIMARY with ml_output set (wrong-phase shadow leak)."""

# 4. ResilientStorage degraded-mode chaos
def test_resilient_storage_drain_vs_append_no_loss(...):
    """FlakyStorage that fails the first N appends then recovers. 8 threads
    hammer append_record concurrently for 1000 records each. Assert:
    load_records returns exactly 8000 records, none duplicated, none
    missing. Currently will likely lose records in scenario B."""

def test_resilient_storage_concurrent_enter_degraded_fires_once(...):
    """Two threads observe the same primary-IO failure. Assert: on_degrade
    callback fires exactly once, warnings.catch_warnings captures exactly
    one warning. Currently will fire twice."""

# 5. BoundedInMemoryStorage init race
def test_bounded_in_memory_concurrent_first_append_no_loss(...):
    """Spawn 32 threads, each calling storage.append_record(switch_name,
    unique_record) for a switch_name that has never been written.
    Assert: load_records returns 32 records, all distinct."""

# 6. Multi-switch shared SqliteStorage
def test_sqlite_storage_multi_switch_concurrent_isolation(...):
    """One SqliteStorage backing two switches 'a' and 'b'. 4 threads
    write to 'a', 4 to 'b', 1000 each. Assert: load_records('a') has
    4000 a-records, load_records('b') has 4000 b-records, no crossover."""

# 7. End-to-end stress (the 'will it melt' test)
def test_switch_hot_path_1M_ops_100_threads(...):
    """LearnedSwitch backed by SqliteStorage + ResilientStorage, 100
    threads, each runs 10_000 (classify, record_verdict) pairs with
    a flaky model (10% exception rate) and a flaky storage (1% failure,
    recovers after 50 ops). Assert: total records ~= 1M (within 0.1%
    tolerance for explicit-loss categories), no raised exceptions in
    caller threads, status() is internally consistent."""
```

Add a `@pytest.mark.concurrency` marker and wire it to a dedicated job in `.github/workflows/` — these tests are higher-flake-risk and slower; don't run them on every PR, do run them on pre-release. Each chaos test should use `ThreadPoolExecutor` with `max_workers=N` and collect exceptions via `future.result()` to avoid swallowing.
