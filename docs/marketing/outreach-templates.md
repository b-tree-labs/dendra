# Outreach Templates — Design Partner Program

**Purpose:** first-dollar customer motion. You (Ben) send these;
I drafted them.

**Sequence:**
1. Cold intro (LinkedIn DM / X DM / cold email).
2. Follow-up 1 (5 days later if no reply).
3. Follow-up 2 (10 days later, value-add only).
4. Warm reply → 20-min call → proposal.

**Tone guidance:**
- Short. Three sentences or fewer for cold outreach.
- No marketing adjectives. No "revolutionary," no "game-changing."
- Lead with a specific observation about their product.
- Ask for ≤ 20 minutes, not "a demo."

---

## Template 1 — Cold intro (LinkedIn / email)

**Subject:** classification primitive for [product] — 20 min?

**Body:**

> Hi [NAME],
>
> I noticed [specific product detail — their triage system, their
> content moderation, their intent router, whatever]. I've been
> building the primitive that every production codebase has to
> reinvent for that kind of decision point — graduated-autonomy
> classification with statistical transition gates, patent-pending,
> Apache 2.0 ([github link]).
>
> We're onboarding 3-5 design partners at $10-25k for 6-month
> priority access + influence on roadmap. Would 20 minutes in the
> next 2 weeks be worth a look?
>
> Ben
> *Axiom Labs / B-Tree Ventures*

---

## Template 2 — Cold intro (X / Bluesky DM)

**Character budget: 2,000.**

> Hey [NAME] — building the classification primitive production
> codebases keep reinventing. Graduated-autonomy, statistical
> transition gates, open-source. Four public-benchmark
> measurements. Patent-pending. Taking on 3-5 design partners —
> $10-25k for 6mo priority access + roadmap input. 20 min to see if
> it fits your triage/router/moderation stack? No demo deck; live
> repo walkthrough. [github.com/axiom-labs-os/dendra]

---

## Template 3 — Follow-up 1 (day +5)

**Subject:** re: classification primitive for [product]

**Body:**

> Quick follow-up on the Dendra design-partner note. We ran it on
> four public intent-classification benchmarks — ATIS / Banking77 /
> HWU64 / CLINC150 — and found two regimes where the primitive has
> measurable impact. Your [product detail] looks like the [narrow-
> domain / high-cardinality] case, which is where Dendra's
> transition-curve story is tightest.
>
> 20 minutes this or next week? I'll bring the figure and the code.
>
> Ben

---

## Template 4 — Follow-up 2 (day +10, value-add only)

**Subject:** [share an artifact, don't pitch]

**Body:**

> [NAME] — last ping. Figured you'd find this useful whether or
> not we end up talking:
>
> We published the two-regime finding in a short preprint:
> [arxiv link].
>
> Short version: for a classifier with 100+ labels, a day-zero
> rule is effectively 0% useful and the only way to ever ship ML
> is with outcome-logging in place from day one. For 10-30 label
> classifiers, the rule stays viable for years and the interesting
> question is when to graduate.
>
> If your [product detail] is in either camp, happy to send the
> `dendra analyze` output for a public repo of yours so you can
> see what it finds in ~60 seconds.
>
> Ben

---

## Template 5 — Warm reply → discovery call setup

**Subject:** thanks — 20-min slot options

**Body:**

> Thanks [NAME]. A few options this week:
>
> - Tuesday 11am–12pm CT
> - Wednesday 3pm–4pm CT
> - Thursday 1pm–2pm CT
>
> [Calendly link as fallback]
>
> Three things I'll cover (total 15 min, 5 min Q&A):
>
> 1. The 6-phase primitive. Live code walkthrough, not slides.
> 2. How it looks in your codebase (I'll run `dendra analyze`
>    on your public repo beforehand and share the report).
> 3. Design-partner terms: $10-25k, 6-month priority access to
>    Dendra Cloud, direct Slack channel, case-study rights.
>
> Ben

---

## Template 6 — Post-call follow-up (design-partner proposal)

**Subject:** Dendra design partner — proposal

**Body:**

> [NAME] — thanks for the time today. Short proposal following up:
>
> **Scope**
> - [specific classification site we discussed]
> - Dendra Phase 0 integration (outcome logging, zero behavior
>   change)
> - Priority access to Dendra Cloud hosted outcome-log and
>   transition-curve dashboard when it ships (estimated 8-10
>   weeks).
> - Direct Slack channel with me for questions / custom pattern
>   development.
> - Case-study rights: we write one together, co-bylined.
>
> **Fee:** [$15k / $20k / $25k depending on scope] paid upfront.
> 6-month engagement.
>
> **Out of scope (year 2+):** SOC 2 certification, enterprise
> license, domain-pack training. Those are separate commitments
> if you want them.
>
> **Next step:** I'll send a one-page Design Partner Agreement
> (template attached) for review. Legal turnaround in [company]
> is usually how long?
>
> Ben

---

## Template 7 — Ghost recovery (day +21, if the deal stalled)

**Subject:** pause or pass?

**Body:**

> [NAME] — just a low-pressure check. We're closing 3-5 design-
> partner slots in the next [2 weeks / month] and I want to be
> honest about the ticking clock. Two cases:
>
> - **Still interested, just busy** — totally get it, say so and
>   I'll hold a slot through [date].
> - **No fit** — also totally fine, say so and I'll stop bugging
>   you.
>
> Either way, thanks for the consideration. [Short personal note
> like "congrats on the [feature] launch" if true.]
>
> Ben

---

## Target-list shaping

**Priority tier 1** (known classifier-heavy, named public engineering
blogs, likely to adopt primitives):

- Supabase (support triage)
- Linear (triage automation)
- PostHog (session/user classification)
- Cal.com (scheduling intent)
- dbt Labs (query-type routing in dbt Core)
- Turso / Neon / Planetscale (classification in their product
  support funnels)
- HuggingFace (won't pay; worth citing for viral adoption)
- Anyscale (Ray classification primitives)
- Arize / Weights & Biases (observability adjacent; potential
  integration)

**Priority tier 2** (enterprise-adjacent SaaS with classification
pain):

- Zendesk / Freshdesk (ticket triage, low chance of self-serve
  but high chance of enterprise conversation year 2)
- Sentry (error categorization — potential integration partnership)
- Rollbar / Honeybadger (similar)
- Vercel / Netlify (support classification internally)

**Priority tier 3** (AI-app companies that need output-safety
classification):

- Perplexity (output moderation for their search results)
- Harvey (legal classification; possibly too early)
- Hippocratic AI (clinical classification; possibly regulated too
  early)
- Runway (content moderation for generative output)

**Avoid for Y1:**
- Large enterprises (procurement cycles kill Q1 deals)
- Government (ditto)
- Academic labs (no revenue)
- Anyone whose primary product *is* classification (Watson,
  DataRobot) — direct competitors

---

## Target count math

- 40-60 outbound attempts (5-8 per target tier 1, plus 10-15
  tier 2, plus some tier 3)
- 30-40% reply rate → 15-20 conversations
- 20-25% conversion of conversations → 3-5 signed deals
- **Expected: 3-5 design partners × $10-25k = $30-125k Q1**

Budget **2 hours/day for 2-3 weeks** on outbound. Everything else
waits until the first deal signs.

---

## Tracking

Keep a simple spreadsheet:

| Target | Tier | First contact | Reply date | Call date | Status | Amount | Notes |
|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... |

Status values: `sent`, `replied`, `call_scheduled`, `proposal_sent`,
`negotiating`, `signed`, `passed`, `ghost`.

Weekly review every Friday. Move stalled deals to `ghost` after 21
days of silence; fire Template 7 before closing.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs)._
