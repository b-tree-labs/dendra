# Feature: swappable phase-graduation gate protocol

**Status:** Designed 2026-04-23. Target ship: v0.3 (alongside Rust core).
**Owner:** Benjamin Booth.

## Claim

The statistical test that gates phase transitions is configurable.
McNemar's paired-proportion test is the default (paper-grounded,
strongest theorem bound) but the protocol accepts alternatives —
accuracy-margin, min-volume, composite (conjunctive), human-
approval — for teams whose data shape or operating context
warrants a different criterion.

## Protocol

```python
class Gate(Protocol):
    def permits_advance(
        self,
        outcomes: list[ClassificationRecord],
        from_phase: Phase,
        to_phase: Phase,
    ) -> GateDecision: ...


@dataclass
class GateDecision:
    permitted: bool
    reason: str
    test_statistic: float | None = None
    p_value: float | None = None
```

Implementations:

- `McNemarGate(alpha=0.01)` — default; paper's paired-proportion test
- `AccuracyMarginGate(margin=0.05, min_n=500)` — simpler; "higher tier is at least X percentage points better over at least N outcomes"
- `MinVolumeGate(min_outcomes=500)` — volume-only; doesn't permit advance below a threshold even if accuracy-based gate would allow
- `HumanApprovalGate(signal_sink=SlackSink(...))` — refuses advance until operator explicitly approves via signal-sink reply
- `CompositeGate([gate_a, gate_b, ...])` — all must permit; conjunctive. The theorem's bound applies per-gate, so composite is strictly safer than any single gate in the composition.

## Configuration

```python
from dendra.gates import CompositeGate, McNemarGate, MinVolumeGate

config = SwitchConfig(
    starting_phase=Phase.RULE,
    phase_limit=Phase.ML_PRIMARY,
    gate=CompositeGate([
        McNemarGate(alpha=0.005),
        MinVolumeGate(min_outcomes=500),
    ]),
)
```

Default when `gate=None`: `McNemarGate(alpha=0.01)` — paper setting.

## Why not runtime-switching gates

A tempting design is to swap the gate mid-run based on observed
conditions (low volume → switch to margin gate; high stakes →
switch to human approval). The theorem's bound on regression
risk assumes a *fixed* gate with a *fixed* α. A runtime swap
undermines the bound unless the composition-of-bounds arithmetic
is done carefully.

Safer: **conjunctive composition**, not runtime switching. State
the full gate as a `CompositeGate` at construction. Each gate's α
is conservative enough that the union respects your target risk.

Revisit runtime-switching in a later version if the analytics
justify it.

## Implementation location

Gates live in the Rust core at `packages/dendra-core/src/gates/`.
Pure math + pure data-structure logic, no I/O. The `Gate` trait
is the portable interface; each language port wraps the Rust
implementations via the pyo3 / wasm-bindgen bindings.

`HumanApprovalGate` is a special case — it requires a signal-sink
emission (host-layer concern). Implementation: the gate's
`permits_advance()` returns `permitted=false, reason="awaiting
human approval"`; the *advance-request machinery* (a host-layer
orchestrator) receives that decision, fires the signal sink, and
blocks/polls for operator reply. Pure core stays pure.

## Patent alignment

`docs/working/patent-strategy.md` §11b.8 explicitly: *"Dependent
claim picks McNemar; independent claim picks 'evidence-based
criterion'."* The protocol is broader than the preferred
embodiment, and the patent language is broad enough to cover any
paired-proportion or margin-based or approval-based gate.

## Tasks to ship

1. Abstract `Gate` trait in Rust core.
2. Implementations: McNemar, AccuracyMargin, MinVolume, Composite, HumanApproval.
3. Host binding: `from dendra.gates import McNemarGate, …`.
4. SwitchConfig `gate: Gate | None = None` field.
5. `advance()` API on LearnedSwitch that consults the configured gate.
6. Example `examples/09_custom_gate.py`.
