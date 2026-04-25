# X / Twitter launch thread — drafts

**Posting target:** Wed May 13, 9:30 AM CT (right after the HN
post lands).
**Voice:** technical-founder. No hashtag spam, no thread-emojis
(🚀 etc.), no "stop scrolling," no "10 things I learned."

Two thread drafts mirroring the HN headline candidates. Pick
the same letter as the HN post for consistency.

---

## Thread A — paper-flavored

**Tweet 1 (the hook):**

> 6 months after you ship a hand-written rule classifier in
> production, the backlog has a ticket that says "we should ML
> this." It doesn't move because the migration is risky.
>
> I'm releasing Dendra today. A primitive for that migration.
> Here's what's in it ↓

**Tweet 2 (the contribution):**

> Dendra wraps a classifier and lets it graduate through 6
> phases: rule → LLM-shadow → LLM → ML-shadow → ML.
>
> Paired-McNemar statistical gate at every phase transition.
> The original rule stays as the safety floor — even at the
> highest-autonomy phase, behind a circuit breaker.

**Tweet 3 (the headline result):**

> Paper measures *transition depth* — how many labeled
> outcomes before ML clears statistical significance against
> the rule.
>
> Across ATIS / HWU64 / Banking77 / CLINC150:
> **every benchmark crosses paired McNemar at the FIRST
> checkpoint. 250 outcomes.**
>
> Two days, not six months.

[Attach Figure 1 — the transition-curves PNG]

**Tweet 4 (the autoresearch hook):**

> Bonus: the library ships a `CandidateHarness` that lets an
> autoresearch loop register candidate classifiers, shadow
> them against production, and get paired-McNemar verdicts
> on whether each beats the live decision.
>
> Autoresearch tells you what to try.
> Dendra tells you when it worked.

**Tweet 5 (proof + call to action):**

> 473 tests. 33 µs p50 classify on the production-recommended
> persist=True path. Native async API. Apache 2.0 on the SDK.
>
> 📦 `pip install dendra`
> 📄 Paper: [arXiv link]
> 🐙 GitHub: github.com/axiom-labs-os/dendra
> 🌐 dendra.dev

**Tweet 6 (optional — depending on engagement):**

> If you build something with this, I want to see it. GitHub
> issues are the fastest way to reach me.
>
> [HN thread link]

---

## Thread B — autoresearch-zeitgeist

**Tweet 1 (the hook):**

> Your autoresearch loop is great at *generating* candidate
> classifiers.
>
> Your *deployment* story is duct tape.
>
> I'm releasing Dendra today — the production substrate that
> fills the gap. Here's how it works ↓

**Tweet 2 (the substrate framing):**

> The dirty secret of LLM-driven autoresearch is the last
> mile: you've got a candidate that looks great on the eval
> set and no infrastructure to test it under live load with
> statistical confidence + a rule safety floor.
>
> Dendra is that infrastructure.

**Tweet 3 (the harness API):**

> ```py
> from dendra import CandidateHarness
>
> harness = CandidateHarness(switch=production, truth_oracle=truth)
>
> harness.register("v3", autoresearch_agent.propose())
> harness.observe_batch(traffic)
> report = harness.evaluate("v3")
>
> if report.recommend_promote:
>     deploy(candidate)
> ```

**Tweet 4 (what's behind the harness):**

> Paired McNemar p-value on discordant pairs against your
> truth oracle.
> Configurable α (we default 0.05).
> The underlying switch's rule safety floor protects production
> from the loop's bad proposals throughout.
>
> Every primitive your loop needs, in one library.

**Tweet 5 (the paper):**

> There's also a paper anchoring the statistical machinery.
>
> Across 4 NLU benchmarks (ATIS / HWU64 / Banking77 /
> CLINC150), every classifier crosses paired McNemar
> significance at 250 labeled outcomes. Tightest transition
> depth in the literature, paired-test, p < 0.01 throughout.

[Attach Figure 1]

**Tweet 6 (proof + call to action):**

> Apache 2.0 SDK. 473 tests. Native async. 33 µs classify p50.
>
> 📦 `pip install dendra`
> 📄 Paper: [arXiv link]
> 🐙 GitHub: github.com/axiom-labs-os/dendra
> 🌐 dendra.dev

**Tweet 7 (optional — if Karpathy framing feels right):**

> H/T to @karpathy whose autoresearch posts crystallized the
> framing. Dendra is the production substrate — the
> deployment companion to whatever your loop is generating.

---

## Mentions / replies-to / quote-of decisions

- **Tag @karpathy?** Only on Thread B, only on the optional
  Tweet 7. Wouldn't tag in the opening — looks sycophantic.
- **Tag @lingjiaochen** (FrugalGPT)? Only after Lingjiao has
  acknowledged via the FYI email, not in the launch thread.
- **Tag @lmsysorg / @ion_stoica** (RouteLLM)? Same logic —
  acknowledge after they engage, not preemptively.
- **Quote-tweet relevant work?** Yes, post-launch, if good
  conversations emerge. Don't preemptively. The thread should
  stand alone for the first few hours.

---

## Engagement plan during the day

- Reply to every quote-tweet with substance (not "thanks!")
- Pin the thread to your profile
- Don't subtweet HN comments — engage in HN
- If a thread takes off (>5,000 impressions in the first hour),
  draft a follow-up tweet with the most-asked question + answer
  — pin it as a reply
- DM thoughtful tweets with "would you like a 30-min product
  call?" if they look like prospects (Wave 2 lead capture)

---

## What NOT to post

- Don't post screenshots of the GitHub stars graph during the
  day. Mid-launch metrics are noise.
- Don't post about competitors directly.
- Don't ratio-bait. If a critic shows up, address the technical
  point or move on.
- Don't post a "thank you" tweet at end-of-day on launch day —
  do that the next morning when you have actual numbers.
