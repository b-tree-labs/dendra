# Dendra — Pricing Deep-Dive

**Companion to:** `business-model-and-moat.md` §3 (pricing ladder)
and `entry-with-end-in-mind.md` §7 (GTM sequencing).
**Generated:** 2026-04-20.
**Audience:** internal + due-diligence. Contains real cost math,
peer-comp specifics, and tier-threshold derivations.

**Purpose:** replace gut-feel 10× volume jumps with a defensible
cost-and-market basis. Any pricing change must re-derive through
this doc's logic.

---

## 1. Unit economics — actual cost to serve

### 1.1 Per-classification infrastructure cost (at AWS list prices, April 2026)

A classification that reaches Dendra Cloud generates, at minimum:

| Cost item | Per-call unit cost | Source |
|---|---:|---|
| ALB request ingress | $0.0000004 | AWS $0.008/hour + $0.008/LCU, amortized |
| Lambda invocation (128 MB, 50 ms) | $0.0000001 | AWS $0.20/1M invocations |
| DynamoDB write (on-demand, ~300 B) | $0.00000125 | AWS $1.25/1M writes |
| S3 PUT (batched outcome, 1:100) | $0.00000005 | AWS $0.005/1k, amortized |
| CloudWatch metric | $0.000000003 | AWS $0.30/metric/mo, amortized |
| Egress (ack response, 1 KB) | $0.00000009 | AWS $0.09/GB |
| **Infra cost per classification** | **~$0.0000017** | Total |

**Per 1M classifications: ~$1.70 in pure infra.**

Reserved capacity (DynamoDB provisioned, Lambda layered) drops
this to **~$0.80/1M** at Pro-tier volume and above — we switch
customers there automatically.

### 1.2 Verdict-log storage (ongoing)

- Per outcome record: ~250 bytes JSONL.
- 1M records = 250 MB.
- S3 Standard at $0.023/GB-mo = **$0.006/mo per 1M outcomes**.
- DynamoDB metadata index at $0.25/GB-mo = **$0.06/mo per 1M**.
- **Total storage cost: ~$0.07/mo per 1M outcomes retained.**

Self-rotating storage caps retention; an older rotated-out record
drops out of storage immediately. Customers' total storage is
bounded by `segments × max_segment_size` (default ~576 MB / switch).

### 1.3 Managed ML-head inference (optional add-on)

Dendra's default ML head (TF-IDF + LR via scikit-learn) runs
in-process at **~105 µs per predict** (measured, §8 of
`industry-applicability.md`). On a shared 2-vCPU container running
continuously for the customer base:

- Container fixed cost: ~$30/mo (Fargate Spot, 0.25 vCPU/0.5GB)
- Throughput: ~9,500 predicts/sec per core at 105 µs
- Marginal cost: near-zero until saturation.
- Amortized across typical mid-tier customer mix: **~$0.02 per
  1M ML predicts.**

Higher-tier ML heads (sentence-transformer + classifier) need
~2 ms per predict and a GPU container at ~$0.40/hr on Spot.
That's **~$0.55 per 1M** — included in pricing for the Pro+
tiers when customers opt into transformer-backed domain packs.

### 1.4 LLM-routed classifications — pass-through only

LLM inference is NOT our cost to bear. Customers provide their
own OpenAI / Anthropic / Azure / Bedrock credentials via a
BYO-keys proxy layer. We do not mark up LLM tokens.

This matches the LangSmith / Braintrust / Helicone / Arize
Phoenix industry standard (§2.3 below) and keeps our unit
economics insulated from LLM price swings.

Dendra's only ancillary cost on LLM-routed classifications is:

- The same infra cost as rule-routed (§1.1): ~$0.0000017
- Plus one extra LLM-proxy hop: <$0.0000001

Still ~$1.70 per 1M on our books.

### 1.5 Billing / Stripe fees

Every paid tier pays Stripe 2.9% + $0.30 per transaction.

| Tier | Monthly price | Stripe fee | Effective revenue |
|---|---:|---:|---:|
| Solo | $19.00 | $0.85 | $18.15 |
| Team | $99.00 | $3.17 | $95.83 |
| Pro | $499.00 | $14.77 | $484.23 |
| Scale | $2,499.00 | $72.77 | $2,426.23 |

Stripe fee as % of price:

- Solo: 4.5% — noticeable but tolerable.
- Team / Pro / Scale: 2.9-3.2% — industry-normal.
- **This is why a $9/mo tier is untenable** — at $9 the fee is
  $0.56 (6.2%), a double-hit.

Annual pricing (collected upfront) reduces fees by ~50% because
it's one transaction per year. Offering 15% annual-billing
discount is economically neutral and captures ~40% of willing
customers.

### 1.6 Full cost-of-goods-sold per tier, Phase-0 customer

Assumes customer at typical volume for tier, all-Phase-0
classifications (no LLM routing through us, no managed ML
inference):

| Tier | Monthly vol | Infra (§1.1) | Storage (§1.2) | Total COGS | Price | Gross margin |
|---|---:|---:|---:|---:|---:|---:|
| Free | 10k | $0.02 | <$0.01 | $0.03 | $0 | n/a (loss-leader) |
| Solo | 100k | $0.17 | $0.01 | $0.18 | $19 | **99.1%** |
| Team | 1M | $1.70 | $0.07 | $1.77 | $99 | **98.2%** |
| Pro | 10M | $8.00 | $0.70 | $8.70 | $499 | **98.3%** |
| Scale | 100M | $80 | $7 | $87 | $2,499 | **96.5%** |

At the reserved-capacity Pro+ pricing, margins are strictly
better at volume, not worse. Software-company economics.

### 1.7 COGS when customer is LLM-heavy (Phase 2+ through our proxy)

Customer at Team tier, 1M classifications/month, 50% routed
through LLM via our BYO-keys proxy:

| Cost item | Cost |
|---|---:|
| Infra (§1.1, 1M calls) | $1.70 |
| Storage | $0.07 |
| LLM proxy compute (extra) | $0.10 |
| **Dendra-side COGS** | **$1.87** |
| LLM API cost (customer's direct bill to OpenAI/Anthropic) | $7.50 |
| | (not on our books) |

**Our margin at Team with heavy LLM is still 98.1%.** BYO-keys
keeps us clean.

---

## 2. Peer-comp grounding (2026 pricing landscape)

### 2.1 Direct analogs — LLM/AI observability tools (dev-tools SaaS)

| Product | Free tier | Paid entry | Metric | Primary focus |
|---|---|---|---|---|
| **LangSmith** | 5k traces/mo | $39/mo (50k traces) | Traces | LLM app observability |
| **Braintrust** | 1k evals/mo | $249/mo (100k evals) | Evals | LLM evaluation/testing |
| **Helicone** | 10k requests/mo | $20/mo (100k requests) | Requests | LLM request logging |
| **Arize Phoenix** | Self-host free; cloud $0 (limited) | $400/mo starter | Traces | ML + LLM observability |
| **Weights & Biases** | 200 GB-mo free | $50/user/mo | per-seat | ML experiment tracking |
| **Langfuse** | 50k events/mo free | $59/mo (100k events) | Events | LLM observability |
| **OpenInference** | OSS | — | — | OpenTelemetry for LLMs |

**Dendra's position:** below Braintrust ($249 floor is high), above
Helicone ($20 for 100k is underpricing), aligned with Langfuse ($59
for 100k) but higher-value unit (classification decisions, not
raw logs).

### 2.2 Classification-adjacent analogs

| Product | Free tier | Paid entry | Notes |
|---|---|---|---|
| **Sentry** (error monitoring) | 5k errors/mo | $29/mo (50k errors) | Per-event, rising tiers |
| **Honeycomb** (observability) | 20M events/mo | $70/mo (1B events) | Very generous free, upmarket paid |
| **LogDNA / Mezmo** (logs) | free 10GB | $49/mo (20GB) | Per-data-volume |
| **PostHog** (product analytics) | 1M events/mo | $450/mo (10M events) | Generous free, expensive paid |
| **LaunchDarkly** (feature flags) | 1k MAU | $100/mo+ (per-seat) | Per-seat (we explicitly don't) |
| **Snyk** (vuln scanning) | Open-source free | $25/dev/mo | Per-developer |
| **SonarQube** (code quality) | Self-host free | $12/dev/mo | Per-developer |

**Pattern observed:** developer-tools SaaS generally converges on
either (a) per-seat pricing ($12-50/dev/mo, LaunchDarkly / Snyk /
Sonar / W&B) or (b) volume-based pricing ($0-100 free tier →
$29-250/mo at entry, Sentry / Helicone / Langfuse / PostHog).

We are firmly in camp (b). Per-seat is a poor fit for a primitive
that gets adopted bottom-up across many classification sites.

### 2.3 BYO-LLM-keys is standard

Every LLM-observability product that handles LLM routing uses
customer-provided keys:

- **LangSmith:** BYO OpenAI/Anthropic.
- **Braintrust:** BYO.
- **Helicone:** BYO via proxy.
- **Arize Phoenix:** BYO.
- **Langfuse:** BYO.

Dendra adopts this pattern — pass-through, zero LLM-cost risk on
our books. Customers' LLM bills go directly to the provider.

### 2.4 Metered-overage pricing in 2026

Peer metered-overage rates (per 1k "events" in the product's
unit):

| Product | Overage rate | Unit |
|---|---|---|
| **LangSmith** | $0.50 / 1k traces | Traces |
| **Helicone** | $0.20 / 1k requests | Requests |
| **Sentry** | $0.0025 - $0.0135 / event | Events (depending on tier) |
| **Langfuse** | $0.60 / 1k events | Events |
| **Honeycomb** | $0.50 / 1M events | Events (generous) |

**Dendra's proposed overage: $0.01 / 1k classifications.** This
is aggressive on the low end — justified because:
- Our marginal cost per classification is ~$1.70/1M = $0.0017/1k
  — we're pricing at ~6× marginal, not 50× like LangSmith.
- Classification is the primitive, not a trace. It's expected
  volume to be high.
- Keeping overage low encourages customers to keep more volume
  on Dendra rather than routing around us.

Tapering to **$0.005 / 1k above 1B/mo** keeps hyperscale
customers engaged without gouging. Still 3× marginal cost.

---

## 3. Tier thresholds — derived, not gut-chosen

The previous version of this doc used 10× volume jumps (10k, 100k,
1M, 10M, 100M) that felt tidy but had no defensible basis. Here's
the re-derivation from first principles.

### 3.1 Persona-DAU math

Each tier target should cover a specific persona. Persona is
parameterized by **daily-active-users (DAU)** of the customer's
product and **classifications-per-DAU-per-day**.

Assume 1 classification per DAU per day as a typical baseline
(chatbot-like workloads). Many products run higher (content
moderation at 5-10/DAU/day); few run lower.

| Persona | DAU | Classifications/day | Classifications/mo (30d) |
|---|---:|---:|---:|
| Side project / hobby SaaS | 50-300 | 50-300 | 1.5k - 9k |
| Indie freelancer tool | 300-3k | 300-3k | 9k - 90k |
| Early-stage startup | 3k-30k | 3k-30k | 90k - 900k |
| Scale-up SaaS | 30k-300k | 30k-300k | 900k - 9M |
| Multi-product SaaS | 300k-3M | 300k-3M | 9M - 90M |
| Large SaaS / Enterprise | 3M+ | 3M+ | 90M+ |

### 3.2 Mapping personas to tier thresholds

| Tier | Threshold | Persona | DAU range | Justification |
|---|---:|---|---:|---|
| **Free** | 10k/mo | Hobby / eval | 50-300 | Covers 30 days of real traffic; generous vs Sentry/Helicone 5k-10k; loss-leader per §1.6 |
| **Solo** | 100k/mo | Indie / freelancer | 300-3k | Fits side-SaaS with ~1-2k DAU; consistent with Vercel Pro $20 |
| **Team** | 1M/mo | Early-stage startup | 3k-30k | 2-4× Sentry Team ($29, 50k errors); higher-value unit (classifications not errors) |
| **Pro** | 10M/mo | Scale-up SaaS | 30k-300k | Aligns with Datadog Pro ($465/mo across 15 hosts); 10× Sentry Business ($80, 100k errors) |
| **Scale** | 100M/mo | Large SaaS | 300k-3M | Below where LaunchDarkly / Honeycomb push into Enterprise; captures multi-BU orgs self-serve |
| **Metered** | above 100M | Hyperscale | 3M+ | Expected; matches industry convention at this volume |

### 3.3 Why the thresholds are approximately 10×

The 10× jumps fall out of the 10× DAU jumps between personas
(hobby → indie → startup → scale-up → multi-product → large), not
from arithmetic aesthetics. If DAU brackets were 5× or 20× the
thresholds would follow.

### 3.4 Price points anchored to market

Each tier's price is calibrated against peer comps at the same
volume bracket:

| Tier | Dendra price | Peer at same volume | Delta |
|---|---:|---:|---|
| Solo $19 | $19 | Helicone $20 (100k reqs); Sentry Team $29 (50k errors) | slightly below |
| Team $99 | $99 | Langfuse $59 (100k events); Sentry Business $80 (100k); Honeycomb Pro $70 (20M) | slightly above — justified by classification being higher-value than raw logs |
| Pro $499 | $499 | Arize Phoenix starter $400; Braintrust $249 (100k evals) | at market |
| Scale $2,499 | $2,499 | LaunchDarkly Enterprise ~$2-5k/mo; Datadog multi-host $2-3k/mo | at market |
| Enterprise $50-500k/yr | custom | LangSmith Enterprise similar; Datadog Enterprise $500k+ | at market |

The Team-tier premium over Langfuse ($99 vs $59) is the main
pricing bet: we argue classification primitives deliver enough
more value than raw LLM logging to justify ~60% more. If this
bet is wrong at launch, drop Team to $79 — it's the lever most
likely to move.

### 3.5 What about per-seat pricing?

Peer-comp data shows per-seat pricing is used when the product's
value scales with developer count (Snyk, Sonar, W&B, LaunchDarkly
for feature-flag ergonomics). **Classification volume scales with
end-user traffic, not developer count.** A 3-engineer team might
run 100M classifications across 20 sites; a 300-engineer team
might run 10M across 5.

Volume-priced tiers are correct. Including "team seats" in each
tier (5/10/50/unlimited) is a collaboration feature only —
shared workspaces, audit views, approval workflows — and doesn't
meter classifier usage.

---

## 4. Overage design

### 4.1 Base tier + overage

Every tier's included volume is the **sweet spot** for the
persona, not the ceiling. Overage kicks in smoothly above the
tier cap:

| Tier | Included | Overage rate |
|---|---:|---|
| Solo | 100k | $0.10/1k above (soft) |
| Team | 1M | $0.03/1k above |
| Pro | 10M | $0.015/1k above |
| Scale | 100M | $0.01/1k above |
| — above 1B | — | $0.005/1k |

Note the tapering: overage rate shrinks at each tier because
our marginal cost shrinks (reserved capacity kicks in at Pro+).
This makes the upgrade math attractive — staying on Scale with
heavy overage costs more than upgrading to Enterprise at some
point, and the customer sees that clearly.

### 4.2 Soft vs hard caps

- **Free:** hard cap. Beyond 10k, requests are accepted but
  outcomes are not recorded (customer sees a gentle upgrade CTA
  in dashboard). No billing surprise.
- **Solo through Scale:** soft cap with overage. Customer pays
  the base tier + overage. A configurable monthly cap prevents
  runaway bills (default 3× tier price; customer can raise).
- **Enterprise:** negotiated cap per contract.

### 4.3 The honest volume-cost chart

For a customer growing through tiers:

```
Volume     Best tier     Monthly bill
──────     ─────────     ─────────────
50k        Free          $0
150k       Solo          $19 + (50k × $0.0001) = $24
800k       Solo          $19 + (700k × $0.0001) = $89 → upgrade to Team ($99)
5M         Team          $99 + (4M × $0.00003) = $219 → upgrade to Pro ($499)
80M        Pro           $499 + (70M × $0.000015) = $1,549 → upgrade to Scale ($2,499)
800M       Scale         $2,499 + (700M × $0.00001) = $9,499
2B         Scale+meter   $2,499 + (1B × $0.00001 + 1B × $0.000005) = $17,499
          or Enterprise  negotiated
```

The overage design rewards upgrading but doesn't punish customers
who want to stay on a self-serve tier longer. Psychologically,
"you could save $X/mo by upgrading" is the right signal.

---

## 5. 2026 trends that shape the pricing

### 5.1 LLM price compression

Haiku 4.5 / GPT-4o-mini costs have fallen ~20× since 2023
Claude 2 / GPT-3.5 baselines. This is ongoing: Haiku 4.5 at
$0.15/1M input is the new floor. Rate of compression: ~50%/year
from 2024-2026.

**Implication:** tools that mark up LLM inference (early Perplexity,
Cody's early model) have compressing margins. Tools that BYO-keys
are insulated. Dendra chose BYO-keys at launch — we're insulated.

### 5.2 Usage-based pricing is normalizing

2024-2025 saw most dev-tools SaaS (Sentry, Honeycomb, Datadog)
adding usage-based tiers alongside per-seat. 2026 is seeing
pure-usage tools (Braintrust, Helicone, Langfuse) outperforming
per-seat peers in land-and-expand metrics.

**Implication:** our pure-volume pricing is aligned with the
trend direction, not fighting it.

### 5.3 Enterprise procurement is back under scrutiny

Post-2024 SaaS-consolidation, enterprise procurement teams have
mandate to reduce vendor count. New tools are being asked to
integrate with incumbent platforms (Datadog, Snowflake) rather
than stand alone.

**Implication:** our integration surface (§4 moat brick #5 in
business-model-and-moat) is load-bearing. Must ship adapters to
Datadog / Sentry / LangSmith / Braintrust before enterprise push
starts in year 2.

### 5.4 Open-source-first is a valuation premium

VC data (Redpoint, Battery Ventures, Accel reports): open-source-
first companies at Series A trade at 2-3× revenue multiples of
closed-source peers. Temporal, Clerk, PostHog, Dagster, dbt Labs
all priced this way.

**Implication:** Apache 2.0 license on core + commercial hosted
tier is the valuation-optimal structure for later fundraising.
Already our structure.

### 5.5 AI-native tools getting tier fatigue

User research (informal, from HN comments 2025): AI-tools with
5+ tiers get complaints. Users find it confusing, suspect they're
being upsold.

**Implication:** our 6 self-serve tiers (Free, Solo, Team, Pro,
Scale, Enterprise) is at the limit. Don't add more. Consider
collapsing Solo and Team into one tier ($49/mo for 500k) if user
research shows tier confusion at launch. Test post-launch before
simplifying.

---

## 6. Recommendations

Pricing is now grounded. Specific adjustments to
`business-model-and-moat.md` §3 and `entry-with-end-in-mind.md`
§7.3:

### 6.1 Keep

- The six-tier ladder (Free / Solo / Team / Pro / Scale / Enterprise).
- No $9/mo tier (fee hit + support load).
- Metered overage above Scale.
- BYO LLM keys (no markup).
- Volume-based, not per-seat.

### 6.2 Adjust

- **Add graduated overage rates per tier** (§4.1). The current
  single $0.01/1k above Scale is too coarse — add per-tier
  overage to reward upgrades.
- **Reserved-capacity infra switch at Pro+** — not customer-
  facing, but it's the operational move that keeps our margin
  expanding at scale.
- **Annual-billing discount (15% off)** — documented as a
  separate product offer, captures the 40% of buyers willing
  to prepay.
- **Soft cap behavior documented** (§4.2) — "we never surprise-
  bill you."
- **Pricing page shows the upgrade math** (§4.3) — don't hide
  that upgrading saves money at a given volume. Treat customers
  as adults.

### 6.3 Lever to watch post-launch

- **Team tier at $99** is the biggest single pricing bet. If
  early customers select "I almost went to Langfuse for $59"
  or "I bounced off at the price" in conversations, drop to $79.
  Don't go below $79 — any tier priced less than Solo × 4 breaks
  the ladder math.

### 6.4 Lever NOT to pull

- **Introducing a $9 tier** remains a bad idea per §1.5. If
  we observe demand for something lower than $19, the answer
  is "make Free more generous (20k/mo?)" not "add a $9 tier."
- **Per-seat pricing.** Ever. It's an anti-adoption signal for
  classification primitives.

---

## 7. Worked example — a mid-market customer over 12 months

Realistic adoption curve for a Y-Combinator-scale SaaS starting
with 1 classification site, growing to 15:

| Month | Sites | Classifications/mo | Best tier | Monthly bill |
|---|---:|---:|---|---:|
| 1 | 1 (OSS install) | 5k | OSS library | $0 |
| 2 | 2 | 30k | Free hosted | $0 |
| 3 | 3 | 80k | Free (at cap) | $0 |
| 4 | 5 | 200k | Solo | $19 |
| 6 | 8 | 600k | Solo (at overage) | $79 → upgrade |
| 7 | 10 | 900k | Team | $99 |
| 10 | 15 | 4M | Team (at overage) | $289 → upgrade |
| 12 | 15 | 10M | Pro | $499 |

**Year-1 bill from this customer: ~$1,500 total.** That pays for
~2 weeks of engineering time amortized across 15 classification
sites. Strong value prop from customer's side; acceptable pay-
off curve from ours (the customer is now a Pro-tier account
with growing usage).

---

## 8. Unit-economics at scale — sanity check

At 1,000 paying customers distributed typically across tiers:

| Tier | Customers | Avg MRR | Total MRR | COGS | Gross profit |
|---|---:|---:|---:|---:|---:|
| Solo | 600 (60%) | $19 | $11,400 | $108 | **$11,292** |
| Team | 250 (25%) | $99 | $24,750 | $443 | **$24,307** |
| Pro | 100 (10%) | $499 | $49,900 | $870 | **$49,030** |
| Scale | 40 (4%) | $2,499 | $99,960 | $3,480 | **$96,480** |
| Enterprise | 10 (1%) | $20,833 ($250k/yr) | $208,330 | ~$5,000 | **$203,330** |
| **Total** | **1,000** | — | **$394,340/mo** | **$9,900** | **$384,440/mo** |

**Annualized: $4.7M ARR with 97.5% gross margin.** At 1,000
paying customers — the Y2 achievable target per the roadmap.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0
licensed. Internal document; share externally only after review._
