# Dendra — Patent Strategy Analysis

**Written:** 2026-04-20.
**Author:** Benjamin Booth (inventor of record).
**Status:** Internal strategic analysis. **Not legal advice.** Before
filing anything, consult a registered patent attorney. See §7 for
the B-Tree Ventures provenance record — Dendra has clean IP with
no academic or institutional co-ownership.
**Confidentiality:** treat this document as protected pre-filing
analysis. Do not share outside the B-Tree Ventures / Axiom Labs
principals + legal counsel.

---

## 0. TL;DR

**Patentable candidates, ranked by strength × commercial leverage:**

| # | Candidate | Novelty | Non-obviousness | Useful? | Rec. |
|---|---|---|---|---|---|
| A | Graduated-autonomy classification primitive with statistically-gated phase transitions | Moderate-high | High | Yes | **FILE PROVISIONAL** |
| B | Static+dynamic analyzer for rule-to-ML graduation candidates | High | High | Yes | **FILE PROVISIONAL** |
| C | Circuit-breaker-aware ML-primary classification w/ automatic safety-floor revert | Moderate | Moderate | Yes | Bundle into A |
| D | Federated transition-depth prediction from cross-org outcome priors | High | High | Yes (future) | Continuation in Year 2 |
| E | Safety-critical architectural cap enforced at construction | Low | Low | Yes | Bundle into A |

**Two load-bearing constraints:**

1. **arXiv publication triggers a 12-month grace period in the US**
   and **immediate bar to patentability in most other jurisdictions**
   (EPO, JPO, China absolute-novelty rules). File at least a
   **provisional before arXiv**, not after.
2. **Software patents are scrutinized post-Alice.** Claims must be
   tied to a concrete technical improvement (latency reduction,
   safety bounds, self-rotating storage) — not just "automate X."
   §4 drafts claim structures with Alice in mind.

**Clean IP provenance:** Dendra is a B-Tree Ventures LLC work with
no academic or institutional co-ownership. See §7 for the
provenance record used to support that position.

**Recommended timeline:** provisional application for candidates A+B
within 30 days (before arXiv preprint of the Dendra paper), utility
conversion within 12 months, PCT international within 12 months of
provisional. See §6.

---

## 1. What's patentable (and what isn't)

The patent threshold in the US (post-Alice, 2014): an invention must
be novel, non-obvious, useful, AND pass the *Alice* two-step test —
(i) is it directed to an "abstract idea"? (ii) if so, does the claim
recite "significantly more" than the abstract idea itself?

For software, passing Alice requires tying the abstract idea (e.g.,
"classify and log outcomes") to a *concrete technical improvement* —
something measurable like reduced latency, bounded safety guarantees,
reduced storage growth, specific hardware behavior, or a novel
computational technique.

**Not patentable by themselves:**
- The six-phase vocabulary (naming is copyright/trademark, not patent).
- The decorator syntax `@ml_switch(...)`.
- The `@name:context` principal naming convention.
- The paper's category taxonomy (§6).
- Individual algorithms that already exist (TF-IDF, McNemar, binomial
  tests).

**Patentable by themselves:**
- The *combination* of those pieces into a system that achieves a
  measurable technical improvement.
- Hardware-adjacent behaviors (self-rotating log storage, sub-µs
  decision path, circuit-breaker with reset).
- Cross-institutional federation systems with specific protocols.

---

## 2. Candidate A — Graduated-autonomy classification with statistically-gated transitions

### 2.1 The invention (draft claim concept)

A **classification system** comprising:

1. A **pluggable decision pipeline** with a fixed set of six
   operational phases (RULE → MODEL_SHADOW → MODEL_PRIMARY → ML_SHADOW →
   ML_WITH_FALLBACK → ML_PRIMARY), each phase defining a specific
   routing behavior between a rule, an LLM classifier, and an ML
   head, where exactly one serves as decision-maker at a time and
   lower-tier classifiers serve as the safety floor.

2. An **outcome logger** that records, for each classification,
   at least: the input, the decision-maker's output, the outputs of
   non-decision-making classifiers operating in shadow, and a
   timestamp, stored in a content-addressable append-only log with
   automatic size-bounded rotation.

3. A **statistical transition gate** that, on presentation of
   outcome evidence satisfying a configurable paired-proportion test
   (McNemar or equivalent) at a specified significance level α,
   permits a phase transition; the gate refuses any transition for
   which the test does not reject the null hypothesis that the
   higher-tier classifier is no better than the current phase's
   decision-maker.

4. A **safety-critical attribute** settable at construction that,
   when true, *categorically refuses construction* of the system in
   the final phase (ML_PRIMARY), enforcing a rule-grounded floor on
   authorization-class decisions.

5. A **circuit breaker** operating at the final phase (ML_PRIMARY)
   that, on detecting ML failure or anomaly, reverts routing to the
   rule and persists in that state until explicit operator reset.

### 2.2 Prior art survey

Known prior art that is *close but distinguishable*:

- **"Shadow mode" deployment** (industry practice, blog posts, ~2015+).
  Used for A/B testing ML in production. **Not prior art** to the
  six-phase lifecycle, the statistical transition gate, or the
  rule-floor safety theorem.
- **"Try ML else fall back to rule"** (ubiquitous pattern).
  Implemented ad-hoc in most production systems. **Not prior art** —
  lacks the statistical gate, the formal phase vocabulary, and the
  circuit-breaker recovery.
- **AutoML platforms** (H2O, AutoGluon, SageMaker Autopilot).
  Select models given data; do not handle the rule-to-ML migration
  path or safety-critical floor.
- **Vowpal Wabbit / online learning** (~2011+). Continuous
  adaptation but no rule safety floor, no phase transitions.
- **Aviation autopilot / automotive ADAS "degrees of autonomy"**
  (SAE J3016 2014, DO-178C process). Provides conceptual ancestor
  but not software classification systems.
- **Google / Meta "gradual rollout"** tooling. Traffic-percentage
  rollouts; not rule→ML specific.
- **Fairlearn / Aequitas / Model Cards**. Fairness instrumentation;
  not phase transitions.

Specific patents to search (attorney to run full FTO):
- US9489625 (Amazon, "shadow service deployment")
- US10628774 (Google, "ML rollout with canary")
- US20220261693A1 (IBM, "classifier with confidence threshold")

**Preliminary finding:** candidate A appears clearly novel against
observed art. The *specific* combination (formal six-phase
vocabulary + paired statistical transition gate + safety-critical
cap + circuit-breaker recovery) is not found.

### 2.3 Claim structure sketch

```
1. A computer-implemented method for production classification,
   comprising:

   (a) providing a switch instance associated with a rule function
       that maps input to a label, wherein said switch instance is
       configured with an operational phase selected from a fixed
       ordered set of six phases;

   (b) for each classification request, routing said request to
       one of: (i) said rule function, (ii) a configured large
       language model classifier, (iii) a configured machine-
       learned head, according to said operational phase;

   (c) recording an outcome record comprising the input, the
       decision-maker's output, outputs of non-decision-making
       classifiers running in shadow, and a timestamp, to an
       append-only log with automatic size-bounded rotation;

   (d) responsive to accumulated outcome records satisfying a
       paired-proportion statistical test at a configured
       significance level, permitting advancement to a higher
       operational phase;

   (e) refusing, at system construction time, construction in
       phase six when a safety-critical attribute is set; and

   (f) upon detection of a failure or anomaly of said machine-
       learned head while operating in phase six, reverting
       routing to said rule function and persisting in said
       reverted state until an explicit reset operation.

2. The method of claim 1, wherein said phases comprise RULE,
   MODEL_SHADOW, MODEL_PRIMARY, ML_SHADOW, ML_WITH_FALLBACK, and
   ML_PRIMARY.

3. The method of claim 1, wherein said paired-proportion test
   is McNemar's exact test for small sample counts and a normal-
   approximation variant for larger counts.

4. The method of claim 1, wherein said outcome log rotates segments
   at a configurable byte threshold and prunes rotated segments
   past a configurable retention count, whereby disk growth is
   bounded without operator intervention.

5. [dependent] ... additional claims for specific phase-transition
   preconditions, the confidence-threshold gate at phases 2 and 4,
   multi-tenant switch instances, etc.
```

### 2.4 Strengths for Alice

- **Concrete technical improvement #1**: bounded probability of
  worse-than-rule behavior (paper §3.3 theorem). This is a
  measurable safety property, not an abstract idea.
- **Concrete technical improvement #2**: sub-microsecond decision
  path overhead (measured in `tests/test_latency.py`). Specific
  latency improvement over LLM-based classification.
- **Concrete technical improvement #3**: self-rotating outcome log
  with fixed cap. Specific storage behavior, not merely "store
  decisions."
- **Concrete technical improvement #4**: construction-time refusal
  of unsafe configurations. Specific behavior of a class
  constructor.

Each of these ties the abstract "classify and log" idea to a
measurable system behavior — the kind of detail that has cleared
Alice in recent USPTO examinations of AI/ML patents.

---

## 3. Candidate B — Static+dynamic analyzer for rule-to-ML graduation

### 3.1 The invention

A **code-analysis system** comprising:

1. A **static analysis module** that parses source code to identify
   functions whose bodies match a library of 50+ patterns indicative
   of classification decision points (if/elif returning string
   literals, match/case over keyword lookup, dispatch tables, etc.),
   and labels each site with an inferred label cardinality, domain
   regime (narrow vs broad), and preliminary fit-score.

2. A **dynamic instrumentation module** that, when requested, wraps
   identified sites with a measurement-only decorator capturing
   call volume, input shape, output distribution, and optional
   outcome signal, and stores the measurements with no decision-
   path mutation.

3. A **savings projector** that combines the static analysis output
   with the dynamic measurements and a reference cost model
   (engineering-cost ranges, regression-cost ranges, token-cost
   ranges), producing per-site estimated annual savings with
   explicit ratio-based decomposition.

4. A **report generator** that emits a machine-readable artifact
   (JSON) suitable for CI integration, diffable across PRs, and
   a human-readable report ranking sites by expected value.

### 3.2 Prior art survey

- **Snyk / Dependabot** — vulnerability scanners. Not classification-
  site scanners; different abstract idea.
- **SonarQube / CodeClimate** — code-quality scanners. Metrics-based;
  no rule→ML graduation domain.
- **MLflow / Weights & Biases** — ML experiment tracking. Not code
  analyzers.
- **Model cards / data sheets** — ML-model documentation. Not
  code-analysis products.

**Preliminary finding:** clearly novel. No known prior art identifies
rule-to-ML graduation candidates with quantified per-site savings.

### 3.3 Claim structure sketch

```
1. A computer-implemented method for identifying and quantifying
   rule-to-ML graduation candidates in a production codebase,
   comprising:

   (a) parsing source files of said codebase to identify
       functions whose abstract syntax trees match patterns from
       a stored pattern library, said patterns characterizing
       classification decision points;

   (b) for each identified function, inferring a label set from
       string literals appearing in return statements, computing
       a label cardinality, and classifying the site into a
       domain regime;

   (c) optionally instrumenting each identified function with a
       measurement-only wrapper that captures call volume,
       input shape statistics, and output distribution during a
       measurement window without mutating the decision path;

   (d) combining static analysis output with dynamic
       measurements and a reference cost model comprising at
       least engineering cost ranges, regression cost ranges,
       and token cost ranges, to compute per-site projected
       annual savings with explicit ratio-based decomposition;
       and

   (e) emitting a machine-readable report ranking identified
       sites by projected savings and a companion diff-friendly
       artifact suitable for continuous-integration
       regression-tracking.

2. The method of claim 1, wherein said pattern library comprises
   at least patterns for if-elif-else chains returning string
   labels, match-case dispatchers, keyword-matching classifiers,
   LLM-prompted classifiers, and rule-tree dispatchers.

3. The method of claim 1, wherein said reference cost model
   comprises at least: AI-assisted baseline migration time of
   1.6 to 3.5 engineer-weeks per site, per-site regression cost
   ranges of $50k to $300k per event, and token-cost ranges based
   on input and output token counts multiplied by current
   commercial LLM pricing.
```

### 3.4 Strengths for Alice

- **Concrete technical improvement**: quantified savings projection
  per site is a specific, measurable output — not merely
  "automate review of code."
- **Concrete technical improvement**: AST-pattern library is a
  specific computational technique tied to a narrow class of code
  structures.
- **Concrete technical improvement**: measurement-only wrapper
  with no decision-path mutation is a specific instrumentation
  technique.

---

## 4. Candidates C, E — bundled into A

Candidate C (circuit breaker) and E (construction-time safety cap)
are each narrow — probably fail the non-obviousness bar on their
own. Bundle into candidate A as dependent claims.

---

## 5. Candidate D — Federated transition-depth prediction (Year 2)

Deferred until we have federation data. The invention:

A system that receives anonymized outcome-pattern signatures from
multiple organizations, fits a regression model predicting
transition depth from dataset attributes (label cardinality,
distribution stability, outcome latency), and returns for each
new site a transition-depth prediction with confidence interval
derived from the cross-institutional prior.

**Why wait:** requires real federation data to show technical
improvement. Premature filing risks a weak "abstract idea" claim.
File a provisional once we have a working multi-org prediction
system (likely 2027 Q2+).

---

## 6. Filing strategy + timeline

### 6.1 Provisional-first approach (recommended)

```
Day  0    : File provisional application for Candidates A+B
            (can be a single combined provisional application).
Day  0+1  : arXiv preprint of the Dendra paper (§7 caveat on
            UT ownership must be resolved first).
Month  3  : First full patent-attorney review + prior-art search.
Month  6  : Finalize utility-application claims.
Month 12  : Convert provisional to utility application(s) —
            can split into A-family and B-family at this point.
Month 12  : File PCT international application (preserves rights
            in EU, Japan, China, UK).
Month 18  : PCT Chapter II amendments (optional).
Month 30  : National-phase entries in selected jurisdictions.
```

### 6.2 Cost estimate (very rough)

| Item | Low | High |
|---|---:|---:|
| Provisional drafting (attorney) | $5k | $15k |
| Utility conversion | $10k | $25k |
| PCT filing + search | $5k | $12k |
| National phase (per jurisdiction, 4 major) | $15k | $40k × 4 |
| **5-year total (4 jurisdictions)** | **~$80k** | **~$220k** |

### 6.3 Why provisional-first

- **Cheap** ($5-15k vs $40k+ for utility).
- **Priority date is what matters** — locks in novelty against
  later prior-art appearance.
- **12-month window** to develop claims, measure commercial
  traction, decide on jurisdictions.
- **Matches arXiv timeline** — file provisional, then publish.

---

## 7. B-Tree Ventures clean-IP provenance record

Dendra is a **B-Tree Ventures LLC work of authorship and
invention**. No academic, governmental, or other institutional
entity holds an ownership claim. This section documents the
provenance facts that support that position so they exist in
writing ahead of filing and in case of any future inquiry.

### 7.1 Ownership facts

- **Inventor of record:** Benjamin Booth, contactable at
  `ben@b-treeventures.com`.
- **Assignee:** B-Tree Ventures, LLC (a Texas limited-liability
  company doing business as Axiom Labs for the commercial side
  of its portfolio).
- **Repository:** `github.com/axiom-labs-os/dendra`, licensed Apache
  2.0. Commit history shows Benjamin Booth as sole committer
  from inception.
- **Development environment:** personal time, personal equipment,
  no institutional compute, no grant-funded facilities, no
  externally-assigned research tasks.
- **License on reference implementation:** Apache 2.0. Patent
  rights are not waived by the Apache 2.0 grant; the grant permits
  users of the code to practice the invention, but does not confer
  rights to make competing products under a different license. See
  §9 for the open-source / patent interaction.

### 7.2 Provenance artifacts to retain

Keep the following on hand in case any party ever asks how Dendra
came to be:

- [ ] Git log of the Dendra repository, including commit dates,
      author identity, and filesystem paths showing development
      on personal machines.
- [ ] Design-doc history (`docs/papers/`, `docs/marketing/`,
      `docs/working/`) showing iterative conception and reduction
      to practice over the 2026 window.
- [ ] Copies of patent-strategy analysis (this file), the paper
      outline, and the reference implementation at priority date —
      captured as a timestamped snapshot at filing time.
- [ ] B-Tree Ventures LLC formation documents and governance
      records confirming the entity's existence and scope.

### 7.3 The clean-IP assertion in the provisional

The SB/16 cover sheet identifies **B-Tree Ventures, LLC** as the
sole assignee and **Benjamin Booth** as the sole inventor. No
co-inventors, no co-assignees, no institutional interests.

This is an administrative statement; the provisional filing
itself is evidence of the date by which B-Tree Ventures claims
the invention. If any third party subsequently asserts a claim,
the provisional priority date + the provenance artifacts in §7.2
are the first line of defense.

### 7.4 If commercial-licensing negotiations produce co-ownership

In the event B-Tree Ventures enters a commercial agreement that
reassigns or co-assigns the patent (e.g., to a partner firm as
part of a licensing deal), the assignee can be updated at utility
conversion via a standard patent-assignment recording with USPTO.
This is routine and does not affect the provisional priority date.
No such agreement is contemplated pre-filing.

---

## 8. Disclosure hazards — what NOT to do until provisional filed

**Do not, before provisional filing:**

- Publish the Dendra paper to arXiv.
- Submit to NeurIPS / ICML (initial submission is public the moment
  the PDF is uploaded to the submission system).
- Post the design on any public blog.
- Present at a conference, workshop, or public meetup.
- Share with anyone outside the inventor circle + legal counsel
  without a signed NDA.

**Safe to do before provisional filing:**

- Continue developing the code (open source is not inherently a
  disclosure — the code reveals *implementation* but the patent
  claim covers *method*; attorney will advise).
- Internal-only design discussion.
- Private customer pilots under NDA.

**One-year US grace period:** even if the paper is accidentally
disclosed, US 35 USC 102(b) gives 12 months to file. This doesn't
apply in most other jurisdictions, so international rights are
forfeit if you disclose before filing.

---

## 9. Open source compatibility

> **2026-04-22 update.** The original framing in this section —
> "Apache 2.0 + patent = the Temporal / Elastic / MongoDB
> pattern" — overstates the commercial-licensing leverage that
> pure Apache 2.0 retains. See
> `docs/working/license-strategy.md` for the revised split-
> license posture (Apache 2.0 on the client SDK; BSL 1.1 with
> Change Date 2030-05-01 on the analyzer and Dendra-operated
> surfaces). The patent analysis in this file remains correct;
> only the license-interaction paragraphs below are superseded.

The provisional patent on the graduated-autonomy method
interacts with Dendra's two licenses differently:

- **On the Apache-2.0 client SDK:** the Apache 2.0 license
  grants a patent license to recipients, so Dendra SDK users
  are free to practice the patented invention as part of using
  the client code.
- **On the BSL-1.1 components:** no Apache-style patent grant
  applies; the BSL governs both copyright and (by virtue of
  restricting what you may do with the code) the scope under
  which the invention may be practiced via the BSL-licensed
  surfaces. Commercial licensing (separate from BSL) is how
  the patent is monetized against non-customer practitioners.

What a patent DOES protect (unchanged):

- Third parties who *don't* use our code but implement the same
  method independently. They need a patent license from us.
- Enterprise customers who want stronger indemnification than
  Apache 2.0 provides — we can sell commercial licenses that
  include patent indemnity.
- Competitors who want to offer a hosted Dendra-derivative
  service. Under the split license, the BSL's Additional Use
  Grant excludes competing hosted services, which — combined
  with the patent — forms the real commercial lever.

The end-state pattern is **HashiCorp / CockroachDB / Sentry**
(split-license, not pure Apache), with the patent providing
additional leverage beyond what the BSL alone provides.

---

## 10. Immediate next actions (sequence matters)

1. **Pause any arXiv / paper submission until provisional is
   filed.** This is the most important protection — §8.
2. **Optional: 1-hour consultation with a registered US patent
   attorney specializing in software + AI patents.** Candidates:
   - Fenwick & West (SV)
   - Kilpatrick Townsend (AI focus)
   - Sidley Austin
   - Austin-local: Munck Wilson Mandala, Sprinkle IP Law Group,
     Henry Patent Law Firm
   - Skip this step entirely if choosing the DIY path per §11a.
3. **Prepare the "invention narrative"** for the attorney (if
   engaged) or for your own DIY drafting: the problem, the novel
   solution, the prior art identified in §2, the commercial
   context.
4. **Snapshot provenance artifacts** per §7.2 — git log,
   design-doc history, and a timestamped tarball of the
   reference implementation.
5. **File the provisional** application for candidates A+B
   combined. Either DIY per §11a.3 or attorney-drafted.
6. **Same day or next business day** → arXiv preprint.

---

## 11a. Low-cost filing path — ~$75 total out-of-pocket

**The $5k-$15k number in §6.2 is attorney-drafted quality. A
provisional application does NOT require an attorney.** Here's the
realistic minimum-cost path.

### 11a.1 USPTO fees (the only mandatory costs)

Filing a provisional patent application (PPA) at USPTO, rates as of
April 2026:

| Entity status | Provisional filing fee | Who qualifies |
|---|---:|---|
| **Micro entity**       | **$75**  | Gross income < 3× median household income AND < 5 prior patent applications. Ben almost certainly qualifies. |
| **Small entity**       | $150     | Business with <500 employees. B-Tree Ventures qualifies. |
| **Standard entity**    | $320     | Everyone else. |

Source: 37 CFR 1.16(d). Micro-entity status is claimed by filing
**USPTO Form SB/15A** alongside the application — zero additional
cost, just a declaration.

**No claims required.** A provisional only needs a **specification**
(description of the invention) and any drawings. Claims are optional
and typically skipped in provisionals anyway — they're drafted during
the utility conversion when attorney help matters most.

### 11a.2 Four filing paths, cheapest first

| Path | Attorney | Out-of-pocket | Quality | Timeline |
|---|---|---:|---|---|
| **A. DIY micro-entity provisional** | None | **$75** | Decent if you're technical and write clearly | Days |
| **B. Pro bono / law school clinic** | Yes (supervised) | $75 (filing fee only) | High for income-qualified applicants | 1–3 months wait |
| **C. Flat-fee provisional service** | Yes | $500–$1,500 | Moderate — template-driven | Weeks |
| **D. Limited-scope attorney review** | Yes | $1,000–$3,000 | High — attorney reviews a DIY draft | 2–4 weeks |
| **E. Full-service firm** | Yes | $5,000–$15,000 | Highest | 4–8 weeks |

**For a solo founder pre-revenue: Path A or B.**

### 11a.3 Path A — DIY provisional ($75 total)

USPTO explicitly supports pro se inventors. Their own guidance:
[uspto.gov/patents/basics/patent-process-overview](https://www.uspto.gov/patents/basics/patent-process-overview).

**What you need to write:**

1. **Title** — e.g., "System and Method for Graduated-Autonomy
   Classification with Statistically-Gated Phase Transitions."
2. **Technical field** — one paragraph placing the invention in
   context (software for production ML classification).
3. **Background** — the problem being solved. Draw from paper §1.
4. **Summary of invention** — the key idea in one page. Draw from
   §2.1 and §3.1 of this doc.
5. **Detailed description** — the longer the better. This is where
   you disclose every variation you might later claim. **The
   single most important page you write.** Draw from:
   - The paper outline (`docs/papers/2026-when-should-a-rule-learn/outline.md`)
   - The implementation (point to `src/dendra/core.py`, storage.py, etc.)
   - The security benchmarks (`tests/test_security_benchmarks.py`)
   - The ROI model (`src/dendra/roi.py`)
   - The analyzer design (`docs/marketing/business-model-and-moat.md` §2)
6. **Drawings (optional but valuable)** — the Figure 1 transition
   curves, a state-machine diagram of the six phases, a dataflow
   diagram of the analyzer. Hand-drawn is fine; USPTO accepts.
7. **Cover sheet** — USPTO Form SB/16 (provisional cover sheet).
8. **Micro-entity declaration** — USPTO Form SB/15A.

**Where to file:** USPTO Patent Center ([patentcenter.uspto.gov](https://patentcenter.uspto.gov/))
— web-based filer, credit card payment.

**The single biggest DIY failure mode: INSUFFICIENT DISCLOSURE.**
A provisional's priority only covers what the specification
*actually describes*. If you later want to claim feature X in the
utility application and feature X isn't in the provisional, you
lose the priority date for feature X.

**Mitigation:** be over-inclusive. Dump everything technical into
the specification — code excerpts, architecture details, alternative
implementations, failure modes, benchmarks, numbers. USPTO doesn't
penalize length. A 50-page provisional costs the same $75 as a
5-page one.

**What you SHOULD NOT try DIY:** the utility conversion (month 12).
That's where claim drafting matters and the $5k-$15k attorney spend
is load-bearing. But by month 12, Dendra should have paying pilots
and the budget will exist.

### 11a.4 Path B — Pro bono / law school clinic (free attorney, $75 filing)

Options for income-qualified inventors:

1. **USPTO Patent Pro Bono Program**. Federal program matching
   inventors with volunteer attorneys. Income-qualified (<3× FPG).
   [uspto.gov/patents/basics/using-legal-services/pro-bono](https://www.uspto.gov/patents/basics/using-legal-services/pro-bono)
2. **VLA (Volunteer Lawyers for the Arts)** Austin — sometimes
   handles IP matters for low-income founders.
3. **Inventors Assistance Center** at USPTO: 1-800-PTO-9199.
   Not drafting help, but free answers to procedural questions.
4. **Law-school IP clinics** in jurisdictions other than the
   inventor's employer — avoids any appearance of institutional
   conflict-of-interest. Several major law schools with IP
   clinics accept remote inventors.

**Trade-offs:** pro bono introduces a 1-3 month wait. If you want
to publish the paper sooner, DIY path A is faster.

### 11a.5 Path D — Limited-scope attorney review ($1-3k)

Compromise path if you have some budget but not $10k:

1. Draft the provisional yourself using §11a.3 guidance.
2. Engage an attorney for a **flat-fee review** — typically $500
   for 1 hour + $1,500 for a full review + revision pass.
3. Austin practitioners who do flat-fee provisional review:
   - Munck Wilson Mandala (Austin, reasonable rates)
   - Egan Nelson LLP
   - Sprinkle IP Law Group
   - Henry Patent Law Firm (not local but known for flat-fee
     startup packages — $1,500-$3,000 for a provisional)
4. Ask specifically: **"Will you review a pro se provisional
   draft and file it, for a flat fee? What's your fee?"**

### 11a.6 Recommended budget sequence for a bootstrapped founder

```
Month 0  :  $75  — DIY provisional (or $1.5k with attorney review)
Month 1–11:  $0   — sell pilots, generate ARR
Month 12 :  $5k–$15k — utility conversion (by then you have budget)
Month 12 :  $5k  — PCT filing
Year 2–3 :  $15k–$40k × jurisdictions for national phase
            (fund this from licensing revenue, not pre-revenue cash)
```

Total **year-one patent spend: $75** in the aggressive DIY case,
**$2k** if you want attorney review on the provisional.

This is the **Dropbox founder's path** — Drew Houston filed his
original Dropbox provisional pro se, used the priority date as the
basis of every subsequent filing. Priority date = value. Quality of
the provisional draft = lower bound on what you can later claim.

### 11a.7 What to do THIS WEEK if you want to move fast

1. **Write the provisional spec yourself.** One weekend's work if
   you pull from the existing `docs/` and `src/` artifacts. Target
   20–40 pages. (Already drafted — see
   `docs/working/patent/01-provisional-specification.md`.)
2. **Snapshot provenance artifacts** per §7.2 — git log, design-
   doc history, timestamped reference-implementation tarball.
3. **Register a USPTO Patent Center account** and claim
   micro-entity status.
4. **File the provisional.** Upload the packet, pay the $75
   micro-entity fee via credit card.
5. **Publish arXiv the next business day** after filing confirmation.

Total cash out-of-pocket: **$75** if DIY, up to **$2-3k** if you
want flat-fee attorney review on the draft.

### 11a.8 What's at stake if you skip filing entirely

- **Priority date lost.** Competitors could file first on a
  re-implementation of your method.
- **International rights forfeit** if paper publishes before filing.
  Most jurisdictions have absolute-novelty rules — no 12-month
  grace period.
- **Weaker enterprise licensing story.** The Temporal/Elastic
  pattern (§9) requires a patent backing the commercial-license
  indemnity tier. No patent → no premium tier.

**For $75, the priority date is yours to lose.**

---

## 11b. Utility-stage prosecution strategy — how to get to issued quickly

After the provisional is filed (§11a), the 12-month clock runs
before the utility application must be filed. Some scope decisions
at provisional time affect utility-stage approval speed. Here's
the strategy that lets the provisional be over-inclusive (maximum
priority coverage) while keeping the utility application on a
fast-issue trajectory.

### 11b.1 Why "fast approval" is a utility concept, not provisional

Provisionals are **not examined**. They just sit at USPTO for 12
months, establishing a priority date. There is no such thing as
"provisional approval" or "provisional rejection." Fast approval
is purely a utility-application-stage concept.

What this means: **the provisional specification can be as broad
and over-inclusive as we want without penalty**. §13 of the
provisional (Additional Embodiments) is explicitly designed to
over-disclose. The utility application, filed within 12 months,
will selectively narrow to a focused set of claims drawn from the
provisional's disclosure.

### 11b.2 Fast-track programs at USPTO (utility stage)

Three USPTO programs shorten the ~2-3-year standard examination
timeline to ~12 months:

- **Track One Prioritized Examination** (37 CFR 1.102(e)). File
  the utility with a `Track One` request; USPTO commits to a
  final disposition in 12 months. Fee: $4,200 (micro entity);
  $4,800 (small entity). Substantial but far cheaper than the
  "in-house counsel for 3 years" alternative.
- **Patent Prosecution Highway (PPH)**. If the utility has been
  favorably examined in any PPH partner office (EPO, JPO, KIPO,
  etc.), USPTO commits to expedited examination based on that
  prior examination. Often free if you're already filing
  internationally.
- **After Final Consideration Pilot (AFCP) 2.0**. Fast-pass for
  amendments submitted after a final rejection. Helps recover
  from a first-action rejection without restarting.

### 11b.3 Strategy: Track One utility in month 11

- Month 11: convert the provisional to a utility application.
- File utility under Track One at ~$4,200 fee (micro entity).
- Claim focus: the **strongest claim only** — the graduated-
  autonomy primitive with statistically-gated transitions
  (Candidate A from §0). Drop Candidate B (analyzer) from the
  utility's independent claims — file it as a continuation at
  month 12 if desired. **Keeping the main utility narrow and
  focused maximizes Track One approval speed.**
- Claim dependent sub-claims from the strongest-embodiment set
  (six-phase enumeration, McNemar test, self-rotating storage,
  safety-critical cap, circuit breaker).
- Expected: first Office Action around month 4-6, Notice of
  Allowance at month 10-12 assuming the claims are well-drafted.

### 11b.4 Claim-drafting rules that speed Track One approval

- **Keep independent claims narrow and concrete.** The broader
  the claim, the more likely it reads on prior art and triggers
  extensive Office Actions.
- **Tie every abstract element to a concrete technical improvement.**
  Reference §8 (measured latency, bounded regression probability,
  self-rotating storage). This is the core Alice-survival trick.
- **Use dependent claims for the ambitious coverage.** Independent
  claims are the narrow, defensible base; dependent claims add
  scope. If the broad dependent claims are rejected, the narrow
  independent claims can still issue.
- **Include method claims + system claims + CRM (computer-readable
  medium) claims in parallel.** This is the standard three-way
  split that survives patent-eligibility challenges across
  jurisdictions.
- **Provide a pre-drafted First Action Interview brief.** In the
  FAI pilot, the applicant can submit a proposed interview agenda
  in advance. Arriving at the examiner's desk with a thoughtful
  proposed-allowable-scope document often shortens prosecution
  by one round.

### 11b.5 Subtle provisional expansions (done in §13) preserve utility-stage optionality

The additional embodiments added to §13 of the specification are
each designed as follows:

1. **Each hedged with "in one embodiment" / "alternatively".** No
   single embodiment is claimed as essential, which preserves the
   ability to later claim narrowly around any subset.
2. **Each independently enabled.** Every expansion describes
   *enough detail* for a skilled practitioner to build it. This
   matters because utility claims must be enabled by the
   specification (35 USC 112); unenabled scope lapses.
3. **Each tied to a concrete technical improvement.** Section 13
   expansions name specific performance, safety, or efficiency
   benefits, preserving Alice-survival at utility stage.
4. **Extensions over existing concepts, not alternatives to them.**
   Section 13 adds to the six-phase primitive; it does not
   replace or contradict the core embodiment. This preserves a
   clean, focused primary claim path.

### 11b.6 Continuation / divisional strategy

[0150] After the utility application is filed, additional
applications can draw on the same priority date:

- **Continuation application**: same specification, different
  claims. Use this to pursue Candidate B (the analyzer) or any
  additional claim-group that wasn't in the initial utility.
- **Divisional application**: mandatory when the utility
  application receives a "restriction requirement" from the
  examiner (forced to pick one of several distinct inventions).
  Each divisional claims a different invention family.
- **Continuation-in-part (CIP)**: adds new matter beyond the
  provisional. Priority date for new matter is the CIP filing
  date, not the provisional date. Avoid unless adding material
  truly post-dates the priority.

Strategy: file the core utility (Candidate A only) at month 11
with Track One; file a continuation at month 11.5 for the
analyzer (Candidate B); consider CIPs in years 2-3 for new
inventions that build on Dendra.

### 11b.7 Rapid-iteration option: file multiple narrow provisionals

An alternative to the single broad provisional we've drafted:
file multiple *narrow* provisionals over time, each covering a
specific embodiment. Each new provisional establishes a priority
date for its specific subject matter. At month 12, file a PCT
application claiming priority from all of them.

**Why we chose the single-broad approach instead:**
- One $75 filing vs many $75 filings.
- One specification to maintain rather than a family.
- Single priority date simplifies the utility-stage narrative.
- The §13 expansions provide broad coverage within the single
  filing.

**When the multiple-narrow approach is better:** when inventions
are genuinely separate (e.g., Candidate A and Candidate D from
§0 are distinct enough that separate provisionals would be
cleaner). For this filing, combining both into one specification
is the right balance.

### 11b.8 Anti-circumvention claim strategy (how broad spec + narrow claims coexist)

The provisional adds §14 ("Anti-circumvention embodiments") and
§15 ("Functional definitions") specifically to cover competitors
who try to escape the patent by surface rearrangement. Those
additions do NOT slow utility-stage approval, because **the
spec's disclosure is never what the examiner searches against —
the claims are**. Here's how to exploit the asymmetry:

**At utility-conversion time (month 11):**

1. **Draft narrow independent claims against the preferred
   embodiment.** These are what Track One examines. Keep them
   concrete and tied to §8's measured improvements.
2. **Draft broad dependent claims that invoke §15's functional
   definitions.** Language like *"wherein the switch instance is
   any discrete unit of state carrying a phase, a rule tier, and
   an outcome log"* — anchored to §15 — preserves the ability
   to capture structural variations without an examiner objecting
   to ambiguity (because §15 defines the term).
3. **Draft a continuation application immediately** (month 11.5)
   that claims the anti-circumvention scope directly. The
   continuation shares the priority date from the provisional,
   so its claims read on §14's structural variations.

**Circumvention-family coverage summary:**

| Attack family | Provisional-spec coverage | Utility-claim strategy |
|---|---|---|
| API renaming (e.g., `@tier_switch` instead of `@ml_switch`) | §14.9 explicitly disclaims naming | Independent claim uses functional language; naming is irrelevant |
| Six-phase → N-phase | §15 "phase" = ordered set of cardinality ≥ 2 | Claim "a plurality of phases" (not "six") in independent claim |
| Statistical test substitution (chi-square, accuracy-margin, human-approval) | §14.3 covers evidence-based graduation | Dependent claim picks McNemar; independent claim picks "evidence-based criterion" |
| Storage-backend / rotation-scheme substitution | §13.6 + §14.4 | Functional claim: "a bounded, append-only outcome record store" |
| Construction-time → runtime / static / policy enforcement | §14.5 | Independent claim: "a safety-floor invariant enforced architecturally, whether at construction time, configuration load time, phase-transition time, or equivalent" |
| Microservice / workflow / event-bus decomposition | §14.1 | Independent claim uses functional "switch instance" from §15 |
| Ensemble / interpolated / hybrid decision-makers | §14.8 | Dependent claim captures single-decision-maker; broader dependent captures weighted combination |
| LLM-managed phase | §14.2 [0155] | Dependent claim expressly covers "phase selection by a language-model prompt" |
| Pure-ML deployment (drop rule) | Excluded — rule-floor is essential | Doesn't circumvent; lacks safety floor; not equivalent |

**The last row is important.** A competitor who drops the rule
floor entirely produces a *different* system — they do not
escape the patent, they practice a different (and worse) design.
An attempt to reach the invention's benefits (bounded regression
probability) requires a rule floor; without one, no bound. The
invention is therefore not a "design pattern among many" — it
identifies the specific architecture that provides the bounded
safety property, and competitors face a choice between
practicing the invention or giving up the safety bound.

### 11b.9 Why the §14 + §15 additions do NOT slow approval

Three reasons §14/§15 are free of downside to fast approval:

1. **Provisionals aren't examined.** The §14/§15 additions enter
   the record at the priority date and stay there as disclosure.
   They are not "claims" — they are "specification support." No
   examiner ever rejects a provisional, so there is no
   examination to slow.
2. **Utility independent claims are what Track One evaluates.**
   Our utility independent claims stay narrow and concrete per
   §11b.4. §14/§15 do not appear verbatim in those claims.
3. **§14/§15 disclosure strengthens §112 enablement arguments.**
   When the examiner asks "is the claim enabled?" the answer is
   "yes — the specification discloses [preferred embodiment] plus
   numerous variations in §14, each independently enabled." This
   *helps* approval, not hurts it.

**Risk mitigation — the "swiss cheese" concern.**
A specification with too many alternatives can (in rare cases)
invite an obviousness rejection: "the invention is just one among
many obvious variations." The §14/§15 text is drafted to avoid
this by:

- Framing variations as **alternative embodiments that practice
  the core invention** (never as "alternative inventions").
- Keeping the preferred embodiment clearly identified and
  primary.
- Describing the core architectural property (§14.14) explicitly
  so variations are clearly within-scope applications of one
  invention, not separate inventions.

### 11b.11 Timeline summary

```
Month 0    :  File provisional — $75 (§11a)
Month 0-11 :  Sell pilots, gather production data, iterate
              on design, measure real-world transition depths
Month 10   :  Engage attorney (~$5k-$10k for utility drafting)
Month 11   :  File utility + Track One request — $4,200 micro fee
Month 12   :  File PCT international — $5k
Month 13-16:  First Office Action (standard Track One timeline)
Month 17-20:  Response + amendment
Month 21-24:  Notice of Allowance (best case)
Month 24+  :  Patent issued — patent-marked products can begin
              using R-in-circle and patent-number marking
```

**Best-case outcome:** patent issued 24 months from the
provisional filing date.

---

## 11. What this analysis does NOT address

- **Trademark filings** for "Dendra," "transition curves" (service
  mark), "Axiom Labs." Separate trademark-counsel workstream.
- **Export-control review** for the sensitivity-router
  components (ITAR / EAR compliance) — if Dendra is distributed
  into dual-use scenarios, engage export-control counsel.
- **Copyright** — Apache 2.0 handles this. No further action.
- **Open-source license compliance** for shipped deps (sklearn MIT,
  datasets Apache, etc.). No conflicts observed.
- **Foreign filing license (FFL)** — USPTO requires 6-month
  domestic-priority window before foreign filing if inventive
  activity happened in the US. Attorney will handle.

---

## 12. Preliminary assessment

**File it.** Candidates A+B are genuinely novel, genuinely useful,
and tied to concrete technical improvements. The combined
provisional would cost ~$10k and lock in priority dates that are
strategically load-bearing for the 3-year business plan in
`business-model-and-moat.md`.

The **only load-bearing prerequisite is resolving UT IP ownership
(§7)**. Once that is resolved in writing, provisional filing can
happen within days.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). All
rights reserved. Pre-filing analysis — internal use only until
patent counsel engaged._
