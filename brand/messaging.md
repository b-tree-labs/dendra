# Postrule · messaging architecture

The canonical statements Postrule makes about itself. Every
landing-page header, pitch deck, launch-day post, press release,
and product-page meta description pulls from here.

Consistency matters more than cleverness. When in doubt, use
the canonical copy verbatim rather than paraphrasing.

## Primary tagline

> **Self-taught classifiers.**

Subhead (companion sentence, used wherever the tagline gets a
single follow-on line):

> *The graduated-autonomy primitive for production classification. Rules graduate to LLM, then to in-process ML, through statistically-gated phase transitions. The rule stays as the safety floor.*

(Internal codename: "self-taught" — landed 2026-05-14 in response to
founder feedback that the prior tagline ("Software that's smarter
every month than the day you shipped it.") pinned the value
prop to a monthly cadence the product can't universally deliver
(low-traffic switches may take longer; high-traffic ones improve
daily). "Self-taught classifiers." captures the autonomy in three
words, doesn't claim a cadence, names the audience, and thematically
echoes the founder's own self-taught engineering path. The previous
"closer #9" tagline is retained below for historical context.)

Use on:
- Landing page hero (`landing/index.html`).
- README.md H1.
- PyPI project description.
- Open Graph / Twitter card descriptions.
- Social-media bio.
- Pitch deck cover (when one exists).

Do not shorten, re-order, or paraphrase without noting the new
form in this doc.

### Historical primary taglines

- **2026-04-29 → 2026-05-14 ("closer #9"):** *Software that's smarter every month than the day you shipped it.* Replaced because the monthly cadence wasn't universally accurate.

## Secondary taglines (contextual alternates)

- **Developer-action subtitle** (paired under the primary): "*Drop a
  rule. Drop a verifier. Watch your classifier get smarter
  automatically.*" Used as the action sub-tagline on the README hero.
- **Category descriptor** (where "primitive" framing matters): "*The
  classification primitive every production codebase is missing.*"
  Was the primary through 2026-04-29; retained for footer-style
  category framings.
- **Research audience:** "*When should a rule learn?*" (matches
  the paper title; works on arXiv description + academic blog).
- **Developer audience (short):** "*One decorator. Six phases. A
  safety floor.*"
- **Enterprise / safety audience:** "*Graduated autonomy, with a
  statistical safety bound.*"
- **Concise label** (for navigation, short slots): "*The
  graduated-autonomy primitive.*"

Use the primary tagline wherever space permits. Secondaries are
for contexts where the primary is too long or the audience is
narrow enough to warrant sharpening.

## Elevator pitches

### 15-second (one-sentence)

> Postrule is a Python primitive that lets a hand-written rule
> graduate to LLM or ML, with a statistical gate at every
> transition and the rule retained as the safety floor.

### 30-second

> Every production system has classification decisions — routing
> a ticket, classifying an intent, selecting a retrieval strategy,
> screening an output for PII. They start as hand-written rules
> because no training data exists on day one. Over time, outcome
> data accumulates, but the rules stay frozen because migrating
> each site to ML is bespoke engineering. Postrule is one
> decorator, six lifecycle phases, a paired-proportion statistical
> gate at every transition, and a safety floor that survives
> jailbreaks and silent ML failures. Install with `pip install
> postrule`; wrap your existing rule; advance phases when the
> evidence clears the test.

### 2-minute

(The 30-second pitch plus:) The central theorem is that the
probability of worse-than-rule behavior at any phase transition
is bounded above by the paired-proportion test's Type-I error
rate — you can literally prove you won't regress past a specific
threshold when you advance. We measured this on four public
classification benchmarks (ATIS, HWU64, Banking77, CLINC150) at
p < 0.01. Transition depths range from 250 outcomes for narrow
domains to 1,500 for high-cardinality domains. Latency overhead
at Phase.RULE is ~1 µs p50 — fast enough that any production hot
path is dominated by the caller's logic, not Postrule's. Postrule ships Apache 2.0 on
the client SDK, Business Source License 1.1 on the analyzer and
operated components (Change Date 2030-05-01 → Apache 2.0).
Filed US provisional patent. Paper under submission. Built by
B-Tree Labs — a B-Tree Labs DBA.

## Audience-specific framings

Same product, three different first sentences depending on who
you're talking to.

### For engineering leaders

> Postrule is the primitive your team needs to migrate
> classification code from rule to ML without running the
> migration risk yourself. The statistical gate proves the bound
> on regression; the rule floor guarantees you never ship
> worse-than-rule behavior to a customer.

### For ML engineers

> Postrule is a decorator + outcome log + phase-transition gate
> that lets you test whether your LLM or ML head actually beats
> your rule in production, and advance only when a paired
> McNemar test says the higher tier is statistically better.

### For researchers

> Postrule is the reference implementation of the six-phase
> graduated-autonomy lifecycle, with paired-proportion
> transitions and a safety-floor guarantee. Paper, benchmarks,
> reproduce scripts, and the analyzer tooling are all OSS.

### For procurement / enterprise buyers

> Postrule is the safety floor for production classification. The
> rule you authored is never removed. A statistical test gates
> every advancement. SOC2, HIPAA, and FedRAMP readiness are on
> the year-two roadmap; the patent (filed provisional) protects
> the architectural claim.

## Positioning statement

> For engineering teams running classification decisions in
> production,
> Postrule is the graduated-autonomy primitive
> that migrates rules to ML under a statistical gate,
> unlike pure-LLM architectures that silently fail,
> unlike shadow-mode frameworks that never tell you when to
> switch,
> and unlike bespoke ML migrations that burn engineer-weeks
> per site.

Following the standard positioning template:
*For [audience] / [product] is [frame of reference] / that [key
benefit] / unlike [alternatives] / [differentiator].*

## What Postrule IS and ISN'T

**Postrule is:**
- A Python primitive (decorator + runtime + storage + statistical
  test + adapter protocols).
- A reference implementation of a published method.
- A research artifact tied to a peer-reviewable paper.
- Infrastructure — the thing that sits between code and ML.

**Postrule is NOT:**
- An AutoML platform. It does not train models; you provide the
  ML head.
- An LLM orchestration framework. Postrule's LLM adapters are
  thin; they call your provider, get a prediction, return it.
- A managed service (yet). Postrule Cloud is on the Year-1 roadmap;
  pre-launch it's OSS-only.
- An observability platform. Postrule emits outcome records to
  whatever storage you configure; Datadog / Honeycomb / LangSmith
  consume those, they aren't Postrule.

## Core claims (cite these numbers verbatim)

| Claim | Number | Source |
|---|---|---|
| Phase.RULE classify p50 | 0.96 µs | `docs/benchmarks/perf-baselines-2026-05-01.md` |
| Phase.RULE dispatch p50 | 1.00 µs | `docs/benchmarks/perf-baselines-2026-05-01.md` |
| Switch overhead vs bare call | ~24× (42 ns → 1 µs) | `docs/benchmarks/perf-baselines-2026-05-01.md` |
| FileStorage batched throughput | 245K writes/sec | `docs/benchmarks/perf-baselines-2026-05-01.md` |
| Benchmarks measured | 4 (ATIS, HWU64, Banking77, CLINC150) | `src/postrule/benchmarks/` |
| Paired-test threshold | p < 0.01 | `docs/papers/...` |
| ATIS transition depth | ≤ 250 outcomes | paper results |
| CLINC150 transition depth | ≤ 1,500 outcomes | paper results |
| Rule→ML accuracy gap (range) | +19 pp (ATIS) → +82 pp (Banking77) | paper results |
| Jailbreak corpus | 20-pattern, 100% rule-floor preserved | `tests/test_security_benchmarks.py` |
| PII corpus | 25-item mixed, 100% recall / 100% precision | `tests/test_security_benchmarks.py` |

When any of these numbers change in the codebase, update this
table and every message that cites them.

## Do-not-say list

Things that sound like they'd fit Postrule's category but misstate
what we actually do. Never use these in public copy.

- "AI-powered classification" — misleading; Postrule's RULE phase
  has no AI at all, and the product is equally for teams that
  never want LLMs in the decision path.
- "Postrule replaces your rules with ML." — wrong. Postrule retains
  the rule as the safety floor *through every phase*, including
  the highest-autonomy phase.
- "Self-improving classifier." — overclaim; the statistical gate
  requires an operator to decide to advance.
- "Production-grade / enterprise-grade ML infrastructure." —
  premature; we're pre-SOC2, pre-HIPAA, pre-FedRAMP. Year-2
  commitment only.
- "The only X that Y." — not verifiable. Use "A X that Y" at most.

## Launch-day copy stubs

Canonical messages for specific launch-day channels. Fill in
`<ARXIV_URL>` and `<LAUNCH_POST_URL>` at go-time.

**HN title:**
> Show HN: Postrule – Classification primitive with statistically-gated rule→ML graduation

**r/MachineLearning title:**
> [R] When Should a Rule Learn? Transition Curves for Safe Rule-to-ML Graduation (+ Python library)

**LinkedIn opener:**
> Postrule is the classification primitive every production
> codebase is missing.

**arXiv abstract first sentence:**
> We present Postrule, a graduated-autonomy classification primitive
> whose six-phase lifecycle advances between a hand-written rule,
> an LLM, and an ML head under a paired-proportion statistical
> gate that bounds the probability of worse-than-rule behavior
> at any transition.

This doc keeps only the canonical one-liners each channel
needs; full per-channel drafts live in internal launch notes.

---

**Maintenance:** update this doc whenever the primary tagline or
any of the core-claim numbers changes. The README, landing page,
launch drafts, and docs all pull from here.
