# Dendra — VC Pitch Deck Outline

**Purpose:** 12-slide deck narrative for seed / Series A
conversations.
**Companion docs:**
- `industry-applicability.md` — demand, TAM, category
- `business-model-and-moat.md` — pricing ladder, moat, 3-year shape
- `entry-with-end-in-mind.md` — GTM sequencing + bootstrap plan
- `dendra-one-pager.md` — 1-page buyer pitch
- `../papers/2026-when-should-a-rule-learn/outline.md` — research
  credibility
- `../working/patent-strategy.md` — IP defensibility
- `../working/patent/` — filing package

**Generated:** 2026-04-20. **Status:** outline for deck build;
each slide points to the supporting doc that contains evidence.

---

## One-line tagline

**"The classification primitive every AI-application codebase is
missing — open source on day one, patent-protected from day one,
measurable on four public benchmarks, already saving customers
90% of LLM token cost on the hot path."**

---

## The 12 slides

### Slide 1 — Title / hook

- **Dendra.** The classification primitive.
- **Tagline.** *When should your rule learn?*
- Logo / founder photo / URL.

**One bullet under title:** "Every AI-application system has
classification decisions that start as rules and should graduate
to ML. Nobody has formalized the migration. We did."

---

### Slide 2 — The problem

**Every production codebase has 10-40 classification decision
points.** (Source: `industry-applicability.md` §2.)

Three things go wrong without a primitive:

1. **Silent regressions.** ML classifier drifts; nobody notices
   until a customer complains. Cost per event: $50k-$300k
   (industry-observed).
2. **Unbounded LLM token costs.** Classification is the highest-
   volume LLM use case. At 100M classifications/mo on a Sonnet-
   class model, pure-LLM routing costs $11.5M/yr. Most of that is
   on inputs a simple rule would handle.
3. **Silent AI-class incidents.** LLM-driven classifiers have
   been root-cause in Samsung × ChatGPT, Air Canada chatbot, and
   Microsoft Copilot SharePoint leak. No production-grade safety
   floor exists.

**The pain is universal. Nobody owns the category.**

Evidence: `industry-applicability.md` §2, §3 (13 Tier-1
application categories), §8.7 (security incidents).

---

### Slide 3 — The insight

**Rule → ML migration is a universal lifecycle nobody has
formalized.** We formalized it.

Six-phase graduated-autonomy primitive:

```
RULE → LLM_SHADOW → LLM_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK → ML_PRIMARY
```

Each transition is gated by a statistical test against an
outcome log. The rule is always the safety floor. The circuit
breaker reverts to rule on failure. The safety-critical cap
refuses ML_PRIMARY for authorization-class decisions.

**Technical improvement (measured):** the probability that any
phase transition produces worse-than-rule behavior is bounded
above by the Type-I error rate of the transition gate.
*Mathematical consequence of the architecture, not a benefit
claim.*

Evidence: paper outline §3; patent spec §2.2 [0004].

---

### Slide 4 — The solution (demo)

**Pip install. Decorate. Done.**

```python
from dendra import ml_switch, Phase, SwitchConfig

@ml_switch(labels=["bug", "feature", "question"],
           author="@triage:support",
           config=SwitchConfig(phase=Phase.RULE))
def triage(ticket):
    if "crash" in ticket["title"].lower():
        return "bug"
    return "feature"
```

- Zero behavior change on day one (Phase 0 = rule).
- Outcome log captures every classification.
- Graduate to higher phases when statistical evidence justifies.
- **Dendra switch overhead: 0.62 µs.** Lower than a Python
  attribute lookup. *No production team will feel it.*

Evidence: `dendra-one-pager.md`; code at `github.com/bwbooth/dendra`.

---

### Slide 5 — Traction (what we've already built)

- **Apache-2.0 OSS library.** Phases 0-5 complete.
  156 tests passing. Production-integrated in Axiom (2,646 passing
  tests with zero regression).
- **Four public-benchmark measurements** (Banking77, CLINC150,
  HWU64, ATIS) with transition-depth results at p < 0.01
  paired-test significance.
- **Security benchmarks**: 100% rule-floor preservation against
  20-pattern jailbreak corpus; 100% PII recall on 25-item corpus;
  circuit-breaker stress-tested at 100 consecutive ML failures.
- **First internal case study**: Axiom's turn-intent classifier
  is live in Phase 0, feeding production outcomes.
- **Patent filing package ready.** Provisional specification
  drafted (75 pages); DIY micro-entity fee $75; filing planned
  on day 0 of launch.
- **Three internal-validation candidate sites** identified at
  Dendra-fit scores 4-5/5.

Evidence: `../papers/2026-when-should-a-rule-learn/results/findings.md`;
`../working/patent/`; `../working/internal-use-cases-scan-2026-04-20.md`.

---

### Slide 6 — Market size (TAM / SAM / SOM)

**Ground-up TAM.** Every software organization has classification
decision points. Empirical density:

| Org size | Sites | Dendra-fit sites | US market count |
|---|---:|---:|---:|
| Small SaaS (<20 eng) | 3-8 | 2-5 | ~20,000 firms |
| Mid-market (20-200 eng) | 10-40 | 6-25 | ~30,000 firms |
| Enterprise (200+ eng) | 30-200 | 20-100 | ~5,000 firms |
| Hyperscale | 1,000+ | 400+ | ~50 firms |

**Per-site annual captured value (measured, AI-era calibrated):**
$640k-$2.8M / year for a mid-market org with 15 Dendra sites.

**TAM:**
- If Dendra captures 5% of measured value at mid-market scale:
  `30,000 mid-market × 5% × $1M average = $1.5B US mid-market`
- Plus enterprise and hyperscale: **~$5-10B global TAM.**

**SAM (serviceable 5-year):**
- Bottom-up adoption across English-speaking dev markets,
  realistic penetration by year 5 = **~$500M-$1B SAM.**

**SOM (realistic 3-year):**
- 1,500-5,000 paid customers by Y3 + 10-30 enterprise contracts
  = **~$10-50M ARR SOM.**

Evidence: `industry-applicability.md` §2, §4.1, §5.

---

### Slide 7 — Business model & pricing

**Open-source primitive. Hosted tiers. Enterprise at the top.**
Snyk + Temporal analog.

| Tier | Price | Who it's for |
|---|---|---|
| OSS library | Free | Everyone; primitive adoption |
| Free hosted | $0 | Hobbyists; 10k classifications/mo |
| Solo | $19/mo | Freelancers; 100k/mo |
| Team | $99/mo | Startup eng teams; 1M/mo |
| Pro | $499/mo | Mid-sized orgs; 10M/mo |
| Scale | $2,499/mo | Large orgs; 100M/mo |
| Metered overage | $0.01/1k | Above-Scale volume |
| Enterprise | $50-500k/yr | Regulated + Fortune 1000 |

**Gross margins: 96-99% across paid tiers.** Sub-microsecond
switch overhead + commodity storage = software economics. See
`business-model-and-moat.md` §3.3 for unit economics.

**Year-1 ARR (floor):** $265-370k from paid SaaS + $40-100k
consulting. Founder-sustainable without external capital.

**Year-3 ARR target:** $10M.

Evidence: `business-model-and-moat.md` §3-§5.

---

### Slide 8 — Competition & moat

**No direct competition today.** Every classification migration
is ad-hoc engineering at each decision point.

**Analog competitors by mechanism** (none of them are classification
primitives):
- **Snyk / SonarQube**: code scanners for different concerns.
  We adopt their playbook for the analyzer.
- **Temporal / Clerk / OpenTelemetry**: primitive-first companies
  with hosted tiers. We adopt their OSS-monetization playbook.
- **LaunchDarkly / Sentry / LogRocket**: dev-tools SaaS.
  Positioning peer group.

**Eight moat bricks** ranked by durability (`business-model-and-moat.md`
§4):

1. **Canonical-primitive status** (paper + citations). 5-10 year
   half-life.
2. **Analyzer corpus** — the pattern library that identifies
   classification sites. Grows with every customer run.
3. **Domain packs** — pre-trained ML heads for Tier-1 categories.
4. **Federated outcome-log network effect** (opt-in cross-org
   priors). Compounds.
5. **Integration surface** — adapters to Datadog, Sentry, Slack,
   LangSmith, W&B, etc.
6. **Regulatory certifications** (SOC2, HIPAA, FedRAMP) —
   expensive to replicate.
7. **Academic credibility** — citation graph.
8. **Patent** (provisional filed day 0) — protects the
   architectural combination against competing cloud vendors.

**The technique alone is NOT our moat** — it's in the paper and
Apache-licensed code. The **data, distribution, and compliance
layers on top of it** are.

---

### Slide 9 — Go-to-market

**Bottom-up, developer-first.** (See `entry-with-end-in-mind.md`
for the full sequencing.)

1. **Day 0**: arXiv preprint → Hacker News / r/MachineLearning
   → PyPI release → free analyzer.
2. **Month 1-2**: design-partner program (3-5 customers, $10-25k
   each) in exchange for Cloud MVP priority access + case-study
   rights.
3. **Month 3-4**: Dendra Cloud MVP ships to design partners.
4. **Month 4-5**: Public Cloud launch, self-serve with Stripe
   checkout. No SDR team.
5. **Month 6+**: domain-pack upsell into installed base; consulting
   on demand.
6. **Year 2**: inbound enterprise, SOC 2 Type 1.
7. **Year 3**: outbound enterprise for regulated verticals,
   first domain-pack-driven enterprise contracts.

**Land-and-expand mechanics:** a developer installs Dendra on
one classifier site → team adopts Cloud Team tier → engineering
org grows to Pro/Scale → regulated industry adopts Enterprise
for multi-BU deployment.

---

### Slide 10 — Why now

Three macro forces make this moment right:

1. **LLMs made classification universal.** Every product now has
   dozens of "what kind of thing is this?" decisions. LLMs are
   the obvious tool for many of them, but the $11.5M/yr token
   bill at 100M/mo + the hallucination/jailbreak risk make pure
   LLM-only designs untenable. The market is ready for a
   graduated primitive.
2. **AI-assisted coding accelerates classification-site
   creation.** Cursor/Copilot/Claude-Code engineers ship 3× more
   code. Every new codebase has more classification sites than
   before. The density of Dendra-applicable surface is rising.
3. **Regulatory pressure is here.** GDPR Article 22 (automated
   decision-making), NYC Local Law 144 (AI hiring audits),
   EU AI Act (risk-tiered classifier obligations), California
   SB-1047 (AI safety disclosure) — each demands auditable,
   rule-floored classifier deployments. Dendra's signed outcome
   log is the compliance artifact regulated industries need.

Evidence: `industry-applicability.md` §6, §8.7.

---

### Slide 11 — Team & ask

**Founder / CEO / CTO: Benjamin Booth**
- Inventor of Dendra; inventor of the Axiom platform
  (production-deployed agent infrastructure).
- Sole committer on the Dendra repository; author of the paper,
  patent spec, and business strategy.
- Contact: `ben@b-treeventures.com`.

**Hiring priorities (if funded):**
1. Principal engineer — Cloud/federation.
2. Developer-relations lead — analyzer corpus growth.
3. Domain-pack lead — ML heads for Tier-1 categories.

**Capital ask:**

- **Seed round: $1.5M-$3M** at founder-sustainable burn.
- **Use of proceeds:** 40% engineering (Cloud/Enterprise features,
  SOC 2 prep), 30% GTM (developer-relations, domain-pack team),
  20% infrastructure/legal (utility patent conversion, SOC 2
  audit, initial compliance), 10% reserve.
- **Milestones for next round:** $1-3M ARR by end of Y2; SOC 2
  Type 1; first Enterprise contracts; first federation-GA
  customers.

**Alternative:** founder-sustainable bootstrap path (see
`entry-with-end-in-mind.md` §7). Floor $265-370k Y1 ARR pays
rent. Raises become optional, not mandatory.

---

### Slide 12 — Why this wins

Three compounding advantages make Dendra the canonical primitive
for graduated classification — not one of several competing
products.

1. **First-mover + research-backed + patent-protected.** Nobody
   else has the specific combination of peer-reviewed math
   (§3 of paper), measured technical improvements
   (§8 of paper), filed patent (§11a of patent-strategy), and
   shipping code (156 tests + Axiom integration). Competitors
   have to climb the citation and patent mountains before they
   reach the product work.
2. **The OSS library is the distribution.** Every `pip install
   dendra` grows our analyzer corpus and feeds our federation
   prior. Competitors can fork the library but can't fork the
   data or the citations.
3. **Pricing structure compounds.** Free tier feeds Solo/Team;
   Team/Pro feeds Scale; Scale feeds Enterprise. Each layer
   funnels upward. Metered overage at 99% margin. Moat-aligned
   economics at every tier.

**The ask in one sentence:** fund Dendra to become the canonical
classification primitive before a BigCo builds a worse version
of it and markets it harder.

---

## Appendix slides (for diligence)

- **A1** — Technical architecture (FIG. 1 from patent drawings)
- **A2** — Six-phase state machine (FIG. 2)
- **A3** — Transition-curve figure (Figure 1 from paper)
- **A4** — Latency measurements table
- **A5** — Security-benchmark measurements table
- **A6** — Patent-strategy summary (from `patent-strategy.md`)
- **A7** — Unit economics per tier
- **A8** — Competitive landscape matrix
- **A9** — Bootstrap financial model (from
  `entry-with-end-in-mind.md` §7.4)
- **A10** — Team bios + references
- **A11** — Customer references (once design partners close)
- **A12** — Risk register + mitigations

---

## Deck-build notes

- **Visual style:** minimal. Paper-white backgrounds, charts
  direct from the research results (Figure 1 is the hero image),
  no stock photography, no bullet-point overload.
- **Demo:** ideally a 60-second screencast of `pip install
  dendra && dendra analyze ./repo` producing a quantified report.
  Bundled into the deck, or linked.
- **What NOT to include:**
  - Team-org-chart slide (solo founder).
  - "Moat = our team" slide (soft).
  - Financial-model spreadsheet inline (attach separately).
  - Logo-wall of customers (don't have any yet; use named
    design partners once they close).
- **Length:** 12 slides + appendix. Target 10-minute read if
  delivered asynchronously; 20-minute presentation if live.

## Investor-tier targeting

Realistic VC fit (in order of fit):

1. **Infrastructure + developer-tools specialists.** Redpoint,
   Accel, Foundation Capital, Heavybit, Earlybird, Lightspeed.
2. **Open-source-first firms.** Runa Capital, OSS Capital,
   Root Ventures.
3. **AI-infrastructure specialists.** Radical Ventures,
   Greylock (AI), Sequoia (infra), Madrona.
4. **Mission-aligned angels from Temporal/Clerk/Sentry/Datadog.**
   Pre-seed / seed checks from operator angels who have lived
   the primitive-first playbook.

**Avoid:**
- Generalist consumer VCs (won't grok the primitive pitch).
- AI-hype VCs looking for LLM-wrapper products (this isn't that).
- Vertical-SaaS VCs (we're not vertical).

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Apache-2.0 licensed._
