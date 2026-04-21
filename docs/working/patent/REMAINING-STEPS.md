# Remaining steps — Dendra provisional patent filing

**Today:** 2026-04-21 (GitHub repo already public → disclosure clock
has started). Target: **file US provisional within 24–48 hours** to
preserve the best-possible international filing posture.

## What's done (automated)

- [x] Provenance snapshot captured: `./provenance-2026-04-21.tar.gz`
      (656 KB, SHA-256 `c0a5f91249e2d77325214f77e45b8d367e7731aa7825677263f425c7acdd0e34`).
- [x] Personal-invention declaration drafted:
      `docs/working/patent/personal-invention-declaration.md` — your factual
      statement that the invention was conceived on personal time, personal
      equipment, personal funds, outside UT employment scope. **Review,
      sign, and keep with filing records.**
- [x] All 8 Mermaid figures rendered to PDF:
      `docs/working/patent/drawings/fig-01.pdf` through `fig-08.pdf`.
- [x] Spec cover fields partially filled: inventor = "Benjamin Booth",
      assignee = "B-Tree Ventures, LLC", UT-OTC caveat removed.
- [x] Cover sheet updated to remove UT-OTC caveat and reference the new
      personal-invention declaration.
- [x] Draft filing packet compiled:
      `docs/working/patent/dendra-ppa.pdf` — **50 pages total**:
      - Cover sheet SB/16 (3 pages)
      - Micro-entity declaration SB/15A (3 pages)
      - Specification (36 pages)
      - Drawings (8 pages, one figure per page)

## What Ben must do — ordered

### TODAY — identity fields (~30 min)

Open these three files and fill in each bracketed `[...]` field:

**`01-provisional-specification.md`** — two fields:
- Line 13: `**Address:** [INVENTOR ADDRESS]` → your home mailing address
- Line 14: `**Citizenship:** [US / OTHER]` → `US` (assuming US citizen)

**`02-cover-sheet-SB16.md`** — several fields:
- `[CITY], [STATE], [COUNTRY]` (residence — city/state where you live)
- `[US CITIZEN / OTHER]`
- `[STREET ADDRESS, CITY, STATE, ZIP]` (mailing address, full)
- `[STREET ADDRESS]`, `[CITY]`, `[STATE]`, `[ZIP]`, `[COUNTRY]` (correspondence
  — same as mailing for most people)
- `[PHONE]` (working phone; USPTO may call)
- `[COUNT]` → **`36`** (specification page count — already computed)
- `[B-TREE VENTURES REGISTERED ADDRESS]` → your LLC's registered
  business address (whatever's on the DBA / formation docs)
- `[STATE]` → the state B-Tree Ventures is incorporated in

**`03-micro-entity-SB15A.md`** — read the four conditions **carefully**.
Confirm each (or don't). See the verification checklist at the end of
this doc.

After filling, **regenerate the packet** by running (in repo root):

```bash
cd docs/working/patent
mkdir -p packet
pandoc 02-cover-sheet-SB16.md -o packet/02-cover-sheet.pdf \
    --pdf-engine=tectonic -V geometry:margin=1in -V fontsize=11pt -V mainfont="Helvetica"
pandoc 03-micro-entity-SB15A.md -o packet/03-micro-entity.pdf \
    --pdf-engine=tectonic -V geometry:margin=1in -V fontsize=11pt -V mainfont="Helvetica"
pandoc 01-provisional-specification.md -o packet/01-specification.pdf \
    --pdf-engine=tectonic -V geometry:margin=1in -V fontsize=11pt -V mainfont="Helvetica"
pdfunite packet/02-cover-sheet.pdf packet/03-micro-entity.pdf \
    packet/01-specification.pdf drawings/fig-01.pdf drawings/fig-02.pdf \
    drawings/fig-03.pdf drawings/fig-04.pdf drawings/fig-05.pdf \
    drawings/fig-06.pdf drawings/fig-07.pdf drawings/fig-08.pdf \
    dendra-ppa.pdf
```

Verify the output: `open dendra-ppa.pdf`. Confirm no `[...]` placeholders
remain visible in the PDF.

### TODAY — back up the provenance archive (~10 min)

The `provenance-2026-04-21.tar.gz` file is in the repo root. Put three
copies in durable locations:

1. **Personal cloud** (iCloud / Google Drive / Dropbox). Tag the file
   with the SHA-256 above so it's re-identifiable.
2. **Off-machine encrypted drive** (USB drive with FileVault or an
   encrypted disk image). Store physically separate from your laptop.
3. **Email to yourself** at a non-primary archive mailbox (optional
   but cheap — Gmail has a 25 MB attachment limit, the archive is
   656 KB).

Record the SHA-256 in a text file alongside your USPTO login notes
— that string is your "this is my priority-state tree" proof if
provenance is ever challenged.

### TODAY OR TOMORROW — create USPTO Patent Center account (~30 min + 3–5 day verify)

Slowest gate. Start this in parallel with everything else.

1. Go to https://patentcenter.uspto.gov/
2. Click **Create account** — USPTO uses **my.uspto.gov** SSO.
3. Complete identity verification. This is the slow step — USPTO uses
   **ID.me** for identity proofing. Allow 3–5 business days. Some users
   need a notarized form or in-person verification at a USPS post office.
4. If ID.me is delayed, USPTO accepts **pre-registration filings** where
   you file as an unregistered user and associate the filing with your
   account later. If the USPTO account isn't verified by your target
   filing day, use pre-registration rather than delay.

### FILING DAY (~1 hour)

1. Log into Patent Center (or use pre-registration flow).
2. Select **File a new application** → **Provisional application under
   35 USC 111(b)**.
3. Upload `dendra-ppa.pdf` as the main application file. (You may be
   prompted to split into application + drawings — just upload the
   single PDF first; if it rejects, separate into `dendra-spec.pdf`
   (cover + micro-entity + specification) and `dendra-drawings.pdf`
   (the 8 figures) and re-upload.)
4. Patent Center will present a **structured form** restating the
   SB/16 fields. Copy from your filled-in cover sheet.
5. **Entity status**: select **Micro entity** — you're certifying via
   the attached SB/15A declaration.
6. **Filing fee**: **$75** (2026 micro-entity rate; confirm on the fee
   screen — rates adjust periodically).
7. **Pay** via credit card (Visa / MasterCard / Amex).
8. **Save the filing receipt PDF** the moment Patent Center returns it.
   It contains:
   - **Application Number** (e.g., `63/XXX,XXX`) — you use this in
     citations for the next 12 months.
   - **Filing Date** — this is your **priority date**. Guard it.
9. Add the receipt PDF to the `./provenance-2026-04-21/` directory and
   recompute the SHA-256 sum of the updated archive. (Or make a second
   archive `post-filing-2026-04-21.tar.gz` with the receipt alongside
   the pre-filing snapshot.)

### AFTER FILING — calendar the deadlines (~5 min)

Three dates to put in your calendar immediately after filing:

1. **Priority date + 10 months** — decide whether to convert to utility
   (standard US) and/or file PCT for international. "Decide" means:
   have a cost-benefit analysis, attorney consultations, and go/no-go
   answer by this date.
2. **Priority date + 11 months** — begin drafting utility / PCT
   applications with attorney assistance. Do not wait to the last minute.
3. **Priority date + 12 months (HARD DEADLINE)** — utility / PCT must
   be filed by this date or provisional rights lapse. There is no
   extension; this is set by statute.

### AFTER FILING — international path (PCT)

You chose international. Here's what that looks like:

- **US provisional** (filing today) → priority date locked.
- **PCT application** (file within 12 months, claiming priority from
  provisional) → extends international filing window to 30 months
  post-priority while deferring expensive per-country fees.
- **National phase entry** (by priority + 30 months) → actually file
  in each desired country (EPO, JP, CN, KR, etc.). This is the
  expensive step (~$5k–15k per major jurisdiction, inclusive of
  attorney fees).

The main downside of the international path from your current posture:
the public GitHub push today likely impairs EPO rights (EPO is
strict-novelty, no grace period for your own disclosure). JP has a
6-month inventor grace period if you file correctly. CN has a
6-month grace for specific disclosures. US is 12 months.

**Practical recommendation before filing:** email the USPTO Inventor
Assistance Center at **1-800-PTO-9199** (free) and ask: *"I disclosed
an invention publicly on 2026-04-21 via GitHub and am filing a US
provisional within 48 hours. What's the correct citation language to
preserve international grace-period eligibility under PCT article
12?"* They'll tell you whether a specific declaration or citation
format is required.

### AFTER FILING — the launch unlocks

Once you have the priority date, the 48-hour launch checklist in
`launch-checklist-48hr.md` can execute without further IP risk:

1. arXiv paper submission (cite "US Provisional No. 63/XXX,XXX").
2. Hacker News / Reddit / X / Bluesky / LinkedIn posts.
3. PyPI release of `dendra` v0.2.0.
4. `dendra.dev` landing page.
5. Outreach messages to design-partner prospects.

## Micro-entity self-check (before signing SB/15A)

Read each item carefully; do not sign unless all four are true:

- [ ] **Small entity.** You (as individual) or B-Tree Ventures LLC
      qualifies as small (< 500 employees, no non-small-entity
      assignment). As a solo LLC, yes.
- [ ] **≤ 4 prior US patent applications.** Excludes provisionals and
      employment-required filings. **Most solo inventors qualify.** If
      uncertain, search your name on https://ppubs.uspto.gov/.
- [ ] **Gross income 2025 under ~$223,740.** USPTO publishes the exact
      current threshold at
      https://www.uspto.gov/patents/laws/micro-entity-status — verify
      on filing day.
- [ ] **No assignment to a non-qualifying entity.** B-Tree Ventures
      qualifies if its 2025 gross income is below the threshold.
      At pre-revenue / early-revenue stage this is met.

If any one is false: file as **small entity** instead (SB/05, $150 fee)
or standard ($320). Don't risk false certification.

## Safety net

Two options if any of the above blocks you:

1. **USPTO Inventor Assistance Center** (1-800-PTO-9199, free
   procedural guidance — they won't give legal advice, but they'll
   tell you which form, which fee, how to file).
2. **Flat-fee patent attorney review** of the specification
   ($500–3,000 depending on who you use). Even 90 minutes of
   attorney time reviewing the spec before filing catches most
   self-filer errors. Not required; worth it if budget allows.

## What I (this automation) did NOT do

- Did not sign anything — declarations, cover sheet, micro-entity
  certification all require your signature.
- Did not submit the filing — you must log into Patent Center and
  pay.
- Did not draft the claims (not required for provisional; see
  §12 of the spec for the "Claim Concepts" that guide utility
  conversion).
- Did not contact USPTO on your behalf — that's on you if you
  have procedural questions.

---

_Generated 2026-04-21 automatically. Cross-check with
`00-filing-checklist.md` — that file is the canonical sequence;
this one adds the "what was automated vs. what's left" split._
