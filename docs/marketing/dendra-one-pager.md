# Dendra — Graduated Autonomy for Production Classification

**By Axiom Labs (a B-Tree Ventures DBA).** Apache-2.0 licensed.

---

## The problem nobody has solved

Every production system has classification decisions. Triage a ticket.
Route an intent. Score content quality. Pick a retrieval strategy.

**Day-zero reality:** you have no data. You ship a rule.
**Day-N reality:** you have outcomes piled up, but the rule still runs.
**Why?** Because nobody invested engineering time to graduate it —
and every team does that migration ad-hoc, without a primitive.

Dendra is the primitive.

---

## How it works

One decorator. Six phases. One safety floor.

```python
from dendra import ml_switch

@ml_switch(labels=["bug", "feature_request"], author="@ben:axiom-labs")
def triage(ticket):
    if "crash" in ticket["title"].lower():
        return "bug"
    return "feature_request"
```

- **Phase 0 — RULE**: your function runs exactly as written.
- **Phase 1 — LLM_SHADOW**: an LLM predicts alongside; rule still decides.
- **Phase 2 — LLM_PRIMARY**: LLM decides when confident; rule is the floor.
- **Phase 3 — ML_SHADOW**: trained ML head runs behind the primary.
- **Phase 4 — ML_WITH_FALLBACK**: ML decides when confident; rule floor.
- **Phase 5 — ML_PRIMARY**: ML decides; circuit breaker → rule on failure.

Every transition is gated by statistical evidence (paper §3.3), signed
by the caller's identity, and auditable. `safety_critical=True` caps
graduation at Phase 4 so the rule remains the contract.

---

## What the data says (measured on four public benchmarks)

Dendra's transition-curve runner was executed against the four standard
intent-classification benchmarks. Figure 1 (this repo, `docs/papers/
2026-when-should-a-rule-learn/results/figure-1-transition-curves.png`)
shows the full transition curves.

| Benchmark | Labels | Rule acc | ML final | Gap | Crossover |
|---|---:|---:|---:|---:|---:|
| ATIS       |  26 | 70.0% | 88.7% | +18.7 | **≤500 outcomes** |
| HWU64      |  64 |  1.8% | 83.6% | +81.8 | ≤1,000 outcomes |
| Banking77  |  77 |  1.3% | 87.8% | +86.5 | ≤1,000 outcomes |
| CLINC150   | 151 |  0.5% | 81.9% | +81.3 | ≤1,500 outcomes |

Two regimes emerge cleanly:

### Regime A — narrow-domain, low-cardinality ("the rule works for years")

**Example:** ATIS (flight-booking, 26 intents). Rules catch 70% on
day one — that's a viable triage system. Dendra's value: it tells you
*exactly* when to graduate (around 500 logged outcomes) and whether
ML's +18 point gain justifies the migration.

### Regime B — broad-domain, high-cardinality ("rules never worked")

**Example:** CLINC150 (151 intents including out-of-scope). Day-zero
rules hit 0.5%. You *cannot* ship an intent router with 151 labels from
100 examples. Dendra's value: its outcome-logging is the scaffolding
that lets you collect enough data to train ML *while still shipping
something*. Without it, you're either rule-broken or ML-blocked.

---

## Ideal use cases

**Strongest fit:**

- **Medium-cardinality classification** (10-50 labels) with domain
  structure. You can ship a rule day-one and want the graduation
  question answered statistically, not by gut.
- **High-cardinality production systems** (50+ labels) that need to
  ship before training data exists. The rule is a fig leaf; Dendra's
  outcome-log is what makes the eventual ML migration possible.
- **Safety-critical decision points** (authorization, moderation,
  classification boundaries) where the rule is a non-negotiable floor
  and ML graduation must be gated.
- **Teams with multiple classification sites** — 10 triage points, 5
  intent routers, 3 content gates — who want one migration primitive,
  not ten.

**Not the best fit:**

- Binary classification with abundant day-one labeled data. Just train.
- Problems where an off-the-shelf LLM classifier hits 90%+ zero-shot.
  Graduation happens on day two and the deeper phases are overkill.
- Systems where outcomes aren't observable post-hoc (no ground-truth
  feedback signal ever arrives).

---

## Why Dendra, not X

- **vs. AutoML (H2O, AutoGluon)**: AutoML selects a model given
  training data. Dendra is about the *path* from no training data to
  a deployed ML classifier — and keeping the rule as a safety floor
  the whole way.
- **vs. online learning (Vowpal Wabbit)**: online learners adapt
  continuously but can't guarantee rule-floor safety. Dendra's safety
  theorem bounds worse-than-rule probability at the Type-I error rate
  of its statistical gates.
- **vs. hand-rolled `try_ml_else_fallback` code**: most production
  teams ship a version of this. Dendra turns it into one library,
  with uniform phase semantics, statistical guards, signed audit
  records, and a transition-curve runner that tells you *when* the
  migration is earned.
- **vs. rule engines (Drools, rule-based triage)**: those are great
  at shipping rules. They have no story for graduating to ML.

---

## What ships today

- **`dendra` v0.2.0** on PyPI (soon). Apache 2.0.
- Zero required runtime dependencies. `sklearn`, `datasets`, `openai`,
  `anthropic`, `httpx`, `matplotlib` are all optional extras.
- Provider-agnostic LLM: OpenAI-compatible, Anthropic, Ollama, llamafile.
- `@ml_switch` decorator, `LearnedSwitch` class, `FileStorage` /
  `InMemoryStorage`, telemetry hooks (`NullEmitter` / `StdoutEmitter`
  / `ListEmitter`), `SklearnTextHead` as the zero-config ML default.
- `dendra bench` CLI — reproduce our transition curves on any of the
  four shipped benchmarks with one command.
- `dendra plot` CLI — render Figure 1-style transition curves.
- `dendra roi` CLI — self-measured ROI report from your own outcome logs.
- Full paper draft: `docs/papers/2026-when-should-a-rule-learn/`
  (target: NeurIPS 2026 main track).
- Provisional patent filing package ready (`docs/working/patent/`).

---

## Pricing at a glance

| Tier | Price | For |
|---|---|---|
| **OSS library** | Free forever, Apache 2.0 | Everyone |
| **Free hosted** | $0 | Side projects, 10k classifications/mo |
| **Solo** | $19/mo | Freelancers, 100k/mo |
| **Team** | $99/mo | Startup eng teams, 1M/mo |
| **Pro** | $499/mo | Mid-sized orgs, 10M/mo |
| **Scale** | $2,499/mo | Large orgs, 100M/mo |
| **Utility** | $0.01/1k | Metered, above Scale cap |
| **Enterprise** | $50-500k/yr | Regulated + Fortune 1000 |

Every paid tier has a published price. No "contact us" gating
except at Enterprise. Volume-based (not per-seat) so a classifier
adoption doesn't penalize team growth. **96-99% gross margin
across self-serve tiers**, driven by the invention's sub-microsecond
switch overhead.

Full unit economics + pricing rationale: `business-model-and-moat.md`
§3-§5. Revenue sequencing for bootstrap-sustainable Y1:
`entry-with-end-in-mind.md` §7.

---

## Contact

- Maintainer: Benjamin Booth — `ben@b-treeventures.com`
- Code: [github.com/axiom-labs-os/dendra](https://github.com/axiom-labs-os/dendra)
- Paper: target NeurIPS 2026 ("When Should a Rule Learn? Transition
  Curves for Safe Rule-to-ML Graduation").

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0 licensed._
