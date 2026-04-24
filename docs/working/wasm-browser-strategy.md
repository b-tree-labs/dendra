# Rust + WASM core refactor plan

**Status:** Deferred from 2026-04-23 session. Queued for a new session after `/compact`.
**Owner:** Benjamin Booth.
**Last updated:** 2026-04-23.

This document is the load-bearing plan for moving Dendra from its
current Python-native implementation to a shared Rust + WASM core
with thin language-specific host layers. It is written to survive
context compaction: anyone picking this up in a new session should
be able to execute from this doc alone, without replaying the
conversation that produced it.

---

## Decision — why we're doing this

Context: at the end of the 2026-04-23 session, Ben asked "why not
now?" in response to my suggestion to defer the Rust + WASM
refactor to v0.4. His argument was:

1. Pre-launch is the cheapest time to make core architectural
   changes. No published consumers; any API shape we pick is free
   to revise.
2. Shipping Python-first → porting TypeScript from Python semantics
   → later refactoring both to share a core = three
   implementations and two migrations. Building the Rust core once
   and writing thin hosts is one implementation.
3. Tech debt accumulates; doing it now avoids months of API
   reconciliation later.
4. "The testing will be the thing" — with a thorough test regime,
   the architectural risk is low.

My honest assessment agreed: **Rust + WASM NOW is the correct call
if there is no external deadline forcing an earlier launch.**

Ben's final call: **do this in a new session after `/compact`.**
Close out the current session's remaining scope (API rename,
examples, framing sweep, design docs, commercial licensing). Then
start fresh on the Rust + WASM work.

---

## Scope summary

What moves to Rust (the `dendra-core` crate, compiled to WASM):

- `Phase` enum + phase-transition logic (RULE → MODEL_SHADOW → MODEL_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK → ML_PRIMARY)
- `SwitchConfig` struct + validation
- `ClassificationResult` and `SwitchStatus` types
- Decision routing: `(phase, config, rule_out, llm_out, ml_out) → ClassificationResult`
- Statistical tests: McNemar's exact (small-N binomial), McNemar normal-approx (large-N), paired-proportion helpers, confidence intervals
- Verdict record format + canonical on-disk / on-wire bytes
- Circuit breaker state machine (in-memory, per-switch)
- Gate protocol (McNemar, AccuracyMargin, MinVolume) — all paired-proportion / threshold math

What stays host-native (per language port):

- Decorator / attribute / macro surface (`@ml_switch` in Python, `@dendra.switch` in TS, `fn` with Mojo semantics)
- Storage backends (file I/O, HTTP, Postgres, S3) — language-idiomatic async
- LLM adapters — HTTP clients per language, calling out to OpenAI / Anthropic / Ollama / Llamafile
- ML heads — scikit-learn on Python; ONNX or equivalent on TS; whatever is idiomatic on each port
- Telemetry emitters — Datadog / Honeycomb / LangSmith client libraries
- Signal sinks — Slack / PagerDuty / webhook clients
- CLI + admin HTTP endpoints

Why this split: the first list is pure logic + pure math, no I/O,
no threading, no language-idiomatic side effects. The second list
is everything that *has* to talk to the host environment in its
native way.

---

## Proposed crate structure

```
packages/
├── dendra-core/             # Rust crate — compiles to WASM + native
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs           # public API surface
│   │   ├── phase.rs         # Phase enum + transitions
│   │   ├── config.rs        # SwitchConfig
│   │   ├── result.rs        # ClassificationResult, SwitchStatus
│   │   ├── routing.rs       # Decision routing logic
│   │   ├── gates/
│   │   │   ├── mod.rs       # Gate trait
│   │   │   ├── mcnemar.rs
│   │   │   ├── binomial.rs
│   │   │   ├── margin.rs
│   │   │   └── composite.rs
│   │   ├── breaker.rs       # Circuit breaker state machine
│   │   ├── outcome.rs       # ClassificationRecord + serialization
│   │   └── stats.rs         # shared statistics utilities
│   ├── tests/
│   │   ├── property/        # proptest-based
│   │   ├── fuzz/            # cargo-fuzz targets
│   │   └── integration/     # end-to-end through the crate
│   └── benches/             # criterion-based perf baselines
│
├── python/                  # pyo3 binding + Python host layer
│   ├── pyproject.toml
│   ├── src/dendra/          # existing Python package layout preserved
│   │   ├── __init__.py
│   │   ├── decorator.py     # @ml_switch — host-native
│   │   ├── storage.py       # FileStorage, InMemoryStorage — host-native
│   │   ├── llm.py           # adapters — host-native
│   │   ├── ml.py            # ML head protocols — host-native
│   │   ├── telemetry.py     # emitters — host-native
│   │   ├── cli.py           # CLI — host-native
│   │   ├── analyzer.py      # static analyzer — host-native (Python AST specific)
│   │   ├── research.py      # host-native
│   │   ├── roi.py           # host-native
│   │   └── _core/           # pyo3 bindings to dendra-core
│   │       ├── __init__.py
│   │       └── native.so    # compiled pyo3 extension
│   └── tests/               # existing Python tests, updated
│
├── typescript/              # wasm-bindgen binding + TS host layer
│   ├── package.json
│   ├── src/
│   │   ├── index.ts
│   │   ├── decorator.ts     # @switch() — TS decorators (stage-3 proposal)
│   │   ├── storage.ts
│   │   ├── llm.ts
│   │   ├── telemetry.ts
│   │   ├── cli.ts
│   │   └── core/            # wasm-bindgen wrapper
│   │       ├── dendra_core.wasm
│   │       └── dendra_core.d.ts
│   └── tests/
│
└── conformance/             # shared test corpus
    ├── switch_rule_phase.yml
    ├── switch_llm_shadow.yml
    ├── switch_safety_critical_refusal.yml
    ├── gate_mcnemar_small_n.yml
    ├── gate_mcnemar_large_n.yml
    ├── breaker_trip_reset.yml
    └── ... (one file per behavioral invariant)
```

The repo becomes a monorepo at that point. No Bazel for now — per-language tooling (Cargo / pyproject.toml / npm) handles each port's build chain; `just` or a simple `Makefile` at repo root orchestrates the cross-language CI lanes.

---

## Execution phases

### Phase 1 — Skeleton + core types (week 1)

- Create `packages/dendra-core` Cargo crate.
- Port `Phase` enum + `SwitchConfig` + `ClassificationResult` + `SwitchStatus` to Rust.
- Write the conformance corpus format (YAML schema, loader, runner harness).
- Cargo build passes, type definitions match the Python source 1:1.
- Commit: `feat(core): skeleton Rust crate + shared conformance corpus`

### Phase 2 — Decision routing + breaker (week 2)

- Port `routing.rs`: given phase + rule/llm/ml outputs, emit `ClassificationResult`.
- Port `breaker.rs`: circuit breaker state machine (trip, probe, reset).
- Write property-based tests for routing invariants (rule-floor respected, phase monotonicity).
- Write proptest for breaker state-machine invariants (consistency under all transition sequences).
- Commit: `feat(core): decision routing + circuit breaker state machine`

### Phase 3 — Gate protocol + statistical tests (week 3)

- Port `stats.rs`: McNemar exact (binomial), McNemar normal-approx, paired-proportion, confidence intervals.
- Port `gates/`: Gate trait + McNemar / AccuracyMargin / MinVolume / Composite implementations.
- Regression tests: paper's ATIS / HWU64 / Banking77 / CLINC150 transition-depth numbers must reproduce (within multi-seed variance) when the Rust gate code is driven from the existing benchmark data.
- Commit: `feat(core): gate protocol + statistical tests with paper-regression passing`

### Phase 4 — Python host via pyo3 (week 4)

- Add pyo3 binding in `packages/dendra-core`'s Cargo.toml under `[[lib]]` crate-type `cdylib`.
- Rewrite `src/dendra/core.py` as a thin wrapper that delegates to the pyo3 extension for all math + routing + decision logic.
- Keep `decorator.py`, `storage.py`, `llm.py`, `ml.py`, `telemetry.py`, `cli.py`, `analyzer.py`, `research.py`, `roi.py` as host-native Python.
- Run existing 200+ Python test suite against the new implementation. Must pass unchanged. This is the load-bearing "did we break anything" check.
- Commit: `feat(python): pyo3 binding + thin wrapper over dendra-core`

### Phase 5 — WASM binding for TypeScript (week 5)

- Add wasm-bindgen binding in `packages/dendra-core` (separate feature flag: `--features wasm`).
- Build WASM artifact via `wasm-pack build --target bundler`.
- Create `packages/typescript` with thin host layer: decorator, storage (file + IndexedDB for browser), LLM adapters (fetch-based), and the TS-facing API surface.
- Write TypeScript equivalents of conformance tests; they must drive the same YAML corpus the Python port uses and produce identical results.
- Commit: `feat(typescript): wasm-bindgen binding + thin host layer`

### Phase 6 — Cross-port conformance + docs (week 6)

- Build the conformance test runner for each port.
- Every YAML case in `conformance/` runs against both Python and TypeScript; outputs must match byte-for-byte.
- Document the host-layer API for both languages.
- Update README + landing with "runs in Python, TypeScript, and the browser via WASM" framing.
- Commit: `feat(conformance): cross-port test runner + documentation`

### Phase 7 — Browser + edge integration (week 7, optional in launch scope)

- Add `packages/typescript` browser-only entry point.
- Write an example: in-browser Dendra classifying user input before it's sent to a server.
- Document edge deployment (Cloudflare Workers, Deno Deploy, Vercel Edge).
- Commit: `feat(browser): browser-native Dendra + example`

### Phase 8 — Mojo-compat shim (week 8, deferrable)

- Verify Python-superset compat: try `mojo run examples/01_hello_world.py`.
- Build a wrapper that imports `dendra` in Mojo idiomatically (`fn` functions, `struct` for config).
- Commit: `feat(mojo): Python-superset compat shim + idiomatic wrappers`

Total: 6-8 weeks to launch scope (through Phase 6). Phases 7-8 are
bonus scope that can ship in v0.3 if calendar pressure bites.

---

## Test regime — the load-bearing safety net

Five layers, all required before the Rust refactor merges:

1. **Conformance corpus** — YAML cases at `packages/conformance/`. Canonical inputs → expected outputs at the *primitive behavioral* level. Every port must pass identical assertions.

2. **Property-based tests** via `proptest` in Rust:
   - *Rule floor invariant:* for any random inputs at any phase, `ClassificationResult.source` is `"rule"` whenever LLM/ML outputs are unavailable.
   - *Phase monotonicity:* `advance()` never decreases phase; sequence of advances produces non-decreasing phase values.
   - *Safety-critical cap:* `SwitchConfig(safety_critical=True)` with `starting_phase=ML_PRIMARY` always raises at construction.
   - *Gate-bound validity:* McNemar gate with α=0.01 permits advance only when computed p-value < 0.01.
   - *Breaker consistency:* state machine reaches reachable states only; no invalid (tripped && advancing) combos.

3. **Fuzz tests** via `cargo-fuzz`:
   - Random ClassificationRecord bytes → parser must never panic, must reject invalid bytes cleanly.
   - Random `SwitchConfig` construction → must either validate cleanly or reject with a specific error.
   - Random Gate input sequences → must return a valid `GateDecision`.

4. **Regression benchmarks:** the paper's four-benchmark transition-depth numbers must reproduce when the Rust gate + routing drives the existing benchmark data:
   - ATIS: transition at ≤ 250 outcomes (narrow, ATIS-like regime)
   - HWU64: ≤ 1,000
   - Banking77: ≤ 1,000
   - CLINC150: ≤ 1,500
   - Tolerance: paper's documented multi-seed variance (see `docs/papers/2026-when-should-a-rule-learn/results/strengthening-plan.md` §3.1).

5. **WASM integration tests:** run the same conformance corpus through the WASM binary from both Python (via wasmtime-py) and TypeScript hosts. Outputs must be byte-identical at the boundary of the WASM module.

Refusing to ship without all five in place is non-negotiable. This is what gives us "behaviorally equivalent to the Python-native v0.2 implementation" as a defensible claim.

---

## API-shape decisions still open

These need to be resolved at the start of the Rust session:

- **Async vs sync.** The core logic is synchronous (pure math + state transitions, no I/O). Host layers can be async-flavored. Proposal: `dendra-core` is fully synchronous; async is a host-layer concern. Python already has a synchronous decorator; TS hosts wrap in Promise where idiomatic.
- **Error propagation.** Rust `Result<T, E>` vs Python exceptions vs TS thrown errors. Proposal: Rust core returns `Result` variants; pyo3 converts to exceptions matching existing Python ones (ValueError, RuntimeError); wasm-bindgen converts to TS-friendly error objects with the same discriminant values.
- **pyo3 extension packaging.** Choose between: pre-built wheels per platform (cibuildwheel), source distribution (user compiles at install), or both. Proposal: both, with pre-built wheels for macOS arm64/x64 + Linux x64/arm64 + Windows x64 as primary distribution.
- **WASM size.** Dendra-core is small (~5000 lines) so WASM should be <100 KB gzipped. If it creeps past 250 KB, investigate rust-std size optimization and LTO.
- **Thread-safety.** Circuit breaker state is per-switch; two concurrent classification calls on the same switch should be safe. Use atomic types in Rust; make the breaker state `Send + Sync`.

---

## Migration path for existing Python users

Since Dendra is pre-launch, there are no existing external users. Internal call sites are all in this repo. The migration is:

1. New `packages/python/src/dendra/` replaces current `src/dendra/`.
2. Most files stay identical (decorator.py, storage.py, llm.py, ml.py, telemetry.py, cli.py, analyzer.py, research.py, roi.py).
3. Only `core.py` becomes a thin wrapper around the pyo3 extension.
4. External API (`from dendra import ml_switch, Phase, SwitchConfig, …`) is unchanged.
5. Existing 200+ tests pass without modification (they drive through the same public API).

Breaking changes are NONE for the Python user. All the architectural change is internal.

---

## What the session-after-/compact should start with

1. **Read this doc.** Everything is here.
2. **Verify the session state**:
   - `git log --oneline -10` — should show the API refactor + design-docs PR landing on main.
   - `git branch` — should be on `main`.
   - `git status` — should be clean.
   - `.claude/.../memory/MEMORY.md` — should show Dendra status as "Rust + WASM refactor queued, design docs complete."
3. **Create a new feature branch**: `feat/rust-wasm-core`.
4. **Start with Phase 1** of the execution phases above.
5. **Commit at each phase boundary**; push after every commit.

The user should not need to re-explain the strategy; this doc is
the strategy. If something is unclear, the design docs in
`docs/working/feature-*.md` (gate protocol, breaker policies, LLM
comparison, externalization boundary) elaborate on the specific
features that live in or near the core.

---

## Related design docs (written in the same session)

- `docs/working/multi-language-roadmap.md` — path D launch plan (Python + TS + Mojo-compat), tier table including Mojo, deferred-Bazel rationale, conformance-corpus approach, feature matrix.
- `docs/working/feature-llm-comparison.md` — multi-LLM scorecard feature design.
- `docs/working/feature-gate-protocol.md` — swappable gate protocol (conjunctive composition).
- `docs/working/feature-breaker-policies.md` — MANUAL + SELF_HEAL recovery, reset UX, flap detection, exponential backoff.
- `docs/working/externalization-boundary.md` — what externalizes, what stays local, security reasoning.

---

## Risk register

- **Rust build complexity on Windows.** Current Python contributors are macOS + Linux. Windows builds via cibuildwheel should work but need early CI verification.
- **pyo3 ABI changes between Python versions.** Abi3 targeting keeps one binary compatible across Python 3.10-3.14.
- **WASM binary size bloat if rust-std gets pulled in.** Monitor per-commit; revert any change that pushes the WASM artifact past 250 KB gzipped.
- **Test-data drift.** Paper's benchmark data is in `docs/papers/2026-when-should-a-rule-learn/results/`. If any seed files get regenerated during the refactor, the regression-benchmark test suite will fail. Pin the seed files explicitly.
- **Contributor onboarding.** Rust is a higher bar than Python. Mitigate with a `CONTRIBUTING.md` section on the Rust core specifically and a "host-layer-only" label on issues that don't require Rust skills.

---

_Copyright (c) 2026 B-Tree Ventures, LLC. Internal strategy doc._
