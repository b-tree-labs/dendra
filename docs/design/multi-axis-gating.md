# Multi-axis gating: design exploration

**Status.** Working document, not normative. v0.1 (2026-04-26).
**Prompted by.** The orientation-agnostic Gate insight: the protocol
takes (current_phase, target_phase) and answers "is target reliably
better than current?". Direction is the caller's interpretation. So
why is "better" only ever about *accuracy*? Other axes (latency, cost,
privacy, coverage) might also gate phase transitions. This document
walks five candidate axes through the existing protocol to find out
where it holds and where it breaks.

**Reading order.** §1 frames. §2 walks the axes. §3 reports. §4
recommends.

---

## 1. Frame

Today the Gate protocol is:

```python
class Gate(Protocol):
    def evaluate(records, current_phase, target_phase) -> GateDecision: ...

@dataclass(frozen=True)
class GateDecision:
    target_better: bool
    rationale: str
    p_value: float | None = None
    paired_sample_size: int = 0
    current_accuracy: float | None = None
    target_accuracy: float | None = None
```

Today the only consumer of this protocol is the *accuracy* axis: the
records hold paired correctness, the McNemar test compares paired
correctness, the gate fires when target is reliably more accurate.

The orientation insight says: there is no inherent "accuracy" in the
protocol. `target_better` means "the target's *something* is reliably
better per the gate's test." The gate could measure latency, cost,
privacy adherence, distributional coverage, calibration, anything that
admits a paired comparison.

**Question.** Does the current protocol generalize across axes? If
yes, multi-axis gating drops in with zero new types. If no, what
extensions are needed?

---

## 2. The five candidate axes

For each axis: **(a)** what is the paired observation, **(b)** what
does "target better" mean, **(c)** what statistical test fits, **(d)**
does the current Gate protocol hold without changes, and if not what
breaks.

### 2.1 Accuracy axis (today's only axis)

- **(a)** Paired observation: `(current_correct: bool, target_correct: bool)`
  per row. Already stored on `ClassificationRecord` as `rule_output`,
  `model_output`, `ml_output` plus `label`; `_paired_correctness`
  extracts it.
- **(b)** Target better = target predicts more rows correctly.
- **(c)** Test: paired McNemar (binary correctness). Already shipped:
  `McNemarGate`. Margin variant: `AccuracyMarginGate`.
- **(d)** Protocol holds. This is the case it was designed for.

### 2.2 Latency axis

- **(a)** Paired observation: `(current_latency_ms: float,
  target_latency_ms: float)` per row. **Not currently stored on
  ClassificationRecord.** The record has a single `timestamp`; nothing
  per-decision-maker.
- **(b)** Target better = target's latency distribution is reliably
  lower (or, viewed from the demotion direction, current's distribution
  has crept above some threshold relative to a baseline).
- **(c)** Test: paired Wilcoxon signed-rank on per-row latency
  differences. Or threshold-based: "fail if current p99 > X."
- **(d)** **Protocol breaks at the *records* layer**, not at the gate
  layer. The gate signature `(records, current, target) → decision`
  still works. But records don't carry per-source latency. We'd need
  either:
  1. Extend `ClassificationRecord` with per-source latency fields
     (`rule_latency_ms`, `model_latency_ms`, `ml_latency_ms`); set
     them on every classify path that runs that source.
  2. Pass timing data through a side channel (e.g., a separate
     latency-log per switch).
  3. Have the gate read from a different substrate (a metrics
     exporter, an APM adapter).

  Option (1) is cleanest for the protocol but bloats the record. The
  current sweet spot is shadow modes that *do* run multiple sources;
  capturing per-source timing while the verdict is being recorded is
  cheap. Worth doing.

### 2.3 Cost axis

- **(a)** Paired observation: `(current_cost_per_call: float,
  target_cost_per_call: float)` per row. Like latency, **not
  currently stored.**
- **(b)** Target better = target's cost is reliably lower (or
  symmetric on the demotion side: ML head's cost has crept above a
  budget).
- **(c)** Test: same family as latency (Wilcoxon, threshold). Often
  the cost is *known constant per source* (rule = $0, local SLM = some
  amortized $/call, frontier API = $X per 1k tokens × usage), so a
  point estimate often suffices and the "test" reduces to a budget
  threshold.
- **(d)** Same conclusion as latency. Protocol holds; records need
  cost annotation.

### 2.4 Privacy / regulatory boundary axis

- **(a)** Per-source attribute (categorical, not paired observation):
  rule = stays in-process, model = depends on adapter, ML = depends on
  feature pipeline. Does this decision-maker keep data inside a
  declared boundary?
- **(b)** Target better = target stays inside the declared boundary
  for a higher fraction of rows (or always, if boundary is hard).
- **(c)** Test: not statistical at all. Boundary adherence is a
  property of the source's adapter (OllamaAdapter stays local;
  AnthropicAdapter calls out). For a hard boundary, the answer is
  binary per source: "would this source ever leave the boundary?". If
  yes and boundary is hard, never use it.
- **(d)** **Protocol awkwardly fits.** A "PrivacyGate" could
  trivially answer target_better=True iff target's adapter satisfies
  the configured boundary AND current's doesn't. But the comparison is
  per-adapter, not per-row. We'd need to read source metadata, not
  records. The gate could still satisfy the protocol shape (records is
  ignored); but it's a different category of check.
  - Alternative: privacy is a *construction-time* refusal, not a
    runtime gate. Like `safety_critical=True` already is.
  - Recommendation: **privacy is not a gate axis.** It's a config
    constraint enforced at switch construction. Same shape as
    `safety_critical`.

### 2.5 Coverage / OOD axis

- **(a)** Paired observation: per row, did each decision-maker abstain
  or predict? Or, did each give a high-confidence answer vs a
  low-confidence one? Stored partially today (each source's confidence
  is captured).
- **(b)** Target better = target handles a wider distribution of
  inputs (fewer abstentions, fewer low-confidence outputs).
- **(c)** Test: paired McNemar on a binary "produced confident
  answer" indicator. Same machinery as accuracy.
- **(d)** Protocol holds with a different paired-extraction function
  (compare per-source confidence to threshold). McNemar fires on the
  binary indicator. No extension needed beyond a small variant of
  `_paired_correctness`.

---

## 3. Findings

### 3.1 Where the current protocol holds

- **Accuracy** (binary correctness paired): McNemar, AccuracyMargin.
- **Coverage** (binary confident-answer paired): McNemar with a
  different paired-extraction function. Same gate code.
- **Cost** (when cost is constant-per-source, common case): a
  threshold gate that ignores `records`. Same protocol shape.

These three axes drop into the existing protocol with at most a small
helper function. Zero new types, zero protocol changes.

### 3.2 Where the records substrate breaks

- **Latency** (per-row continuous, paired): the gate protocol holds,
  but `ClassificationRecord` lacks per-source latency fields. To gate
  on latency we have to extend the record (cheap, one PR).
- **Cost** (when cost varies per call, e.g., variable token use):
  same fix.

The fix is bounded: add optional `*_latency_ms: float | None`
and (less urgently) `*_cost: float | None` fields to
`ClassificationRecord`. Existing records have None; new records on
shadow paths populate them. Latency-gate code reads them.

### 3.3 Where the protocol awkwardly fits

- **Privacy / regulatory boundary**: not a per-row test. Better
  modeled as a construction-time constraint (mirroring
  `safety_critical=True`). A "PrivacyGate" technically satisfies the
  protocol but conflates two categories. **Recommend keeping privacy
  as a config constraint, not a gate.**

### 3.4 Composition: how many gates per direction?

When multiple gates fire (e.g., accuracy demote AND latency demote),
what does the lifecycle do? Three options:

1. **OR-of-axes (most conservative).** Demote on any axis fire.
   Fastest reaction; possibly thrashy.
2. **AND-of-axes (least conservative).** Demote only when all axes
   agree something is wrong. Slow to react.
3. **Per-axis target.** Each axis demotes to a different fallback
   path. Latency-driven demote drops to a faster-but-less-accurate
   tier; accuracy-driven demote drops to the rule.

(3) is intellectually attractive but breaks the linear-lifecycle
model. It implies a graph, not a sequence.

For v1, **(1) OR-of-axes** is the simplest and most aligned with the
"smart rule that doesn't get dumb" promise. The current
`CompositeGate(any_of=[...])` already implements OR semantics for
forward gates; the same construct works in the demotion direction.

### 3.5 The rule-floor concept generalizes naturally

Today's "rule floor" is implicitly an *accuracy* floor: the rule is
the safe baseline if accuracy degrades. In a multi-axis world, the
rule is the floor on **most** axes:

| Axis | Rule's role |
|---|---|
| Accuracy | low ceiling but reliable; the safety baseline |
| Latency | typically fastest (no model inference) |
| Cost | typically free (no API calls) |
| Privacy | local by construction (no external data egress) |
| Coverage | bounded by keyword set; brittle but predictable |

So when *any* axis breaches its bound, the natural fallback target
is the rule. This justifies single-step demotion as the default
demotion shape for v1 (which is what we'd already designed). N
dimensions don't break that — each axis gates demote-to-rule
independently.

### 3.6 Bidirectional safety theorem under n axes

Per axis, the per-evaluation Type-I error is bounded by the gate's
α. Across `k` axes evaluated independently, the union-bound bounds
the joint per-evaluation FPR by `k·α`. Across `T` evaluation
intervals, total error is bounded by `T·k·α`. Operators tune α down
(e.g., 0.001 instead of 0.01) when k or T is large.

This is exactly the same shape as the existing one-axis bound, just
multiplied by k. The safety story stays clean.

---

## 4. Recommendation

### v1 scope (Phase C as planned)

Ship the autonomous demote loop on the **accuracy axis only**, using
the existing `Gate` protocol unchanged. Concrete shape:

```python
config = SwitchConfig(
    gate=McNemarGate(),                  # accuracy: advance
    drift_gate=McNemarGate(alpha=0.005), # accuracy: demote (drift)
    auto_demote=True,
    phase_cooldown_records=200,
)
```

The `drift_gate` slot is named for its current usage (drift on the
accuracy axis). It is a `Gate`, not a special type. The auto-demote
loop calls `drift_gate.evaluate(records, current, Phase.RULE)` and
demotes on `target_better=True`.

### v1.1 scope (post-launch, harvested from launch feedback)

Add latency-axis support:

1. Extend `ClassificationRecord` with optional per-source latency
   fields.
2. Add a `WilcoxonGate` (or `LatencyThresholdGate`) implementation
   under the existing `Gate` protocol.
3. Add a `latency_gate` slot to `SwitchConfig` (optional; default None).
4. Auto-demote loop OR-composes accuracy and latency drift signals.
5. Document the n-axis pattern as the canonical way to extend Dendra.

### Renaming consideration

Today `drift_gate` carries a strong "accuracy drift" implication. If
we expect `latency_gate` and `cost_gate` next, we might consider
either:

- Keep `drift_gate` as the accuracy-axis demote slot, add `latency_gate`
  / `cost_gate` as siblings. Different *purpose* per slot is honest.
- Generalize to a single slot: `demote_gates: list[Gate] = []`.
  Each gate runs on every check; OR-composed. More uniform, but
  requires the user to label each gate's purpose for the audit log.

For v1 ship the first option (`drift_gate` only). For v1.1, evaluate
which feels more natural after we've added latency. **Don't over-design
the multi-axis API today** — but don't bake assumptions that prevent
extending to it tomorrow.

### What the exploration validated

- The direction-agnostic `Gate` protocol generalizes cleanly to at
  least 2 of the 5 axes considered with no changes (coverage, cost-
  threshold).
- 2 more axes (latency, variable-cost) need only a `ClassificationRecord`
  extension, no protocol change.
- 1 axis (privacy) doesn't fit gating naturally; better as a
  construction constraint.
- The "rule is the floor on every axis" intuition holds.
- The safety theorem extends bidirectionally and across n axes via
  union bound.

### What the exploration changes

Almost nothing in v1. The current Gate / GateDecision design holds.
Phase C goes ahead as planned with the `drift_gate` slot. Multi-axis
arrives in v1.1 by adding sibling slots; no breaking changes needed.

The two artifacts worth landing now:

1. **`docs/design/multi-axis-gating.md`** (this file).
2. **A note in the paper §10.5 future work** that the lifecycle
   safety claim extends to n axes by union bound, and that latency /
   cost gates are the natural next axis.

The bigger thing this validated: we picked the right naming
(`target_better`, single Gate protocol). If we'd kept `advance` /
`demote` baked in, axis 2 would have demanded a refactor. We're
already future-proof at the protocol level.

---

## 5. Vocabulary inventory: 1D bake-ins to fix in v1.x

The Gate protocol is direction-agnostic, but the *prose* surrounding
it still bakes in 1D up/down semantics. v1 ships the accuracy
lifecycle, where "floor" / "ceiling" / "above" / "below" are
intuitive. v1.x adds axes where these terms stop carrying the right
meaning (the rule isn't "below" on the latency axis, it's the
fastest; on cost, it's the cheapest; on privacy, it's the local
default). Catalog of terms to migrate when multi-axis lands:

| Today's term | 1D bias | Direction-agnostic alternative |
|---|---|---|
| "rule floor" | implies the rule is *below* | "rule anchor" or "rule reference" |
| "safety floor" | same | "safety anchor" |
| "phase ceiling" | implies higher = better | "phase bound" or "advancement bound" |
| "above the floor" / "below the floor" | up/down framing | "outside the safe envelope" / "inside the safe envelope" |
| "drifted below the rule" | down framing | "drifted away from the rule baseline" |
| "promote" / "demote" | up/down on accuracy lifecycle | keep where the lifecycle is meant; otherwise "step toward target" |
| "graduated autonomy" | implies linear progression | keep as-is for the accuracy lifecycle (it's accurate); add "directional autonomy" for the multi-axis framing |

Approximate scope of a rename pass at the time of v1.x:

- Code comments + docstrings: ~25 sites in `src/dendra/`.
- Design + paper docs: ~50 sites across `docs/design/`,
  `docs/papers/`, `docs/THREAT_MODEL.md`, plus `docs/working/` notes.
- Customer-facing docs (README, FAQ, getting-started): currently
  zero references; would only acquire them if v1 marketing leans into
  the floor metaphor (it doesn't today).

Approach for v1.x:
1. Land the multi-axis library work first (LatencyGate, CostGate, sibling slots, ClassificationRecord extension).
2. Pick the canonical term ("anchor" preferred for now, pending a working session on naming).
3. Sweep all sites; one PR.
4. Update the paper's §3.1 lifecycle table + §10 discussion to use the chosen term.

**Not v1 work.** v1 substance is correct under the current vocabulary;
the rename is a v1.x concern that arrives with the multi-axis API.

---

_Copyright (c) 2026 B-Tree Labs. Apache-2.0 licensed._
