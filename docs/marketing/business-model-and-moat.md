# Dendra — Business Model, Analyzer, and Moat

**Companion to:** `industry-applicability.md` (the demand side) and
`dendra-one-pager.md` (the pitch).
**Generated:** 2026-04-20.
**Status:** strategic draft for internal discussion.

---

## 1. The best industry analog

Dendra's shape is closest to a **two-layer stack that has worked before**:

- **The primitive layer** — an open-source library that becomes the
  default way to solve a problem. Analogs: **Temporal** (durable
  execution), **OpenTelemetry** (observability), **Clerk/Auth0**
  (auth), **Sentry SDK** (error tracking). All are free/OSS primitives
  that monetize the **cloud + enterprise** layer on top.
- **The scanner layer** — a tool that discovers latent occurrences of
  the problem in a customer's codebase and quantifies the cost of
  *not* having the primitive. Analogs: **Snyk** (finds vulns, sells
  fixes), **SonarQube** (finds quality debt, sells the platform),
  **Datadog Application Security Monitoring** (observed risk → upsell).

**The combined model — "Snyk + Temporal" — is the tightest analog.**
Snyk's scanner is the lead generator; its vuln-fix platform is the
durable product. Temporal's primitive is the wedge; its cloud is the
durable product.

Neither exists alone. Dendra needs both.

---

## 2. The analyzer — our lead-gen engine (design sketch)

A product called **Dendra Analyzer** (working name) that runs in
three modes. The user doesn't need to adopt Dendra the library first
— the analyzer produces its own value.

### 2.1 Static mode (free tier)

Runs on a git repository. Purely AST + ripgrep; no runtime required.

**What it finds:**

- Functions that return string labels from a finite set (`if/elif` /
  `match-case` / dispatch tables).
- Dispatch tables and rule registries.
- Keyword-matching classifiers (regex + `.any()` patterns).
- LLM-prompted classifiers already present (`prompt.classify`-style).

**What it reports per site:**

- File + line range.
- Label set (inferred from string literals in `return` statements).
- Cardinality bucket: narrow (≤10), medium (11–50), high (51+).
- Regime classification (ATIS-like vs CLINC-like) per our two-regime
  paper finding.
- Dendra-readiness score 1–5 (same rubric the scan subagent used).

**Deliverable:** a markdown report + a `dendra-analyzer.json`
artifact that CI can diff across PRs.

**Pricing:** free forever for public repos; free for first 3 sites
for private repos.

### 2.2 Dynamic mode (paid tier — "Dendra Insight")

Adds the runtime layer. Users wrap their candidate sites with a
*measurement-only* decorator (not the full Dendra switch) that logs:

- Call volume + latency distribution.
- Input shape/length (for ML-head sizing estimates).
- Output distribution (to detect label drift, stale branches).
- Outcome signal if a caller provides one (optional).

After 24–72h of production traffic, the analyzer produces:

- **Per-site projected savings** based on measured call volume ×
  per-graduation unit economics from `industry-applicability.md`.
- **Portfolio view** (same report, rolled up across sites).
- **Recommended graduation order** — which sites to convert first
  (highest ratio of volume × rule-weakness).
- **"Hidden sites"** — classification-shaped code paths the static
  scanner missed, surfaced by observed call patterns.

Users can stay on measurement indefinitely without adopting the
full `@ml_switch` decorator. This **normalizes data collection
before conversion** — a crucial trust step.

### 2.3 Graduation mode (the full Dendra product)

Once a site graduates, the decorator becomes the real thing and the
transition-curve runner produces live dashboards.

### 2.4 Why the analyzer monetizes well

- **Lead generation that doesn't feel like sales.** The static
  scanner runs in 30s on any repo, produces immediate insight, and
  the JSON artifact is trivially shareable internally.
- **The dynamic layer is hard to cheat.** Measuring real traffic is
  work-intensive; once running, it creates switching cost.
- **Projected savings are quantified per-site.** Finance teams sign
  purchase orders for "$250k/year to save $1.8M/year," not for
  "possibly useful primitive."

---

## 3. Monetization tiers — the full pricing ladder

> **See `pricing-deep-dive.md` for the grounded derivation of these
> tier thresholds + cost math.** This section is the summary. Tier
> thresholds are derived from persona-DAU brackets (§3 of that doc),
> price points anchored to peer comps (§2), COGS numbers from
> actual AWS/Stripe rates (§1).

Six self-serve tiers, one metered-utility product, one enterprise
contract. The OSS library is always free. The analyzer static mode
is always free (loss-leader that fuels the corpus moat per §4). Every
paid tier has a published price — no "contact us" gating except at
Enterprise.

### 3.1 Tier ladder

| Tier | Price | Classifications/mo | Retention | Switches | Team seats | Support | Buyer persona |
|---|---|---:|---:|---:|---:|---|---|
| **OSS library** | free (Apache 2.0 client SDK + BSL 1.1 analyzer/server, BSL Change Date 2030-05-01 → Apache 2.0) | unlimited (self-hosted) | any | any | any | GitHub issues | Everyone; primitive adoption |
| **Free (hosted)** | **$0** | 10,000 | 7 days | 1 | 1 | Community forum | Hobbyist; side projects; eval |
| **Solo** | **$19/mo** | 100,000 | 30 days | Unlimited | 1 | Email, best-effort | Freelancer; side-SaaS; indie dev |
| **Team** | **$99/mo** | 1,000,000 | 90 days | Unlimited | 10 | Email, 1 biz-day | Startup eng team; small product |
| **Pro** | **$499/mo** | 10,000,000 | 1 year | Unlimited | 50 | Email, biz-hours SLA | Mid-sized eng org; multi-product |
| **Scale** | **$2,499/mo** | 100,000,000 | 2 years | Unlimited | Unlimited | 24-hour SLA, private Slack | Large eng org; multi-BU; prod-critical |
| **Metered overage** | **$0.01 / 1k classifications** above 100M/mo, tapering to **$0.005 / 1k** above 1B/mo | — | — | — | — | — | Above-Scale volume customers |
| **Enterprise** | **$50k–500k/yr** | custom | custom | custom | custom | Named AE, indemnity, SOC2/HIPAA/FedRAMP as needed | Regulated industries, Fortune 1000 |
| **Services** | $10k–$1M per engagement | — | — | — | — | — | Co-deployment, custom integrations |

### 3.2 Why these specific prices — summary

Full derivation: `pricing-deep-dive.md`. One-line summary of each
choice:

- **No $9 tier.** Stripe fee at $9 is 6.2% vs 2.9% at $99; $9 buyer
  has the same support cost at 1/10 revenue; Free wins the "try it
  cheap" comparison. (`pricing-deep-dive.md` §1.5.)
- **Free = 10k/mo.** Generous vs Sentry/Helicone free tiers; enough
  for real side-project traffic; infrastructure cost <$0.03/mo so
  zero-margin is fine. (§1.1, §3.2.)
- **Tier thresholds 10× apart.** Not arithmetic — follows 10× DAU
  persona jumps (hobby → indie → startup → scale-up → multi-product
  → enterprise). (§3.2.)
- **Price points.** Calibrated against Langfuse, Helicone, Sentry,
  Honeycomb, Braintrust at matching volumes. Team tier $99 is the
  biggest single bet (premium vs Langfuse $59); dropping to $79 is
  the primary lever if post-launch conversion is soft. (§3.4.)
- **Pro + Scale both exist.** Avoids the Pro-to-Enterprise jump
  that kills conversion at peer products; Scale at $2,499 (~$30k/yr)
  captures multi-BU orgs inside self-serve. (§3.2.)
- **Metered overage.** Pass-through to our cost plus 3-6× markup.
  Matches industry convention above Scale-tier volumes. Tapers at
  1B/mo. (§4.)
- **BYO LLM keys.** No LLM-cost risk on our books. Matches
  LangSmith, Braintrust, Helicone, Langfuse, Arize Phoenix industry
  standard. (§2.3.)

### 3.3 Unit economics at each tier

Per-classification COGS from `pricing-deep-dive.md` §1 (at AWS /
Stripe April 2026 list rates; Phase-0 rule-only customer):

| Tier | Monthly vol | Infra | Storage | Total COGS | Gross margin |
|---|---:|---:|---:|---:|---:|
| Free | 10k | $0.02 | <$0.01 | $0.03 | n/a (loss-leader) |
| Solo ($19) | 100k | $0.17 | $0.01 | $0.18 | **99.1%** |
| Team ($99) | 1M | $1.70 | $0.07 | $1.77 | **98.2%** |
| Pro ($499) | 10M | $8.00 | $0.70 | $8.70 | **98.3%** |
| Scale ($2,499) | 100M | $80 | $7 | $87 | **96.5%** |

Reserved-capacity infrastructure switch at Pro+ volume drops infra
to ~$0.80/1M (from $1.70/1M on-demand). See `pricing-deep-dive.md`
§1.1 for the AWS-list-rate breakdown.

LLM-routed customers' costs don't change our margin — we use
BYO-keys pass-through, so the customer's LLM bill (e.g., $7.50/mo
for 50% LLM routing at 1M/mo through Haiku/Mini) goes directly to
the LLM provider, not our books. See `pricing-deep-dive.md` §1.7.

Net: **software-company economics at every paid tier**, insulated
from LLM price volatility because we never hold LLM inventory.

### 3.4 Load-bearing tier in year 1

**Team tier ($99/mo)** is the year-1 center of gravity. It's priced
for small startup eng teams that have 3-10 classification sites and
moderate traffic. The self-serve motion from Free → Solo → Team is
the bottom-up adoption engine; Pro and Scale close from within that
funnel as customers grow.

### 3.5 Annualized revenue per tier (Y1 plan basis)

| Tier | Target customer count (Y1 end) | ARR per customer | ARR contribution |
|---|---:|---:|---:|
| Free | 5,000+ | $0 | $0 (adoption asset) |
| Solo | 200 | $228 | $46k |
| Team | 50 | $1,188 | $59k |
| Pro | 10 | $5,988 | $60k |
| Scale | 1 | $29,988 | $30k |
| Design-partner | 3-5 (one-time, paid Q1) | $10-25k | $30-75k |
| Consulting | — | — | $40-100k |
| **Y1 total** | **~260 paid** | — | **$265k-$370k ARR + consulting** |

Matches the §7.4 table in `entry-with-end-in-mind.md` (the
bootstrap plan). Floor-case numbers.

---

## 4. Moat — how do we keep people from cloning this?

The technique itself — rule → LLM-shadow → LLM-primary → ML-shadow →
ML-with-fallback → ML-primary with statistical gates — is **in the
paper**. We *want* people to use it. The moat isn't the technique.

### 4.1 Moat bricks (in order of durability)

1. **Canonical-primitive status.** The paper makes Dendra's six-phase
   lifecycle *the* vocabulary the literature uses. When future
   research cites "transition curves," it cites our paper. When
   vendors ship a graduated classifier, "it's Dendra" becomes the
   default. Lasts **5–10 years** if we publish 2 follow-ups.

2. **Analyzer corpus.** The static scanner's rule-pattern library (50+
   code patterns that indicate classification sites) is the part
   that's *empirically hard*. Building it requires running against
   hundreds of real repos and tuning pattern precision/recall. **Every
   customer run improves our patterns**, and we don't share the
   pattern library. Classic snyk-style data moat.

3. **Domain packs.** Pre-trained ML baselines for the Tier-1 categories
   (support triage, content moderation, clinical coding, fraud, SOC
   alerts, intent routing). A new adopter integrates a domain pack
   and skips cold-start. A fork cannot replicate this without
   customer traffic.

4. **Federated outcome-log network effect.** Opt-in anonymous sharing
   of (hashed-input, label-distribution, graduation-outcome) triples
   — not user data — from customer installs. The more orgs share,
   the better our **transition-depth predictor** becomes at
   telling a new user "your classifier will graduate at ~N outcomes".
   Individual installs get less value from local data than from
   the federation. This compounds.

5. **Integration surface.** Adapters for Snowflake events, Datadog
   logs, Sentry issues, Slack, Linear, Jira, PagerDuty, Zendesk,
   Salesforce Service Cloud, LangSmith traces, Weights & Biases
   runs. Each integration is a moat brick — re-building a hundred
   of them is multi-year work.

6. **Regulatory / compliance certifications.** Dendra's signed
   outcome-log becomes a **FedRAMP / SOC2 / HIPAA / GDPR** artifact
   with the right audit paperwork. Expensive to replicate, licensable.
   Vega (the identity layer across our stack) is the partner here.

7. **Academic credibility.** The paper + follow-ups give us a
   citation graph competitors have to climb over.

8. **The name.** Dendra + "graduated autonomy" + "transition curves"
   is defensible linguistic turf.

### 4.2 Things that are NOT our moat

Being honest about this keeps the strategy grounded:

- The six-phase lifecycle — copyable.
- The `@ml_switch` decorator API — copyable.
- The scikit-learn ML head — commodity.
- Per-customer outcome logs without federation — not a moat, just
  customer data.

### 4.3 Defensive hygiene

- Trademark "Dendra" and "Transition Curves" (the latter as a
  business-service trademark).
- Keep the paper's **category taxonomy** (§6) *incomplete* in the
  first publication — the completed version is in the enterprise
  product as proprietary regression coefficients.
- Ship new phases or extensions faster than the rate at which
  re-implementations catch up. A moving primitive is harder to fork.

---

## 4.4 The AI-coding era pushes primitives toward commoditization

A consequence of LLM-assisted coding that sharpens our moat strategy:

- **Writing a Dendra clone is easier than ever.** A senior eng with
  Claude Code can produce a working six-phase graduated-classifier
  library in 2–3 days. The *code* of the primitive is commodified.
- **Therefore the moat is not in the primitive's code.** It is in
  everything *around* the primitive: corpus, federation, domain
  packs, audit signing, integration surface, canonical citation.
- **This accelerates the urgency of year-one moves.** If we spend
  year one only on the library, we lose the moat race to whoever
  builds the analyzer or the federation first.
- **AI assistants amplify network effects.** Once Dendra is in
  enough public codebases, Claude/Cursor/Copilot *suggest* Dendra
  patterns by default on any classification-shaped function.
  Reverse-network-effect: presence in training data becomes moat.
- **Reframed defensibility priority order:** (1) publish + canonical
  status; (2) analyzer corpus; (3) federated outcome-log network
  effect; (4) domain packs. Code itself is #7.

**Concrete adjustment:** bring forward the **analyzer OSS launch**
from Y2 to Y1 H2. Corpus compounding is the single most moat-
building activity we can do, and it competes against a shrinking
window before a fast-follower ships their own scanner.

---

## 5. Pricing-to-value calibration

Cross-referencing the measured savings per `industry-applicability.md`
§4-§5 (mid-market SaaS, 15 classification sites, AI-era calibrated):
**$640k-$2.8M/year** captured value.

Dendra's pricing captures ~5-25% of that value depending on tier:

| Tier | ARR | % of mid-market-customer value (low-end $640k) | % of high-end value ($2.8M) |
|---|---:|---:|---:|
| Team ($99/mo) | $1.2k | 0.2% | 0.04% |
| Pro ($499/mo) | $6.0k | 0.9% | 0.2% |
| Scale ($2,499/mo) | $30k | 4.7% | 1.1% |
| Enterprise ($250k/yr midpoint) | $250k | 39% | 8.9% |

**Interpretation:**
- **Team → Pro customers** pay a tiny fraction of Dendra's captured
  value — deliberately. We're pricing for adoption, not value
  capture, at this stage of the ladder.
- **Scale** starts pricing for value — ~5% of measured customer
  savings. Still generous.
- **Enterprise** captures ~10-40% of customer value, which is the
  band infrastructure primitives successfully charge (compare:
  Datadog captures ~15-30% of observability ROI; Snyk ~20-35% of
  security-incident-avoidance value).

The asymmetric pricing is deliberate: **the bottom of the ladder is
a growth asset, the top is the revenue engine.** Volume drives
adoption; enterprise drives ARR.

### 5.1 Metered overage is pure margin

Above-Scale usage-based pricing at $0.01/1k classifications has
~99% gross margin given the invention's sub-microsecond overhead
and commodity storage costs. A customer doing 500M
classifications/mo pays $2,499 base + $4,000 overage = **$6,499/mo**,
of which approximately $6,350 is margin.

### 5.2 Why not SaaS-standard per-seat?

Most dev-tools competitors (LaunchDarkly, Snyk) price per developer
seat. We don't. Per-seat pricing is **anti-adoption** for a primitive
— every engineer who wraps a classifier adds marginal cost to the
customer, creating a friction against widespread use. Instead, we
price on classifications/month (the infrastructure cost we actually
incur), which aligns with value generation and has no adoption
penalty.

The seat-count caps at each tier (1, 10, 50, unlimited) exist for
team-collaboration features (shared workspaces, audit views), not
to meter classifier usage.

---

## 6. Three-year shape of the business

### Year 1 (2026) — bootstrap, primitive, first revenue

- Dendra OSS on PyPI; paper on arXiv; four-benchmark measurements
  published.
- Free tier live from day 0. Solo / Team / Pro / Scale self-serve
  tiers GA by end of Q2.
- 3-5 design-partner contracts ($10-25k each, Q1).
- 1-2 domain packs shipped (support-triage, content-moderation).
- **Targets:** 1,000 GitHub stars, 10,000 PyPI downloads/mo,
  5,000 Free hosted signups, 260 paid customers, **$265-370k ARR
  + $40-100k consulting** (founder-sustainable, no outside
  capital required).

### Year 2 (2027) — enterprise inflection

- Scale and Enterprise tiers mature; first Enterprise contracts
  close.
- Domain packs library expands to 4-5 categories.
- SOC 2 Type 1 audit completed.
- First named-account customer closes at $100-250k ARR.
- Optional: Seed / Series A round if the bottom-up funnel is
  growing faster than founder-only can support.
- **Targets:** 5,000 GitHub stars, 50,000 PyPI downloads/mo,
  25,000 Free signups, 1,500 paid customers, 3-5 Enterprise
  contracts, **$1-3M ARR**.

### Year 3 (2028) — canonical primitive + regulated-industry entry

- Paper 2 published (production case study + federation results).
- Domain packs library at 8-10 categories; clinical-coding and
  fraud packs driving regulated-industry sales.
- SOC 2 Type 2 + HIPAA or FedRAMP baseline completed.
- Federation (opt-in cross-org outcome-pattern aggregation) GA;
  transition-depth predictor improves for all customers.
- Metered-overage revenue material; first 1B-classifications/mo
  customer.
- **Targets:** canonical-primitive status (5+ academic citations,
  pip-install shows up in large codebases by default), **$10M
  ARR**, 10-15 Enterprise contracts, patent (utility) issued.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0 licensed._
