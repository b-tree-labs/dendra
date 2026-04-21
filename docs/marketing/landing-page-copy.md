# Dendra — Landing Page Copy

**Target URL:** `dendra.dev`
**Purpose:** single-page developer-first site. Code above copy.
**Stack recommendation:** plain HTML/CSS or Astro / Next.js static
build. Deploy to Cloudflare Pages or Vercel. Zero JS beyond a code-
copy button is ideal.

---

## Hero section

### Headline (H1)

> **The classification primitive every production codebase is missing.**

### Sub-headline

> When should your rule learn? Dendra's six-phase graduated-autonomy
> primitive answers it with a p-value — and a safety floor that
> survives jailbreaks, silent ML failures, and unbounded token
> bills.

### Primary CTA (install command + button)

```bash
pip install dendra
```

**[Get started →]** (button linking to Quickstart in docs)

### Secondary links

**[Read the paper →]** (arXiv)   **[See the code →]** (GitHub)   **[Pricing →]** (anchor)

---

## Proof row (below hero, above fold)

One-line stats in a 4-column grid:

- **6 phases** from rule to ML, statistically gated
- **0.6 µs** switch overhead (sub-microsecond decision path)
- **4 public benchmarks** with measured transition curves
- **Apache 2.0** open source, patent-pending

---

## Code-first section (the thing to copy)

### Heading

> **Wrap your classifier. Ship outcomes. Graduate when evidence earns it.**

### Code block (the hero code)

```python
from dendra import ml_switch, Phase, SwitchConfig

@ml_switch(
    labels=["bug", "feature_request", "question"],
    author="@triage:support",
    config=SwitchConfig(phase=Phase.RULE),
)
def triage(ticket):
    title = ticket.get("title", "").lower()
    if "crash" in title:
        return "bug"
    if title.endswith("?"):
        return "question"
    return "feature_request"
```

### Caption under the code

> Zero behavior change on day one. Dendra logs every outcome. When
> your evidence crosses the statistical gate, advance the phase and
> the LLM or ML head takes over — with the rule always available as
> the safety floor.

---

## Three-pillar explainer (3-column grid)

### Pillar 1 — Bounded risk

Icon: shield / floor line

> **The rule is always the safety floor.** A paired-proportion
> hypothesis test gates every phase transition. The probability that
> any graduation produces worse-than-rule behavior is bounded above
> by the test's Type-I error rate. Verified on four public
> benchmarks at p < 0.01.

### Pillar 2 — Cut token cost

Icon: dollar / chart-down

> **Route 80% through your rule. Pay LLM tokens on 20%.** At 100M
> classifications/month with a Sonnet-class model, the LLM-only
> spend is $11.5M/yr. Dendra's Phase-4 routing drops this to
> essentially zero while preserving the LLM's judgment on hard
> cases.

### Pillar 3 — Survives jailbreaks

Icon: lock / circuit breaker

> **20-pattern jailbreak corpus: 100% rule-floor preserved.**
> Prompt injection cannot change what a compiled rule returns. The
> LLM runs in shadow. Safety-critical classifiers are capped at
> Phase 4 — no ML-primary for authorization decisions, ever.

---

## Measured results section

### Headline

> **Four public benchmarks. Transition depths measured at p < 0.01.**

### Figure

Display Figure 1 (the 4-panel transition-curve plot from the
paper results directory):
`docs/papers/2026-when-should-a-rule-learn/results/figure-1-transition-curves.png`

### Caption

> Banking77, CLINC150, HWU64, ATIS — all four measured, all four
> show ML overtaking the rule by the first checkpoint with
> statistical significance. **Two regimes emerge:** narrow-domain
> rules stay viable for years (ATIS, ~70% rule floor), high-
> cardinality rules are non-starters (CLINC150, 0.5% rule floor —
> you need Dendra's outcome-log to ever ship ML at all).

### Secondary stat row

- **ATIS transition depth:** ≤ 250 outcomes (narrow domain)
- **CLINC150 transition depth:** ≤ 1,500 outcomes (151 labels)
- **Gap from rule → ML:** +19 pp (ATIS) to +82 pp (Banking77)

**[See the paper →]** **[Reproduce the results →]** (link to `dendra bench`)

---

## Analyzer CTA section

### Headline

> **Find the classifiers in your codebase. Free. 30 seconds.**

### Code block

```bash
dendra analyze ./my-repo
```

### Copy

> Runs entirely locally. No upload. No signup. Walks your Python
> source, identifies classification decision points via six AST
> patterns, scores each for Dendra-fit, and outputs a JSON
> artifact for CI diff tracking.

```
Scanned 12,408 Python files; found 7 classification sites.
  src/support/triage.py:42  — 5 labels, medium cardinality
    Dendra-fit: 4.5/5
    Regime: narrow-domain rule-viable
    ...
```

**[Get the analyzer →]** (install command)

---

## Pricing section

### Headline

> **Volume-based pricing. No per-seat fees. Free forever for the
> library.**

### Tier table

| Tier | Price | Classifications/mo |
|---|---|---:|
| **OSS library** | Free | unlimited (self-hosted) |
| **Free hosted** | **$0** | 10,000 |
| **Solo** | **$19/mo** | 100,000 |
| **Team** | **$99/mo** | 1,000,000 |
| **Pro** | **$499/mo** | 10,000,000 |
| **Scale** | **$2,499/mo** | 100,000,000 |
| **Metered** | $0.01/1k above Scale | unlimited |
| **Enterprise** | Custom | Custom |

### Copy

> Every paid tier has a published price. No "contact us" gating
> below Enterprise. Volume-priced so adding another classifier
> doesn't cost you another seat. Cancel anytime.

**[See full pricing →]** (link to docs pricing page with gross-margin breakdown)

---

## Who's it for (quick list)

Categories where Dendra has measurable impact today:

- **Customer-support triage** (bug/feature/question/escalation)
- **Chatbot intent routing**
- **LLM output moderation / PII filtering** (safety-critical)
- **Fraud and anomaly triage**
- **SOC alert classification**
- **Content moderation**
- **Clinical coding** (ICD-10, CPT)
- **RAG retrieval-strategy selection**
- **Agent tool routing**

**[See all 13 categories →]** (link to industry-applicability.md)

---

## Agent-first install section

### Headline

> **Your AI coding assistant already knows how to install Dendra.**

### Copy

> Dendra ships a SKILL.md that Claude Code, Cursor, and Copilot
> Workspaces can load as context. Just ask:
>
> *"Add Dendra to the triage function in src/support/triage.py."*
>
> Your assistant will wrap the function, add the import, infer the
> labels, and leave a minimal, reviewable diff.

### Code block

```bash
dendra init src/support/triage.py:triage --author "@you:team"
```

### Caption

> `dendra init` is the deterministic CLI path that skips the
> LLM's risk of hallucinating decorator syntax. Your agent should
> reach for it by default.

---

## About / trust section (footer-ish)

### Short paragraph

> Dendra is built and maintained by **Axiom Labs** (a B-Tree
> Ventures LLC DBA). The reference implementation is Apache 2.0.
> The underlying primitive is covered by a filed provisional
> patent (USPTO application pending). Paper submission targets
> NeurIPS 2026.

### Contact

- **GitHub:** [github.com/axiom-labs-os/dendra](https://github.com/axiom-labs-os/dendra)
- **Paper:** [arxiv.org/abs/...](https://arxiv.org) *(post-submission)*
- **Email:** `ben@b-treeventures.com`
- **X / Bluesky:** *[pick one]*

### Legal footer

*Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0
license on reference code. "Dendra," "Transition Curves," and
"Axiom Labs" are trademarks of B-Tree Ventures, LLC.*

---

## Design notes

- **Visual style:** paper-white background, black-and-white Figure 1
  as hero visual, monospace for every code block. Emulate the
  Temporal / Clerk / Tailscale landing pages — quiet technical.
- **No animation** beyond hover states on CTAs.
- **No logos from prospective customers** until they've signed
  on publicly.
- **No "free trial" language** — use "Get started" pointing at the
  free tier.
- **Mobile-first:** the code blocks should render readably on
  phones. Use `overflow-x: auto` on `<pre>` blocks.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Apache-2.0 licensed. Copy deck for public site; copy freely when
building the HTML._
