# Dendra — multi-language roadmap

**Status:** Decision made 2026-04-23. Ben chose Path D: launch with
Python + TypeScript + Mojo-compat-shim; Go / Rust / Java / C# fast-follow.
Executed via the Rust + WASM core refactor — see
[`wasm-browser-strategy.md`](./wasm-browser-strategy.md) for the
architectural plan.

## Decision

Dendra launches as **a classification primitive with three
language-native surfaces** (Python, TypeScript, Mojo-compat) rather
than as a Python-only library with "ports coming later." The
framing "primitive with reference implementations" is more durable
than "Python library that we'll someday port."

## Tier table

| Tier | Language | Status | Notes |
|---|---|---|---|
| **1 (launch)** | Python | Shipping | Reference implementation. Existing core.py + analyzer.py + ROI + research. Pyo3 binding to the Rust core after refactor. |
| **1 (launch)** | TypeScript / JavaScript | Target | SDK-only (decorator + storage + adapters + core API). No analyzer; AST-pattern code is Python-specific. wasm-bindgen binding to the Rust core. Node.js + browser + Deno + Bun all work. |
| **1 (launch)** | Mojo | Compat shim | Python-superset compatibility; `import dendra` works out-of-the-box. Idiomatic Mojo (`fn`, `struct`) follows in v0.4. |
| **2 (fast-follow, Y1 H2)** | Go | Planned | Infrastructure-language of choice; Dendra-as-sidecar / Dendra-in-microservice is a common pattern. |
| **2 (Y2)** | Rust | Planned | Beyond the core: a native Rust SDK with idiomatic trait impls for teams that want zero-GC classification. |
| **2 (Y2)** | Java / Kotlin | Planned | Enterprise JVM shops; SDK-only scope. |
| **2 (Y2)** | C# / .NET | Planned | Microsoft-stack enterprise; SDK-only scope. |
| **3 (Y3+, demand-driven)** | Julia | Deferred | Scientific computing niche. |
| **3 (Y3+, demand-driven)** | C++ | Deferred | Embedded / HPC contexts. |
| **3 (Y3+, demand-driven)** | Fortran | Deferred | HPC legacy. Most Fortran use cases orchestrate classification from a Python wrapper anyway. |

## Architectural approach — shared Rust + WASM core

All language ports (beyond Mojo's Python-compat shim) share a
single Rust implementation of the pure-logic + pure-math bits:
`Phase` enum, `SwitchConfig`, `SwitchResult`, decision routing,
statistical tests (McNemar exact + normal-approx + margin),
circuit breaker state machine, Gate protocol, OutcomeRecord
serialization.

Each host port is a thin language-native layer that:
1. Provides idiomatic syntax (Python decorator, TS decorator, Go
   struct embedding, Rust trait impl).
2. Handles I/O concerns (storage backends, HTTP LLM adapters,
   telemetry emitters, CLI).
3. Delegates all math + routing + state-machine logic to the
   Rust core via pyo3 / wasm-bindgen / cgo / etc.

**Why:** eliminates port-cost for the shared logic; guarantees
behavioral parity across languages; single performance-optimization
surface; browser + edge enablement is automatic via WASM.

**Timing:** deferred from the 2026-04-23 session. Executed in a
fresh session after `/compact`. Full plan in
[`wasm-browser-strategy.md`](./wasm-browser-strategy.md).

## Why not Bazel

Considered and deferred. Bazel (or Buck2) shines at 5+ languages
with tight interdependencies. For launch with 2-3 ports + clean
Rust-core-and-thin-host layering, per-language tooling (Cargo +
pyproject.toml + npm + Mojo-native) plus a shared YAML conformance
corpus at `packages/conformance/` is lighter, has zero onboarding
tax, and doesn't require contributors to learn BUILD files before
they can send a PR.

Revisit when Go / Rust / JVM ports land and cross-language build
hermeticity becomes a concern. Documented as a deferred decision
rather than a rejected one.

## Cross-port synchronization

Four-part strategy:

1. **Monorepo layout.** `packages/dendra-core/` (Rust) +
   `packages/python/` + `packages/typescript/` + later `packages/go/`,
   `packages/rust/`, etc. Shared `docs/` + `brand/` + `notes/` +
   `LICENSE*` at repo root.
2. **Shared conformance corpus** at `packages/conformance/*.yml`.
   Canonical test cases. Every port must pass identical assertions.
3. **Semver parity.** All ports ship the same version number.
   Features that aren't yet ported sit on a feature branch until
   every launch-tier language has them. `packages/*/VERSION` files
   checked by release workflow.
4. **Feature matrix** at `docs/feature-matrix.md`, updated per
   release, explicit about which features are Python-only (e.g.,
   the analyzer for AST reasons).

## Feature matrix (target state)

Columns: each language port. Rows: feature. Cells: `✓` (shipped in
this port's current version), `—` (not implemented), `planned-vN`
(on roadmap for a specific version).

| Feature | Python | TypeScript | Mojo | Go | Rust | Java | C# |
|---|---|---|---|---|---|---|---|
| `@ml_switch` decorator + `LearnedSwitch` | ✓ | ✓ | ✓ (via compat) | planned-v0.3 | planned-v0.3 | planned-v0.5 | planned-v0.5 |
| `Phase` enum + transitions | ✓ | ✓ | ✓ | planned-v0.3 | planned-v0.3 | planned-v0.5 | planned-v0.5 |
| OpenAI / Anthropic / Ollama adapters | ✓ | ✓ | ✓ | planned-v0.3 | planned-v0.3 | planned-v0.5 | planned-v0.5 |
| Static analyzer (`dendra analyze`) | ✓ | — | ✓ (via compat) | — | — | — | — |
| ROI reporter | ✓ | — | ✓ (via compat) | — | — | — | — |
| Multi-LLM comparison (`dendra compare`) | planned-v0.3 | planned-v0.3 | planned-v0.3 | planned-v0.4 | planned-v0.4 | — | — |

The feature matrix lives in the root `docs/` once the Rust + WASM
refactor starts populating it.

## Messaging implications

Current README / landing say "Python library." Update to:

> "Dendra is a classification primitive with reference
> implementations in Python and TypeScript, plus Mojo compatibility
> via Python-superset semantics. Ports to Go / Rust / Java / C#
> are tracked in the feature matrix."

Taglines and one-pager copy unchanged — the primitive framing
works across all languages; "Python library" was the specific
phrasing that tied us to one language.

See [`brand/messaging.md`](../../brand/messaging.md) for the
canonical one-liners that need adjustment.

---

_See also: `feature-llm-comparison.md`, `feature-gate-protocol.md`,
`feature-breaker-policies.md`, `externalization-boundary.md`,
`wasm-browser-strategy.md`. These are the companion design docs
produced in the same 2026-04-23 session._
