# v1 readiness — authoritative scope document

**Date:** 2026-04-24 (updated after 7-audit synthesis + product-scope expansion).
**Owner:** Benjamin Booth.
**Status:** v1.0 shipping target — approximately 6 focused sessions from ready.

> **Read this first if you're picking up a compacted session.**
> This doc supersedes every prior audit and scope note. It contains:
> (a) everything shipped in recent sessions, (b) the full v1 fix + feature
> backlog with severity + effort, (c) pending decisions from Ben,
> (d) proposed sequencing, and (e) what's explicitly deferred past v1.
>
> Sources: `v1-audit-features.md`, `v1-audit-concurrency.md`,
> `v1-audit-performance.md`, `v1-audit-security.md`,
> `v1-audit-chaos.md`, `v1-audit-test-quality.md`,
> `v1-audit-benchmarks.md` — this doc is the synthesis of all of them
> plus the product-scope expansion from 2026-04-24.

## Verdict

**Architecture is sound. Test suite is real. Product story now complete.**
The 7-audit sweep found 28 findings + 4 benchmark regressions; Ben's latest
scope directive adds a full VerdictSource family (LLM judge, committee, webhook,
human-reviewer) and bulk ingestion primitives. Combined: ~6 focused sessions of
work before the repo can flip public without embarrassment.

---

## 1. What's already shipped in this session

Locked in, tests green, do not regress:

- **`LearnedSwitch.advance()` + gate architecture** — `Gate` protocol,
  `McNemarGate` (default), `ManualGate`. Evidence-gated graduation works.
- **Auto-advance** (`auto_advance=True` default) — every
  `auto_advance_interval` verdicts, `record_verdict` triggers `advance()`.
  Tagged `auto=true` on telemetry.
- **Three additional gate types** — `AccuracyMarginGate`, `MinVolumeGate`,
  `CompositeGate.all_of() / any_of()`. Any `Gate`-conforming object works.
- **Rename** — `record_prediction` → `record_verdict` across 27 files.
- **Auto-log on classify** (`auto_record=True` default) — classify/dispatch
  auto-append an UNKNOWN `ClassificationRecord` with all shadow observations
  captured. Drift / ROI / dashboards work without `record_verdict` calls.
- **Fluent verdict shortcuts** — `result.mark_correct()` /
  `.mark_incorrect()` / `.mark_unknown()` on `ClassificationResult` with
  back-references threaded automatically.
- **`switch.verdict_for(input)` context manager** — yields a holder,
  defaults to UNKNOWN on block-exit without a mark.
- **`on_verdict=callback`** hook on SwitchConfig — fires after every
  successful `record_verdict`, exceptions swallowed.
- **Hoisted kwargs** — `starting_phase`, `phase_limit`, `safety_critical`,
  `confidence_threshold`, `gate`, `auto_record`, `auto_advance`,
  `auto_advance_interval`, `on_verdict` are all top-level on
  `LearnedSwitch` and `@ml_switch`.
- **Name autogen** — defaults to `rule.__name__`; collision detection
  via weakref registry.
- **Author autogen** — defaults to `@<module>:<name>`.
- **`ResilientStorage`** — wraps FileStorage with in-memory fallback +
  recovery probes. (Has bugs, see backlog #4, #5 below.)
- **`SqliteStorage`** — WAL mode, stdlib-only, shipped and tested.
- **`FileStorage` hardening** — POSIX `flock`, optional `fsync`,
  atomic rotation. (Has path-traversal bug, see backlog #1.)
- **`StorageBase` ABC** + `serialize_record` / `deserialize_record`
  public helpers.
- **Storage-backends doc** promoted from `docs/working/` to
  `docs/storage-backends.md`.
- **API-reference doc rewrite** — role-oriented sections, no anxiety-
  inducing motivational copy.
- **Getting-started guide** — mental model: "you call two things;
  Dendra logs and graduates automatically."
- **McNemar de-emphasized** in public docs — framed as the default gate
  among several.
- **Eight examples + example 09** (`09_verdict_webhook.py`).
- **`.pylintrc`** at repo root — minimal disables for example-file
  conventions only.
- **`.vscode/settings.json`** — Python extension points at venv; pylint
  / ruff / pytest configured.

**Test count at session start:** 195.
**Test count now:** 349 passing, 7 skipped. Ruff clean. Pylint 9.83/10 on
examples.

---

## 2. V1 fix-sprint backlog — 28 original findings + 4 benchmark regressions

### LAUNCH BLOCKERS — CRITICAL

| # | Area | Finding | Fix size |
|---|---|---|---|
| 1 | Security | **Path traversal in FileStorage.** `append_record("../pwned", rec)` escapes base_path. 5-line fix: reject `..`, absolute paths, resolve + verify containment. | 5 LoC + tests |
| 2 | Security | **`safety_critical=True` bypassable post-construction.** `SwitchConfig` is mutable; `config.starting_phase = ML_PRIMARY` skips the cap. Falsifies README "rule floor can never be removed." | 20 LoC (runtime re-check in classify + frozen field or setter guard) |
| 3 | Concurrency | **Shadow-stash cross-contamination.** Single-slot instance fields corrupted by thread-interleaved classify/record_verdict. Silently poisons McNemar gate math. | 30 LoC (threading.RLock + return stash inline on Result) |
| 4 | Chaos | **ResilientStorage silent eviction.** Fallback FIFO-evicts at cap; `degraded_writes` counter claims they were written. Audit trail lies. | 20 LoC (separate "evicted" counter + signal) |
| 5 | Chaos | **ResilientStorage partial-drain duplicates.** Per-switch drain with mid-switch failure leaves earlier switches duplicated across primary + fallback. | 30 LoC (per-switch drain checkpoint + dedup) |
| 6 | Chaos | **Breaker state lost on crashloop.** `_circuit_tripped` is process-local. Proposed: always-on persistence when `persist=True`, opt-in otherwise. | 40 LoC (breaker-state file in storage dir) |
| 7 | Docs | **api-reference self-contradiction on `advance()`.** Already mostly cleaned this session; re-verify. | 5 min verify |
| **29** | **Perf** | **`auto_record=True` + `persist=True` = 1,537× slowdown.** FileStorage opens fd + flocks per call. New default × new "production" recommendation = 2.6ms classify. Unshippable without fix. Keep the default; fix the cost (keep fd open + batched append). | 60 LoC (FileStorage fd-pool + optional batch) |

### HIGH — credibility gaps, ship-blockers for public launch

| # | Area | Finding | Fix size |
|---|---|---|---|
| 8 | Security | **"20-pattern jailbreak corpus" is a tautology.** Inputs prepended with rule's keyword. Patent §[0095]-[0098] cites this. **DECISION NEEDED:** real adversarial tests or retract? Recommendation: real tests. | 100 LoC if real tests |
| 9 | Security | **Rule hot-swappable** via `switch._rule = ...`. `slots=True` on LearnedSwitch + frozen rule attribute. | 15 LoC (also a small perf win) |
| 10 | Security | **Outcome log persists raw input verbatim.** Marketing says HIPAA-safe; implementation writes raw PII. **DECISION NEEDED:** ship redaction hook or drop HIPAA framing for v1? Recommendation: ship hook (40 LoC). | 40 LoC (Storage `redact=` hook) |
| 11 | Chaos | **`except Exception` escapes BaseException.** KeyboardInterrupt / CancelledError bypass the rule floor. 3 classify-branch call sites. | 10 LoC (replace `Exception` with `BaseException` + re-raise KeyboardInterrupt / SystemExit) |
| 12 | Chaos | **Adapter normalize returns `labels[0]` silently** on mismatch. Poisons training data + gate math. | 15 LoC (raise or record sentinel `<unknown>`) |
| 13 | Chaos | **No adapter timeout.** Hung provider blocks classify() for minutes. Default 30s timeout, configurable. | 10 LoC per adapter (OpenAI / Anthropic / Ollama / Llamafile) |
| 14 | Perf | **README latency numbers 70% off.** Benchmark agent has the real numbers in `docs/working/v1-audit-benchmarks.md` and `docs/working/benchmarks/v1-baseline-2026-04-24.jsonl`; regression guard at `tests/test_latency_pinned.py` is shipped. Update README + paper + FAQ to match. | 30 min docs |
| 15 | Perf | **`record_verdict` on FileStorage ~1.9ms.** Connection pool + batched writes. **Folded into #29** above; the fix is the same FileStorage hot-path optimization. | covered by #29 |
| 16 | Concurrency | **Five mutation surfaces unlocked.** Single `threading.RLock` on LearnedSwitch wrapping `_classify_impl` / `record_verdict` / `advance` / `reset_circuit_breaker`; separate lock on ResilientStorage state machine. | 20 LoC (covers F2, F3, half of F1) |
| 17 | Feature | **PII recall/precision claim (100%/100%)** vs test threshold (0.80/0.85). Update README to match test OR tighten test. Recommendation: tighten test with a broader out-of-corpus set (see #19). | 30 min |
| 18 | Feature | **Paper results use unpaired z-test, not McNemar.** Code supports paired; JSONL result files are stale. Re-run the four benchmarks with `--paired` and commit. | 1 hour |
| **28** | **Perf** | **`auto_record=True` default tax: 3.3×** on classify (0.50 → 1.67 µs). Lazy-construct ClassificationRecord; defer allocation until storage actually appends. | 40 LoC |
| **30** | **Perf** | **`auto_advance` spike: 164× at interval boundaries.** p99 = 287µs per 100th verdict. Cache last gate-decision; skip re-eval if log hasn't grown by K records. Also consider: default interval 100 → 500 or exponential backoff after refusals. | 30 LoC |
| **31** | **Perf** | **CompositeGate 1.9× McNemar alone** — each sub-gate re-walks paired-correctness extraction. Cache the pairs at gate entry, pass to sub-gates. | 15 LoC |

### MEDIUM — ship with, fix in v1.0.1 unless time permits

| # | Area | Finding | Fix size |
|---|---|---|---|
| 19 | Security | PII corpus self-tuned. Add an out-of-corpus eval set. | 60 LoC |
| 20 | Security | `author` spoofable. Document that it's provenance not authz. | docs only |
| 21 | Security | `reset_circuit_breaker()` / `advance()` lack authz + not in outcome log. Fold into telemetry / add to outcome log. | 30 LoC |
| 22 | Concurrency | `BoundedInMemoryStorage` lazy-init race (covered by #16 lock). | 0 (covered) |
| 23 | Perf | `slots=True` on dataclasses (covered by #9); Verdict frozenset module-level; `_find_label` dict cache. | 15 LoC |
| 24 | Chaos | Confidence values not clamped to [0, 1]. | 5 LoC |
| 25 | Chaos | 10MB inputs written without size bound. Configurable max. | 10 LoC |
| 26 | Feature | `dendra bench` CLI untested. | 30 LoC tests |
| 27 | Feature | LLM-adapter internals untested (prompt render, label normalize, logprob → confidence). | 80 LoC tests |
| 28' | Feature | README ATIS row mixes seed=100 and seed=500 data. | 15 min |

### LOW — doc polish, fix anytime

- README file-tree says `llm.py` → it's `models.py`.
- README says "195 tests" → 349.
- README 0.62 µs vs FAQ 0.5 µs for same Phase-0 claim.
- `_SWITCH_REGISTRY` keys on `id(storage)` (two FileStorage on same path collide silently).
- Telemetry failures silently swallowed (document).

---

## 3. V1 feature additions (from 2026-04-24 scope expansion)

All moved to v1 per Ben's directive ("the future is now/next"):

### 3.1 `VerdictSource` family

New protocol and implementations — a peer to `Gate`, `ModelClassifier`, `MLHead`:

```python
@runtime_checkable
class VerdictSource(Protocol):
    def judge(self, input, label, record=None, /) -> Verdict: ...
    def judge_batch(self, items, /) -> Iterable[Verdict]: ...  # optional, default loops
```

**Implementations shipping in v1:**

| Name | Purpose | Effort |
|---|---|---|
| `CallableVerdictSource(fn)` | escape hatch; any `(input, label) -> Verdict` callable | 20 LoC |
| `LLMJudgeSource(judge_model, *, require_distinct_from=None, guard_against_same_llm=True)` | single-LLM judge with self-judgment guardrail | 100 LoC |
| `LLMCommitteeSource([models], mode="majority"\|"unanimous"\|"confidence_weighted")` | multi-LLM committee pattern from G-Eval / MT-Bench / Arena literature | 150 LoC |
| `WebhookVerdictSource(endpoint, *, poll_interval, auth)` | subscribe to external signals (queue / HTTP polling) | 200 LoC |
| `HumanReviewerSource(queue_backend, *, timeout)` | queue-based manual labeling with pluggable queue (in-memory / Redis / SQS) | 200 LoC |

**Guardrails built in:**
- Same-LLM-as-classifier-and-judge raises `ValueError` at construction
  (opt-out flag required with explicit acknowledgment).
- Every verdict stamped with `source="llm-judge:<id>"` /
  `"llm-committee:<ids>"` / `"webhook:<endpoint>"` /
  `"human-reviewer:<queue>"` for audit-chain filtering.
- Default is NONE — users must explicitly configure a VerdictSource.

### 3.2 Bulk verdict ingestion primitives

| Method | Purpose | Effort |
|---|---|---|
| `switch.bulk_record_verdicts(iterable)` | batch API; single storage txn where supported; auto-advance deferred to end-of-batch | 80 LoC |
| `switch.export_for_review(limit=None, since=None, filter=...)` | produce a reviewer-facing queue (UNKNOWN records, serializable) | 60 LoC |
| `switch.apply_reviews(reviewed)` | ingest back reviewer-annotated records, correlate by input hash | 50 LoC |
| `switch.bulk_record_verdicts_from_source(inputs, source)` | composition: classify + judge + record in one call | 30 LoC |
| `BulkVerdict` + `BulkVerdictSummary` dataclasses | support types | 20 LoC |

### 3.3 Examples

| # | File | Demonstrates | Status |
|---|---|---|---|
| 10 | `10_bulk_verdict_ingestion.py` | cold-start preload + periodic reviewer queue | not started |
| 11 | `11_llm_judge.py` | `LLMJudgeSource` single-judge pattern with bias guardrails | not started |
| 12 | `12_llm_committee.py` | `LLMCommitteeSource` majority-vote pattern | not started |
| 13 | `13_webhook_verdicts.py` | `WebhookVerdictSource` external-signal ingestion | not started |
| 14 | `14_human_reviewer_queue.py` | `HumanReviewerSource` queue-based labeling | not started |

### 3.4 Docs additions

- `docs/verdict-sources.md` — full matrix of when to use which, bias
  warnings, scenario-to-source mapping.
- `docs/bulk-verdicts.md` — workflow walkthrough for
  preload / periodic / drift-triggered patterns.
- Getting-started update — new section "Advanced: bulk + VerdictSource
  workflows."

### 3.5 Revised product positioning

> "Bring your rule and your truth source. Dendra supplies the ML+AI
> engine, the evidence chain, and the audit trail — whether your truth
> comes from humans, LLMs, downstream signals, or all three."

---

## 4. Test-quality gaps (from 2026-04-24 audit)

| Item | Effort |
|---|---|
| **Write `tests/test_concurrency.py`** red-bar tests for F1-F4 (shadow-stash, breaker race, advance-mid-classify, ResilientStorage state machine). Ship BEFORE the lock-refactor fixes so red→green is visible. | 150 LoC |
| **Research-module integration tests.** research.py coverage 50% → 85%+. Exercise `train_ml_from_llm_outcomes` end-to-end and `run_benchmark_experiment` round-trip. | 120 LoC |
| **Delete the 6 tautologies** — `test_walks_the_lifecycle`, `test_prediction_has_label_and_confidence`, `test_six_phases_present`, `test_fake_llm_satisfies_protocol`, `test_cannot_instantiate_without_overrides`, `test_config_attached_to_switch`. | 15 min |
| **Tighten the 7 brittle tests** (exact-string matches on JSONL format, warning wording, CLI output prose, emoji in rationale, magic-number `fit_score >= 4.0`). | 1 hour |
| **auto_record × storage matrix** — BoundedInMemory / InMemory / File / SQLite / ResilientStorage. | 50 LoC |
| **on_verdict × auto_advance interaction** — verify hook fires in the right order around auto-advance. | 30 LoC |
| **verdict_for + auto_record=True** — ensure no double-count. | 20 LoC |
| **Nested CompositeGate** — composite inside composite. | 30 LoC |
| **MinVolumeGate kwarg-forwarding** — verify inner gate's args respected. | 20 LoC |

---

## 5. Decisions (stamped 2026-04-24)

| # | Question | Decision |
|---|---|---|
| D1 | Jailbreak corpus: real adversarial tests or retract claim? | **Real tests, sandbox-only.** Local stub/fake adapter by default. No outbound network, no API keys consumed. Live-provider runs gate on opt-in env var (`DENDRA_JAILBREAK_LIVE=1`), unset in CI. |
| D2 | Breaker persistence: opt-in or always-on? | **Always-on when `persist=True`.** One breaker-state file in the storage dir. Zero new API surface. Rule-floor promise now survives process restarts. No opt-out flag — tied to `persist=True`. |
| D3 | HIPAA framing: redaction hook + keep, or drop for v1? | **Ship the hook + keep framing.** 40 LoC. `Storage(redact=fn)` pattern. Compliance box-check is strategically load-bearing ("wide market of consumers" — Ben 2026-04-24). |
| D4 | `auto_record=True` with `persist=True` default cost: flip off or fix? | **Fix FileStorage hot-path (item #29).** Keep default on. fd-pool + optional batched append. Silent empty audit logs under the "production" recommendation are non-negotiable. |
| D5 | `VerdictSource` family + bulk ingestion in v1 scope? | **Yes.** Sessions 5–6 as scoped. Closes "where does truth come from" product story. |

**Strategic context (Ben, 2026-04-24):** "We want as wide of a market of
consumers as we can possibly get and we need to start checking compliance
boxes." → HIPAA-adjacent framing + redaction hook are not ornamental; they
unlock regulated-industry adopters. Keep the compliance surface deliberate
across v1 docs.

---

## 6. Proposed sequencing — 6 sessions of work

Each session is roughly a half-day of focused work. Each ships green tests + updated docs. No merged session should leave the suite red.

### Session 1 — concurrency red-bar

Goal: failing tests that expose F1-F4 bugs + the perf regressions we introduced.

- Write `tests/test_concurrency.py` with 4 failing tests for F1-F4.
- Write benchmark regression tests pinning the current regression numbers.
- No production code changes yet.
- Commit: "tests(concurrency, perf): red-bar v1 concurrency + perf bugs"

### Session 2 — concurrency + security criticals

Goal: all 7 CRITICAL findings fixed; concurrency tests flip green.

- #3 + #16: `threading.RLock` on LearnedSwitch + move stash to
  locals / inline on result. Tests flip green.
- #1: FileStorage path-traversal guard.
- #2: `safety_critical` runtime re-check in `_classify_impl`.
- #4 + #5: ResilientStorage separate-counter + per-switch drain
  checkpoint + dedup.
- #6: breaker-state persistence (behind `persist=True`).
- #7: verify api-reference doc fix.

### Session 3 — perf regressions + FileStorage hot path

Goal: auto_record default becomes affordable across all storage backends.

- #29 + #15: FileStorage fd-pool + optional batched append.
- #28: lazy `ClassificationRecord` construction in classify.
- #30: gate-decision caching in `advance()`; default interval 100 → 500
  OR exponential backoff.
- #31: pairs-extraction caching in `CompositeGate`.
- Re-run benchmarks; update pinned numbers in `test_latency_pinned.py`.

### Session 4 — remaining HIGH + BaseException + adapter hardening

- #8: real adversarial jailbreak tests (or retract, pending D1).
- #9: `slots=True` on LearnedSwitch + rule-attribute lock.
- #10: redaction hook on Storage base + docs (pending D3).
- #11: `BaseException` handling in ML / LLM paths.
- #12: adapter normalize behavior (raise vs sentinel).
- #13: adapter timeouts.
- #17: PII corpus reconcile.
- #18: paper results re-run with paired McNemar.

### Session 5 — new features (VerdictSource family)

- `VerdictSource` protocol + dataclass.
- `CallableVerdictSource`, `LLMJudgeSource` (with bias guard).
- `LLMCommitteeSource`.
- Tests for each.
- Examples 11, 12.

### Session 6 — bulk ingestion + external verdict sources

- `bulk_record_verdicts` + `export_for_review` + `apply_reviews` +
  `bulk_record_verdicts_from_source` + `BulkVerdict` dataclass.
- `WebhookVerdictSource` (HTTP polling + webhook endpoint skeleton).
- `HumanReviewerSource` (in-memory queue + interface for Redis/SQS).
- Examples 10, 13, 14.
- `docs/verdict-sources.md` + `docs/bulk-verdicts.md`.
- Getting-started update.
- Re-run test-quality audit; fill any MEDIUM gaps from §4.

### Session 7 — native async API (pulled into v1 2026-04-24)

Sequenced AFTER #29 is solved (Session 3). The perf fix decouples
classify latency from disk durability on the sync path; async adds
an event-loop-native surface for FastAPI / LangGraph / LlamaIndex
callers that can't afford a threadpool-slot per request.

- `async def aclassify(input)` / `async def adispatch(input)` on
  `LearnedSwitch` (sibling to sync `classify` / `dispatch`).
- `async def arecord_verdict(...)` sibling.
- Async storage protocol additions (`async_append_record`,
  `async_load_records`) with default sync-wrapping via
  `asyncio.to_thread`; opt-in native async implementations for
  FileStorage / SqliteStorage using `aiofiles` / `aiosqlite`.
- Async adapter siblings — `OpenAIAsyncAdapter`,
  `AnthropicAsyncAdapter`, `OllamaAsyncAdapter`,
  `LlamafileAsyncAdapter` wrapping each provider's async client.
- `async for v in WebhookVerdictSource.stream()` — native async
  iteration where the upstream pattern is pull-to-consume.
- Async examples — `15_async_fastapi.py` minimal FastAPI route;
  `16_async_committee.py` showing `asyncio.gather` across a
  committee.
- `docs/async.md` — when to use which API, interop guarantees
  (sync + async on the same switch is supported; storage state is
  shared; locks protect both entry points).

Contract: sync API remains the primary reference. Async is a peer
surface, not a replacement. No sync method is deprecated.

### Post-sprint — MEDIUM / LOW cleanup + release prep

- Medium-severity items #19–28'.
- LOW doc polish.
- Research doc + paper updates with new numbers.
- Brand/positioning audit (#54), SVG diagrams (#59), local-model
  installer exploration (#57) — can land in parallel sessions.

**Total:** ~7 core sessions + 1 cleanup session. ~8 sessions to v1.0.

---

## 7. What's explicitly deferred past v1

- Warehouse connectors (Snowflake, BigQuery, Airbyte).
- Reviewer-tool adapters (Labelbox, Prodigy, Scale AI, Argilla).
- Active-learning sampling strategies (`uncertainty_sampling`).
- Multi-annotator consensus + confidence-weighted verdicts.
- Rust / WASM core refactor.
- Enterprise-tier gate workflows (multi-user approval, signed audit chain).
- `PostgresStorage`.
- TypeScript + Mojo-compat bindings (Path D multi-language
  roadmap — v1.1 / v0.3 per existing design).

**Pulled INTO v1 (2026-04-24):** Native async `classify` / `dispatch`
and async adapter siblings — see Session 7 below. Ben's directive:
"nail concurrency concerns across the board" — async is part of the
concurrency story, not a separate roadmap item.

---

## 8. Dependencies + ordering constraints

- Session 2 depends on Session 1's red-bar tests existing (else we can't
  distinguish fix-from-masking).
- Session 3 benefits from Session 2 (lock refactor makes perf changes
  safer).
- Session 5 (VerdictSource) has zero dependencies on Sessions 2–4 — can
  start in parallel after Session 1 if we want to parallelize.
- Session 6 depends on Session 5.
- **Session 7 (async API) must follow Session 3** — the async surface
  inherits the fd-pool / batched-flush storage layer, and the shape of
  those primitives determines what the async storage protocol looks
  like. Building async on top of the pre-fix storage would either
  bake in the 1537× regression or require a double refactor.
- All sessions depend on test suite staying green at session end.

## 8b. Sequencing directive (Ben, 2026-04-24)

> "Ship 'Solve #29' first. Then, the async API. Let's nail
> concurrency concerns across the board."

Interpretation:
- Session 3's #29 fix is the watershed milestone — the repo stops
  being embarrassing on the "production" recommendation.
- Async API lands after that as a new session (Session 7).
- "Across the board" means the #16 lock refactor (Session 2) is
  non-negotiable — we don't bolt async on top of race conditions.

---

## 9. State of the world (session-handoff snapshot)

- **Branch:** `feat/api-refactor-plus-design-docs` (per memory — verify).
- **Test count:** 349 passing, 7 skipped.
- **Ruff:** clean.
- **Pylint:** 9.83/10 on examples.
- **Examples running:** 01–09 all green.
- **Key docs (for future session to re-sync):**
  - `docs/getting-started.md` — current mental model.
  - `docs/api-reference.md` — public surface.
  - `docs/storage-backends.md` — backend matrix.
  - `docs/working/v1-audit-*.md` — the 7 individual audits.
  - `docs/working/benchmarks/v1-baseline-2026-04-24.jsonl` — raw
    benchmark data.
  - `tests/test_latency_pinned.py` — regression-guard benchmarks.

**If this doc and `MEMORY.md` disagree, this doc wins.**
