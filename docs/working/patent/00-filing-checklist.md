# Dendra Provisional Patent Filing — Action Checklist

**Generated:** 2026-04-20.
**Path chosen:** DIY micro-entity provisional, ~$75 total cash
out-of-pocket.
**IP provenance:** B-Tree Ventures LLC, sole inventor + assignee
(no institutional co-ownership). See `../patent-strategy.md` §7.
**Status:** pre-filing. Ben owns every action item below.

> This is inventor-prepared material, **not legal advice**. Review by
> a registered patent attorney is still recommended before filing,
> but is not strictly required. Flat-fee review options in
> `../patent-strategy.md` §11a.5.

---

## The path in one glance

```
Today         →  Draft checked in (this directory is ready)
Day 1         →  Snapshot provenance artifacts  (per §7.2)
Day 1         →  Create USPTO Patent Center account
Day 2-5       →  Review + personalize specification (file 01)
Day 2-5       →  Generate drawings (file 04)
Day 5         →  Compile filing packet (single PDF)
Day 5         →  File provisional at Patent Center — $75
Day 5-6       →  arXiv preprint the paper
Day 5+        →  Priority date locked
Month 11      →  Decide on utility conversion (budget window)
Month 12      →  File utility + PCT with attorney ($5-15k)
```

---

## Files in this package

| # | File | What it is | Who touches it |
|---|---|---|---|
| 00 | **00-filing-checklist.md** (this file) | Action list + sequencing | Ben |
| 01 | **01-provisional-specification.md** | The invention spec — ~40-50 pages ready to file | Ben reviews, may add |
| 02 | **02-cover-sheet-SB16.md** | USPTO Form SB/16 content | Ben personalizes |
| 03 | **03-micro-entity-SB15A.md** | USPTO Form SB/15A declaration | Ben personalizes + signs |
| 04 | **04-drawings.md** | Drawing-by-drawing text descriptions + Mermaid source for each | Ben renders to PDF/PNG |
| 05 | **05-provenance-snapshot.md** | Script + checklist to capture the clean-IP provenance record at filing time | Ben runs the script |

---

## Action items — in order

### STEP 1 — Snapshot clean-IP provenance (Day 1, 15 minutes)

- [ ] Open `05-provenance-snapshot.md`.
- [ ] Run the provenance-capture script (or its commands
      manually). It produces a timestamped `provenance-<date>.tar`
      containing: the git log, a tarball of the reference
      implementation at priority date, the patent-strategy
      analysis, the paper outline, and filesystem metadata
      supporting the B-Tree Ventures provenance claim.
- [ ] Archive the tarball somewhere durable (personal cloud
      backup + off-machine copy).

This is the "first line of defense" record per §7.2 of
`patent-strategy.md`. If any party ever questions provenance, you
have a timestamped snapshot of the pre-filing state.

### STEP 2 — Register USPTO Patent Center account (Day 1, 30 minutes)

- [ ] Go to [patentcenter.uspto.gov](https://patentcenter.uspto.gov/).
- [ ] Click "Create account" — USPTO uses **my-USPTO.gov** SSO.
- [ ] Verify email, complete identity verification (may require
      notarized forms or in-person verification — allow 3-5 days).
- [ ] Once verified, bookmark the filer dashboard.

**Alternative:** if SSO verification is slow, Patent Center
accepts **"pre-registration" filings** — you can file as an
unregistered user and associate the filing with your account
later. Not recommended for first-time filers; see USPTO guidance.

### STEP 3 — Generate drawings (Day 7, 1-2 hours)

- [ ] Open `04-drawings.md`.
- [ ] For each figure, the Mermaid source is provided — paste into
      [mermaid.live](https://mermaid.live) and export as SVG.
- [ ] Convert each SVG to PDF (browser Print-to-PDF works fine).
- [ ] Number each page per USPTO convention: "FIG. 1 of 8" etc.
- [ ] USPTO accepts black-and-white line drawings. Simple is fine.

### STEP 4 — Review + personalize the specification (Day 7, 1-2 hours)

- [ ] Open `01-provisional-specification.md`.
- [ ] Read through once end-to-end — the spec is intentionally
      over-inclusive; everything stays.
- [ ] Fill in bracketed fields:
  - `[INVENTOR FULL LEGAL NAME]` — "Benjamin Booth"
  - `[INVENTOR ADDRESS]` — your current mailing address
  - `[FILING DATE]` — leave blank; Patent Center stamps this
  - `[ASSIGNEE]` — "B-Tree Ventures, LLC"
- [ ] Add any post-2026-04-20 developments you want covered.
- [ ] Do NOT remove content — more disclosure = more protection.

### STEP 5 — Compile the filing packet (Day 8, 30 minutes)

The USPTO PDF packet should contain, in order:

1. **Cover sheet SB/16** (from file 02, converted to PDF).
2. **Micro-entity declaration SB/15A** (from file 03).
3. **Specification** (from file 01) — the invention description.
4. **Drawings** (from file 04) — PDF pages, numbered.

**How to compile:** render each markdown to PDF (Pandoc works
well: `pandoc 01-provisional-specification.md -o spec.pdf`).
Concatenate into one PDF per USPTO guidance:

```
pandoc 02-cover-sheet-SB16.md -o 02.pdf
pandoc 03-micro-entity-SB15A.md -o 03.pdf
pandoc 01-provisional-specification.md -o 01.pdf
# drawings already PDF from step 3; combine:
pdftk 02.pdf 03.pdf 01.pdf fig-1.pdf fig-2.pdf ... cat output dendra-ppa.pdf
```

or use macOS Preview's "Combine files" feature.

### STEP 6 — File at Patent Center (Day 8, 30 minutes)

- [ ] Log in to [patentcenter.uspto.gov](https://patentcenter.uspto.gov/).
- [ ] Select "File a new application" → "Provisional application".
- [ ] Upload `dendra-ppa.pdf` as the main application file.
- [ ] Cover-sheet fields: Patent Center will have you re-enter the
      SB/16 info via a form (it generates its own cover automatically).
- [ ] Entity status: select **Micro entity** (you're certifying
      via the SB/15A declaration attached).
- [ ] Fee: **$75** (2026 rate; check the fee schedule on the
      filing screen for current amount).
- [ ] Pay via credit card (USPTO accepts Visa/MC/Amex).
- [ ] Save the **Application Number** — you'll use this in
      citations for the next 12 months.
- [ ] Save the **Priority Date** (today's date) — this is the
      load-bearing result of the filing.

### STEP 7 — arXiv the paper (Day 8 or next business day)

- [ ] Once you have the USPTO priority-date confirmation email,
      arXiv the Dendra paper.
- [ ] In the paper's acknowledgments/metadata section, add:
      *"Provisional US patent application filed [date] — priority
      established."* Attribute to B-Tree Ventures LLC.

### STEP 8 — Calendar the 12-month deadline (Day 8, 5 minutes)

- [ ] Add to calendar: **MONTH 10 — decide on utility conversion**.
- [ ] Add to calendar: **MONTH 12 — utility + PCT filing deadline**
      (absolute — provisional rights lapse after 12 months).

---

## What I (Claude) did NOT draft for you

The following require Ben's signature, identity, or judgment and
cannot be pre-filled:

- The **micro-entity certification** — requires a true statement
  under penalty of perjury that you meet the income + filing-
  history criteria. Read the SB/15A template carefully before
  signing.
- The **cover sheet signature** — legal declaration of
  inventorship. Sign it yourself.
- Payment — your credit card.

---

## Costs — total out-of-pocket

| Item | Cost | Paid to |
|---|---:|---|
| USPTO provisional filing fee (micro entity) | $75 | USPTO |
| *Optional: flat-fee attorney review* | $0 to $3,000 | Attorney |
| *Optional: notary for SB/15A (most banks do free)* | $0 | Bank |

**Minimum: $75.**
**Recommended: $75 + optional $1,500 attorney review of the spec
before filing** if you can swing it. Still an order of magnitude
cheaper than my earlier full-service estimate.

---

## What this filing buys you

1. **Priority date** on both Candidate A (graduated-autonomy
   classification) and Candidate B (static+dynamic analyzer).
2. **12 months** to measure commercial traction, refine claims,
   and prepare the utility application.
3. **Apache 2.0 compatibility preserved** — your code license and
   your patent rights coexist (see `patent-strategy.md` §9).
4. **"Patent pending"** — usable in marketing and sales
   conversations immediately after filing.

---

## Questions to answer BEFORE STEP 1

- [ ] Are you in the US for the invention period? (If yes, file US
      first. If no, jurisdictional order changes — defer filing
      until you clarify with counsel.)
- [ ] Is there any prior disclosure you've made? (Blog post, talk,
      Twitter thread describing the six-phase model?) If yes,
      12-month US grace period counts from that date, and
      international rights may already be impaired.
- [ ] Are there any co-inventors? (The six-phase concept + the
      analyzer concept appear to be sole-Ben per commit history.
      If anyone else contributed inventive ideas, they must be
      named as co-inventors — required under 35 USC 116.)

If any of these answers is uncertain, **email the USPTO Inventor
Assistance Center at 1-800-PTO-9199** for procedural guidance
(free) before filing.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Pre-
filing inventor material._
