# Dendra — Trademark Strategy

**Drafted:** 2026-04-22.
**Status:** Initial strategy draft for review. Not legal advice.
Before filing, validate with a trademark attorney (see §8 for
flat-fee options) or file DIY via USPTO TEAS Plus. Companion to
`patent-strategy.md` and `license-strategy.md`.

---

## 0. TL;DR

| Term | Strength | File? | Class(es) | Est. cost | Priority |
|---|---|---|---|---:|---|
| **DENDRA** | Arbitrary / strong | **File immediately** | IC 9 + IC 42 | $700 DIY (TEAS Plus, $350 × 2) | **P0 — this week** |
| **TRANSITION CURVES** | Suggestive / moderate | File with docs of use | IC 42 | $350 | P1 — within 60 days of launch |
| "Graduated autonomy" | Descriptive / weak | Don't file — protect via citation | — | — | Not a trademark play |
| "Smart switch" / "ML switch" / "AI switch" / "if/else/ML" / "if/else/AI" | Generic / descriptive | **Don't file** (will be rejected) | — | — | **Use as SEO fuel, not trademarks** |
| `@ml_switch` (decorator identifier) | Descriptive for the API | Don't file | — | — | Protected by the patent, not trademark |
| AXIOM LABS | Arbitrary / strong | File if becoming the commercial face | IC 9 + IC 42 | $700 | P2 — after Dendra registered |

**One-line strategy:** own the *brand* (DENDRA, TRANSITION
CURVES, AXIOM LABS); let the *category names* (smart switch, ML
switch, etc.) stay generic and capture them via SEO content.

---

## 1. Why trademark matters for Dendra specifically

The business-model analysis identifies "canonical-primitive
status" as a 5-10 year moat brick (see `business-model-and-moat.md`
§4.1). Trademark is the legal instrument that enforces this:

- A registered mark gives us the right to stop others from using
  the name in a way that causes market confusion. Without
  registration, we only have common-law rights in the geographic
  area where we've actually done business.
- Registered marks are displayed as ® — a signal to enterprise
  procurement that the product has a real commercial owner.
- Registration blocks squatters from registering "dendra.io,"
  "getdendra.com," etc. with trademark infringement as leverage
  (though squatting is also addressed via UDRP and domain
  registrations).
- A Dendra-branded domain-pack registry (year 2+) is only
  defensible if DENDRA is registered at the pack level.

Trademark also interacts with the patent strategy: `patent-
strategy.md` §11 flags trademarks as a separate workstream; this
doc fills that gap.

---

## 2. Trademark 101 (context for the decisions below)

Marks are ranked on a "distinctiveness spectrum" that determines
whether USPTO will grant registration:

| Category | Definition | Example | Protectability |
|---|---|---|---|
| **Fanciful / coined** | Made-up words | "Exxon," "Kodak" | Strongest |
| **Arbitrary** | Real word, unrelated to goods | "Apple" for computers | Strong |
| **Suggestive** | Hints at function without describing | "Greyhound" for buses | Moderate |
| **Descriptive** | Describes the goods directly | "Cold and Creamy" for ice cream | Weak — needs secondary meaning (5+ years of use) |
| **Generic** | The name of the goods themselves | "Bicycle" for bicycles | **Unregistrable** |

Applied to Dendra's candidate terms:

- "Dendra" = arbitrary (Greek *δένδρον* = "tree"; no inherent
  tie to classification software). **Registrable, strong.**
- "Transition curves" = suggestive (the phrase implies
  measurement of transitions without describing what they are).
  **Registrable with some care.**
- "Graduated autonomy" = descriptive (the method literally
  grants graduated autonomy to a classifier). Weak — we'd have
  to build secondary meaning over years. **Don't file.**
- "Smart switch" / "ML switch" / "AI switch" = descriptive or
  generic (the phrases describe exactly what the product does).
  **USPTO will reject.**
- "if/else/ML" / "if/else/AI" = descriptive + punctuation is
  tricky; even weaker than "ML switch." **Don't file.**
- `@ml_switch` = descriptive for the decorator. Code identifiers
  are rarely registered; even if granted, the scope is narrow
  (use as a source identifier, not use as code). **Don't file.**

---

## 3. Recommended filings

### 3.1 DENDRA — file this week, P0

- **Mark:** DENDRA (standard-character word mark).
- **Classes:**
  - **International Class 9** — downloadable software /
    computer programs. This is the class that covers the PyPI
    package and any packaged distribution.
  - **International Class 42** — software-as-a-service; SaaS
    platforms; platform-as-a-service. This is the class that
    covers Dendra Cloud, the hosted analyzer, and any
    future-hosted product.
- **Filing form:** TEAS Plus at USPTO (cheapest tier — requires
  a pre-approved ID of goods/services description, which is
  easy to hit for standard software terms).
- **Fee:** $350 per class × 2 classes = **$700**.
- **Specimen of use:** a screenshot of the GitHub / PyPI page,
  the Dendra Cloud landing page, or the CLI output. Any public
  commercial use anchors the specimen.
- **Filing basis:**
  - If launched before filing: "Section 1(a) — actual use" with
    the specimen already in hand (simpler, faster examination).
  - If filing before launch: "Section 1(b) — intent to use"
    with a Statement of Use filed within 6 months of a Notice
    of Allowance (more steps, higher fees).
- **Recommendation: wait until Day 1 of public launch**, then
  file 1(a) with the arXiv / PyPI / GitHub links as specimens.
  The 48-hour launch window is the right moment.

### 3.2 TRANSITION CURVES — file within 60 days post-launch, P1

- **Mark:** TRANSITION CURVES (standard-character word mark).
- **Class:** IC 42 only (it describes a service Dendra provides —
  computing and reporting transition curves, not a downloadable
  product).
- **Filing form:** TEAS Plus.
- **Fee:** $350 for single class.
- **Specimen of use:** the analyzer or Dendra Cloud UI showing
  per-site transition curves; the paper's Figure 1; a blog post
  or landing page that uses "Transition Curves" as a service
  mark (capitalized, followed by ™ or ℠ pre-registration).
- **Why wait 60 days:** we need documented commercial use of
  "Transition Curves" as a *service mark*, not just as a phrase
  in the paper. The landing-page copy and the analyzer UI
  anchor this. Filing too early risks a Section 2(e) refusal
  ("descriptive") that's harder to overcome without a clear
  commercial-use record.
- **Risk:** USPTO may examine this as descriptive of a graph
  shape. Mitigation: use it consistently as "Transition Curves™"
  with the ™ symbol from Day 1, anchoring source-identifying
  use rather than descriptive use. The ™ symbol is available
  without registration and creates the commercial record.

### 3.3 AXIOM LABS — file when commercial identity anchors it, P2

- **Mark:** AXIOM LABS (standard-character word mark).
- **Classes:** IC 9 + IC 42 if the brand is used commercially
  for software / SaaS (likely) ; IC 35 if used primarily for
  business services (consulting); IC 41 if used for educational
  materials (unlikely).
- **Filing:** defer until Axiom Labs has a real commercial face
  — a landing page, a customer engagement under the Axiom Labs
  name, or a product-line page where Axiom is the vendor and
  Dendra is the product. Filing too early with no use creates a
  1(b) intent-to-use burden that can lapse.
- **Estimated fee:** $700 (IC 9 + IC 42).

### 3.4 Logo / design marks — defer

Design marks (logos) are registered separately. Wait until the
brand has a finalized logo; filing a logo mark before the design
is settled means filing again if the logo changes. Year 2
decision.

---

## 4. The synonym question — "smart switch," "ML switch," "AI switch," "if/else/ML," "if/else/AI"

### 4.1 Don't trademark them. Here's why.

- **USPTO will refuse registration** under Section 2(e)(1) as
  "merely descriptive" of the goods, and likely also as generic
  (no secondary meaning available because the phrases describe
  the function directly).
- **Even if granted, the scope would be narrow.** Descriptive
  marks only prevent others from using the mark in the exact
  form and field; competitors could sidestep by saying "our
  product is a smart ML switching library" without capitalizing
  "Smart Switch."
- **Filing is $350+ per class plus any office-action responses
  ($200-500 each).** For a mark that will be refused, this is
  pure waste.
- **The "trademark bully" risk.** Asserting a registered mark
  for a generic term invites Streisand-effect pushback —
  cf. King.com suing over "Candy Crush" and the community
  backlash. An OSS-adjacent primitive does not want this
  optics hit.

### 4.2 Use them as SEO fuel — the right strategic move

These phrases are **what developers search for**. The strategy
is to capture search intent, not ownership:

- **Landing page subtitle and meta description:** include
  phrases like "the smart switch for production classification"
  / "when your if/else becomes ML." This puts Dendra on the
  first page for those searches without asserting trademark in
  the phrases.
- **Blog content:** titles like "From if/else to ML — the
  graduated-autonomy pattern" or "Smart switch, smart fallback:
  what production classifiers actually need." Use the generic
  phrases in the article body; use DENDRA™ (capitalized,
  source-identifying) in references to the product.
- **GitHub repo description:** similar — "Graduated-autonomy
  classification primitive. The smart switch your codebase is
  missing." Generic phrasing attracts; the brand name captures.
- **Paper metadata:** arXiv abstract uses phrases like "if/else
  to ML migration," "graduated autonomy," "ML switching." These
  are method descriptors in the paper, not trademarks.
- **Category-defining vocabulary:** adopt Google / Docker's
  pattern — let the category term stay generic; own the brand.
  Docker never tried to trademark "container"; they trademarked
  "Docker" and "Docker Desktop." Kubernetes never trademarked
  "container orchestration"; they trademarked "Kubernetes."

### 4.3 If someone else files one of these as a mark

Low risk. USPTO would likely refuse any of these as descriptive.
If a competitor managed to register, say, "MLSwitch" as their
product name (arbitrary as applied to *their* product, not a
direct description), that is fine — they own their brand. Our
brand is DENDRA, not "ML switch." The category term becoming
contested is expected and healthy — every category with multiple
vendors has competing generic descriptors.

Monitor for anyone registering marks that are confusingly
similar to DENDRA itself (e.g., "Dendra ML," "DendraFlow," etc.)
— that is an opposition-proceeding matter, not a synonym
matter. See §6 for monitoring.

---

## 5. The `@ml_switch` decorator name

This is a subtle case: a code identifier that developers type
into their code. Could it be trademarked?

- **Technically possible but rarely done.** Code identifiers
  aren't traditional source identifiers — they're functional
  elements of the code. USPTO occasionally grants marks on
  software API names (e.g., `REACT`, `JQUERY`) but only where
  the API name has become a strong brand identifier for a
  specific vendor.
- **Not strategically valuable here.** The patent covers the
  *method* regardless of what the decorator is named. Patent
  strategy §11b.8 already anticipates rename-based
  circumvention and functionalizes the claim language. Adding
  a trademark on `@ml_switch` doesn't improve the patent
  coverage; it just adds legal clutter.
- **Counter-argument:** if Dendra's success makes `@ml_switch`
  the dominant API name in the category, trademark protection
  could prevent a forked project from also using `@ml_switch`
  as their public API. This is a year-3+ concern, not a
  launch-week concern.
- **Recommendation:** don't file at launch. Revisit in year 2
  if `@ml_switch` has become the de-facto name in the category.

---

## 6. Post-filing enforcement and monitoring

### 6.1 What to watch for

- **Confusingly similar marks at USPTO:** new trademark
  applications that contain "Dendra" or clearly evoke it
  ("Dendraflow," "Dendra AI," "DendraML"). USPTO publishes
  applications in the Official Gazette for a 30-day opposition
  window — monitor for relevant filings.
- **Domain squatting:** someone registers
  "dendra-ai.com," "getdendra.io," "dendra.dev" (that last one
  needs to be ours from day one per the 48-hour checklist).
- **Brand usage in competitor marketing:** a competitor
  saying "works with Dendra" is nominative fair use and fine;
  a competitor saying "our product is Dendra-compatible™" and
  using the mark in a way that implies affiliation is not
  fine — send a polite "please use this attribution language
  instead" email.
- **NPM / PyPI / GitHub namespace squatting.** Register
  `dendra`, `@dendra/*` namespace, and common variants on PyPI
  / NPM / GitHub org proactively during launch week.

### 6.2 Monitoring tools

Free / cheap:
- **USPTO TMng** — USPTO's own search, free, weekly manual
  checks for "Dendra*" and "Transition Curves*."
- **Google Alerts** on "Dendra ML," "Dendra classification,"
  "DENDRA trademark" — free.
- **Markify / Trademark Angel free tier** — automated watch
  for new applications in selected classes, approximately
  $15-30/mo.

Paid (year 2+):
- Full brand-watching service (CompuMark, Corsearch) — $500-
  2,000/yr. Overkill until there's real revenue at stake.

### 6.3 If a dispute arises

- **First line: polite cease-and-desist letter.** DIY-template
  or attorney-drafted ($200-500). Most disputes end here.
- **UDRP** for domain squatting — ICANN's Uniform Domain-Name
  Dispute-Resolution Policy. Filing fee ~$1,500, decision in
  6-8 weeks. Good track record for clear-infringement cases.
- **USPTO opposition proceeding** if a confusing mark is
  published in the Gazette. File a Notice of Opposition
  within 30 days. Attorney fees $5-15k.
- **Federal trademark infringement suit** — last-resort,
  expensive ($50k+ through discovery). Only for clear cases
  with commercial damage.

---

## 7. International filings

US registration is the P0 priority. International follows
revenue and adoption:

- **Madrid Protocol** — single international application
  covers 100+ countries via WIPO. Filed based on a US
  application. Fee ~$2,000-5,000 depending on countries.
  Appropriate once US is registered (month 9-12 after US
  filing) and there's international customer demand.
- **Priority countries** given the business plan: EU (via
  EUIPO), UK, Canada, Japan, Australia. China is often
  worth filing defensively even without customers there
  (common squatting target).
- **Cost estimate for Madrid across 5 priority jurisdictions:**
  ~$3,000-6,000 including attorney fees.
- **Timeline:** year 2, not year 1.

---

## 8. Attorney vs. DIY — the cost-sensitive path

Consistent with the DIY provisional strategy (`patent-strategy.md`
§11a), trademark filing is a viable DIY path for a bootstrapped
founder:

- **DIY via TEAS Plus:** $350 per class, filed directly at
  [uspto.gov/trademark](https://www.uspto.gov/trademarks). USPTO
  provides form-based filing and the TEAS Plus pre-approved
  goods/services IDs minimize the risk of filing errors.
- **Flat-fee trademark attorney:** $500-1,500 for application
  preparation, filing, and office-action response. Good middle
  ground if not confident in DIY. Firms that advertise flat-
  fee trademark packages:
  - LegalZoom: $249-699 (basic to premium package)
  - LegalForce / Trademarkia: $199-$999
  - Sam Mollaei / bootstrapping-focused IP attorneys: $500-
    1,500 flat
  - USPTO's free legal help resources: Law School Clinic
    Certification Program has participating schools with free
    trademark clinics for qualifying applicants
- **Full-service firm:** $2,000-5,000 for soup-to-nuts on a
  single-class filing. Overkill for a bootstrapped founder on
  straightforward word marks.

**Recommendation for Ben:** DIY via TEAS Plus for DENDRA this
week. Keep $500-1,500 in reserve for potential office-action
response (common and not necessarily alarming — about 50% of
applications get at least one).

---

## 9. Timeline summary

```
This week    :  File DENDRA (IC 9 + IC 42) via TEAS Plus    — $700
               Buy dendra.dev, dendra.io, dendra.ai domains   — $60
               Register @dendra org on GitHub, PyPI, NPM     — $0
               Start using DENDRA™ consistently in copy       — $0
Month 0-1    :  Launch. Document "Transition Curves" usage
               in landing page, analyzer UI.                  — $0
Month 2      :  File TRANSITION CURVES (IC 42)                — $350
Month 4-6    :  Respond to any office actions (if any)        — $0-1,500
Month 9-12   :  Registration granted (typical timeline)       — $0
                Decide AXIOM LABS filing                       — $700 if filed
Year 2       :  Madrid Protocol for EU/UK/JP/CN/AU            — $3,000-6,000
               Monitor for adversarial filings                — $15-30/mo tool
```

**Year-one trademark spend (DIY, realistic case):** ~$1,200
($700 Dendra + $350 Transition Curves + $60 domains + $100
reserve for office actions).

---

## 10. Open questions (for attorney review if engaged)

These are items worth validating with a trademark attorney
before a full commercial launch. None block the P0 DENDRA
filing.

- [ ] Clearance search — has anyone registered DENDRA or a
      confusingly similar mark in IC 9 or IC 42? TESS (USPTO
      search) suggests no current conflicts but a professional
      clearance search ($200-500) is cheap insurance before
      filing.
- [ ] Exact goods/services description — the TEAS Plus
      pre-approved IDs need to be selected from USPTO's
      Acceptable Identification of Goods and Services Manual.
      Correct selection affects scope.
- [ ] Specimen evaluation — USPTO is picky about specimens of
      use. Screenshots need to show the mark being used "in
      connection with" the goods/services, not just on a
      logo mock-up.
- [ ] Section 1(a) vs 1(b) timing — whether launch is
      complete before filing or not.
- [ ] Declaration signatory — B-Tree Ventures, LLC is the
      applicant; the 1(a) declaration is signed by an
      authorized officer (Ben, as the LLC's member/manager).

---

## 11. Budget summary

| Item | Year 1 | Year 2+ | Cumulative |
|---|---:|---:|---:|
| DENDRA filing (IC 9 + IC 42) | $700 | — | $700 |
| TRANSITION CURVES filing | $350 | — | $1,050 |
| Domain registrations (5 TLDs) | $60 | $60/yr | $1,170 |
| Office-action responses (if any) | $0-1,500 | — | up to $2,670 |
| AXIOM LABS filing (optional) | — | $700 | up to $3,370 |
| Madrid Protocol (5 jurisdictions) | — | $3,000-6,000 | up to $9,370 |
| Monitoring tools | $0 | $360/yr | up to $9,730 |
| **3-year trademark budget total** | **$1,110-2,610** | **$4,120-7,120** | **~$5,230-$9,730** |

Order of magnitude: **low four figures in year one, low five
figures over three years.** Small relative to patent spend
($75 Y1 provisional, $15k+ Y2 utility per `patent-strategy.md`
§6.2).

---

## 12. What this doc does NOT decide

- **Design-mark / logo trademark** — deferred to year 2 when
  the logo is finalized.
- **International jurisdictional strategy beyond Madrid** —
  country-by-country selection is year 2 work.
- **Enforcement posture** — how aggressively to police the
  mark. Consensus: polite first, escalate only on clear
  commercial damage, never enforce against OSS non-commercial
  use or nominative fair use.
- **Licensing the trademark to customers** — relevant for
  a "built on Dendra" certification / badge program. Year 2+
  if at all.
- **Certification mark** — a separate category of mark ("this
  product meets Dendra's compatibility standard"). Year 3+,
  tied to the domain-pack ecosystem.

---

## 13. Next actions

1. [ ] **Today:** verify dendra.dev is available and register
      it; register github.com/axiom-labs-os/dendra as already
      planned; register `dendra` on PyPI (likely already
      reserved via previous launches — verify).
2. [ ] **This week:** run a free TESS search on "Dendra" in
      IC 9 and IC 42 to confirm no conflicts.
3. [ ] **This week (or Day-1 of launch):** file DENDRA via
      TEAS Plus. Pay $700. Keep receipt + application number
      alongside the provisional-patent filing receipt in the
      provenance snapshot.
4. [ ] **Start using DENDRA™ consistently.** Every landing-
      page instance of the name includes the ™ symbol from
      Day 1 until registration completes (at which point ™
      becomes ®).
5. [ ] **Reserve name-adjacent handles:** dendra on PyPI,
      NPM, GitHub, X, Bluesky, Hacker News, Discord.
6. [ ] **Send this doc to a trademark attorney for a single-
      hour review** (~$200-400 flat) before the filing goes
      in. Not required but cheap insurance on the DENDRA
      filing specifically.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Internal strategy document. Not legal advice — consult a
registered trademark attorney before filing._
