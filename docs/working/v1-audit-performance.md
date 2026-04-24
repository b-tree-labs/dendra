# Performance audit (v1 readiness)

Audit date: 2026-04-24
Auditor: performance sweep against `main`
Hardware: local dev machine, Python 3.14.3 (CPython), warmed caches
Command: `pytest tests/test_latency.py -m benchmark -v -s`

## Summary

The README's **classify-side** latency claims are **directionally defensible but numerically stale and mixed-apples-with-oranges**. On this machine the bare Python keyword rule measures 0.17 µs p50 (README: 0.12 µs), and Dendra's switch at Phase.RULE measures 1.08 µs p50 (README: 0.62 µs, "5× overhead"). The shape of the claim — "switch overhead is single-digit-microseconds, dominated by rule work once ML is in the path" — holds; the **specific numbers do not**, and no test enforces them (the only assertion is `p50 < 20 µs`). The biggest honest-to-god hotspot is **not** `classify()`: it is `record_verdict()` on any durable backend (FileStorage ~1.4 ms/call, Sqlite ~1.1 ms/call, FileStorage+fsync ~1.9 ms/call) — **three orders of magnitude slower than classify**. Users who enable `persist=True` pay this on every outcome write. That is architecturally fine (outcome logging is off the decision path), but it deserves a README sentence so nobody benchmarks `sw.classify(); sw.record_verdict(...)` as a pair and concludes Dendra is slow.

## Verified claims

| README claim | Test | Measured (this run) | Defensible? |
|---|---|---|---|
| Rule call: 0.12 µs p50 | `test_rule_is_submicrosecond` — asserts `< 3 µs`, not `~0.12` | **0.17 µs p50** | Order-of-magnitude yes; exact number no. Hardware-dependent and not pinned by the test. |
| Dendra switch @ Phase 0: 0.62 µs p50 (5× overhead) | `test_phase_rule_overhead_is_small` — asserts `< 20 µs` | **1.08 µs p50** (≈6× over rule on this box) | Shape yes (single-digit µs, O(1×)–O(10×) rule). The specific "0.62 µs / 5×" pair is stale. |
| Real ML head (TF-IDF+LR on ATIS): 105 µs p50 | **Not measured** by `test_latency.py`. The file uses a **synthetic** `_FakeFastMLHead` (simulated via `sum(ord(c)...)`), not a real sklearn pipeline. Assertion: `p50 < 2000 µs`. | Fake head: 0.96 µs p50 | **Not verified in-repo.** The 105 µs number must be sourced from an external benchmark run (likely `tests/test_ml_primary.py` or the ATIS end-to-end). Flag for v1: cite or re-run. |
| Local LLM (llama3.2:1b): ~250 ms p50 | **Hardcoded constant** `llm_p50_us = 250_000` in `test_rule_vs_ml_throughput_report`. No live LLM measurement. | n/a — not measured | Honest in code comments ("we measured ... in an earlier session"), but README presents it as a live number. Acceptable for pre-v1 if caveated. |

Additionally measured, not in README:

| Call | Measured |
|---|---|
| `classify()` default (NullEmitter telemetry) | **0.87 µs p50** |
| `dispatch()` with matching `Label.on` action | 1.71 µs p50 |
| `record_verdict()` on BoundedInMemoryStorage | 1.97 µs |
| `record_verdict()` on FileStorage (fsync=False) | **1,446 µs** |
| `record_verdict()` on FileStorage (fsync=True) | **1,874 µs** |
| `record_verdict()` on SqliteStorage | **1,103 µs** |
| `record_verdict()` on ResilientStorage(FileStorage), healthy | 1,447 µs (zero overhead over primary) |
| `McNemarGate.evaluate()` on 100k records | 26.5 ms |
| `switch.status()` on 10k records (3-pass loop) | 1.51 ms |

Running on: Python 3.14.3 CPython, macOS Darwin 25.4.0.

## Unverified / undocumented performance characteristics

1. **ML-head p50 (105 µs)** is not exercised by any in-repo benchmark. `tests/test_latency.py` deliberately uses a synthetic head ("Deterministic for timing"). The number must be regenerated from `tests/test_ml_primary.py` or a live ATIS run before v1 claims it.
2. **Telemetry overhead.** `classify()` wraps its emit in `try/except Exception: pass` every call. With `NullEmitter` this is free; with a real emitter (e.g. a Prometheus exporter), cost is user-backend-dependent and undocumented.
3. **Storage-backend-vs-classify ratio.** Nobody benchmarks `classify + record_verdict` as a pair, so the README's "5× overhead" comparison is incomplete: with `persist=True`, the combined call jumps from ~1 µs to ~1,500 µs (**three orders of magnitude**), dominated entirely by the outcome log, not the switch itself.
4. **Dispatch action timing.** `_maybe_dispatch` always calls `time.perf_counter()` twice per labeled dispatch, even when the action is trivial. This is fine but unmeasured.
5. **`_derive_author` stack walk.** Done once at construction (not hot path), but untested for cost — relevant only if users construct switches per-request (an anti-pattern we should warn against).

## Hotspots

### Hotspot 1 — FileStorage append = new file descriptor per call

- **Location**: `src/dendra/storage.py:474-497` (`FileStorage.append_record`)
- **Cost**: **~1.4 ms per call** (fsync=False), ~1.9 ms (fsync=True)
- **Scope**: Not on the classify path. **Is** on the outcome-log path, which fires on every `record_verdict()`. At 1k outcomes/sec that is a CPU core burned on file-open overhead.
- **What it does per call**: `mkdir(parents=True, exist_ok=True)` → flock (exclusive) → `path.stat()` for rotation check → `os.open()` with O_WRONLY|O_CREAT|O_APPEND → `os.write()` → optional `os.fsync()` → `os.close()` → flock release. That is ≥4 syscalls and a mkdir stat-check per write.
- **Remediation**:
  - Cheap: cache `self._switch_dir(name).exists()` after first write so we skip `mkdir` on the hot path (probably saves 50–200 µs).
  - Medium: keep the fd open between writes, flock once per fd. Standard append-log pattern. Brings per-write down into the tens of microseconds on a local SSD.
  - Architectural (already there): recommend `SqliteStorage` for production — it is faster *and* crash-safe.

### Hotspot 2 — SqliteStorage connects-per-call

- **Location**: `src/dendra/storage.py:717-730` (`SqliteStorage.append_record`) and `_connect` at 678-698
- **Cost**: **~1.1 ms per call** — dominated by `sqlite3.connect()` + 3× `PRAGMA` setup.
- **Scope**: outcome-log path. Same as above — not classify, but every `record_verdict()`.
- **Why this design**: the docstring explicitly calls it out — "A fresh connection is opened per call; no shared-connection thread-safety concerns." This is a correctness choice, not an oversight.
- **Remediation**:
  - Cheap: run `PRAGMA journal_mode=WAL; PRAGMA synchronous=...; PRAGMA busy_timeout=...` only once at `_init_schema()` time (WAL mode persists in the file; synchronous persists **per connection** so this one stays), dropping 2 of the 3 PRAGMAs per call. Marginal win (~10–50 µs).
  - Medium: thread-local connection pool (`threading.local()`). Removes `connect()` entirely from the hot path. Keep the "fresh connection" policy as opt-in for unusual sandboxes.
  - Architectural: accept the ~1 ms per outcome as fine for production (outcome-write throughput caps at ~900/sec/process, well above real classify rates after rule matches).

### Hotspot 3 — `record_verdict()` allocates a full dataclass + hits `time.time()` always

- **Location**: `src/dendra/core.py:871-949`
- **Cost**: ~2 µs on BoundedInMemoryStorage. Dominated by `ClassificationRecord(...)` construction (13 fields) and the set-comprehension `{o.value for o in Verdict}` built on **every call**.
- **Scope**: always runs when the user records an outcome.
- **Remediation**:
  - Cheap: hoist `_VALID_VERDICTS = frozenset(o.value for o in Verdict)` to module level. Saves ~100–300 ns per call.
  - Cheap: the `try/except Exception: pass` around `self._telemetry.emit` inside `classify`, `dispatch`, and `record_verdict` is fine for safety but allocates an exception-frame on every call when telemetry is `NullEmitter`. Consider `if isinstance(self._telemetry, NullEmitter): pass else: ...` — no measurable difference today but removes a branch.

### Hotspot 4 — `McNemarGate.evaluate()` walks the full log

- **Location**: `src/dendra/gates.py:220-280`, via `_paired_correctness` at line 127
- **Cost**: **26.5 ms at 100k records**. Linear in log size — a single pass, one `getattr` per record per source field.
- **Scope**: not on the classify path. Runs on `sw.advance()` (operator-initiated or periodic background job). At 100k records, 26 ms is cheap; at 10M records, it is ~2.6 s, still fine for a background job.
- **Remediation**: none needed for v1. If users ever hit M-row logs, add an incremental streaming gate. Document the linear-scan cost in the class docstring.

### Hotspot 5 — `status()` does three full passes over the outcome log

- **Location**: `src/dendra/core.py:1040-1076`
- **Cost**: 1.5 ms at 10k records (~150 ns/record × 3 passes: total, shadow, ml).
- **Scope**: dashboard/reporting, not classify.
- **Remediation**: single-pass accumulator. Mostly a readability win, not a performance one.

### Hotspot 6 — `classify()` at Phase.RULE allocates a dataclass every call

- **Location**: `src/dendra/core.py:671-683`
- **Cost**: **~0.5 µs out of the 0.87 µs** classify total is `ClassificationResult(...)` construction + assignment to `_last_rule_output` + `_last_shadow = None`. A `@dataclass(frozen=True)` with 7 fields has no `__slots__` so every call hits `__dict__`.
- **Scope**: core hot path at the common phase.
- **Remediation**:
  - Medium: add `slots=True` to `@dataclass` on `ClassificationResult` and `ClassificationRecord`. Python 3.10+ supports it; requires 3.10 min version bump if we aren't there. Estimated save: 100–200 ns per call.
  - Architectural (for anyone who wants a **1 µs** dendra): a fast path `classify_label(input) -> str` that returns the raw label and skips dataclass construction when the caller doesn't need source/confidence/phase. Already how some microbenchmark-sensitive users hand-inline it.

### Hotspot 7 — `_find_label` is a linear scan inside `dispatch()`

- **Location**: `src/dendra/core.py:571-577`
- **Cost**: O(N_labels) per `dispatch()`. With 150-label CLINC150 that is 150 comparisons per call.
- **Scope**: `dispatch()` hot path only (not `classify()`).
- **Remediation**: cache a `_label_by_name: dict[str, Label]` on label assignment. O(1) lookup. Trivial win for high-cardinality label sets.

## Recommended benchmarks to add

Target: before v1 ship, have a `pytest -m benchmark` suite that **asserts numeric ranges** (not just sanity caps), runs in CI nightly, and regenerates the README numbers. All of these are `pytest-benchmark`-friendly.

1. **`test_classify_phase_rule_matches_readme`**: assert `0.3 µs < p50 < 3 µs` for the Phase.RULE classify. If this fails, the README headline is wrong.
2. **`test_record_prediction_bounded_inmemory`**: assert `p50 < 5 µs` on `BoundedInMemoryStorage`.
3. **`test_record_prediction_file_storage`**: assert `p50 < 3 ms` with `fsync=False`, `p50 < 5 ms` with `fsync=True`. README should cite these.
4. **`test_record_prediction_sqlite_storage`**: assert `p50 < 2 ms`. Document "production default" throughput.
5. **`test_classify_plus_record_combined`**: cite this pair explicitly in README — it is the honest per-outcome cost.
6. **`test_ml_head_real_tfidf_lr_on_atis`**: use the actual trained head, not `_FakeFastMLHead`. This is what validates the "105 µs" claim.
7. **`test_gate_evaluate_linear_scaling`**: run McNemar at 1k / 10k / 100k records, assert linearity. Gives operators a sizing rule.
8. **`test_dispatch_with_large_label_set`**: CLINC150-scale (150 labels). Catches the `_find_label` linear-scan regression if we ever grow the label list further.
9. **`test_resilient_storage_healthy_overhead`**: assert ResilientStorage adds `< 5%` over bare primary when healthy. (Confirmed zero-overhead today; pin it.)
10. **CI wiring**: add a `benchmarks` job to `.github/workflows/ci.yml` that runs `pytest -m benchmark` and publishes JSON to a `benchmark-results/` artifact. Gate on regression vs. last green tag — `pytest-benchmark`'s `--benchmark-compare-fail=mean:10%` is the standard idiom.

### Honest bottom line for v1

The README's classify-side numbers should be **re-measured on the intended release hardware and pinned into the test suite**. The "0.12 µs / 0.62 µs / 5× overhead" story is the right story; the digits are stale. The `105 µs` and `250 ms` numbers are not measured in-repo at all and need either a live test or a dated footnote. None of this is a correctness problem — it is a credibility problem, and cheap to fix before launch.
