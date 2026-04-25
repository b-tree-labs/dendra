# CHANGELOG draft — v1.0.0

This is the entry to land in `CHANGELOG.md` on launch day. Pull
into the actual CHANGELOG immediately before the v1.0.0 commit
+ tag.

---

## v1.0.0 — 2026-05-13

The first public release. Public-launched alongside the
companion paper *"When should a rule learn? A statistical
framework for graduated ML autonomy"* on arXiv.

### Highlights

- **Six-phase graduated-autonomy lifecycle** (`Phase.RULE` →
  `Phase.MODEL_SHADOW` → `Phase.MODEL_PRIMARY` →
  `Phase.ML_SHADOW` → `Phase.ML_WITH_FALLBACK` →
  `Phase.ML_PRIMARY`) with paired-McNemar statistical gates
  at every transition.
- **Rule safety floor** retained throughout. `safety_critical=True`
  refuses construction in any phase without a rule fallback;
  the circuit breaker auto-reverts ML decisions to the rule on
  failure.
- **`CandidateHarness`** for autoresearch / agent-loop
  integration. Shadow candidate classifiers against live
  production, run paired-McNemar significance tests against a
  truth oracle, return promotion verdicts.
- **Native async API** — `aclassify`, `adispatch`,
  `arecord_verdict`, `abulk_record_verdicts`. Async LLM
  adapter siblings (`OpenAIAsyncAdapter`,
  `AnthropicAsyncAdapter`, `OllamaAsyncAdapter`,
  `LlamafileAsyncAdapter`). Committee judging via
  `asyncio.gather` for parallel-LLM verdicts.
- **VerdictSource family** — `CallableVerdictSource`,
  `LLMJudgeSource` (with self-judgment bias guardrail),
  `LLMCommitteeSource` (majority / unanimous aggregation),
  `WebhookVerdictSource`, `HumanReviewerSource`.
- **Bulk ingestion** — `bulk_record_verdicts`,
  `bulk_record_verdicts_from_source`, `export_for_review` /
  `apply_reviews` for reviewer round-trip.
- **Storage backends** — `BoundedInMemoryStorage` (default),
  `InMemoryStorage`, `FileStorage` (POSIX flock + optional
  fsync + batched-async mode), `SqliteStorage` (WAL),
  `ResilientStorage` (auto-fallback wrapper). Pluggable
  `redact=` hook at the storage boundary for HIPAA / PII
  workloads.
- **Production performance** — 33 µs p50 classify on the
  `persist=True` recommended path (batched FileStorage), 195
  µs p50 with per-call fsync durability, 0.5 µs p50 at
  Phase 0 with `auto_record=False`.

### Key contributions vs prior art

- Tighter paired-McNemar transition depth (≤ 250 outcomes
  across 4 NLU benchmarks) compared to the unpaired-z-test
  results in earlier cascade-routing literature.
- Production-deployment substrate for autoresearch loops —
  every primitive needed (shadow phases, statistical gate,
  rule floor, audit chain, async committee judging) ships
  in one library. See `docs/autoresearch.md` for the
  positioning.

### Breaking changes from v0.2.x (pre-public-release)

This is the first public release; v0.2.x was internal-only.
Any downstream code from a private v0.2.x snapshot would need
to handle:

- `record_prediction` renamed to `record_verdict`.
- `Phase.LLM_*` renamed to `Phase.MODEL_*`.
- `ClassificationResult.output` renamed to `.label`;
  `ClassificationRecord.output` renamed to `.label`.
- `auto_record=True` is now the default on `LearnedSwitch` —
  classify / dispatch auto-append an `UNKNOWN` outcome record.
- `auto_advance=True` is now the default — `record_verdict`
  triggers `advance()` every `auto_advance_interval` records
  (default 500, was 100 in early drafts).
- `LearnedSwitch` now uses `__slots__` — subclasses adding
  attributes must declare their own `__slots__`.

### Statistics

- 473 tests passing, 4 skipped (require optional extras /
  network).
- 19 runnable examples (`examples/01_hello_world.py` through
  `examples/19_autoresearch_loop.py`).
- 0 hard runtime dependencies. LLM adapters, ML head, and
  benchmarks are optional extras.

### License

- Client SDK: Apache-2.0.
- Analyzer / server / dashboards: BSL-1.1 with Change Date
  2030-05-01 (production self-hosted use is permitted by the
  license; competing-hosted-service is prohibited).

### Acknowledgments

The framework's lineage owes most directly to *FrugalGPT*
(Chen et al., 2023) and *RouteLLM* (Ong et al., 2024) for the
cascade-routing pattern, *Dietterich 1998* for the McNemar-
in-ML-eval methodology, and *Sculley et al. 2015* for the
production-ML-technical-debt framing that motivates the rule
safety floor. The autoresearch positioning takes its cue
from the loop pattern Karpathy and others have been
articulating through 2024–2025.

Thanks to everyone who reviewed drafts, ran early benchmarks,
and pushed back on weak claims.

---

## How to use this draft

On launch day, between the v1.0.0 commit and tag:

1. Open `CHANGELOG.md`
2. Insert the content above, ABOVE the existing v0.2.0 entry
3. Commit as part of the same `release: v1.0.0` commit per the
   runbook
4. Use the same content (lightly trimmed) as the GitHub
   Release notes
