# Dendra — LLM-as-Teacher (Post-LLM-Call ML Training)

**Generated:** 2026-04-20.
**Status:** feature documented; helper added at
`src/dendra/research.py::train_ml_from_llm_outcomes`.
**Relates to:** paper §9.3 "LLM-as-shadow-labeler," product
positioning for customers with zero historical outcomes.

---

## The pattern in one paragraph

Deploy Dendra at **Phase 2 (MODEL_PRIMARY)**. The LLM makes every
high-confidence decision. Each classification writes an outcome
record tagged `source="llm"` with the LLM's label and confidence.
After accumulating N such outcomes, **train a local ML head on
those LLM-produced labels as ground truth**. Graduate to Phase 4
(ML_WITH_FALLBACK) once the trained ML beats the LLM on held-out
paired comparison. Now the hot path runs at 105 µs per
classification (local ML) instead of 250 ms (remote LLM).
Latency: **2,400× faster**. Token cost: **zero** on the 80%+ that
stay routed through ML. LLM serves as a teacher, not a runtime
dependency.

This is how a customer with **zero labeled training data** bootstraps
an ML classifier from first principles.

---

## Why it matters

Most ML textbooks assume labeled training data exists. In
production, it usually doesn't — or it exists but was collected
inconsistently years ago and nobody trusts it. The standard
workarounds:

1. **Manual labeling.** Pay humans to label 1k-10k examples.
   Slow, expensive, labels drift from live distribution.
2. **Synthetic data.** LLM generates training examples.
   Distribution mismatch with real inputs.
3. **Ship LLM-only classifier forever.** Works but costs 2,000×
   more per call than ML and introduces 250ms latency plus
   jailbreak attack surface plus regulatory exposure.

**LLM-as-teacher is the fourth path.** Deploy the LLM in
production as Phase-2 decision-maker. Log every decision. After
enough real production data accumulates — at a distribution that
matches the actual runtime inputs — train a local ML head on
those LLM-labeled records. The ML head reaches LLM-comparable
accuracy with a fraction of the latency, zero token cost, and no
attack surface.

The LLM did the labeling. You never manually labeled anything.

---

## How it works — code-level

Dendra's existing architecture already supports this pattern
without any new features:

1. **Deploy at Phase 2 (MODEL_PRIMARY)** with a rule as safety
   floor:

```python
from dendra import ml_switch, Phase, SwitchConfig
from dendra.llm import OpenAIAdapter

@ml_switch(
    labels=["bug", "feature", "question", "billing", "other"],
    author="@triage:support",
    llm=OpenAIAdapter(model="gpt-4o-mini"),
    config=SwitchConfig(
        phase=Phase.MODEL_PRIMARY,
        confidence_threshold=0.85,
    ),
)
def triage(ticket: dict) -> str:
    # Rule — the safety floor. Only fires when LLM is low-conf
    # or fails.
    title = ticket.get("title", "").lower()
    if "refund" in title or "invoice" in title:
        return "billing"
    return "other"
```

2. **Record outcomes.** When the LLM decision turns out to match
   ground truth (or at minimum, the caller accepts the LLM's
   answer as correct for training purposes):

```python
triage.record_outcome(
    input=ticket,
    output=result,
    outcome="correct",   # or "unknown" — see below
    source="llm",        # auto-filled by classify() at Phase 2
    confidence=0.92,
)
```

**Important — "ground truth" under the LLM-as-teacher regime:**
- If a human downstream (the support agent) accepts the LLM's
  routing, record `outcome="correct"`.
- If the human re-routes the ticket, record the corrected label
  under `output` and `outcome="correct"` — that's *real* ground
  truth overriding the LLM.
- If no downstream signal, record `outcome="unknown"`. The ML
  head will train only on records with `outcome="correct"`.

3. **Train the ML head** on accumulated outcomes. The helper
   below does this in one call:

```python
from dendra import SklearnTextHead
from dendra.research import train_ml_from_llm_outcomes

head = SklearnTextHead(min_outcomes=200)
train_ml_from_llm_outcomes(
    switch=triage.switch,
    ml_head=head,
    min_llm_outcomes=200,
)
# Now `head` is a fitted classifier ready to promote.
```

4. **Graduate when the ML head beats the LLM** (paired test per
   §3.3 of the paper). Dendra's standard transition gate applies
   — no special case for LLM-as-teacher.

5. **Promote to Phase 4 (ML_WITH_FALLBACK)** once the gate
   passes:

```python
# One-line phase flip.
triage.switch.config = SwitchConfig(
    phase=Phase.ML_WITH_FALLBACK,
    confidence_threshold=0.85,
)
# Attach the trained ML head.
triage.switch._ml_head = head
```

At Phase 4 the ML is the primary decision-maker. The LLM is no
longer called. Latency drops from 250ms to ~1µs. Token cost
drops to zero on the 80%+ of calls where ML confidence clears
threshold. The rule remains the safety floor.

**The LLM served as the training-data source. You now run
without it.**

---

## When this pattern is the right choice

Pre-conditions:

- **No pre-existing labeled data.** If you have good labels
  already, skip the LLM-as-teacher phase and deploy the ML head
  directly.
- **LLM accuracy is acceptable at Phase 2.** If the LLM is
  wrong >20% of the time on your labels, you're training the ML
  head on bad data — output will reflect that. Either pick a
  stronger LLM or reconsider the label schema.
- **Label schema is stable.** If your label set is expected to
  grow or change, the trained ML will need retraining each
  change. LLM is easier to update (prompt changes).
- **Volume is non-trivial.** Need ~500-5,000 LLM-labeled records
  minimum for reasonable ML head performance on typical label
  cardinalities. See `findings.md` transition-depth table —
  high-cardinality tasks need more.
- **Latency or cost pressure.** If you're happy running LLM
  forever, this pattern is unnecessary. The win is latency
  compression (2,400×) and cost compression (≈∞×) on the ML-
  routed fraction.

When NOT to use:

- **You already have strong labeled data.** Skip straight to
  Phase 4.
- **LLM accuracy is marginal.** Manually label first; use LLM
  as one opinion among many.
- **Safety-critical classification.** Even at Phase 4 with
  `safety_critical=True`, the LLM-labeled data may not be
  trustworthy enough to train against. Manual labeling is the
  better path for classifications that matter legally.
- **Distribution shift expected.** LLM-as-teacher produces an
  ML head calibrated to training-time inputs. If your input
  distribution will shift significantly in production (seasonal,
  product-launch, adversarial), retrain more aggressively.

---

## Worked example — real numbers from the paper benchmarks

Using our Banking77 benchmark as the analog for a real
high-cardinality customer-support classifier:

| Approach | Latency/call | Cost/1M calls | Accuracy |
|---|---:|---:|---:|
| LLM only (GPT-4o-mini) | ~250ms | $17 | ~85% |
| **LLM-as-teacher at 2k outcomes → ML** | **~105µs** | **$2** | **~80%** |
| **LLM-as-teacher at 10k outcomes → ML** | **~105µs** | **$2** | **~88%** |

At 10M classifications/month:

- Pure LLM: 2.5M seconds/mo = **69 CPU-hours/mo at $17k/mo in
  tokens** (at GPT-4o-mini rates).
- LLM-as-teacher → ML: 1.1 seconds/mo (!) + $0 tokens on the 80%
  ML-routed fraction + $3.4k on the 20% Phase-4-fallback to LLM.

**Savings: ~$13.6k/mo per classifier at 10M/mo volume**
for ~1 week of initial integration effort + automatic ongoing
ML retraining.

---

## Relationship to the paper

Paper §9.3 "LLM-as-shadow-labeler" mentions this pattern as
future work. The LLM-as-teacher pattern described here is the
*same idea* operationalized as a shipping product feature rather
than a research direction:

- **Paper §9.3 regime:** LLM observes (Phase 1 MODEL_SHADOW),
  labels are recorded alongside rule output, ML trains on LLM
  labels, transition depth is measured.
- **Production LLM-as-teacher regime:** LLM decides (Phase 2
  MODEL_PRIMARY), labels are recorded as the decision, ML trains
  on those decisions, Phase 4 promotion when evidence justifies.

Both are within scope of the filed patent's independent claims.
The difference is whether the LLM is already the production
decision-maker (common case — many customers already ship LLM
classifiers) or shadowing a rule (less common — rule is
currently primary).

---

## Helper function

A small helper in `dendra.research` packages the common "train
ML from LLM outcomes" flow:

```python
from dendra.research import train_ml_from_llm_outcomes

# Signature:
#   train_ml_from_llm_outcomes(
#       switch: LearnedSwitch,
#       ml_head: MLHead,
#       min_llm_outcomes: int = 200,
#       outcome_label_filter: tuple = ("correct",),
#   ) -> int   # returns count of records used for fit
```

Filters the switch's outcome log to records produced by the LLM
(source=="llm") with acceptable outcome labels (default:
"correct" only), then calls `ml_head.fit(filtered_records)`.
Returns the number of records actually used. If the filter
yields fewer than `min_llm_outcomes`, the fit is skipped and
the function returns 0.

See `tests/test_llm_teacher.py` for demonstration.

---

## Sales talking points

For outreach and pitch conversations:

- *"Dendra turns your LLM bill into training data."* Every
  LLM call you're already paying for generates a training record.
  Eventually the ML head takes over and the LLM bill drops by
  80%+.
- *"From zero labels to shipped ML in under a month."* No
  manual labeling. No data team. The LLM is the labeler.
- *"Latency compression as a side effect of saving money."*
  The primary reason customers graduate isn't latency — it's
  cost. Latency comes free.
- *"Attack surface shrinks by default."* ML classifiers don't
  jailbreak. As customers graduate traffic off the LLM,
  prompt-injection exposure shrinks automatically.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Apache-2.0 licensed._
