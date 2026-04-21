# Dendra — Entering With the End in Mind

**Companion to:** `business-model-and-moat.md` (end state) and
`industry-applicability.md` (demand).
**Generated:** 2026-04-20.
**Updated:** 2026-04-20 with §7 bootstrap-aware revenue plan.
**Question it answers:** what does year-one positioning look like if
the year-three target is a canonical primitive + $10M ARR
Snyk-Temporal hybrid, **and** the founder is bootstrapped and needs
revenue in year one? See §7 for the resolution.

---

## 1. The endpoints that constrain entry

Three year-three outcomes must all be true. Each rules out a certain
kind of year-one move.

### Endpoint 1 — "Dendra" is the default noun for graduated classification

Every serious ML engineer knows what "a transition curve" is, the
way they know what "a backprop" is. Papers cite Dendra v0.2.0 (2026)
in their related-work sections.

**Entry constraint:** we must publish, cite cleanly, and ship the
primitive *as a primitive*. The name, the six-phase lifecycle, and
the paper's vocabulary have to be **front and center** from day one.

**What this rules out:**
- Branding as "the rule learner" or "the ML migrator" — generic
  vertical framing.
- Leading with case studies — cases come after primitive.
- Closed-source year one — would kill cite velocity.

### Endpoint 2 — The analyzer corpus is a moat

By year three, our static scanner recognizes 50+ code patterns for
classification sites, tuned against hundreds of real repos. A fork
of the OSS library *cannot* replicate this without the same customer
base.

**Entry constraint:** the analyzer must be **free from day one** —
even before it's monetized — to accumulate corpus. Every run against
a public repo is training data for our pattern library.

**What this rules out:**
- Paid analyzer at launch — cuts off data flywheel.
- Private repo–only scanner — limits corpus diversity.
- Hand-maintained pattern library — can't keep up with the surface.

### Endpoint 3 — Enterprise revenue comes through regulated verticals

By year three, the big ARR contributions come from domain packs
(clinical coding, fraud, content moderation) + audit-log signing
(Vega-backed, FedRAMP/SOC2). Those require credibility that
exceeds "cool OSS library."

**Entry constraint:** we must build *institutional trust* in year
one even though we're not selling to enterprise yet. That means
research credibility (published paper), security hygiene (SPDX
everywhere, signed releases), and careful use of the Axiom Labs
brand.

**Clean-provenance constraint:** Dendra is a pure B-Tree Ventures
LLC work — no academic or institutional co-ownership overhang.
This keeps IP clean for commercial licensing and keeps the
adoption pitch simple ("one vendor, one license, one roadmap").

**What this rules out:**
- Move-fast-break-things posture (alienates the enterprise
  prospects we'll need in year two).
- Naming competitors (we promised soft-indirect framing —
  regulated-industry buyers dislike aggressive positioning).

---

## 2. The year-one positioning — three load-bearing choices

### Choice A — We are a *primitive*, not a *product category*

| Anti-pattern (product category) | Correct framing (primitive) |
|---|---|
| "Dendra — AI customer-support triage" | "Dendra — graduated-autonomy classification primitive" |
| "Dendra — the chatbot router" | "Dendra — when should your rule graduate?" |
| Vertical-specific landing pages | One landing page; the library IS the product |
| Sales calls about use cases | Docs, GitHub issues, a `pip install` command |

**Why:** primitives get copied into every vertical by their users.
Products get copied by competitors.

### Choice B — Research credibility is the opening act, not the footnote

Order of public events (load-bearing):

1. **Paper on arXiv** ("When Should a Rule Learn?"). This is the
   *first* public artifact.
2. **v0.2.0 to PyPI**, one business day later.
3. **Figure 1 + the two-regime blog post** (one technical post
   cross-posted to Hacker News + r/MachineLearning).
4. **Analyzer Free** — scan your repo in 30 seconds, get a JSON
   report. No signup.

**Why order matters:** arXiv is what gets us cited. If we lead with
the library or the blog post, they stand alone. If we lead with the
paper, everything downstream is anchored to a citable artifact.

### Choice C — The anchor customers are *published*, not *hidden*

Three to five lighthouse production adopters in year one. **Their
adoption is public.** They blog about it (or we do, with their
name), and their classification site is named. No anonymized
testimonials.

Candidates matching both "natural Dendra fit" and "publicly
blogs about engineering":

- Supabase (routing in their support triage).
- Linear (their triage automation).
- HuggingFace's own classification loops (they won't pay but will
  use and cite).
- Cal.com, PostHog, dbt Labs (mid-market OSS companies that publish
  engineering posts).
- An Axiom internal case study from the turn-classifier (shipping
  this session).

**Why this matters:** the lighthouse customers *are* the case-study
section of paper 2 (2027). They also feed the analyzer corpus and
the domain-pack training data. Every anchor customer is pre-loaded
for the year-three endgame.

---

## 3. What entry *feels* like to a first-time user

The day-one experience defines the brand. Here's the target:

```
$ pip install dendra
$ dendra analyze ./my-repo
Scanned 12,408 Python files; found 7 classification sites.

  src/support/triage.py:42  — 5 labels, medium cardinality
    Dendra-fit: 4.5/5
    Regime: narrow-domain rule-viable (ATIS-like)
    Estimated: rule accuracy ~70%; ML would add ~15-20pp after ~500
               outcomes (based on comparable public benchmarks)

  src/mod/content_score.py:88  — 3 labels, binary-ish
    Dendra-fit: 4/5
    Regime: safety-critical boundary
    Recommend: Phase 4 cap (ML_WITH_FALLBACK, never ML_PRIMARY)

  ... (5 more)

Report written to .dendra/analyze-2026-04-20.json
```

Three minutes from `pip install` to actionable insight, zero signup.
That's the Snyk playbook; it's what pulls mid-market buyers through
to the paid tier without a sales call.

---

## 4. What we explicitly DON'T do in year one

Being clear about this is what keeps positioning coherent.

- **No outbound enterprise sales motion.** No SDR seat, no
  Salesforce pipeline, no "schedule a demo" CTA above the fold.
  Inbound-only for any enterprise-shaped conversation.
- **No vertical-specific landing pages.** One primitive, many
  uses.
- **No competitive comparisons in marketing.** Indirect framing
  only (per feedback memory).
- **No closed-source anything** in the core library. Year one is
  100% Apache-2.0 on the core. Paid tiers (§7) are orthogonal.
- **No data-sharing federation yet.** It's on the roadmap (opt-in
  year 2), but we don't promise it year one.
- **No SSPL / BSL / ELv2 relicensing.** These licenses
  disqualify Dendra from most enterprise procurement. Stay
  Apache-2.0 on core indefinitely.
- **No SOC2 / FedRAMP / HIPAA certifications in year one.**
  They cost $50k-$300k each and can't be achieved in a quarter
  anyway. They are a year-2+ commitment.

Each "not yet" is a future-value preserved. The endgame needs each
of these to feel *inevitable* by the time we do it, not *opportunistic*.

> **Explicitly what we DO allow in year one** — see §7. The
> original draft of this document said "no sales team / no
> hosted product" under this heading; that stance was correct for
> venture-backed primitives (Temporal, Clerk) and wrong for a
> bootstrapped founder who needs cash flow. §7 reconciles.

---

## 5. Entry narrative (30-second pitch)

> *"Every production system has classification decisions that start
> as hand-written rules. Nobody has formalized the migration to ML.
> Dendra is the primitive: one decorator, six phases, statistical
> gates at every transition. The transition curves on four public
> benchmarks show when each phase earns its graduation. Start with
> `pip install dendra` — the paper is on arXiv and the analyzer
> runs on your repo in 30 seconds."*

This fits on a slide. It names the problem (primitive) before the
product (decorator). It sources credibility (benchmarks + arXiv).
And it ends with a zero-friction next step.

---

## 6. Success metrics for year one (end-in-mind calibrated)

Each metric points directly at a year-three prerequisite. Two
groups: **adoption metrics** (OSS-native growth), and
**revenue metrics** (bootstrap sustainability per §7).

### 6.1 Adoption metrics

| Y1 metric | Threshold | Enables Y3 outcome |
|---|---|---|
| GitHub stars | 1,000+ | Canonical-primitive status |
| PyPI downloads/mo | 10,000+ | Analyzer corpus diversity |
| arXiv citations | 5+ | Paper defensibility |
| Analyzer runs/mo | 1,000+ | Pattern-library refinement |
| Public case studies | 3–5 | Year-2 domain-pack demand |

None of these need sales motion. All are OSS-native.

### 6.2 Revenue metrics (per §7 pay-as-you-go)

| Y1 metric | Lower-bound target | Stretch target | Enables |
|---|---:|---:|---|
| Design-partner cash closed (Q1) | $20k | $50k | Runway through Q2 |
| Support-contract MRR (end-Q2) | $2k | $9k | First recurring revenue |
| Free hosted signups (end-Q4) | 2,000 | 5,000 | Adoption-funnel top |
| Paid self-serve customers (end-Q4) | 100 | 260 | Self-serve motion works |
| Cloud self-serve MRR (end-Q4) | $30k | $70k | Year-2 inbound enterprise foundation |
| Domain packs shipped | 1 | 2 | Year-2 upsell surface |
| Consulting engagements closed | 2 | 6 | Gap-filling cash, case study pipeline |
| Y1 total revenue (range) | $113k | $327k | Founder sustainability |
| Y1 exit ARR run-rate | $120k | $300k | Year-2 planning basis |

Revenue metrics are **floor** numbers — keeping them meets
bootstrap sustainability. Stretch numbers accelerate year-2
enterprise readiness without requiring outside capital.

---

## 7. Accelerating to revenue without burning the endgame

### 7.1 The tension

The canonical-primitive analogs (Temporal, Clerk, OpenTelemetry,
Sentry) spent 2-3 years in pure developer-first mode before
monetizing. They had venture capital paying the bills. **A
bootstrapped founder doesn't have that runway.** This document's
earlier draft said "no sales / no hosted cloud / wait until year
two" — that stance was correct for VC-backed primitives and wrong
for a founder who needs to pay for rent while building.

The resolution is **not** to start a loud enterprise sales motion.
It is to distinguish **revenue moves that preserve primitive
positioning and enterprise optionality** from moves that burn
either.

### 7.2 The two taxonomies

Every revenue move is rated on two axes:

- **Primitive-safe?** Does it preserve the OSS-primitive-first
  story that developers will adopt from `pip install`?
- **Enterprise-safe?** Does it preserve the year-3 enterprise
  procurement path (no SSPL allergy, no "this vendor wants a
  demo for everything" friction)?

A move is **safe to pull in year one** only if both axes are
green.

| Revenue move | Primitive-safe? | Enterprise-safe? | Pull year 1? |
|---|---|---|---|
| Apache-2.0 core library (no charge) | ✅ | ✅ | **YES** (already planned) |
| Support contracts on OSS | ✅ | ✅ | **YES** |
| Design-partner pilot contracts (3-5 customers) | ✅ | ✅ | **YES** |
| Dendra Cloud (self-serve hosted) at commodity pricing | ✅ | ✅ | **YES**, month 4+ |
| Paid analyzer dynamic tier ("Insight") | ✅ | ✅ | **YES**, month 4+ |
| Domain packs (support, moderation, fraud) as one-time products | ✅ | ✅ | **YES**, month 6+ |
| Founder consulting engagements | ✅ | ✅ | **YES**, ad hoc |
| Training / certification program | ✅ | ✅ | YES but low priority Y1 |
| Outbound SDR team | ❌ (dev trust) | neutral | NO |
| SSPL / ELv2 relicensing | ❌ | ❌ (legal blocks) | NEVER |
| Closed-source core modules | ❌ | neutral | NO |
| "Contact us for pricing" gating | ✅ | ❌ (friction) | NO |
| SOC2 / FedRAMP certifications | neutral | neutral | NO (too expensive Y1) |
| Paid-only analyzer (no free tier) | ❌ (kills corpus flywheel) | neutral | NO |

### 7.3 Year-one revenue plan, month by month

A bootstrap-aware sequencing of the green-listed moves. Each
step is additive; nothing is dropped or replaced.

**Month 0-1 — Launch (same as original plan).**
- arXiv preprint.
- `pip install dendra` to PyPI.
- Blog post + Hacker News + r/MachineLearning.
- Free analyzer at `dendra analyze`.
- **Revenue: $0.**

**Month 1-2 — Open the design-partner program.**
- Publish an "Early Design Partner Program" landing page.
  Invite-only, 3-5 slots. No public pricing.
- Offer: **$10-25k flat** in exchange for: 6-month priority
  access to Dendra Cloud when it ships (§month 3-4); direct
  Slack channel with founder; case study rights; influence on
  roadmap.
- Target: close 2-3 design partners by end of month 2.
- **Revenue target: $20-50k cash, month 2.** Enough for 2-3
  months of bootstrapped runway.

**Month 2-3 — Cloud MVP build.**
- No revenue moves. Build Dendra Cloud MVP for design partners.

**Month 3-4 — Cloud MVP ships to design partners.**
- First support contracts attach to design partners: optional
  $1-3k/month "priority support" add-on.
- **New recurring revenue: $2-9k MRR starting month 4.**

**Month 4-5 — Public Cloud launch across the self-serve ladder.**
- Six self-serve tiers go live with published pricing (see
  `business-model-and-moat.md` §3.1):
  - **Free ($0)**: 10k classifications/mo — adoption asset.
  - **Solo ($19/mo)**: 100k/mo — freelancer entry.
  - **Team ($99/mo)**: 1M/mo — startup eng-team tier.
  - **Pro ($499/mo)**: 10M/mo — mid-sized org.
  - **Scale ($2,499/mo)**: 100M/mo — large org.
  - **Metered overage: $0.01/1k** above 100M/mo.
- Stripe checkout for all tiers. No "contact us" gating below
  Enterprise. No sales call needed for self-serve tiers.
- Target: **5,000+ Free signups and 150-250 paid customers** by
  end of Y1 across Solo/Team/Pro/Scale.
- **New MRR ramp: $5-15k/mo by month 6; $30-70k/mo by Q4.**

**Month 5-6 — First domain pack ships.**
- Support-ticket triage domain pack: **$1,500 one-time** or
  **$150/mo subscription** bundled with Cloud Pro.
- Domain pack = pre-trained ML head + rule template + labeled
  evaluation corpus.
- **Ancillary revenue: $5-20k first quarter.**

**Month 6-9 — Consulting engagements fill gaps.**
- 1-2 consulting engagements per quarter at **$10-30k each**.
- Typical scope: migrate an existing classifier site to
  Dendra; build a custom domain pack; set up CI integration.
- **Cash-funded runway: $20-60k per quarter.**

**Month 9-12 — Second domain pack + self-serve scale.**
- Ship content-moderation domain pack.
- Cloud self-serve growing to 50-150 paying customers.
- First inbound enterprise inquiry (likely). Handle by
  upgrading one design partner to a named "Enterprise Early
  Access" agreement, not by starting outbound sales.

### 7.4 Year-one revenue targets (quarterly)

Realistic ranges for a founder-only team with no external
capital. Self-serve tiers per §7.3 + design partners + support
contracts + ad-hoc consulting + domain packs:

| Quarter | Design-partner cash | Self-serve MRR (ending) | Packs + consulting | Quarter total |
|---|---:|---:|---:|---:|
| Q1 | $20-50k | $0-2k | $0 | **$20-50k** |
| Q2 | $0-15k | $5-15k | $5-15k | **$25-75k** |
| Q3 | $0 | $15-35k | $15-40k | **$60-145k** |
| Q4 | $0 | $30-70k | $20-60k | **$120-280k** |
| **Y1 total** | **$20-65k** | **$150-360k (cumul)** | **$40-115k** | **$225-540k** |
| **Y1 exit ARR** | — | **$360-840k run-rate** | — | — |

Upgraded numbers reflect the full tier ladder (Free → Solo →
Team → Pro → Scale) capturing adoption across the developer
spectrum rather than only Team/Pro buyers. The Free tier doesn't
generate revenue directly but pulls Solo/Team conversions at
the expected SaaS funnel rate (2-5% Free → paid).

These are **not** venture-scale numbers. They are bootstrap-
sustainable numbers. A founder with $100-300k in Y1 revenue and
rising MRR can afford to keep building toward the year-3
enterprise inflection without diluting.

### 7.5 Guardrails — what "pay as you go" must NOT become

The pay-as-you-go plan above works only if it doesn't slip into
patterns that burn the endgame. Warning signs that the plan is
drifting into the "burned-endgame" zone:

- **Pricing pressure on the core library.** If any feature in
  the Apache-2.0 core gets paywalled, the primitive story is
  over. If a user opens a GitHub issue and we respond "that's a
  Cloud-tier feature," we've lost.
- **Roadmap captured by design partners.** Design partners buy
  input, not control. If Dendra's roadmap starts reading like
  "Customer A's custom requirement + Customer B's custom
  requirement," the primitive has become a services business.
  Cap design partner roadmap influence at "direction, not
  detail."
- **"Contact us for pricing" creep.** Every tier in year 1 must
  have a published price. The moment we hide pricing for any
  tier, we signal "enterprise vendor," which trips year-3
  procurement friction.
- **Certifications promised too early.** If a year-1 prospect
  asks for SOC2 and we say "we're working on it" — say "no"
  instead. Promising certifications we can't deliver burns
  trust faster than declining.
- **Outbound sales hiring.** A single outbound SDR before year
  2 turns the brand from "primitive" to "vendor." Don't hire.
  Refer inbound enterprise to a waitlist instead.
- **Closing too many services engagements.** More than ~$100k/
  quarter in consulting signals "consulting company." Cap
  services at a fraction of total revenue so the product
  remains primary.

If any of these warning signs appears, pull back on the specific
revenue move triggering it — do not let revenue pressure compound
the mistake.

### 7.6 The load-bearing discipline, preserved

The end-in-mind discipline from the earlier draft of this
document is unchanged in spirit: **let every year-three revenue
lever be pre-loaded in year one's work.**

What changes now is that some of those year-three revenue
levers — hosted cloud, support contracts, domain packs —
ship in year one at commodity pricing. They pre-load the
year-three enterprise levers (same code, same cloud, same
domain packs, priced up for enterprise scale, wrapped with
SOC2 / support SLA / indemnity). The primitive stays free.
The pricing scales with buyer size. The path is continuous.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0 licensed._
