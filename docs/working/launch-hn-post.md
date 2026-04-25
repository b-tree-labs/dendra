# HN launch post — drafts (A and B)

Two headline candidates per the v1-readiness D8 decision. Pick
one on May 12 (T-1 day). Body is identical between drafts; only
the title and the opening hook differ.

**Posting time target:** 7:30–8:30 AM CT (Wed May 13).
**Submission URL:** `https://dendra.dev/` (the landing page).

---

## Draft A — paper-flavored headline

### Title

> **Show HN: Dendra — When should a rule learn? A statistical framework for graduated ML autonomy**

### Body

Hi HN,

I've been working on a problem that I think most teams running
production classifiers have lived: you ship a hand-written
rule, it works, six months pass, and the backlog acquires a
ticket that says "we should ML this." The ticket doesn't move
because replacing the rule is one of the highest-risk
migrations you can do in a production system.

Dendra is a primitive for that migration. A Python library
(`pip install dendra`) that wraps a classifier and lets it
graduate through six lifecycle phases — rule → LLM-shadow →
LLM → ML-shadow → ML — with a paired-McNemar statistical gate
at every transition and the original rule retained as a safety
floor with a circuit breaker.

The accompanying paper measures transition-depth across four
public NLU benchmarks (ATIS, HWU64, Banking77, CLINC150).
Headline result: **every benchmark crosses paired statistical
significance at the first checkpoint — 250 labeled outcomes**
— against a hand-written keyword rule. ML accuracy ranges from
83.6% (HWU64) to 88.7% (ATIS); the rule never goes above 70%.

Three things I think are interesting:

1. **The rule never leaves.** Even at the highest-autonomy
   phase (ML decides every call), the rule sits behind a
   circuit breaker that automatically reverts on ML failure.
   A `safety_critical=True` flag refuses construction in a
   no-rule-fallback phase.

2. **It composes with autoresearch loops.** The library ships
   a `CandidateHarness` that wraps a live switch and lets an
   external loop (LLM agent, A/B harness, human researcher)
   propose candidate classifiers, shadow them against
   production traffic, and get paired-McNemar verdicts on
   whether each candidate beats the live decision. The
   one-line mental model: *autoresearch tells you what to
   try; Dendra tells you when it worked.*

3. **The deployment story is real.** `persist=True` ships a
   batched FileStorage that drains every 50 ms; classify p50
   is ~33 µs on the production-recommendation path. There's a
   redaction hook at the storage boundary for HIPAA / PII
   workloads. Native async API with `aclassify` /
   `LLMCommitteeSource.ajudge` running judges in parallel via
   `asyncio.gather`.

The library is Apache 2.0 (the SDK) + BSL 1.1 (the analyzer/
server, with production self-hosted use permitted; no
competing-hosted-service). The paper is on arXiv: [link].
Repo: `axiom-labs-os/dendra`. Landing page (with paper, docs,
hosted-beta waitlist): `https://dendra.dev`.

I'd love feedback on:

- The "rule should keep learning" framing vs the academic ML
  literature on online learning + cascade routing (FrugalGPT,
  RouteLLM lineage; differentiation in §2 of the paper)
- Whether the autoresearch / `CandidateHarness` integration
  story lands or feels forced
- Real production scenarios where you'd want a graduated-
  autonomy classifier and the existing primitives don't fit

Happy to answer questions.

— Ben Booth (B-Tree Ventures, Austin)

---

## Draft B — autoresearch-zeitgeist headline

### Title

> **Show HN: Dendra — autoresearch tells you what to try; Dendra tells you when it worked**

### Body

Hi HN,

The autoresearch / agent-loop pattern is great at *generating*
candidate classifiers — new rules, refined prompts, learned ML
heads. The dirty secret is that nobody's solved the *deployment*
side: you've got a candidate that looks great on the eval set,
and now you're staring at production traffic with no
infrastructure to test it under real load with statistical
confidence and a rollback path that survives the candidate
going wrong.

Dendra is the production substrate that fills that gap. A
Python library (`pip install dendra`) that gives you:

- A `LearnedSwitch` primitive that wraps a classifier and lets
  it graduate from rule → LLM → ML over six lifecycle phases,
  with a paired-McNemar statistical gate at every transition
  and the rule retained as a safety floor (with a circuit
  breaker that auto-reverts on ML failure).
- A `CandidateHarness` that wraps a live switch, lets an
  external loop register candidate classifiers, shadows them
  against production traffic, runs paired-McNemar significance
  tests against a truth oracle, and tells the loop whether
  each candidate is statistically justified to promote.

The autoresearch loop reads `report.recommend_promote`; the
rule floor protects production from the loop's bad proposals
throughout. The harness ships in v1.

There's also a paper (on arXiv: [link]) measuring transition
depth across four public NLU benchmarks. Headline result: every
benchmark crosses paired statistical significance at the first
checkpoint — 250 labeled outcomes. Two days of moderate
production traffic, not six months.

A few things I think are interesting:

1. **Every primitive an autoresearch loop needs lines up with
   what the library already shipped for the rule-to-ML
   migration story.** Shadow phases. McNemar gate. Circuit
   breaker. Audit chain. Async committee judges. Redaction
   hooks. The harness is a thin orchestrator on top of
   primitives that already existed — that's a clue that the
   integration is real, not hand-wavy.

2. **The harness deliberately doesn't modify the switch.**
   Candidates run alongside production, never instead of.
   Promoting a winning candidate stays the loop's call,
   gated by your normal deployment process. The harness's
   job is to tell the loop *when* the swap is justified, not
   to perform it.

3. **The deployment story is real.** `persist=True` ships a
   batched FileStorage at ~33 µs classify p50. Redaction
   hook at the storage boundary for HIPAA / PII workloads.
   Native async API with `aclassify` and committee judging
   via `asyncio.gather`.

License is Apache 2.0 SDK + BSL 1.1 analyzer (production self-
hosted use permitted; no competing-hosted-service). Repo:
`axiom-labs-os/dendra`. Landing page (with paper, docs, hosted-
beta waitlist): `https://dendra.dev`.

I'd love feedback on:

- Whether the substrate framing matches what you've duct-taped
  around your own autoresearch / agent loops
- The McNemar gate as a promotion bar — is the alpha=0.05
  default right, or should the default be tighter?
- Real production scenarios where the loop generates great
  candidates and the deployment story is the bottleneck

Happy to answer questions.

— Ben Booth (B-Tree Ventures, Austin)

---

## Side-by-side comparison

| | A (paper-flavored) | B (autoresearch-zeitgeist) |
|---|---|---|
| **Hook** | "We have a backlog ticket" | "Autoresearch's deployment problem" |
| **Lead audience** | Production ML engineers | Agent / autoresearch builders |
| **Best HN thread shape** | Technical / methods discussion | Product / positioning discussion |
| **Risk** | Could read as "yet another MLOps tool" | Could read as bandwagoning the autoresearch buzz |
| **Defense** | Paper does the heavy lifting | The harness + example 19 do the heavy lifting |
| **Karpathy mention** | None (clean) | Tag @karpathy on the X thread (not HN) — or skip entirely |

## My recommendation

**B for HN.** The autoresearch zeitgeist is *current*, the
slam-dunk integration is novel, and the audience that votes
on HN is closer to "agentic systems builder" than "MLOps
practitioner" right now. A would have been the right call in
2023. B is the right call in May 2026.

Use A as the **paper title** (which is what cs.LG readers see)
and B as the **HN title** (which is what HN readers see).
Different audiences; different best-frame.

---

## Comments-pre-draft (anticipated questions + answers)

When you're sitting at the keyboard at 9:30 AM watching the
thread, expect these questions. Pre-thinking your answers
makes you 3× faster:

### "How is this different from FrugalGPT / RouteLLM?"

Those operate at *inference time*: given a query, pick which
LLM to route to. Dendra operates at *deployment time*: given a
production classifier, pick when to graduate it from rule to
LLM to ML. Different problem. We cite Chen et al. 2023 and Ong
et al. 2024 in §2 — they're directly upstream.

### "Is this just AutoML?"

No. AutoML automates **offline** model selection on a labeled
dataset. Dendra automates **online** model promotion against
live production traffic, with a statistical gate and a rule
safety floor. They compose: AutoML produces candidates, Dendra
deploys them. (FAQ has a longer answer.)

### "Why McNemar specifically?"

Paired correctness on the same test rows, exact-binomial
two-sided p-value on discordant pairs, non-parametric, robust
to base-rate skew. Dietterich 1998 recommends it for the case
where you can only evaluate classifiers once on a single test
set — which is exactly the online case. The library's `Gate`
protocol means you can swap it for any other test (we ship
`AccuracyMarginGate`, `MinVolumeGate`, `CompositeGate`,
`ManualGate` for operator approval).

### "What about the rule being silently wrong?"

Real concern. The rule floor isn't a guarantee that the rule
is *correct* — it's a guarantee that the system doesn't fall
*below* the rule's behavior when ML graduates fail. If the
rule is wrong, the user-visible decision is wrong, and ML
accuracy is measured against that. The paper §7 calls this
out; we recommend a labeled-validation set as the truth oracle
in `CandidateHarness` exactly because it lets you catch
"rule is wrong about reality" cases.

### "Why Apache + BSL split?"

Apache 2.0 on the SDK because we want maximum adoption — every
production system can `pip install dendra` and use the library
forever, free, no strings. BSL 1.1 on the analyzer/server so
that we can sustainably operate the hosted version without
someone else cloning Dendra Cloud as a competitor. Production
self-hosted use of the analyzer is *permitted by the
license* — only competing-hosted-service is prohibited.

### "What happens at scale?"

Single-process: 1.9M classify ops/sec at Phase 0 with
auto_record=False. With persist=True (batched FileStorage),
~30k ops/sec. Async API for FastAPI / LangGraph. Storage
backends are pluggable; SqliteStorage gets WAL mode for
multi-process. v1.1 brings async-native storage backends and
PostgresStorage. (See `docs/storage-backends.md`.)

### "Why are you releasing the paper and the library together?"

The paper and the library are the same thing — the paper *is*
the library's behavioral contract, and the library *is* the
paper's reference implementation. Releasing one without the
other is half a contribution. Reviewers can verify any claim
by running the benchmark harness; readers can adopt any
pattern by `pip install`.

### "Who are you?"

Ben Booth. Bootstrapped solo founder at B-Tree Ventures,
Austin. Previously did internal-tools / workforce-software
work at Uber. The provisional patent on the
graduated-autonomy primitive was filed 2026-04-21 with a
clean B-Tree Ventures provenance chain. The library and paper
are the public face of the same work.

---

## Comments-DON'T-make list

- Don't promise features ("v1.1 will have X" is fine; "we'll
  add X tomorrow" is a trap)
- Don't engage with bad-faith critics — let HN moderate
- Don't compare to specific competitors by name unless asked
  directly; if asked, be honest and brief
- Don't use the word "leverage" or "empower" anywhere
- Don't link to your pricing page in the HN body — let it sit
  one click away on the landing page
