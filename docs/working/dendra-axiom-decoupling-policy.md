# Dendra / Axiom Coupling Policy

**Written:** 2026-04-20.
**Applies to:** all integrations of Dendra inside Axiom (and any
future B-Tree Ventures / Axiom Labs products that Dendra touches).
**One-sentence principle:** *Axiom is **Dendra-ready**; Axiom does
not require Dendra; Dendra never requires Axiom.*

**Institutional bundles** (SoilMetrix and other named customers):
shipped as a commercial bundle where Dendra is pre-licensed and
pre-wired as part of the deployment. Individual/OSS users install
Axiom stand-alone and opt into Dendra via `pip install
axiom[learning]` when they want it. Same code path, different
distribution choice.

---

## 1. Why this matters

Each product has its own market, pitch, and adoption path:

- **Dendra** is a universal classification primitive. Its pitch is
  "every production codebase needs this." Dependencies that require
  a specific platform (Axiom or otherwise) weaken that pitch.
- **Axiom** is an agent platform. Its pitch is "the infrastructure
  substrate for institutional LLM agents." A hard dependency on a
  classification library makes the install heavier and couples
  Axiom's fate to Dendra's release cadence.

**The coupling asymmetry we want:**

| Dimension | Dendra | Axiom |
|---|---|---|
| Must install for the other to run? | No | No |
| Knows about the other in code? | No | Yes (optional) |
| Breaks if the other is missing? | N/A | No (graceful fallback) |
| Ships tests that assert the other exists? | No | No |

Dendra is strictly upstream. Axiom is an opinionated consumer.

---

## 2. The rules

### 2.1 Dendra knows nothing about Axiom

- Dendra's `src/dendra/`, tests, and docs never reference Axiom,
  classroom, Neutron_OS, Vega, Keplo, or any sibling product.
- Dendra benchmarks are public datasets, never Axiom workloads.
- Dendra examples stay generic (triage, intent routing).

**Current status (2026-04-20):** compliant. Searched the dendra
repo: no mentions of "axiom", "keplo", "vega", "neutron" outside the
`docs/working/internal-use-cases-scan-2026-04-20.md` internal-scan
artifact (which is allowed — it's a scan report, not production code).

### 2.2 Axiom treats Dendra as an optional extra

- `dendra` appears in `[project.optional-dependencies]`, not in
  core `dependencies`.
- All axiom modules that touch Dendra guard their imports with
  `try: import dendra except ImportError: ...` and fall back to
  a no-op path.
- Caller-visible APIs in axiom never accept or return Dendra types
  (`LearnedSwitch`, `Outcome`, `Phase`, etc.). Dendra types stay
  internal to axiom.
- Axiom's public test suite must pass in BOTH modes: `pip install
  axiom` and `pip install axiom[learning]`.

### 2.3 The Axiom `dendra_adapter` shim

All Axiom-side Dendra integration goes through one small shim
(`axiom/src/axiom/infra/dendra_adapter.py`, see §3 for the
surface). This prevents try/except boilerplate from proliferating
and gives us one place to evolve the pattern.

The shim exposes:

- `optional_switch(name, rule, labels, author, *, safety_critical=False)` —
  returns a `LearnedSwitch | None` depending on whether Dendra is
  installed.
- `safe_classify(switch, input)` — runs `switch.classify(input)` in
  a try/except, no-ops when `switch is None`.
- `safe_record_outcome(switch, **kw)` — forwards to
  `switch.record_outcome`, no-ops when `switch is None`.

Axiom code never touches `from dendra import ...` directly outside
this shim.

### 2.4 What Axiom IS allowed to do

- Depend on Dendra's stable public API version (`dendra>=0.2,<1.0`).
- Ship examples in Axiom docs that show Dendra integrations.
- Publish case studies that namedrop Dendra (e.g., the turn-
  classifier integration feeds Dendra's paper §5 production
  validation).
- Reuse Dendra's outcome-log format for its own observability store.

### 2.5 What Axiom IS NOT allowed to do

- Re-export Dendra types from `axiom.*`.
- Make Dendra's `LearnedSwitch` appear in Axiom class signatures,
  protocol definitions, or config schemas.
- Require Dendra to pass Axiom's test suite.
- Teach Axiom's federation protocols to sync Dendra outcome logs
  (that is a Dendra concern; a future federation adapter can live
  in *Dendra* and consume Axiom's identity layer).

---

## 3. The shim — concrete surface

```python
# axiom/src/axiom/infra/dendra_adapter.py

from typing import Any, Callable, Optional

try:
    from dendra import (
        FileStorage, LearnedSwitch, Outcome, Phase, SwitchConfig,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def is_available() -> bool:
    return _AVAILABLE


def optional_switch(
    *,
    name: str,
    rule: Callable[[Any], str],
    labels: list[str],
    author: str,
    safety_critical: bool = False,
    storage_path: Optional["Path"] = None,
) -> Optional["LearnedSwitch"]:
    """Return a LearnedSwitch if Dendra is installed, else None.
    Callers must tolerate None throughout the classification path."""
    if not _AVAILABLE:
        return None
    cfg = SwitchConfig(phase=Phase.RULE, safety_critical=safety_critical)
    storage = FileStorage(storage_path) if storage_path else None
    sw = LearnedSwitch(
        name=name, rule=rule, author=author, config=cfg, storage=storage,
    )
    sw.labels = list(labels)
    return sw


def safe_classify(switch, input) -> None:
    """Run classify() if a switch exists; swallow everything."""
    if switch is None:
        return
    try:
        switch.classify(input)
    except Exception:
        pass


def safe_record_outcome(switch, *, input, output, outcome, **kw) -> None:
    """Record an outcome if a switch exists; swallow everything."""
    if switch is None:
        return
    try:
        switch.record_outcome(
            input=input, output=output, outcome=outcome, **kw,
        )
    except Exception:
        pass
```

Axiom classifiers call `optional_switch` at import and
`safe_classify` / `safe_record_outcome` in their decision paths.
A missing Dendra install produces zero side effects.

---

## 4. Why this coupling model is actually *good for both products*

### 4.1 Good for Dendra

- Preserves the **primitive** pitch — "any codebase" includes
  codebases that don't run Axiom.
- Anchors the federation story (Dendra paper §9.3 future work,
  business-model-and-moat.md §4.1) in Dendra's own contract, not
  in Axiom's.
- Axiom's turn-classifier case study feeds Dendra's paper without
  creating a reader expectation that Dendra users must adopt Axiom.

### 4.2 Good for Axiom

- Lets Axiom stay lightweight for users who just want the agent
  platform. Dendra's install footprint (sklearn optional extra,
  etc.) stays out of the base install.
- Axiom's release cadence is independent — Dendra 1.0 doesn't
  force an Axiom bump.
- Classroom / Vega / federation work in environments (air-gapped,
  regulated) where dropping an extra dependency is a big deal.
- When/if Axiom Labs decides to productize Dendra-in-Axiom as a
  bundled offering, the bundle is additive — no retrofit needed.

### 4.3 Good for Axiom Labs as the commercial entity

- Two products, two distinct go-to-market motions, one shared
  commercial parent.
- Neither product is a hostage to the other's roadmap.
- Customer-A can buy Dendra without being asked about Axiom;
  Customer-B can buy Axiom Enterprise without paying for Dendra
  primitives they don't yet want.
- The integration pattern (this shim) IS the bundled-product
  feature when we want to sell both.

### 4.4 Institutional-bundle path (named enterprise customers)

Enterprise Axiom deployments — SoilMetrix and other named
customers — are bundled: Dendra licenses are granted as part of
the institutional contract and Dendra is pre-installed/pre-wired
on those deployments. The customer experience is "Axiom with
Dendra on by default" — no opt-in step.

How this works given §2's decoupling rules:

- Same code, same shim — institutional bundles are distribution
  SKUs, not forks.
- Install profile: `pip install axiom[learning]` is part of the
  institutional bootstrap script.
- Dendra license granted via the existing commercial-licensing
  mechanism (Axiom Labs handles the paperwork).
- Outcome logs can, at the customer's option, be federated across
  institutional nodes — this is a Dendra feature consumed by the
  bundle, not a new coupling.

**Axiom's public-facing positioning:** "Dendra-ready." Phrase is
adoption-neutral — it tells operators Axiom integrates cleanly if
they also run Dendra, without claiming Dendra is required. Same
pattern LaunchDarkly uses ("OpenTelemetry-ready"), Sentry uses
("Sourcemap-ready"), etc.

---

## 5. Retroactive changes this policy forces

As of this writing:

- [ ] Move `dendra>=0.2.0` from `axiom/pyproject.toml`
      `dependencies` to `[project.optional-dependencies]` as
      the `learning` extra.
- [ ] Add `axiom/src/axiom/infra/dendra_adapter.py` (the
      shim above).
- [ ] Refactor `axiom/src/axiom/agents/turn_classifier.py` to use
      the shim (currently has a hard `from dendra import ...`).
- [ ] Refactor `axiom/tests/test_turn_classifier_dendra.py` to
      tolerate `dendra_adapter.is_available() == False`.
- [ ] Add an `axiom/tests/test_no_dendra.py` that runs with Dendra
      stubbed out and confirms all classifier paths still work.
- [ ] Update the internal-use-case scan doc's §2 + §3 to note
      "integrates via adapter shim; optional dep."
- [ ] Future integrations (auto_classifier.py sensitivity
      router.py) use the shim on first write — no hard imports.

---

## 6. What this policy does NOT preclude

- Rich, opinionated co-marketing between Dendra and Axiom.
- A bundled "Axiom Labs production stack" SKU that ships both.
- Shared dev tooling (the same repo workspace, shared .envrc,
  shared CI templates).
- Cross-referencing each other's docs.
- Both products sharing a commercial brand ("Axiom Labs" as DBA).

The policy is about *code-level coupling*, not business-level
affinity.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0 licensed._
