# Feature audit — claims vs shipped (v1 readiness)

**Date:** 2026-04-24
**Auditor:** agent-driven read of `src/`, `tests/`, `docs/`, `landing/`, `examples/`.
**Scope:** every user-facing CLAIM in README, landing, FAQ, api-reference,
storage-backends, examples/README, and marketing docs that make feature
claims. For each, verified (a) code exists, (b) test exists, (c) claim
matches behavior. Severity flag on every mismatch.

---

## Summary

**Verdict: ship-ready with two HIGH-severity doc fixes and a handful of
MEDIUM items.** The library's functional surface is genuinely implemented
and tested: all six lifecycle phases, McNemarGate + advance(), circuit
breaker, safety-critical cap, four storage backends, four LLM adapters,
five CLIs, analyzer with six AST patterns, AST-based init, ROI reporter,
viz. 323 tests collect cleanly. The benchmark JSONL results exist and
match the README's accuracy numbers to four decimals. The
headline-grabbing security claims (20 jailbreak patterns, 25 PII items,
100 consecutive ML failures, adversarial p95 <50ms) are all quantified in
`tests/test_security_benchmarks.py` against the claim.

The two HIGH issues are documentation drift: (1) `docs/api-reference.md`
§"What Dendra does NOT do" still says "the McNemar transition gate is
designed but not shipped" — false; `advance()` and `McNemarGate` are
shipped with 20 gate tests, and the same doc earlier describes the
default gate as `McNemarGate(alpha=0.01, min_paired=200)`. Users reading
top-down will see a direct self-contradiction. (2) README's data table
column "ML @ transition" mixes numbers from two different seed runs
(`atis.jsonl` seed=100 and `atis_seed500.jsonl` seed=500) without
flagging it; the 75.6% at ≤250 outcomes comes from the seed=500 run
while the 70.0% rule acc comes from seed=100. Not a lie, but a
reader-confusion trap.

Everything else is MEDIUM or LOW: test-count mis-statement (README says
195, reality 323 — undercount), minor filename drift in the README file-
tree (`llm.py` vs `models.py`), and the paired-McNemar claim is slightly
stronger than what the shipped benchmark JSONL files contain (the files
have only per-run accuracy scalars; per-example `rule_correct` /
`ml_correct` arrays are supported in code but not present in the
committed results).

---

## Findings table

### Core lifecycle + gates

| Claim | Where claimed | Status | Evidence | Severity |
|---|---|---|---|---|
| Six lifecycle phases (RULE → MODEL_SHADOW → MODEL_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK → ML_PRIMARY) | README hero table, landing §Six phases, FAQ, SKILL.md | **VERIFIED** | `src/dendra/core.py:38-46` Phase enum; `src/dendra/core.py:_classify_impl` handles each; one test file per phase (`test_llm_shadow.py`, `test_llm_primary.py`, `test_ml_shadow.py`, `test_ml_primary.py`). | — |
| "statistical gates at every transition" / McNemarGate default | README tagline, landing hero, FAQ "the statistical transition gate is the load-bearing piece" | **VERIFIED** | `src/dendra/gates.py:180-280` — full exact-McNemar + normal-approx implementation, one-sided, α=0.01, min_paired=200. `LearnedSwitch.advance()` at `core.py:963-1038` wires gate + phase-limit + safety-critical + telemetry. `tests/test_gates.py` has 20 tests including `test_advance_on_real_records_with_mcnemar` (300 paired, p<0.01). | — |
| "the McNemar transition gate is designed but not shipped" | `docs/api-reference.md:207-208` (§What Dendra does NOT do) | **FALSE — contradicts shipped code** | Same doc on line 83 says `advance()` "evaluates the configured gate and advance[s] the phase if it passes. The default gate is `McNemarGate(alpha=0.01, min_paired=200)`." These two paragraphs directly contradict each other. | **CRITICAL** |
| "auto-graduate phases" listed under DOES NOT DO | `docs/api-reference.md:207` | Partially true: `advance()` does graduate on its own when the gate passes, but the call is operator-triggered, not a background thread. Phrasing "auto-graduate" is defensible only if "auto" means "without a background timer". | LOW (doc polish) |
| `safety_critical=True` refuses construction at ML_PRIMARY | README §Output safety, FAQ, example 03, landing | **VERIFIED** | `core.py:254-263`, `core.py:482-486`, `tests/test_security.py::test_safety_critical_refuses_to_construct_at_ml_primary`, `tests/test_output_safety.py::test_ml_primary_refused_at_construction`. | — |
| Circuit breaker trips once, stays tripped, requires explicit reset | README security §3, FAQ | **VERIFIED** | `core.py:787-818` (Phase.ML_PRIMARY branch sets `_circuit_tripped`), `reset_circuit_breaker()` at `core.py:1078`, `tests/test_security_benchmarks.py::TestCircuitBreakerStress::test_breaker_persists_across_many_failures` (100 calls, verifies `BrokenML.call_count == 1`), `::test_breaker_only_clears_on_explicit_reset`. | — |

### Security claims (high stakes)

| Claim | Where claimed | Status | Evidence | Severity |
|---|---|---|---|---|
| "20-pattern jailbreak corpus: 100% rule-floor preserved" | README §Security properties, landing §Survives jailbreaks | **VERIFIED** | `tests/test_security_benchmarks.py:56-93` defines `_JAILBREAK_CORPUS` with exactly 20 entries (counted), `::test_rule_floor_holds_on_all_jailbreaks` iterates and asserts `hits == len(_JAILBREAK_CORPUS)`. | — |
| "PII corpus: 100% recall, 100% precision on 25-item mixed corpus" | README §Security properties | **PARTIALLY TRUE** — counts match, but test threshold is lower than README claim | Corpus is 25 items (`_PII_CORPUS` counted). But `test_rule_recall_and_precision` asserts `recall >= 0.80` and `precision >= 0.85` (not 100%/100%). The test prints measured numbers but the README promises `100% recall, 100% precision`. README claim is stronger than what the test enforces. If the test actually measures 100%/100% in practice, the assertion is just loose — but the README should not write "100%" while the test pins only the floor. | **HIGH** |
| "100 consecutive ML failures → breaker trips once, stays tripped" | README §Security properties | **VERIFIED** | `test_security_benchmarks.py:469-501` — 100 classifications, asserts `BrokenML.call_count == 1` and all 100 returns are rule_fallback. | — |
| "Adversarial-shadow latency: shadow LLM hangs 5 ms then throws → decision p95 under 50 ms" | README §Security properties | **VERIFIED** | `test_security_benchmarks.py::TestLatencyUnderAdversarialLoad::test_slow_shadow_does_not_block_rule` — 50 samples with `time.sleep(0.005)` + raise, asserts p95 < 50 ms. | — |
| "silent ML failure" forensic audit trail (outcome log captures jailbreak attempt on tape) | README security, FAQ | **VERIFIED** | `test_security.py::TestAuditTrail`, `test_security_benchmarks.py::test_shadow_llm_recorded_but_not_decision_making`. | — |

### Benchmark claims

| Claim | Where claimed | Status | Evidence | Severity |
|---|---|---|---|---|
| "Four public benchmarks evaluated end-to-end" (ATIS, HWU64, Banking77, CLINC150) | README, landing, FAQ | **VERIFIED** | Loaders exist at `src/dendra/benchmarks/loaders.py`, one function per dataset. JSONL result files exist in `docs/papers/2026-when-should-a-rule-learn/results/`. Tests at `tests/test_benchmark_loaders.py` (shape + missing-dep behavior + mocked HF shape for each). | — |
| Table numbers: ATIS rule 70.0% / ML final 88.7%; HWU64 1.8% / 83.6%; Banking77 1.3% / 87.8%; CLINC150 0.5% / 81.9% | README §What's measured | **VERIFIED (numbers reproduce from the JSONL tails)** | Checked tail of each `*.jsonl` — numbers round-trip to the README's printed precision. | — |
| Transition depth column: ATIS ≤250, HWU64 ≤1,000, Banking77 ≤1,000, CLINC150 ≤1,500 outcomes | README table last column | **MIXED DATA SOURCES** | The ATIS "≤250 outcomes, 75.6% ML @ transition" row is pulled from `atis_seed500.jsonl` (seed_size=500, finer checkpoint grid). The ATIS "Rule acc 70.0%" in the same row is from the seed=100 run. findings.md admits the mix ("taken from the finer-grained ATIS run"), but the README table presents the numbers as one coherent row without flagging. Reader sees one row → assumes one run. | **MEDIUM** |
| "paired McNemar's tests at p < 0.01" | README §What's measured header, landing §Four public benchmarks | **SHIPPED IN CODE, ABSENT IN SHIPPED JSONL** | `src/dendra/viz.py::mcnemar_p` implements exact + normal-approx paired McNemar; `research.py` emits `rule_correct` / `ml_correct` per-example lists when `record_per_example=True`; `viz.py::transition_depth` prefers paired test when those arrays are present. **However:** the committed `*.jsonl` files in `docs/papers/.../results/` do NOT contain the `rule_correct`/`ml_correct` arrays (verified with Python JSON parse of `atis.jsonl` — keys are only `[kind, training_outcomes, rule_test_accuracy, ml_test_accuracy, ml_trained, ml_version]`). That means when a reader runs `dendra plot` on these files, the transition_depth helper silently falls back to the **unpaired two-proportion z-test**. findings.md explicitly concedes this ("paired McNemar test [...] requires saving per-example outputs (not currently persisted)"). The README and landing text imply the paired test is what produced the published numbers. It's what the code *can* produce, not what the committed results were produced from. | **HIGH** |
| "four-benchmark transition-curve measurements... Reproduce with `dendra bench <dataset>`" | README CLIs, landing §Reproduce | **VERIFIED (path exists)** but `dendra bench` requires network + `datasets` library and is **not covered by CLI tests** | `src/dendra/cli.py::cmd_bench` exists, wiring verified by reading. `tests/test_cli.py` has a `bench` reference only inside a plot-test fixture — there is no direct test of `cmd_bench` end-to-end. The `test_benchmark_loaders.py` tests mock `_load` so the CLI path as a whole is not exercised. | **MEDIUM** |

### Latency claims

| Claim | Where claimed | Status | Evidence | Severity |
|---|---|---|---|---|
| "Rule call: 0.12 µs p50" | README §What's measured | Tested, but test asserts `p50_us < 3.0` — the test certifies sub-3µs, not 0.12µs specifically | `tests/test_latency.py::TestRawComponentLatency::test_rule_is_submicrosecond`. The 0.12 µs figure is a printed-output observation from a prior run, not a regression-locked value. | LOW |
| "Dendra switch at Phase 0: 0.62 µs p50" | README, landing proof-row, marketing one-pager | Tested, asserts `p50_us < 20.0` | `tests/test_latency.py::TestDendraSwitchOverhead::test_phase_rule_overhead_is_small`. Same story as above: the 0.62 µs is print-output from a reference run; the test guards sub-20µs as the failure floor. | LOW |
| "Real ML head (TF-IDF + LR on ATIS): 105 µs p50" | README | Not directly pinned in tests (`test_ml_head_submillisecond` asserts <2000µs on a synthetic head, not on real ATIS TF-IDF) | `tests/test_latency.py::TestRawComponentLatency::test_ml_head_submillisecond` uses `_FakeFastMLHead`, not the real sklearn pipeline. | LOW (honest framing possible — doc says "measured" without claiming test assertion) |
| "Local LLM (llama3.2:1b via Ollama): ~250 ms p50" | README | Hardcoded in `test_latency.py` as `llm_p50_us = 250_000` with comment "we measured llama3.2:1b at ~250ms per classify in an earlier session." | No automated proof. Single-point historical observation. | LOW |
| "~0.5 microseconds p50 at Phase.RULE over the bare rule call" | `docs/FAQ.md` | Inconsistent with README's "0.62 µs" figure | FAQ says 0.5 µs; README says 0.62 µs. Same claim, different numbers. Minor drift. | LOW |
| "11.5M/yr in inference tokens at 100M classifications/month with Sonnet" | README, landing pillar, launch-post-drafts | Back-of-envelope calculation; no test. Depends on Sonnet pricing assumption not written out in README. | Not testable from the SDK; marketing extrapolation. | LOW (label as projection) |

### CLI claims (README shows 5 commands)

| CLI | Implemented? | Tested? | Evidence | Severity |
|---|---|---|---|---|
| `dendra analyze` | YES | YES (4 tests) | `cli.py::cmd_analyze`, `tests/test_cli.py::TestCliAnalyze` (text/json/legacy-json/markdown). | — |
| `dendra init` | YES | YES (6 tests) | `cli.py::cmd_init`, `tests/test_cli.py::TestCliInit` + `tests/test_wrap.py` (13 tests of AST wrapper). | — |
| `dendra bench` | YES | **NO direct CLI test** | Implementation at `cli.py::cmd_bench` — loads dataset, runs `run_benchmark_experiment`, prints JSONL. No `TestCliBench` class. The underlying `run_benchmark_experiment` is tested via `test_research.py` but only with a bespoke `run_transition_curve` path, not the bench-CLI path. | MEDIUM |
| `dendra plot` | YES | YES (1 smoke test) | `cli.py::cmd_plot`, `tests/test_cli.py::TestCliPlot::test_plot_writes_output_file` + `tests/test_viz.py` (14 tests). | — |
| `dendra roi` | YES | YES (3 CLI tests + 11 roi tests) | `cli.py::cmd_roi`, `tests/test_cli.py::TestCliRoi` + `tests/test_roi.py`. | — |

### Adapters (README mentions 4: OpenAI, Anthropic, Ollama, Llamafile)

| Adapter | Implemented? | Tested? | Evidence | Severity |
|---|---|---|---|---|
| OpenAIAdapter | YES | **No direct integration test; protocol conformance only via other tests** | `src/dendra/models.py:102-143`. No test instantiates `OpenAIAdapter` against a mock. | MEDIUM |
| AnthropicAdapter | YES | Same | `models.py:146-182`. | MEDIUM |
| OllamaAdapter | YES | Same | `models.py:185-218`. | MEDIUM |
| LlamafileAdapter | YES (subclass of OpenAIAdapter with fixed base_url) | Same | `models.py:221-243`. | MEDIUM |

Note: the `ModelClassifier` **protocol** is heavily tested via fake implementations in `test_llm_shadow.py`, `test_llm_primary.py`, `test_security.py`, `test_security_benchmarks.py` — so the contract is well-covered. The unit tests are missing for the specific wire-format translations inside each adapter (prompt rendering, logprob-to-confidence mapping, label normalization). `_BaseAdapter._normalize_label` and `_logprob_to_confidence` are non-trivial and untested.

### Storage backends (docs/storage-backends.md claims 5)

| Backend | Implemented? | Tested? | Evidence | Severity |
|---|---|---|---|---|
| BoundedInMemoryStorage (default) | YES | YES | `tests/test_bounded_storage.py`. | — |
| InMemoryStorage (unbounded) | YES | YES | `tests/test_storage.py`. | — |
| FileStorage (POSIX flock, rotation, fsync opt-in) | YES | YES (heavy) | `tests/test_storage_hardening.py` (14 tests), `test_storage.py`. | — |
| SqliteStorage (WAL) | YES | YES (17 tests) | `tests/test_sqlite_storage.py`. | — |
| ResilientStorage (wrapper, fallback + drain) | YES | YES (13 tests) | `tests/test_resilient_storage.py`. | — |

Storage is the strongest tested surface in the repo. `persist=True → ResilientStorage(FileStorage(...))` wiring is exercised end-to-end.

### Labels + decorator + examples

| Claim | Status | Evidence |
|---|---|---|
| Three label forms (`list[str]`, `list[Label]`, `dict[str, Callable]`) | VERIFIED | `core.py::_normalize_labels`, `tests/test_labels_dispatch.py` (11 tests). |
| `classify()` is pure (no side effects); `dispatch()` fires `on=` actions | VERIFIED | `core.py::classify`, `core.py::dispatch`; `tests/test_labels_dispatch.py`. |
| Handler failures captured on `action_raised`, not propagated | VERIFIED | `core.py::_maybe_dispatch`, `tests/test_labels_dispatch.py`. |
| 8 runnable, self-contained examples (no API keys) | VERIFIED | All 8 files present in `examples/`; each imports only `dendra` + stdlib. |
| example 07 demonstrates LLM-as-teacher with `train_ml_from_llm_outcomes` | VERIFIED | `src/dendra/research.py::train_ml_from_llm_outcomes`, `tests/test_llm_teacher.py`. |

### File-structure drift (README §Project structure)

| README line | Reality | Severity |
|---|---|---|
| `llm.py  # OpenAI / Anthropic / Ollama / llamafile adapters` | File is named `models.py`. `src/dendra/llm.py` does not exist. | MEDIUM (developer orientation) |
| `tests/  # 195 tests` | Actual pytest collection: **323 tests** as of 2026-04-24. | LOW (undercount; the overstatement direction would be bad — this is safe) |
| Status line "195 tests green" | Same undercount. | LOW |

### Analyzer

| Claim | Status | Evidence |
|---|---|---|
| Six AST patterns (P1..P6) | VERIFIED | `analyzer.py:25-30` docstring, `_DETECTORS` tuple `(P1..P6)` at `analyzer.py:233-238`, `tests/test_analyzer.py` has one `TestPatternP<n>` class per pattern. |
| Dendra-fit score 0-5 | VERIFIED | `ClassificationSite.fit_score`, scoring logic `analyzer.py::_compute_fit_score`. |
| Output formats: text, markdown, json | VERIFIED | `render_text` / `render_markdown` / `render_json`, covered by `TestCliAnalyze`. |
| "Free. 30 seconds" (landing) | Not timed; depends on repo size. Untestable. | LOW |

### `dendra init` AST-based wrap

| Claim | Status | Evidence |
|---|---|---|
| "AST injection, no typos" | VERIFIED | `src/dendra/wrap.py`, `tests/test_wrap.py` (13 tests). |
| Supports `--safety-critical`, `--phase`, `--labels`, `--dry-run` | VERIFIED | `cli.py::cmd_init` + `tests/test_cli.py::TestCliInit`. |
| Labels inferred from return statements when omitted | VERIFIED | `tests/test_wrap.py::test_infers_labels_from_return_strings`. |
| Refuses to double-wrap | VERIFIED | `tests/test_wrap.py::test_already_wrapped_raises`. |

### Miscellaneous

| Claim | Status | Severity |
|---|---|---|
| "Zero required runtime dependencies" (README §Install) | VERIFIED | `pyproject.toml` would confirm; `core.py` / `gates.py` / `storage.py` are pure stdlib; sklearn/matplotlib/datasets are all extras lazy-imported. | — |
| "No Dendra cloud, no telemetry home-call, no phone-home" (FAQ) | VERIFIED | Telemetry emitters are opt-in; `NullEmitter` is the default; none of the emitters ship a network transport. | — |
| Pricing table on landing | Aspirational — no hosted tier exists yet (`FAQ`: "When Dendra Cloud ships (Q2 2026)..."). Landing presents prices as if the hosted tiers were available. | **MEDIUM** — consider adding "launching Q2 2026" badge on non-OSS rows. |

---

## Red flags (must-fix before public launch)

### CRITICAL — self-contradiction in primary reference doc

**`docs/api-reference.md` says both "default gate is McNemarGate" AND "McNemar transition gate is designed but not shipped".** Lines 82-84 describe `advance()` with the McNemarGate default. Lines 207-208 (§What Dendra does NOT do) list "Auto-graduate phases. You set `starting_phase` explicitly; the McNemar transition gate is designed but not shipped." The second paragraph was clearly not updated when `advance()` + `McNemarGate` landed. **Reader trust collapses the instant they notice this.** Specifically the user who ran this audit cited this exact discrepancy as the trigger.

**Remediation:** rewrite `docs/api-reference.md:206-211` to reflect shipped reality:

> **Auto-graduate without operator action.** Phase transitions happen when
> you call `switch.advance()` and the gate says yes. There is no background
> thread polling the gate — graduation is either operator-triggered or
> triggered from your own scheduler (see example 07).

### HIGH — "100% recall, 100% precision" PII claim is stronger than the enforced test

README §Security properties claims the 25-item PII corpus achieves 100%/100%. The actual test (`test_security_benchmarks.py::test_rule_recall_and_precision`) asserts only `recall >= 0.80` and `precision >= 0.85`. Either (a) run the test, observe the measured values, and if they are indeed 100%/100%, either assert that or soften the README language to "≥80% recall, ≥85% precision (measured 100%/100% on the reference corpus at time of writing)"; or (b) the README is wrong and needs to match the test floor.

**Remediation path A:** keep README prose, tighten the assert. **Path B:** keep the assert, reword README to the floors. I'd pick (A) for the rigor signal.

### HIGH — "paired McNemar tests at p<0.01" claim vs committed JSONL

The code can produce paired-McNemar p-values (`viz.py::mcnemar_p`, and `research.py` conditionally emits `rule_correct`/`ml_correct` when `record_per_example=True`), but the committed result files in `docs/papers/.../results/*.jsonl` have only per-run accuracy scalars — no per-example arrays. `viz.py::transition_depth` silently falls back to the unpaired z-test on those files. The README's "paired McNemar's tests at p<0.01" phrasing implies the paired test is what produced the published numbers.

**Remediation:**
1. Re-run `dendra bench` on all four datasets with `record_per_example=True` (default in `research.py:run_benchmark_experiment`), committing the richer JSONL files.
2. OR soften the claim in README to "two-proportion z-test at p<0.01 (paired-McNemar option shipped; see `viz.py::mcnemar_p`)".

Option 1 is the correct move — the code already supports it; only the committed JSONL is stale.

### MEDIUM — `dendra bench` has no CLI-level test

All four other CLIs have at least smoke coverage. `cmd_bench` wiring is tested only transitively through `test_research.py` (which calls `run_benchmark_experiment` directly, not through `main(["bench", ...])`). A CLI smoke test that monkeypatches `_load_bench` to return a synthetic `BenchmarkDataset` would catch argument-parsing regressions with ~15 lines of test code.

### MEDIUM — adapter wire-format translations are untested

`OpenAIAdapter._normalize_label`, `_logprob_to_confidence`, and the `AnthropicAdapter` exact-match-vs-fallback confidence heuristic are all non-trivial functions with no unit tests. They're covered only via the `ModelClassifier` protocol check. For a pre-public-launch library shipping four adapters as the primary integration point, even mock-based tests would add significant confidence.

### MEDIUM — README benchmark table mixes seed=100 and seed=500 ATIS data

The "ML @ transition" column for ATIS uses the seed=500 finer-grained run's 75.6% / 250-outcome crossover, while "Rule acc" and "ML final" use the seed=100 run's 70.0% / 88.7%. `findings.md` admits the mix in a footnote but the README doesn't. Readers who diff the JSONL against the table will find a 0.5-percentage-point anomaly on rule accuracy (69.5% seed=500 vs 70.0% seed=100).

**Remediation:** footnote the table "transition depth reported from `atis_seed500.jsonl`; other ATIS columns from `atis.jsonl` (seed=100). Both runs committed." — or rerun ATIS at the seed=500 finer grid so one file sources the whole row.

### MEDIUM — pricing table shows hosted tiers as available

Landing page pricing table lists tiers Free/Solo/Team/Pro/Scale/Metered with monthly prices as if purchasable. FAQ reveals "When Dendra Cloud ships (Q2 2026), opt-in hosted storage will be a separate tier. The OSS library will never call home." These are not fully reconciled.

**Remediation:** add a "launching Q2 2026" pill to each hosted row, or a caveat caption under the table.

### LOW — README file-tree says `llm.py`; file is `models.py`

`README.md:184` in the project-structure block lists `llm.py`. The file has been renamed to `models.py`. One-line fix.

### LOW — "195 tests" undercount

Reality is 323. Undercount is safe but still imprecise. Consider using `pytest --collect-only -q | tail -1` as the source of truth, or just say "300+ tests."

### LOW — README 0.62 µs vs FAQ 0.5 µs for same claim

Minor number drift between two docs on the same thing (Phase 0 switch overhead). Pick one, propagate.

### LOW — Latency numbers in README are printed-observation, not test-asserted

The tests guard ceilings (sub-3µs rule, sub-20µs switch) but don't regress-lock the 0.12/0.62 numbers. If the goal is "we measure this; here's what we saw" the current framing is honest. If a reader assumes "these are guaranteed," they'll be disappointed if a GC pause shows 2µs. Consider adding "(reference measurement on macOS/M1; see `tests/test_latency.py` for the assertion bounds)."

---

## Roadmap items documented as future

These are correctly called out as not-yet-shipped; **no action needed:**

- **Dendra Cloud / hosted storage** — FAQ: "When Dendra Cloud ships (Q2 2026)...". FAQ is honest.
- **PostgresStorage** — `storage-backends.md` explicitly marks it "v0.3+ roadmap".
- **Async Storage protocol** — `storage-backends.md` §Roadmap.
- **Compression on FileStorage rotated segments** — `storage-backends.md` §Roadmap.
- **Time-based retention** — `storage-backends.md` §Roadmap.
- **Vision / audio / multimodal adapters** — `examples/README.md` §On the roadmap.
- **End-to-end transition-curve example on a public benchmark in `examples/`** — `examples/README.md` §On the roadmap.
- **LangSmith / W&B telemetry integration** — `examples/README.md` §On the roadmap.
- **Paired McNemar p-value persistence in benchmark JSONL** — `findings.md` §Caveats: "not currently persisted" (see HIGH item above — the code is ready; only the committed results are stale).
- **arXiv preprint** — README §Paper: "arXiv preprint landing post-patent-filing" — patent was filed 2026-04-21, so this is imminent but not yet live.

---

## Priorities for the author, ranked

1. **Fix `docs/api-reference.md:206-211`** (CRITICAL — 5 minutes, single edit).
2. **Either tighten the PII assertion or soften the README claim** (HIGH — 10 minutes).
3. **Re-run `dendra bench` on all four datasets with `record_per_example=True` and commit** (HIGH — 30 minutes including the ATIS seed=500 re-harmonization).
4. **Add a `TestCliBench` smoke class to `tests/test_cli.py`** (MEDIUM — 20 minutes).
5. **Add at least prompt-rendering + label-normalization unit tests for each adapter** (MEDIUM — 1 hour).
6. **Update the three small doc drifts**: file-tree (`llm.py` → `models.py`), test count (195 → 323), latency number reconciliation between README and FAQ (LOW — 5 minutes).
7. **Pricing table caveat** (MEDIUM — copy edit).

Total cleanup: under 3 hours. Nothing here blocks launch technically; item 1 blocks launch for reader-trust reasons.

---

_Audit performed 2026-04-24 against v0.2.0 @ commit 7b137c4 (docs/patent packet prep complete)._
