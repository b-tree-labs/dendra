# Dendra — 48-Hour Launch Checklist

**Purpose:** the exact sequence of actions to ship Dendra to the
public and open the design-partner revenue motion. Done in 48
hours if you clear your calendar.

**Prerequisite:** provisional patent filed or about to be filed
(must complete before any public disclosure — see
`patent/00-filing-checklist.md`).

---

## Hour-by-hour plan

### Day 1 — Morning (hours 0-4)

- [ ] **H+0: File the provisional patent.** USPTO Patent Center
      upload; $75 micro-entity fee. The package is ready in
      `docs/working/patent/`. Use checklist file 00.
- [ ] **H+1: Run the provenance-snapshot script** from
      `patent/05-provenance-snapshot.md`. Archive the tarball to
      three locations (local, cloud, off-machine).
- [ ] **H+2: Create the public GitHub repo** at
      `github.com/axiom-labs-os/dendra`. Push the current workspace
      with full commit history.
- [ ] **H+3: Verify GitHub Actions CI runs green** on the first
      push (workflow is already in `.github/workflows/test.yml`).

### Day 1 — Afternoon (hours 4-8)

- [ ] **H+4: Register PyPI account** (if not already).
- [ ] **H+5: Build the distribution**: `python -m build` in the
      repo root. Verify `dist/dendra-0.2.0.tar.gz` and
      `dist/dendra-0.2.0-py3-none-any.whl` exist.
- [ ] **H+6: Upload to PyPI** via `python -m twine upload dist/*`.
      Verify `pip install dendra` works from a fresh venv.
- [ ] **H+7: Tag the release** on GitHub: `git tag v0.2.0 && git
      push --tags`. The release workflow auto-uploads to PyPI
      for future releases.
- [ ] **H+8: Send the arXiv submission.** Paper from
      `docs/papers/2026-when-should-a-rule-learn/outline.md`
      expanded into a full PDF. arXiv assigns an ID within 24
      hours.

### Day 1 — Evening (hours 8-12)

- [ ] **H+8: Buy the `dendra.dev` domain** if not owned. ~$15
      at Porkbun / Namecheap / Cloudflare Registrar.
- [ ] **H+9: Deploy landing page.** Use the copy deck at
      `docs/marketing/landing-page-copy.md`. Render as a static
      HTML/CSS site. Cloudflare Pages or Vercel deploy.
      Target: under 2 hours of work.
- [ ] **H+11: Write the Hacker News post.** Title: *"Dendra — the
      classification primitive every codebase is missing (paper +
      measurements + code)"*. Link to arXiv, PyPI, GitHub, and the
      analyzer command. Save the draft — don't post yet.
- [ ] **H+12: Sleep.** Serious move. You'll need focus tomorrow.

### Day 2 — Morning (hours 12-18)

- [ ] **H+12: Post to Hacker News** early US-morning (07:00 ET
      is ideal for global visibility during US work hours).
- [ ] **H+12: Cross-post to r/MachineLearning** with the paper
      and figure. Link to arXiv.
- [ ] **H+13: Post to X / Bluesky** — thread: (1) hero claim,
      (2) Figure 1, (3) the code block, (4) link to HN /
      arXiv / GitHub.
- [ ] **H+14: Engage HN comments** for the first 2 hours.
      Technical questions are common and worth answering. Do
      not pitch the Cloud product in comments; point to the
      paper + library.
- [ ] **H+16: Open the design-partner program page** on
      `dendra.dev/design-partners` with a simple contact form.
- [ ] **H+18: Post to LinkedIn** with a more business-framed
      version, same links. Tag 10-15 people in your network.

### Day 2 — Afternoon (hours 18-30)

- [ ] **H+18: Send the first 20 outreach messages.** Use
      Templates 1-2 from `docs/marketing/outreach-templates.md`.
      Target list: tier-1 from that doc (Supabase, Linear,
      PostHog, Cal.com, dbt Labs, Turso, Anyscale, Arize,
      HuggingFace, Perplexity — pick 20).
- [ ] **H+22: First-hour follow-ups** on any HN/Reddit/Twitter
      reply that looks like a potential design partner. Move
      to email as soon as appropriate.
- [ ] **H+24: End of Day 2.** You're live. Expect 50-200 GitHub
      stars, 1-3 design-partner replies, 500-2000 analyzer runs
      on public repos (if the HN post traction is mid-tier or
      better).

### Day 3 — Morning (hours 30-36)

- [ ] **H+30: Respond to every HN/Reddit/Twitter question**
      that's pending. Technical depth wins trust.
- [ ] **H+32: Schedule first calls** from design-partner replies.
      Use Template 5.
- [ ] **H+34: Tactical fixes** from the weekend. Broken install
      path? Docs typo? PyPI package metadata issue? Triage and
      push patch releases (v0.2.1, v0.2.2).
- [ ] **H+36: Run `dendra analyze`** on the top 10 publicly-
      accessible target repos. Save the JSON artifacts.
      Reference them in follow-up messages.

### Day 3 — Afternoon (hours 36-48)

- [ ] **H+36: Second outreach wave** — 20 more messages using
      the previous day's traction as a social proof anchor.
      ("We just launched; [N] GitHub stars in 48 hours,
      [M] paying developers on the analyzer. I think you'd be
      interested.")
- [ ] **H+40: Write a thank-you post** to HN/Reddit/Twitter.
      List first-day numbers. Linking to a "what's next"
      roadmap (pull from `docs/working/roadmap-2026-04-20.md`)
      sustains the attention cycle by a day or two.
- [ ] **H+44: Close your inbox.** The next 48-hour block is
      for cleanup + first-call prep, not launch.

---

## What you're doing at hour 48

1. **Public existence secured.** Patent filed, paper on arXiv,
   code on GitHub + PyPI, landing page live.
2. **40+ outreach messages sent.** Expect 10-20 replies.
3. **2-5 design-partner calls scheduled** for week 2.
4. **Hacker News / r/ML / LinkedIn / X coverage complete.**
   You've used the launch moment.

If one or more of the above isn't true at hour 48, you've used
the time on something off-plan. Return to this checklist before
starting new work.

---

## What NOT to do during the launch window

- **No feature-building.** If you find a gap in the library
  during a demo call, note it and ship a patch release later
  that day. Don't accept "let me fix that now" as an excuse
  to stop outreach.
- **No Cloud-product work.** Cloud MVP is a month 3-4
  commitment (see `docs/working/roadmap-2026-04-20.md`
  workstream 4). Don't drift.
- **No long-form content.** No deep-dive blog posts until day
  5+. The HN post + paper are enough public material for week 1.
- **No cold outreach to enterprises.** Tier-1 list only. Enterprise
  outreach is Year 2.
- **No "free forever" promises** to the first customers trying to
  negotiate the design-partner fee down. Hold the line at $10k
  floor. If the prospect won't pay $10k for 6 months of priority
  access to a patent-pending primitive, they're not a design
  partner — they're a tire-kicker. Move on.

---

## First-week metrics you're tracking

| Metric | Hour-48 target | End-of-week target |
|---|---:|---:|
| GitHub stars | 50+ | 500+ |
| PyPI downloads | 100+ | 2,000+ |
| Analyzer runs (public) | 500+ | 5,000+ |
| arXiv views | 50+ | 1,000+ |
| Outreach replies | 5+ | 15+ |
| Calls scheduled | 2+ | 8+ |
| Design partners signed | 0 | 1-2 |

Floor numbers above. Stretch numbers are 3-5× these.

---

## Weekly review — Friday of launch week

Block 2 hours. Look at:

1. Which outreach channel produced the most replies. Double down.
2. Which questions keep coming up on HN/Reddit/GitHub issues.
   Write the FAQ that week.
3. Which design-partner candidates are warm vs ghost. Fire
   Template 7 on ghosts.
4. What's the gap between "library works" and "Cloud MVP that
   design partners can use"? Set the next week's engineering focus.

---

## If launch traction is soft

Honest signals and responses:

- **<20 HN points, <100 GitHub stars, <5 replies.** Launch didn't
  hit. Root-cause in 48 hours: check the HN post title (often
  the bottleneck), check landing-page clarity, check whether the
  hero code block runs cleanly with `pip install dendra`. If the
  diagnosis is "wrong message," rewrite landing page + HN post
  + re-launch in 2 weeks with a sharper frame. If the diagnosis
  is "right message but buried," reach out personally to 10
  engineering-blog writers and ask for coverage.
- **Moderate traction, few replies.** The message resonated but
  outreach is the gap. Double down on outbound: 40-60 more
  targeted messages over week 2, pointing at the HN post as
  social proof.
- **Strong traction, no design-partner closes.** Conversion is
  the gap. Run 3-5 calls that week, offer to waive the fee for
  the first 2 partners in exchange for extended case-study
  rights. Get the first logo closed no matter what.

---

## Long-tail discipline

After hour 48, **stop doing launch work and start doing product
work**. The temptation is to keep mining the launch-week
traffic. Resist. The design-partner motion closes deals
through sustained follow-up, not launch-week volume.

Week 2 priorities (in order):

1. Close 1 design partner.
2. Continue outreach.
3. Start Cloud MVP build.
4. Ship patch release with bug-fixes from launch feedback.
5. Start paper's final edit for conference submission.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
This checklist is part of the internal operations docs. Live,
not static — update it as you learn from execution._
