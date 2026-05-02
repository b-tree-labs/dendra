# Dendra · voice and tone

How Dendra talks. What the product sounds like in docs, marketing,
support, error messages, and code comments. If the mark is the
visual identity, this is the verbal one.

## The axis

**Technical, measured, quiet.** Dendra is built by engineers for
engineers. It never oversells. It shows, then explains. It is
specific, bounded, and honest about what it does not do.

Three tone coordinates:

- **Technical** (not academic, not casual) — domain-correct
  vocabulary; specific numbers over generalities; code above
  prose where code will do.
- **Measured** (not bold, not cautious) — claims are bounded by
  evidence. When we say "bounded by α," we cite the theorem.
  When we say "tested," we cite the corpus.
- **Quiet** (not loud, not whispering) — no exclamation points,
  no superlatives, no hype words. The work is interesting enough
  without adjectives.

Think: the documentation of a serious infrastructure primitive
written by someone who would be embarrassed to overstate.

## Words to use

- *bounded, bound, bound above by, bound below by*
- *measured, measurement, measured at p < 0.01*
- *evidence, outcome, outcome record, paired outcome*
- *gate, threshold, crossing, passes*
- *earn, earned, graduate, graduation, advance, advancement*
- *rule, rule floor, safety floor, fallback*
- *classify, classification, classifier, classification site*
- *phase, phase transition, lifecycle*
- *specific, concrete, bounded*
- *primitive* (Dendra is a primitive, not a platform)

## Words to avoid

The AI-startup-hype vocabulary that makes the brand look like
anyone else in the category. If a word feels familiar from Scale /
Adept / Cohere / Writer / Glean marketing, it's probably on this
list.

- *revolutionary, game-changing, transformative, paradigm-shifting*
- *cutting-edge, state-of-the-art, best-in-class, world-class*
- *AI-powered, ML-powered, intelligent, smart* (as standalone
  adjectives for Dendra itself — Dendra *uses* ML; it isn't
  vaguely "intelligent")
- *seamless, frictionless, magical, effortless*
- *unleash, unlock, empower, supercharge*
- *reimagine, reinvent, revolutionize*
- *delight, delighted, delightful*
- *low-code, no-code* (Dendra is code; embrace that)
- *turnkey, out-of-the-box* (overused, tell what's actually
  configurable)
- *leverage* (use "use")
- *utilize* (use "use")
- *enablement* (use "enable")
- *solution* (use what the thing actually is)
- *synergy, ecosystem, disruption, pivot*

## Sentence shape

- **Short before long.** One idea per sentence. Break up compound
  claims. Subject-verb-object; active voice.
- **Numbers over adjectives.** "1.00 µs p50 at Phase.RULE" not "lightning fast."
  "4.3:1" not "plenty of contrast." "four benchmarks at p < 0.01"
  not "rigorously tested."
- **Examples over explanations.** A six-line code block usually
  does the job of a six-paragraph explanation.
- **Verbs at the front.** "Wrap your classifier." "Record
  outcomes." "Advance the phase." Not "You can wrap …" or
  "Wrapping your classifier is the first step."
- **Footnote the hedges.** If something has a limitation, state
  it crisply. Don't bury it. Don't overstate it either.

## Person and voice

- **Second person** for instructions. "Wrap your classifier," not
  "The user wraps a classifier."
- **First person plural** ("we") for Dendra/B-Tree Labs claims.
  "We measured this on four benchmarks," not "Dendra was measured
  on four benchmarks" (passive) or "I measured this" (too
  personal). Reserve "I" for author blog posts only.
- **Third person** for the product in reference docs. "`ml_switch`
  returns a `ClassificationResult`," not "We return a `ClassificationResult`."

## On the primitive framing

Dendra is a **primitive**, not a platform, suite, or product
family. Language that reinforces this:

- "A primitive for X" not "a platform that does X"
- "One decorator" not "a family of APIs"
- "Six phases" not "a fully-featured phase system"
- "Wrapped" not "integrated"
- "Ships" not "launches" or "releases" (except for actual release
  announcements)

## On the theorem

When discussing the statistical guarantee, always state the bound,
always name the test, never overclaim:

- **Correct:** "The probability of worse-than-rule behavior at
  any transition is bounded above by the paired-proportion test's
  Type-I error rate α."
- **Incorrect:** "Dendra guarantees safety." (Bound is
  probabilistic; "guarantees" is wrong.)
- **Also incorrect:** "Dendra reduces risk." (Not specific.)

## On safety

Safety claims are the highest-integrity claims Dendra makes.
They are load-bearing for enterprise procurement.

- Use "safety floor" for the rule-as-architectural-guarantee.
- Use "safety-critical" for the `safety_critical=True` flag.
- Do not confuse "safety" (about the floor) with "reliability" or
  "robustness" (adjacent but distinct).
- The jailbreak + PII corpora have specific numbers (100% / 100%);
  always cite the numbers, never say "high" or "strong."

## On competitors

**No naming.** The `entry-with-end-in-mind.md` §4 rule: Dendra
does not name competitors in marketing, never says "better than
X," never posts comparison charts. Indirect framing only.

- **Correct:** "Unlike pure-LLM architectures, Dendra retains the
  rule as safety floor." (Frames by architecture, not by company.)
- **Incorrect:** "Unlike LangChain, Dendra …" (Names a company.)
- **Also incorrect:** "Other classifier libraries have drifted
  from their rules." (Vague dig — worse than nothing.)

## Error messages

Dendra error messages are short, specific, and actionable. They
name the thing that went wrong and what the caller should do.

- **Correct:** `safety_critical switches cannot start in
  ML_PRIMARY; cap at ML_WITH_FALLBACK (paper §7.1).`
- **Too apologetic:** `Sorry, this operation isn't supported in
  safety-critical mode.`
- **Too abstract:** `Invalid configuration.`
- **Too chatty:** `Dendra could not construct your switch because
  you specified safety_critical=True in combination with
  Phase.ML_PRIMARY, but this combination is disallowed because…`

## Documentation structure

- Docs lead with a **minimal running example** before explaining
  anything.
- Concepts are introduced **as they're needed**, not in a
  glossary-first doc.
- The **README is the landing page for the repo** and should read
  like a primitive's docs, not like a marketing site.
- **Three audiences, three places** (future state):
  `docs/` for end users, `docs/papers/` for research, internal
  scratch on disk only (gitignored). Keep them separate.

## Customer support

When responding to issues, questions, or community posts, the
same voice rules apply — technical, measured, quiet. Plus:

- **Acknowledge before you correct.** If the user is wrong about
  something, state what they've got right before explaining the
  correction.
- **Prefer pointing to docs or code over explaining from
  scratch** — but when pointing, also give the one-sentence
  summary so the pointer isn't a cop-out.
- **No "sorry."** Acknowledge the problem, fix it. Unless we
  actually did something that wronged the user, "sorry" reads as
  hollow customer-support script.
- **Close the loop.** If a bug is filed, update the ticket when
  it's fixed; don't leave the reporter wondering.

## Signing off

Internal docs and commit messages are signed:

- Commit trailers: `Co-Authored-By:` for AI / pair programming.
  `Signed-off-by:` per DCO for every non-bot commit.
- Public-facing content (blog, landing, paper) is attributed to
  **Dendra** or **B-Tree Labs** as appropriate. Individual
  attribution (Benjamin Booth as author) appears in the paper,
  patent filings, and select first-person blog posts only.

## When in doubt

Read three paragraphs of your draft. If it could have been
written by a SaaS marketing team, rewrite until it couldn't.
