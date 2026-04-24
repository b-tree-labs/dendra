# Test-quality audit (v1 readiness)

## Summary

**Verdict: adequate, not rigorous.** The suite is well-structured and behavior-oriented — it's not theatrical green-bar work. Branch coverage is 80% overall, and the critical paths (gates, phases, storage durability, security invariants) have substantive tests with real assertions. But there are two load-bearing holes that ship blockers should address *before* v1:

1. **Zero concurrency tests on `LearnedSwitch`.** The concurrency audit (`docs/working/v1-audit-concurrency.md`) flagged shadow-stash cross-contamination (CRITICAL), circuit-breaker race (HIGH), `advance()`-mid-classify race (HIGH), and `ResilientStorage` unlocked state (HIGH). The test suite does not exercise any of them. `grep threading` on `tests/` returns nothing for the hot path.
2. **Auto-record / on_verdict hook has narrow tests** (`tests/test_auto_record_and_verdict.py` — 12 tests total). No interleave with graduation, no interaction with ResilientStorage degraded mode, no on_verdict + auto_advance simultaneously, no behavior under storage failure.

The suite is good at *unit-level* invariants. It is weak at *system-level* interactions, which is where v1 regressions will come from.

## Coverage numbers (pytest --cov --cov-branch)

| Module | Stmts | Miss | Branch | BrPart | Cover |
|---|---|---|---|---|---|
| `__init__.py` | 9 | 0 | 0 | 0 | **100%** |
| `analyzer.py` | 310 | 40 | 138 | 16 | 84% |
| `benchmarks/rules.py` | 57 | 0 | 22 | 0 | **100%** |
| `cli.py` | 154 | 39 | 34 | 4 | **71%** ← weak |
| `core.py` | 456 | 32 | 140 | 10 | 92% |
| `decorator.py` | 31 | 2 | 0 | 0 | 94% |
| `gates.py` | 157 | 15 | 50 | 6 | 89% |
| `ml.py` | 68 | 48 | 28 | 3 | **24%** ← sklearn adapter (opt-in) |
| `models.py` | 106 | 77 | 16 | 1 | **25%** ← LLM adapters (opt-in) |
| `research.py` | 125 | 55 | 34 | 2 | **50%** ← ML-head path untested |
| `roi.py` | 92 | 0 | 4 | 0 | **100%** |
| `storage.py` | 355 | 28 | 88 | 13 | 90% |
| `telemetry.py` | 23 | 4 | 2 | 1 | 80% |
| `viz.py` | 126 | 41 | 46 | 5 | **67%** ← plot rendering |
| `wrap.py` | 88 | 2 | 34 | 2 | 95% |
| **TOTAL** | **2159** | **383** | **636** | **63** | **80%** |

Modules below 80% on load-bearing code: `cli.py` (71%) and `research.py` (50%). The `ml.py`/`models.py` numbers are fine — those are provider adapters behind `pytest.importorskip`.

## Strong tests (keep as-is; real safety net)

1. `tests/test_storage_hardening.py:180` — `test_no_data_loss_under_contention` — 4 spawn-based processes × 250 records under `flock`. Real multi-writer contention. High mutation-survival: break the flock → test fails.
2. `tests/test_storage_hardening.py:206` — `test_no_data_loss_with_frequent_rotation` — forces mid-flight rotation under contention. Canary for the rotation-race fix.
3. `tests/test_sqlite_storage.py:134` — `test_no_data_loss_under_contention` — same shape for SqliteStorage + WAL. Both backends tested the same way is a real quality signal.
4. `tests/test_gates.py:137` — `test_advances_when_target_beats_current` — McNemar with 300 constructed paired records and a real chi-squared p-value assertion. Would catch off-by-one in the contingency matrix, incorrect p-value computation, or a reversed `<` comparison.
5. `tests/test_gates.py:552` — `test_advance_on_real_records_with_mcnemar` — end-to-end: real records in real storage, real gate, assert phase actually mutates. The whole-graduation integration test.
6. `tests/test_security.py:182` — `test_ml_exception_trips_breaker_and_stays_tripped` — exercises the real breaker sticky behavior. Would catch any regression that accidentally auto-resets the breaker.
7. `tests/test_resilient_storage.py:121` — `test_recovery_drains_fallback_to_primary` — full degrade → heal → probe → drain cycle with callback assertions.
8. `tests/test_output_safety.py:195` — `test_broken_moderator_cannot_block_output` — proves shadow exceptions cannot reach the caller under real LLM failure.
9. `tests/test_gates.py:538` — `test_auto_advance_gate_exception_does_not_break_record` — proves a broken gate cannot take down `record_verdict`.
10. `tests/test_viz.py:233` — `test_ml_strictly_better_yields_small_p` — McNemar p-value implementation tested against known numerical ground truth.

## Weak tests (rewrite or delete before v1)

1. `tests/test_gates.py:91` — `test_walks_the_lifecycle` — **tautology against `_PHASE_ORDER`**. If someone breaks `next_phase()` by removing a phase from the tuple, this test fails — but it also fails if they rename a phase in exactly the same way in both places. Mutation survival is low (a subtle phase-skip bug would pass the check). **Fix**: add one property-based test (`hypothesis`) asserting `next_phase` is monotone and that `list(Phase)` round-trips.
2. `tests/test_llm_shadow.py:81` — `test_prediction_has_label_and_confidence` — **tautology**. Constructs `ModelPrediction("bug", 0.9)` and asserts `.label == "bug"` and `0 <= conf <= 1`. Tests the dataclass, not any code. **Fix**: delete, or replace with a round-trip that passes through the real code path.
3. `tests/test_llm_shadow.py:54` — `test_six_phases_present` — **tautology re-stating the enum definition**. Duplicates what the `Phase(Enum)` declaration already enforces at import time. **Fix**: delete.
4. `tests/test_analyzer.py:42` — `test_if_elif_string_returns_matches` + siblings (P2-P6) — the corpus and the pattern checker are written in the same PR. The test asserts "the checker finds this hand-written snippet" which is a restatement of the implementation. **Symptom**: `assert s.pattern in ("P1", "P4")` — the test itself admits it doesn't know which pattern should fire. **Fix**: one realistic third-party classifier captured from the wild (e.g. `requests` library's status-code dispatch) per pattern, asserting the *label set* and *regime* only — not the pattern ID.
5. `tests/test_llm_shadow.py:77` — `test_fake_llm_satisfies_protocol` — **duplicates the Protocol's runtime check** (`@runtime_checkable`). The isinstance check is what `runtime_checkable` already guarantees. **Fix**: delete.
6. `tests/test_storage_hardening.py:105` — `TestStorageBaseABC.test_cannot_instantiate_without_overrides` — **tests Python's `abc` machinery, not our code**. **Fix**: delete.
7. `tests/test_labels_dispatch.py:123` — `test_label_without_on_does_not_dispatch` — **asserts no action fired**, which is the empty-set restatement. Survives a mutation that removes the entire dispatch machinery. **Fix**: strengthen — assert the dispatch path is exercised but returns `None`, or merge into the positive test.
8. `tests/test_core.py:158` — `test_defaults` — reads the dataclass defaults and re-asserts them. Survives any refactor that keeps the defaults. **Fix**: either delete (the defaults are in README and CHANGELOG — those are the contract) or re-frame as a changelog-tied regression test with a comment pointing to the changelog entry.
9. `tests/test_core.py:163` — `test_config_attached_to_switch` — **tests that `.config` is stored on the instance**. Restatement of the `__init__` signature. **Fix**: delete or merge with a test that actually uses the config.
10. `tests/test_decorator.py:23-74` — The entire `TestDecoratorBehavior` class is thin: each test invokes the decorator, calls one method, asserts the delegation worked. **Mutation survival low** — replace the decorator body with a pass-through and most of these still pass. **Fix**: one end-to-end test that exercises classify → verdict → status through the decorator and asserts specific values at the end.

## Brittle tests (will fail on innocent refactors)

1. `tests/test_analyzer.py:51` — `assert s.fit_score >= 4.0` — the `4.0` magic number is the analyzer's current scoring constant. Any tuning of the fit-score weights will break it without indicating a real regression. **Fix**: assert monotonic ordering relative to another snippet, not an absolute number.
2. `tests/test_wrap.py:85` — `assert result.modified_source.startswith("from dendra import ml_switch, Phase, SwitchConfig\n")` — exact-string match on the generated import line. Adding one export breaks it. **Fix**: parse the generated source and assert `ml_switch`/`Phase`/`SwitchConfig` are importable names.
3. `tests/test_resilient_storage.py:105,227` — asserts on warning substring (`"primary backend failed"`). Changing the wording breaks the test. Mild — warnings are part of the operator contract, but tie to the message key not the exact prose.
4. `tests/test_gates.py:164,263` — asserts on `d.current_accuracy == pytest.approx(0.40)` with a hand-computed expected. If the gate's accuracy definition ever changes (e.g. include UNKNOWN rows) these break innocuously. **Fix**: assert on the *delta*, not the absolute.
5. `tests/test_storage.py:76-77` — `assert '"label": "bug"' in lines[0]` — exact substring on the JSONL format. A future compact encoding change (sorted keys, no spaces) breaks it. **Fix**: parse the line as JSON.
6. `tests/test_gates.py:330` — `assert "✗" in d.rationale` — ties test to an emoji in the rationale. **Fix**: assert `d.advance is False` only (already covered) or parse a structured `rationale_parts` field.
7. `tests/test_cli.py:44-185` — many CLI tests assert on exact output substrings ("Dendra static analyzer", "Dendra-fit", "Projected annual value"). Any help-text rewording breaks them. **Fix**: use `--format json` for the assertions; keep text-render tests as smoke only.

## Coverage gaps (features without real tests)

Severity-ordered.

**1. Concurrency (flagged CRITICAL + HIGH in concurrency audit, zero test coverage).**
- No test for simultaneous `classify()` + `record_verdict()` interleave → F1 shadow-stash bug passes silently today.
- No test for `reset_circuit_breaker()` racing with in-flight classify → F2.
- No test for `advance()` racing with `classify()` → F3.
- No test for two threads tripping the circuit breaker concurrently.
- No test for `ResilientStorage` under threaded append load → F4.
- **Recommendation**: add `tests/test_concurrency.py` with 6–8 tests using `ThreadPoolExecutor` + `concurrent.futures`. See "Recommended additions" below for exact shapes.

**2. `auto_record=True` interaction with non-default paths.**
- `tests/test_auto_record_and_verdict.py` covers auto-record with default (bounded in-memory) storage only. No test with `persist=True`, no test with `ResilientStorage` degraded mode, no test where the on_verdict hook raises *during* auto-logging (the existing test covers the explicit `record_verdict` path).

**3. `on_verdict` hook — 3 tests (`tests/test_auto_record_and_verdict.py:125-150`).**
- No test for what happens when the hook is slow (blocks `record_verdict`?).
- No test that the hook receives a record with all fields populated (rule_output, model_output, ml_output, action_*) when available.
- No test that the hook fires exactly once per `record_verdict` call under auto_advance=True.

**4. `verdict_for` context manager.**
- 4 tests. Missing: `verdict_for` with `auto_record=True` (does it double-log?). Missing: `verdict_for` + shadow observation under Phase.MODEL_SHADOW (does the shadow stash leak across blocks?). These interact directly with the F1 concurrency bug.

**5. `MinVolumeGate` / `AccuracyMarginGate` / `CompositeGate`.**
- Each gate has 3–6 tests covering happy path + construction validation. Missing: `CompositeGate.all_of([CompositeGate.any_of([...]), ...])` — nested composition. Missing: a gate that raises from `evaluate()` inside a composite — does the composite swallow or propagate? Missing: delegate's `GateDecision` fields are correctly forwarded through `MinVolumeGate` (today only `rationale` is asserted).

**6. `research.py` — 50% coverage.** The 3 existing tests exercise the rule-only path. The ML-head-trained path (`research.py:258-353`) is completely uncovered — that's where the `retrain_every` + `fit()` + `predict()` loop lives, which is the core of the whole transition-curve story.

**7. `cli.py` — 71% coverage.** Uncovered lines include error-handling branches (43-96 in `dendra init` error dispatch, 101-117 in legacy flag handling). If we promise the CLI is a public contract, these need tests.

**8. `plot_transition_curves` rendering paths (`viz.py:183-244`) — zero coverage.** The smoke test invokes the function but none of the styling / multi-run / crossover-annotation branches are asserted.

## Recommended additions (high mutation survival, ship before v1)

Ordered by what a v1 regression is most likely to look like.

```python
# tests/test_concurrency.py — NEW FILE

def test_shadow_stash_survives_threaded_interleave():
    """F1: two threads classifying + recording must not cross-contaminate."""
    # 8 threads × 100 (classify + record_verdict) cycles on the same switch,
    # each thread records its own input → label mapping; assert every log row's
    # input matches its label per the per-thread mapping. Currently FAILS.

def test_circuit_breaker_reset_is_atomic():
    """F2: reset_circuit_breaker + in-flight classify must not leave breaker
    in an inconsistent state."""

def test_advance_during_classify_is_serialized():
    """F3: advance() mid-classify must not mix phase-branched stash state."""

def test_resilient_storage_threaded_degrade_enter_recover():
    """F4: 4 threads appending while primary flaps must not double-fire
    on_degrade or lose records."""
```

Each of these is 20–40 lines and directly tests a bug the concurrency audit already identified. Land the fixes + tests together.

```python
# tests/test_auto_record_and_verdict.py — ADDITIONS

def test_auto_record_interacts_with_resilient_storage_degradation():
    """auto_record + primary storage failure → record lands in fallback."""

def test_on_verdict_receives_fully_populated_record_at_phase_ml_shadow():
    """Hook gets rule_output + model_output + ml_output in ML_SHADOW phase."""

def test_verdict_for_plus_auto_record_does_not_double_log():
    """verdict_for() block with auto_record=True must not produce 2 rows."""
```

```python
# tests/test_gates.py — ADDITIONS

def test_composite_any_of_inside_all_of_composes_correctly():
    """Nested CompositeGate: all_of([any_of([A, B]), C])."""

def test_composite_propagates_delegate_exception():
    """If a sub-gate raises, CompositeGate behavior is documented and tested."""

def test_min_volume_gate_forwards_all_decision_fields():
    """MinVolumeGate must forward p_value, paired_sample_size, *_accuracy,
    not just advance + rationale."""
```

```python
# tests/test_research.py — ADDITIONS

def test_run_transition_curve_with_real_ml_head_retrains_at_interval():
    """Exercises the uncovered retrain_every loop — the core research path."""

def test_ml_accuracy_populated_on_checkpoints_once_ml_trained():
    """ml_accuracy must go from None → float after first retrain."""
```

### Cheap wins (can ship in a single PR)

- Delete the ~6 tautological tests listed in "Weak tests" 1/2/3/5/6/9. They cost maintenance, signal nothing.
- Swap exact-string assertions for JSON parsing in `test_storage.py:76-77`, `test_wrap.py:85`. 5 lines each.
- Add a `conftest.py` fixture `switch_under_concurrent_load` that spins up a `ThreadPoolExecutor` and yields — unlocks the concurrency test file without 40 lines of boilerplate per test.

### Don't worry about (ship as-is)

- `ml.py` / `models.py` 24–25% coverage — that's all optional provider adapters behind `importorskip`. Users who plug in sklearn or openai get real integration coverage in their own test suites.
- Benchmark tests (`test_benchmark_loaders.py`, `test_latency.py`) — these are non-blocking and `pytest.mark.benchmark`-opt-in.
- `viz.py` plot rendering — smoke-covered, visual diffing correctly scoped out.

## Bottom line

The suite catches *most* regressions to the core classify/record/advance/gate logic. It does **not** catch concurrency regressions, which is the largest known source of real v1 bugs (per the concurrency audit). Before v1 ships: add `tests/test_concurrency.py` (4 tests, ~150 lines) and delete the ~6 tautological tests listed above. Everything else can wait for v1.1.
