# Launch-day post drafts

Copy-paste-ready drafts for Hacker News, r/MachineLearning, and
LinkedIn. Optimized for the channel's conventions. Replace
`<ARXIV_ID>` and `<BLOG_URL>` placeholders immediately before
posting.

**Timing.** Post HN first, at 07:00 ET on a Tue/Wed/Thu. Post
r/MachineLearning within 30 minutes of the HN submission so
cross-referral hits while both are warm. LinkedIn 2-4 hours
later once the HN thread has enough comments to anchor social
proof.

---

## Hacker News — Show HN post

**Title** (under 80 chars; HN truncates at 80):

> Show HN: Dendra – Classification primitive with statistically-gated rule→ML graduation

**Alternate title candidates** (rank by CTR if you want to A/B):

- `Show HN: When should your if/else graduate to ML? Dendra answers with a p-value`
- `Show HN: A decorator that graduates your classifier from rule to ML, with a safety floor`

**URL:** `<BLOG_URL>` (the dogfood post) — gives HN a content
anchor other than the repo. Alternative: point at
`dendra.dev` if the landing page is up before posting.

**First comment** (post it yourself within 60 seconds of
submission; HN rewards thread authorship):

> Hi HN! I'm Ben, the author of Dendra and the paper.
>
> **The one-sentence pitch:** every production system has
> classification decisions — routing a ticket, classifying an
> intent, selecting a retrieval strategy, screening an output
> for PII. They start as hand-written rules because no training
> data exists on day one. Over time, outcome data accumulates,
> but the rules stay frozen because migrating each site to ML
> is bespoke engineering at every decision point.
>
> Dendra is one decorator, six lifecycle phases, statistical
> gates at every transition, and a safety floor that survives
> jailbreaks, silent ML failures, and unbounded token bills.
>
> ```python
> from dendra import ml_switch, Phase, SwitchConfig
>
> @ml_switch(
>     labels=["bug", "feature_request", "question"],
>     author="@triage:support",
>     config=SwitchConfig(phase=Phase.RULE),
> )
> def triage(ticket: dict) -> str:
>     title = ticket.get("title", "").lower()
>     if "crash" in title:
>         return "bug"
>     if title.endswith("?"):
>         return "question"
>     return "feature_request"
> ```
>
> Wrap your rule at Phase.RULE → zero behavior change. Dendra
> logs every classification. When outcome evidence accumulates
> past a paired-proportion statistical test (McNemar's exact),
> you advance the phase and the LLM (or ML head) takes over —
> with the rule always available as the floor.
>
> **What's novel:** the statistical transition gate bounds the
> probability of worse-than-rule behavior by the test's α. You
> can literally prove you won't regress past a specific
> threshold when advancing phases. Paper's §3.3 has the theorem.
>
> **What's measured:** four public benchmarks (ATIS, HWU64,
> Banking77, CLINC150) with paired McNemar at p < 0.01. Latency:
> 0.62 µs p50 switch overhead at Phase 0. At 100M
> classifications/mo, LLM-only designs with a Sonnet-class
> model run $11.5M/yr in tokens; Dendra at Phase 4 drops that
> to essentially zero while preserving LLM-quality decisions
> on the 20% of traffic the rule/ML can't handle.
>
> Paper: `<ARXIV_URL>`
> Code: `https://github.com/axiom-labs-os/dendra`
> Analyzer on public repos: `<BLOG_URL>`
>
> I'm happy to go deep on the statistical theorem, the two-regime
> paper finding, the safety-critical architectural cap, the
> analyzer corpus-moat design, or why we chose split Apache +
> BSL licensing over pure OSI-open. Fire away.

**Anticipated pushback → pre-written responses** (keep as a
cheat sheet next to the HN tab; do NOT post pre-emptively):

1. **"This is just shadow mode."** → Shadow mode says "run both,
   log both." Dendra says "run both, log both, and tell me when
   the evidence is strong enough to switch." The paired-test
   gate is what shadow mode doesn't have.
2. **"Why not Vowpal Wabbit / online learning?"** → Different
   problem. VW is continuous adaptation with no rule floor.
   Dendra is rule-to-ML migration with the rule preserved as
   safety floor. FAQ has the longer answer.
3. **"BSL is not open source, you're evil."** → Three-part reply:
   (a) The *client SDK* (what you import) is Apache 2.0,
   commercial-friendly, free forever. (b) Only the analyzer and
   future hosted components are BSL. (c) The BSL auto-converts
   to Apache 2.0 on 2030-05-01 — promise is in the license file.
   HashiCorp / CockroachDB / Sentry ship BSL into the Fortune
   500 without drama.
4. **"Apache 2.0's patent grant covers the invention."** → Yes,
   correct. That's why every Apache-SDK user is automatically
   licensed to practice. The patent's teeth are against
   hyperscaler clones that don't use the code — which is exactly
   the class of use the BSL is written to gate.
5. **"What about latency?"** → 0.62 µs p50 at Phase 0. Hard
   number from `tests/test_latency.py`. Not a hand-wave.
6. **"This is YAGNI for most people."** → Agree, probably. The
   analyzer is free. Run `dendra analyze` on your codebase; if
   it finds three sites, you probably don't need Dendra. If it
   finds thirty, now you have a prioritized list.

---

## r/MachineLearning — [R] submission

**Post subreddit:** `/r/MachineLearning` (capital-R for
research-flair posts get more ML engagement than [Project] flair;
paper + benchmarks qualify).

**Title:**

> [R] When Should a Rule Learn? Transition Curves for Safe Rule-to-ML Graduation (+ Python library)

**Body:**

> **Problem.** Classification decisions in production systems
> start as rules. Moving them to ML is risky — you might regress
> past the rule. Most teams either ship ML too early (regression
> hazard) or never ship ML at all (tech debt). There's no
> *principled* criterion for *when* to advance.
>
> **Contribution.** We define a six-phase lifecycle (RULE →
> LLM_SHADOW → LLM_PRIMARY → ML_SHADOW → ML_WITH_FALLBACK →
> ML_PRIMARY) and prove that, when each phase transition is gated
> by a paired-proportion statistical test at significance level α,
> the probability of producing worse-than-rule behavior at any
> transition is bounded above by α. The rule is retained as the
> safety floor throughout — at the terminal phase a circuit
> breaker reverts routing to the rule on ML anomaly.
>
> **Measurement.** On four public classification benchmarks
> (ATIS, HWU64, Banking77, CLINC150), paired McNemar's exact
> tests at p < 0.01 tell you the transition depth: for ATIS
> (26 labels, narrow domain, "rule-viable" regime), ML earns
> its graduation at ≤ 250 outcomes; for CLINC150 (151 labels,
> broad domain), ≤ 1500 outcomes. Full transition curves, ML
> ceiling accuracies, and rule baselines in the paper.
>
> **Two-regime finding.** The transition depth per-example is
> bimodal — narrow-domain benchmarks (ATIS) and broad-domain
> benchmarks (CLINC) need very different graduation budgets.
> We identify the discriminating factors in §6 of the paper.
>
> **Library.** `pip install dendra` — the reference
> implementation. One decorator, four LLM adapters
> (OpenAI/Anthropic/Ollama/llamafile), a scikit-learn ML head
> default, a self-rotating outcome log, and a `dendra analyze`
> static scanner for finding graduation candidates in a
> codebase. 195 tests, latency benchmarks, jailbreak + PII
> corpora.
>
> **Paper:** `<ARXIV_URL>`
> **Code:** `https://github.com/axiom-labs-os/dendra`
> **Analyzer on public repos (Sentry, PostHog, HuggingFace,
> LangChain):** `<BLOG_URL>`
>
> We're also running a design-partner program for teams with
> production classifiers they'd like to graduate — happy to
> chat.

**Tags to add:** `[R]`, `classification`, `production-ML`,
`statistics`.

**Cross-posting:** `/r/datascience` if the HN + ML posts are
pulling moderate traffic; `/r/programming` if they're quiet.

---

## LinkedIn — launch announcement

**Audience:** engineering directors, ML platform leads, heads
of data. Keep it business-framed, less technical depth than HN.

**Post body** (paste as-is; LinkedIn supports line breaks but
not markdown):

> After 18 months of design and a provisional patent filed last
> week, Dendra is public today.
>
> Dendra is the classification primitive every production
> codebase is missing.
>
> Every production system has classification decisions — routing
> a ticket, classifying an intent, selecting a retrieval
> strategy, screening an output for PII. They start as
> hand-written rules because no training data exists on day
> one. Over time, outcome data accumulates, but the rules stay
> frozen because migrating each site to ML is bespoke
> engineering at every decision point.
>
> Dendra is one decorator, six lifecycle phases, statistical
> gates at every transition, and a safety floor that survives
> jailbreaks, silent ML failures, and unbounded token bills.
>
> Highlights:
>
> 🔹 One-line install: `pip install dendra`
> 🔹 Zero behavior change on day one — wrap your existing rule,
>    production is unchanged.
> 🔹 Statistical transition gate proves the probability of
>    worse-than-rule behavior is bounded by the test's α.
> 🔹 Measured on four public benchmarks with paired McNemar's
>    exact tests at p < 0.01.
> 🔹 0.62 µs p50 latency overhead at the rule phase — 5× a bare
>    function call.
> 🔹 Static analyzer scans your codebase in 30 seconds and tells
>    you which sites are Dendra-fit candidates.
>
> We ran the analyzer on Sentry, PostHog, HuggingFace
> Transformers, and LangChain — 394 classification sites where
> a hand-maintained rule quietly decides something
> consequential, and where graduated-autonomy would add
> observability and a path to ML without risking regression.
> Full writeup: `<BLOG_URL>`
>
> Paper: `<ARXIV_URL>`
> Code: https://github.com/axiom-labs-os/dendra
>
> If your team runs classifiers at scale and you're interested
> in a design-partner slot (6-month priority access to Dendra
> Cloud when it ships, direct founder Slack, case-study
> rights), DM me or email partners@b-treeventures.com.
>
> Tagging a few folks I know have this exact problem in
> production: [tag 5-10 specific people in your network who
> are directors / staff engs at classifier-heavy product
> companies — Supabase, Linear, PostHog, Cal.com, dbt Labs,
> HuggingFace, Anyscale, Arize, Braintrust, LangSmith. Don't
> tag them unless you've had direct conversation history.]
>
> #MachineLearning #ProductionML #Classification #DevTools #OSS

---

## Post-launch cadence

**Hour 0 (T+0):** HN post goes live. First comment within 60
seconds. Upvote it yourself (once). Email 5 closest colleagues
asking them to read; don't ask for upvotes (HN penalizes vote
rings).

**Hour 0-2:** Stay at the HN tab. Reply to every technical
question within 15 minutes. Technical depth wins front-page
ranking far more than clever marketing copy.

**Hour 0.5:** r/MachineLearning post goes live with cross-link
to the HN thread in the body.

**Hour 2-4:** LinkedIn post. Include the HN point count and r/ML
upvotes as social proof if either looks decent (>20 HN points,
>50 r/ML upvotes).

**Hour 8:** If HN traction is moderate+ (front page / >100
points), post to Bluesky + X threads mirroring the LinkedIn
content. If HN traction is soft, don't amplify — instead, pivot
to personal outreach: email 10 engineering-blog writers with a
tight pitch (≤ 100 words, HN link + paper link).

**Day 2:** Start design-partner outreach (Templates 1-2 from
`docs/marketing/outreach-templates.md`) to 20 tier-1 targets.
Reference the HN post as social proof if decent.

**Day 3:** Thank-you post on HN + LinkedIn listing first-day
numbers. Link to "what's next" section of the roadmap. This
sustains attention cycle 24-48 more hours.

## If launch traction is soft

See `docs/working/launch-checklist-48hr.md` §"If launch traction
is soft" — the three diagnostic cases and their responses.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Internal operations doc — update these drafts post-launch with
actual numbers + learnings for the next launch._
