# Reviewer outreach — launch-day FYI emails

**Sending target:** Wed May 13, ~9:45 AM CT (after HN + X +
LinkedIn are live).
**Tone:** "FYI, here's relevant work, no obligation." NOT
"please review this on a deadline." We're signaling, not
asking.
**Length cap:** 150 words per email. Anything longer is asking
for too much.
**Subject lines:** specific, low-friction. Avoid "Show HN-style"
energy.

Two drafts in this doc — for **Hamel Husain** and **Lingjiao Chen**
(the original "free roll" picks). If the Cowork reviewer-list
output surfaces other names you want to send to, I'll draft
each one in the same shape; drop the name + their public-page
URL and any context (mutual connection, prior interaction).

---

## Draft 1 — Lingjiao Chen (FrugalGPT author)

**To:** lingjiao@stanford.edu (or current MSR address — verify
on his lab page)
**Subject:** FrugalGPT lineage — paper + library released today
**Send time:** 9:45 AM CT, May 13

Hi Lingjiao,

I released a paper + Python library this morning that's
explicitly downstream of your FrugalGPT work. The framing:
where FrugalGPT operates at inference time (which model do I
route this query to), the paper extends the cascade pattern to
*deployment time* — when does a hand-written production rule
graduate to LLM, and when does the LLM graduate to a learned
ML head. Six lifecycle phases, paired-McNemar gate at each
transition, the rule retained as a circuit-breaker floor.

Headline result: across ATIS / HWU64 / Banking77 / CLINC150,
every benchmark clears paired McNemar at 250 labeled outcomes.

Paper: [arXiv link]
Library: pip install dendra
Repo: github.com/axiom-labs-os/dendra

No need to respond — just wanted you to see the work given
the lineage. If you have time and the framing lands, I'd love
your thoughts.

— Ben Booth (B-Tree Ventures, Austin)

---

## Draft 2 — Hamel Husain (eval consultant + practitioner)

**To:** hamel.husain@gmail.com (or his current contact —
verify on hamel.dev)
**Subject:** Production substrate for autoresearch loops — released today
**Send time:** 9:45 AM CT, May 13

Hi Hamel,

I shipped a Python library this morning called Dendra that I
think hits some of the eval / production-deployment patterns
you write about. The hook: most autoresearch / agent loops
generate good candidate classifiers and ship them via duct
tape. The library is the production substrate — wraps a live
classifier, lets a loop register candidates, shadows them
against real traffic, returns paired-McNemar verdicts on
whether each candidate beats the live decision.

There's a paper anchoring the statistical machinery (paired
McNemar across 4 NLU benchmarks) and a CandidateHarness API
that I think is the differentiating piece.

Library: pip install dendra
Repo: github.com/axiom-labs-os/dendra
Landing: dendra.dev

No response needed — wanted to put it on your radar given how
much of your writing is about the production-eval gap. If you
end up looking at it and find something off, GitHub issues are
the fastest channel back to me.

— Ben Booth (B-Tree Ventures, Austin)

---

## Draft 3 (template) — for Cowork-list approvals

**To:** [verified email]
**Subject:** [their work] — paper + library released today
**Send time:** 9:45 AM CT, May 13

Hi [first name],

I released a paper + Python library this morning that I think
connects to [their specific paper / area / blog post]. The
framing: [one-sentence Dendra summary tailored to their angle].

Headline result: every benchmark in the paper crosses paired
McNemar significance at 250 labeled outcomes — tighter than
the unpaired-test result in the same literature.

Paper: [arXiv link]
Library: pip install dendra
Repo: github.com/axiom-labs-os/dendra

No need to respond — just wanted you to see it given [the
specific bridge — shared paper, mutual connection, prior
public engagement on the topic]. If something jumps out and
you have a few minutes, GitHub issues or [their preferred
channel] are how I'd hear back.

— Ben Booth (B-Tree Ventures, Austin)

**Filling notes:**

- The "[bridge]" line is non-negotiable. If you can't articulate
  *why this person specifically*, the email reads as cold mass-
  mail and gets ignored.
- "[their specific paper]" should be a real paper / blog they've
  recently published. Cowork's profile-research output is the
  source for this.
- If you can drop a 2nd-degree mutual-connection name, the open
  rate roughly doubles. Format: "saw you've worked with [mutual
  name] who I [shared context]; dropping this on her/his
  recommendation."

---

## Process

1. T-1 (May 12) — Cowork reviewer list arrives. Pick top 3-5 names.
2. T-1 — Verify email addresses for each via their public lab /
   blog / GitHub. **Don't guess.** Bouncing a launch-day email
   is worse than not sending one.
3. T-1 — I draft each one using Template 3, fill in the
   bridge line, and send for your review.
4. T-0 morning — You give the green light or edit any of them.
5. T-0 9:45 AM CT — Send. **One at a time, not bulk.** Each
   should look like an individual email, not a campaign.

## What NOT to do

- Don't ask for an upvote on HN.
- Don't ask for a retweet on X.
- Don't ask for a review (we explicitly decided no pre-launch
  review process).
- Don't follow up if no response. Single send. The launch-day
  signal is enough; chasing makes it weird.
- Don't BCC anyone. If a recipient learns they were BCCed on a
  reviewer email, you've burned that relationship.
- Don't use a CRM-style "campaign" — these are individual
  notes from a founder, not marketing emails.
