# Landing-page wireframe — dendra.dev

**Stack target:** Astro static site → Firebase Hosting → GoDaddy DNS CNAME.
**Audience tiers (in priority order):**

1. **ML engineers / engineering leads** with classifiers in production
2. **Agent / autoresearch builders** looking for a deployment substrate
3. **Compliance / regulated-industry buyers** (HIPAA / export-control)

**Tone:** technical but inviting. Lean toward "we'll show you,"
not "let me sell you." No marketing-speak verbs ("leverage,"
"empower," "unlock"). Real numbers in headlines. Code on screen
where it earns its space.

**Conversion goals (in priority):**
1. `pip install dendra` (developer adoption)
2. **GitHub star** (social proof)
3. **arXiv paper read** (technical credibility)
4. **Hosted-waitlist signup** (lead capture for Wave 2)

This doc is the source of truth for copy + structure. Once you
sign off, I generate the Astro site directly from it.

---

## Page section map

```
[NAV BAR]
[HERO]                              ← the headline + 3-line pitch + CTA buttons
[THREE-AUDIENCE TRIPTYCH]           ← "Why are you here?" gateway
[CODE-FIRST PROOF]                  ← 12 lines of code that runs
[PAPER RESULT]                      ← the 250-outcome McNemar table
[AUTORESEARCH HOOK]                 ← CandidateHarness section (the slam-dunk)
[SAFETY GUARANTEE]                  ← rule floor + circuit breaker callout
[PRICING TIERS]                     ← Free / Solo / Team / Enterprise stub
[FAQ TEASER]                        ← top 4 questions with link to full FAQ
[FOOTER]
```

---

## NAV BAR

**Left:** DENDRA logomark (animated rising-accent on first scroll, per `brand/motion.md`).
**Right:** `Docs` · `Paper` · `GitHub` · `Pricing` · [`Get the Hosted Beta` — primary button, links to waitlist anchor].

Sticky-on-scroll. Hide hamburger menu on mobile only.

---

## HERO

**Visual layout:** left side text, right side a live-rendered terminal showing example 06's output (no animation overload — single `dendra/example_06_output.png` is fine, swap for a 3-second animated GIF if it lands cleanly).

### Headline (primary candidate)

> # When should a rule learn?

Sub-headline:

> ## A statistical framework for graduated ML autonomy. From rule to LLM to ML, with paired-McNemar gates at every transition and the rule retained as a safety floor.

### Headline (autoresearch-zeitgeist alternative — A/B candidate)

> # Autoresearch tells you what to try.
> # Dendra tells you when it worked.

Sub-headline:

> ## The production substrate for autoresearch loops. Shadow your candidates against live traffic, run paired-McNemar significance tests, promote when the evidence justifies it. The rule floor protects you the whole time.

### CTA buttons (under the headline, side by side)

- **`pip install dendra`** — primary button, monospaced. Click → expands to a copy-paste tooltip + scrolls to the Code-First Proof section.
- **Read the paper →** — secondary, links to the arXiv URL.
- **Star on GitHub →** — tertiary, links to the repo.

### Beneath the buttons (small, italics)

> Apache-2.0 client SDK · BSL-1.1 hosted analyzer · Python 3.10+ · zero hard runtime deps.

### Stat row (under CTAs, four columns)

| Stat | Source |
|---|---|
| **≤ 250 outcomes** | transition depth across 4 NLU benchmarks |
| **33 µs p50** | classify latency, persist=True production path |
| **473 tests** | full coverage including red-bar concurrency |
| **0 hard deps** | adapters are optional extras |

---

## THREE-AUDIENCE TRIPTYCH

Three side-by-side cards. Each starts with a question that
self-identifies the visitor's tier; clicking jumps to the
relevant deeper section.

### Card 1 — "I have a classifier in production."

> Six months ago you wrote a rule. The backlog has a ticket
> that says "we should ML this." The ticket doesn't move
> because replacing the rule is risky.
>
> Dendra is the migration runtime. Six lifecycle phases. A
> McNemar gate at every transition. The rule never leaves —
> it stays as the circuit-breaker floor even at the end-state.
>
> [`See the migration walkthrough →`](#paper-result)

### Card 2 — "I'm building an autoresearch loop."

> Your loop generates great candidates. Your deployment story
> is duct tape.
>
> Dendra ships a `CandidateHarness` that's the missing
> substrate. Shadow your candidates against live production,
> get paired-McNemar verdicts, promote when the evidence
> justifies it. The rule floor protects production from your
> loop's bad proposals.
>
> [`See the autoresearch integration →`](#autoresearch-hook)

### Card 3 — "I need an audit chain for compliance."

> Every classification on tape. Rule output, LLM output, ML
> output, verdict, timestamp, source. Pluggable redaction at
> the storage boundary for HIPAA / PII / export-control
> workloads. Operator actions (breaker reset, phase advance)
> on the same audit chain.
>
> [`See the compliance surface →`](#safety-guarantee)

---

## CODE-FIRST PROOF

Anchor: `#code-first-proof`.

**Heading:** `Twelve lines.`
**Sub-heading:** `Pip-install, drop a rule, run.`

```python
# pip install dendra

from dendra import ml_switch

@ml_switch(labels=["bug", "feature_request", "question"])
def triage(ticket: dict) -> str:
    title = (ticket.get("title") or "").lower()
    if "crash" in title:
        return "bug"
    if title.endswith("?"):
        return "question"
    return "feature_request"

result = triage.classify({"title": "app crashes on login"})
# ClassificationResult(label="bug", source="rule", confidence=1.0, phase=Phase.RULE)
```

**Below the snippet:**

> That's Phase 0 — `RULE`. Add an LLM, transition to
> `MODEL_SHADOW`. Add an ML head, transition to `ML_SHADOW`.
> Each transition gate-controlled by paired-McNemar
> significance against your accumulated outcome log. The rule
> stays as the circuit-breaker target throughout.
>
> [`Walk through the full lifecycle →`](https://github.com/axiom-labs-os/dendra/blob/main/examples/06_ml_primary.py)

---

## PAPER RESULT

Anchor: `#paper-result`.

**Heading:** `Transition depth ≤ 250 across four NLU benchmarks.`
**Sub-heading:** `The headline result, with paired McNemar.`

**Layout:** left column is the table (below); right column is
Figure 1 (the transition curves PNG from
`docs/papers/2026-when-should-a-rule-learn/results/figure-1-transition-curves.png`).

| Benchmark | Labels | Rule | ML final | Paired McNemar p | Trans. depth |
|---|---:|---:|---:|---:|---:|
| ATIS | 26 | 70.0% | **88.7%** | 1.8e-33 | ≤ 250 |
| HWU64 | 64 | 1.8% | **83.6%** | < 1e-260 | ≤ 250 |
| Banking77 | 77 | 1.3% | **87.7%** | ≈ 0 | ≤ 250 |
| CLINC150 | 151 | 0.5% | **81.9%** | ≈ 0 | ≤ 250 |

**Below the table:**

> Every benchmark crosses paired statistical significance at
> the **first** checkpoint. Two hundred and fifty labeled
> outcomes — two days of moderate production traffic, not six
> months. Reproducible: `dendra bench atis` regenerates
> Figure 1 in seconds.

CTA: **`Read the paper →`** [arXiv link].

---

## AUTORESEARCH HOOK

Anchor: `#autoresearch-hook`.

**Heading:** `The deployment substrate for your autoresearch loop.`
**Sub-heading:** `Generate candidates with whatever you've got. Dendra gates them.`

**Three-step diagram (visual, hand-drawn-feeling, NOT a flowchart):**

1. Your loop proposes a candidate (rule, prompt, ML head, gate threshold)
2. `CandidateHarness` shadows it against live production
3. Paired-McNemar verdict tells the loop: PROMOTE or HOLD

**Code beside the diagram:**

```python
from dendra import CandidateHarness, LearnedSwitch

sw = LearnedSwitch(rule=production_rule, ...)

harness = CandidateHarness(
    switch=sw,
    truth_oracle=labeled_validation_lookup,
    alpha=0.05,
)

# Autoresearch loop iteration:
candidate = autoresearch_agent.propose_next(sw.storage)
harness.register("v3", candidate)
harness.observe_batch(eval_traffic)
report = harness.evaluate("v3")

if report.recommend_promote:
    autoresearch_agent.commit_candidate(candidate)
```

**Below:**

> Every primitive an autoresearch loop needs. Already shipped:
> shadow phases, paired-McNemar gate, circuit breaker, audit
> chain, async committee judges, redaction hooks. The harness
> is the named seam.

CTA: **`See example 19 — the full loop →`** [GitHub link].

---

## SAFETY GUARANTEE

Anchor: `#safety-guarantee`.

**Heading:** `The rule floor cannot be removed.`
**Sub-heading:** `Architectural guarantee, paper §7.1.`

**Three-column callout:**

### Column 1 — Rule never leaves

In the highest-autonomy phase (`ML_PRIMARY`), the ML head
decides. The rule sits behind a circuit breaker. ML failure,
timeout, anomaly → breaker trips, rule takes over,
automatically.

### Column 2 — Construction-time refusal

Mark a switch `safety_critical=True` and Dendra refuses *at
construction time* to put it in any phase without a rule
fallback. Cannot be overridden without a code change reviewed
by humans.

### Column 3 — Audit chain

Every classification on tape. Rule output, LLM output, ML
output, verdict, timestamp, source. Operator actions on the
same chain. Pluggable redaction at the storage boundary for
HIPAA / PII / export-controlled workloads.

---

## PRICING TIERS

Anchor: `#pricing`.

**Heading:** `Pricing.`
**Sub-heading:** `OSS is fully usable in production. Hosted is when you don't want to run it yourself.`

**Three-tier card layout:**

### Free — `$0`

- Apache-2.0 client SDK, MIT-vibe license terms
- Self-host the analyzer (BSL 1.1 — production permitted, competing-hosted-service prohibited)
- Run all six lifecycle phases
- Run the paired-McNemar gate
- Community support (GitHub issues)
- Suitable for: hobbyists, OSS users, self-managed deployments

**[`pip install dendra` →]**

### Solo — `$29/mo`

Everything in Free, plus:

- We host the analyzer + dashboards
- Outcome-log persistence we run (no DB to manage)
- Email support
- Slack / email alerts on breaker trips
- Single workspace

**[`Join the hosted beta waitlist →`]**

### Team — `$99/mo per seat`

Everything in Solo, plus:

- Multi-user audit chain
- Compliance-ready CSV / JSON export
- 99.9% SLA
- Priority support
- Roles + permissions on operator actions

**[`Join the hosted beta waitlist →`]**

### Enterprise — `Contact us`

Everything in Team, plus:

- Self-hosted Dendra Cloud option
- Custom SLA
- Signed audit-chain integrity (HSM)
- Multi-user approval workflow on phase transitions
- Dedicated solutions engineer

**[`Email us →`] (mailto:enterprise@dendra.dev)**

---

## WAITLIST FORM

Anchor: `#waitlist`.

**Heading:** `Hosted beta — waitlist`
**Sub-heading:** `Wave 1 is OSS-only. Wave 2 (Q3 2026) ships the hosted analyzer + Solo / Team tiers. Tell us about your use case and we'll prioritize the rollout.`

**Form fields:**

- Email (required)
- Company / project name (required)
- One sentence: what would you classify with Dendra? (required, freeform, ~280 char limit)
- [Submit] button

**On submit:** thank-you state with two links:
- "Star us on GitHub for updates"
- "Read the paper while you wait"

---

## FAQ TEASER

Anchor: `#faq`.

**Heading:** `Quick questions.`
**Sub-heading:** `[Read the full FAQ →](https://docs.dendra.dev/faq)`

**Top 4 from FAQ.md, expanded inline as accordions:**

1. **Why is there a *rule*? Isn't the LLM supposed to replace it?**
2. **Is Dendra "machine learning"?**
3. **How is this different from AutoML?**
4. **How does this relate to Karpathy's autoresearch loop pattern?**

Each opens to its current FAQ.md answer, truncated at 200 words
with "Read more →" link to full version.

---

## FOOTER

**Three columns:**

### Product
- Docs
- Paper (arXiv)
- GitHub
- Pricing
- Hosted beta waitlist

### Company
- About B-Tree Ventures
- Contact
- Trademarks
- License (Apache 2.0 + BSL 1.1)

### Connect
- X / Twitter
- LinkedIn
- Email

**Bottom strip:** `© 2026 B-Tree Ventures, LLC.` · `Built in Austin, TX.` · `Apache-2.0 SDK · BSL-1.1 analyzer.`

---

## Build notes

### Visual

- Astro + Tailwind. Use the brand kit's existing palette
  (graphite primary, accent-orange secondary, ink-soft
  neutrals — see `brand/voice.md`).
- Hero typography: Space Grotesk display.
- Body: TeX Gyre Pagella for long-form, system-default for nav
  / forms.
- Logomark animation: import the existing
  `brand/logo/dendra-mark-animated.svg`. One-shot rising
  accent on first scroll into view.
- All page-internal anchor links smooth-scroll.

### Performance

- Astro static export means zero JS by default. Add
  `client:visible` only for the waitlist form.
- Image optimization: serve PNG via Astro's image component;
  Figure 1 should be served at 2× retina (1920px wide source
  → 960px display).
- Lighthouse target: > 95 on every category at launch.

### SEO

- `<title>`: "Dendra — when should a rule learn?"
- `<meta description>`: 155 chars. Draft: "Dendra is the
  graduated-autonomy classification primitive. Migrate
  production classifiers from rule to LLM to ML with
  paired-McNemar statistical gates and a rule safety floor.
  Open-source Python library + paper."
- `<meta og:image>`: existing `brand/dendra-github-social-preview.svg`
  (1280×640) per the brand kit.
- Canonical URL: `https://dendra.dev/`
- Schema.org JSON-LD: SoftwareApplication + ScholarlyArticle (the paper).

### Hosting + DNS

- Astro `astro build` → static `dist/`
- `firebase init hosting` → connect to Firebase project
- `firebase deploy --only hosting`
- GoDaddy DNS: add a CNAME `dendra.dev → <project>.web.app`
  per Firebase custom-domain instructions.
- Cost: $0/mo until traffic exceeds Firebase free tier
  (10 GB/mo egress, 1 GB stored). Wave 1 traffic stays well
  under both.

### Build pipeline (for launch-day readiness)

1. **Astro project init** → `npm create astro@latest` in a new
   `landing/` subdirectory of the repo (or its own repo —
   recommend its own repo so the SDK doesn't get static-asset
   noise in its commit history).
2. **Tailwind + brand kit setup** → import the palette CSS
   variables from `brand/colors.css`.
3. **Page sections** → one `.astro` component per section
   above; `index.astro` composes them.
4. **Waitlist form action** → posts to a Firebase Function
   that writes to Firestore. ~30 lines of code. **Or** use a
   third-party form service (Formspree, Tally) for Wave 1
   simplicity.
5. **Local preview** → `npm run dev`.
6. **Deploy** → `npm run build && firebase deploy`.
7. **DNS cutover** → CNAME flip on launch day after the
   site is live and verified at the `*.web.app` URL.

---

## Decisions Ben needs to make

1. **Which hero headline?** — A (paper-flavored, currently in
   the talk) or B (autoresearch-zeitgeist). My lean: **B for
   the page, A for the paper title.** Different audiences read
   each.
2. **Pricing — confirm $29 / $99/seat / contact-us tiers?** —
   matches what we discussed. Easy to revise later but pick a
   starting point so the page can ship.
3. **Waitlist form: Firebase Function + Firestore (own
   infrastructure) vs Formspree/Tally (third-party)?** — my
   lean: **third-party for Wave 1** (zero ops), migrate to own
   infrastructure for Wave 2 when we wire up Stripe + Clerk
   anyway.
4. **Repo structure: own `dendra-landing/` repo, or
   `landing/` directory inside `axiom-labs-os/dendra`?** — my
   lean: **own repo** (cleaner separation; landing-page
   commit noise doesn't bury library work).

Reply with answers and I'll start building Astro components.
The page can be live on staging in 2-3 days of focused work
once these are stamped.
