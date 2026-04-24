# Enterprise licensing tiers — roadmap

**Status:** Draft 2026-04-23. Owner: Benjamin Booth (B-Tree Ventures).
Feeds into `docs/marketing/business-model-and-moat.md` §3.

## Why this doc exists

Earlier sizing (comparables: Modular-tier licensing at
$1M–$5M/year per enterprise) is *miles below* what Dendra can
underwrite at scale. This document sketches a pricing roadmap
that reflects the actual value Dendra captures in two
adjacencies: **AI-safety regulatory compliance** and
**multi-LLM procurement leverage**.

## What Dendra is actually worth, by buyer

### 1. Operational buyer (per-developer / per-switch)

Today's SaaS pricing ladder (from
`docs/marketing/business-model-and-moat.md` §3.1):

| Tier | Price | Ceiling | Anchor |
|---|---|---|---|
| Free hosted | $0 | 1 switch | dev-to-prod trial |
| Solo | $19/mo | 10 switches | individual-IC value |
| Team | $99/mo | 50 switches | small-team value |
| Pro | $499/mo | 200 switches | mid-market IT |
| Scale | $2 499/mo | 1 000 switches | large eng-org |

This tier tops out around **$30k ARR** per account. Good for
category creation. **Not** where the revenue live-ends.

### 2. Platform buyer — multi-LLM procurement ($100k–$1M ARR)

Once `dendra compare` produces a category-specific scorecard
(`docs/working/feature-llm-comparison.md`), Dendra becomes the
contracting-layer system of record for **which LLM deserves
which workload** inside the enterprise. That saves 20–40% of
LLM spend for a typical mid-cap deploying GPT + Claude + a
local model. At $5M+ annual LLM spend, 30% savings is $1.5M —
easily worth $100–300k in licensing.

Pricing anchor: **$100k entry, $1M ceiling** per enterprise,
priced as % of LLM spend saved. "You save $X; we take 10%."

### 3. Regulatory-compliance buyer ($1M–$10M ARR)

The real sleeper. EU AI Act, NIST AI RMF, state-level
insurance/finance rules all require **evidence that the
decision-maker for a consequential classification is itself
reviewable**. Dendra's provenance chain — rule-authored,
shadow-observed, statistically-gated, circuit-breaker-
protected, immutable outcome log — is a **compliance artifact
kit**, not just a classifier.

Once a bank / insurer / health system adopts Dendra for one
regulated classification, the adjacent classifications follow
(they're all subject to the same audit), and the licensing
moves from per-switch to **per-regulated-decision-class** to
**enterprise site license**.

Pricing anchor: **$1M entry, $10M ceiling** for an enterprise
site license covering every regulated classification at the
firm. "The audit package is worth more than the classifier."

### 4. Sovereignty / defense / critical-infrastructure ($10M+)

Dendra's rule-floor invariant (the rule is plain code, never
replaced) maps directly onto the regulatory framing used by
nuclear, aviation, and defense classification systems: a
"verified floor" primitive that a learned component sits
*above* rather than *replaces*. This is the high end of the
pricing envelope and needs a named account executive.

Pricing anchor: **$10M+** per agency / prime contractor, with
deployment in air-gapped environments (runs on the Rust + WASM
core, no outbound calls, all telemetry captured locally). This
tier earns the "graduated autonomy" framing its public-safety
interpretation.

## Tier-to-capability map (what unlocks at each step)

| Capability | Operational | Platform | Regulatory | Sovereignty |
|---|---|---|---|---|
| Classifier primitive + breaker | ✓ | ✓ | ✓ | ✓ |
| Multi-LLM scorecard (`dendra compare`) | — | ✓ | ✓ | ✓ |
| Category-specific routing YAML | — | ✓ | ✓ | ✓ |
| Immutable outcome log + signed provenance | — | — | ✓ | ✓ |
| Gate-audit trail per phase transition | — | — | ✓ | ✓ |
| Multi-user approval workflow | — | — | ✓ | ✓ |
| Air-gapped Rust/WASM runtime, no outbound calls | — | — | — | ✓ |
| On-prem key escrow, BYO HSM | — | — | — | ✓ |
| Contracted SLA on breaker + rule-floor behavior | — | — | — | ✓ |

## Why OSS first

The Apache-2.0 client SDK (decorator, config, storage,
telemetry, viz, adapters) is the adoption engine. Every
platform/regulatory/sovereignty sale originates from a team
that already uses the OSS SDK for a production classification.
The BSL-1.1 components (analyzer, graduation research tooling,
CLI) are what the paying tiers unlock.

**Pricing power is earned by adoption, not asserted.** The
SDK has to be *good enough to displace every hand-rolled
rule→ML pipeline in the enterprise* before the regulatory
narrative is credible.

## Go-to-market sequencing

1. **2026-Q2**: OSS launch (free tier usage). Goal = 1 000 stars,
   50 production deployments. No revenue.
2. **2026-Q3**: Operational tier launch (SaaS). Goal = 30 paying
   teams, $30k MRR. Category-creation marketing.
3. **2026-Q4**: `dendra compare` ships. Platform tier launches.
   First $100k ACV signed by a mid-cap AI-forward company.
4. **2027-H1**: First regulated-industry reference account
   (bank / insurer / healthcare). Regulatory tier priced as
   site license.
5. **2027-H2**: First sovereignty / defense deployment.

## Risks to the high-end pricing thesis

- **Commoditization via major-platform bundling** (AWS, GCP, Azure
  ship an "ML-graduation" primitive in their AI platforms, making
  Dendra a feature not a product). Mitigation: the **Rust + WASM
  core + patent claims** make Dendra *the primitive*, not a
  re-implementation. The integration surface matters less than
  the IP moat.
- **AI Act / NIST AI RMF interpretations don't require
  graduated-autonomy provenance**. Mitigation: the patent
  explicitly claims the provenance chain; even a non-
  compliance-driven adoption still benefits from the audit
  trail. And: we write the reference interpretation, not the
  regulator.
- **Customer concentration** at the high end. A single
  sovereignty account becomes 40% of revenue; we need 3+ to
  de-risk. Mitigation: sales cadence targets 3 sovereignty
  accounts before permitting any single one above 30% of
  bookings.

## Open questions for pricing discussions

- Should the regulatory tier bundle a named compliance-
  engineer retainer (high-touch, premium) or be pure software
  (high-margin, lower-touch)? Bias: retainer for first 3
  accounts to nail the narrative, then software-only.
- Should the sovereignty tier require a separate licensing
  entity (Axiom Labs Defense, LLC) for DFARS / ITAR /
  export-control clean-room purposes? Almost certainly yes —
  separate cap table, separate board, separate clearance
  requirements. That's a structural, not pricing, decision.
- How do we price air-gapped deployments where we can't
  observe usage? Honor-system audits + periodic attestation +
  spot-check rights in the contract. Not perfect, but common
  practice in the sovereignty tier.
