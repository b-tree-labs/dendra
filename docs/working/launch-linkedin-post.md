# LinkedIn launch post — single long-form

**Posting target:** Wed May 13, 9:30 AM CT (right after X
thread).
**Audience:** professional network. Skews more enterprise / ML
eng leadership / former Uber colleagues / academic-adjacent.
**Voice:** more reflective + framing-heavy than X. LinkedIn
audiences read paragraphs, not threads.

One draft. Paragraph-prose. No emojis.

---

After about a year of work, I'm releasing Dendra today.

Dendra is a Python library and an accompanying paper for a
problem I've watched teams in three different companies live
through: shipping a hand-written rule classifier in production,
watching it accumulate enough outcome data to be replaceable
with ML, and then never doing the migration because it's too
risky. The rule is legible — you can read it, argue about it
in code review, fix it on a Friday. The learned classifier is
a black box that might be better on average and quietly worse
on a long tail of cases your tests don't cover.

The library is a primitive for that migration. It wraps a
classifier and lets it graduate through six lifecycle phases —
hand-written rule, LLM in shadow, LLM in primary, ML in
shadow, ML with rule fallback, ML primary — with a paired
statistical gate at every transition (McNemar's exact-binomial
test on discordant pairs) and the original rule retained as a
circuit-breaker safety floor. Even at the highest-autonomy
phase, the rule is still in the system. A bad ML deploy trips
the breaker; the rule takes over automatically; an operator
investigates and resets when the dependency is healthy.

The paper measures the transition depth — how many labeled
outcomes you need before the learned classifier clears paired
statistical significance against the rule — across four public
benchmarks (ATIS, HWU64, Banking77, CLINC150). Every benchmark
clears at the first checkpoint. 250 outcomes. Two days of
moderate production traffic, not six months. The paired-McNemar
result is tighter than what the previous (unpaired)
methodology in the same literature delivers, and it's
methodologically cleaner — same test rows, two classifiers,
correct paired comparison.

There's a second story worth telling. The library ships
something called CandidateHarness, which I think will end up
being the more interesting piece. The autoresearch / agent-loop
pattern that's been getting a lot of public discussion lately
is great at generating candidate classifiers — new rules,
refined prompts, learned ML heads. It's terrible at deploying
them. The harness wraps a live classifier, lets an external
loop register candidates, shadows them against production
traffic, and returns paired-McNemar verdicts on whether each
candidate is statistically justified to promote. The
loop-in-production pattern in one library, with a rule safety
floor underneath the entire stack.

Three audiences I've designed for:

- Production ML engineers who have a rule and a "we should ML
  this" backlog ticket. The migration runtime is for you.
- Agent and autoresearch builders whose loops are generating
  good candidates and shipping them via duct tape. The
  CandidateHarness is for you.
- Compliance and regulated-industry teams (HIPAA-adjacent,
  export-control, audit-chain). The redaction hooks at the
  storage boundary, the audit chain, and the
  safety_critical=True architectural guarantee are for you.

The library is Apache 2.0 on the client SDK, BSL 1.1 on the
hosted analyzer (with production self-hosted use permitted —
only competing-hosted-service is restricted). The paper is on
arXiv. The repo is github.com/axiom-labs-os/dendra. The
landing page, with the paper, the docs, and a hosted-beta
waitlist, is at dendra.dev.

I'd love feedback. The launch is today; the thread on X has
the technical hook, the HN post has the methodology
discussion, and the GitHub issues are the fastest way to file
a bug or a feature request. I'm aiming to be present and
responsive all day.

If you've worked with me at Uber or before, this is what I've
been building since I left. If you've watched me write
production-ML safety patterns over coffee in Austin, you've
seen pieces of this. Thanks for the conversations along the
way.

— Ben

[Attach Figure 1 — the transition-curves PNG]

[Link: dendra.dev]

---

## Format / engagement notes

- LinkedIn surfaces longer posts well; don't compress this
  into a 3-paragraph tease. Full ~600 words is fine.
- Don't include hashtags. LinkedIn hashtags signal recruiter-
  spam; the audience for this is allergic.
- Comment on the post within 30 minutes with a single
  follow-up: "Happy to answer questions in the comments —
  here or in the GitHub issues."
- Re-share once at end of day if engagement is good ("Thanks
  for the response on this morning's launch — here's what
  happened today: HN thread, X thread, repo at X stars, paper
  at Y reads"). Skip if engagement is flat.
- Tag @ B-Tree Ventures (the company page). Don't tag former
  employers — feels like leveraging.

## Engagement targets

- Ideal: 1,000 impressions / 50 reactions / 10 comments / 5
  shares. Indicates the network is interested.
- Floor: 200 impressions / 10 reactions. Below this, LinkedIn
  isn't reaching the audience and the launch energy is
  elsewhere.
- Ceiling: a former colleague reposts to a senior-leadership
  network. Gold for Wave 2 lead generation.
