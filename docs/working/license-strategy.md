# Dendra — License Strategy (Decision Record)

**Decision date:** 2026-04-22.
**Decided by:** Benjamin Booth (sole inventor, B-Tree Ventures, LLC).
**Status:** Decision locked. Implementation (repo changes) follows
this document. Supersedes the Apache-2.0-throughout posture in
`entry-with-end-in-mind.md` §2 and the Apache-only framing in
`patent-strategy.md` §9.

---

## Decision

Dendra ships under a **split-license** posture from its first
public commit:

- **Apache 2.0** on the client SDK surface — everything a customer
  imports into their production process.
- **Business Source License 1.1 (BSL)** on the analyzer, server,
  and cloud-facing components, with an automatic **Change Date of
  2030-05-01** and **Change License of Apache 2.0**.

This replaces the original "Apache 2.0 on the entire repository"
plan.

---

## Rationale

### The trigger: the provisional changes the calculus

Before the provisional was filed (2026-04-21), Apache 2.0 was
load-bearing for two reasons: (1) citation velocity and primitive
positioning, (2) *defensive* — permissive licensing was the only
instrument available to preserve first-mover brand in the absence
of IP protection.

With the provisional in hand, reason (2) is obsolete. Patent
priority now does the defensive work that permissive licensing
used to do. That frees us to re-derive the license choice from
scratch rather than inheriting it from pre-patent constraints.

### Why not stay Apache 2.0 throughout

The `patent-strategy.md` §9 characterization —
"Apache 2.0 + patent = the Temporal / Elastic / MongoDB pattern" —
overstates how much commercial-licensing leverage this posture
actually retains:

- **The Apache 2.0 license includes a patent grant.** Section 3
  grants every recipient a perpetual, worldwide, royalty-free
  patent license covering the licensor's contributions. In
  practice, every `pip install dendra` user receives a patent
  license to practice the invention as embodied in the code they
  received.
- **The patent therefore only has teeth against adopters who
  don't use our code** — a vanishingly small commercial market.
  Independent re-implementers exist, but they are rare; the
  typical commercial-cloud competitor forks the Apache code
  rather than re-implementing.
- **Elastic, MongoDB, and HashiCorp all moved away from Apache**
  (to SSPL, SSPL, and BSL respectively) precisely because the
  Apache patent grant left them unable to prevent AWS /
  hyperscalers from offering hosted versions of their product.
  "Apache 2.0 + patent indemnity tier" is a real product — it
  sells indemnification against *third-party* patent suits — but
  it is not a lever against competitor clouds.

### Why BSL specifically (not SSPL, ELv2, MPL, proprietary)

Evaluated alternatives:

| License | Readable code? | Cite velocity | Competitor-cloud block | Enterprise acceptability | Converts back? |
|---|---|---|---|---|---|
| Apache 2.0 | Yes | High | **No** | Very high | N/A |
| **BSL 1.1** | Yes | High | **Yes** (during BSL window) | High (HashiCorp, CockroachDB, Sentry, Couchbase all ship BSL into F500) | **Yes** — automatic on Change Date |
| SSPL | Yes | Medium | Yes | **Low** (OSI-rejected; many F500 procurement policies block) | No |
| ELv2 | Yes | Medium | Yes | Medium | No |
| MPL 2.0 | Yes | High | No | High | N/A |
| Proprietary / source-closed | No | **None** | Yes | Depends on contract | N/A |

**Why BSL wins the tradeoff:**

1. **Code stays readable on GitHub.** Auditability preserved.
   Cite velocity preserved — papers can still cite line numbers.
   Training-data presence in Claude/Cursor/Copilot preserved.
2. **Commercial-production carve-out blocks hyperscaler clones**
   during the protection window without requiring legal
   enforcement of the patent. The Change Date (2030-05-01) is a
   hard-coded conversion to Apache 2.0 — four years is enough
   time for the corpus / federation / domain-pack moat bricks
   to solidify.
3. **BSL is a known quantity in enterprise procurement as of 2026.**
   HashiCorp Terraform, CockroachDB, MariaDB MaxScale, Couchbase,
   Sentry — all ship BSL. None have serious procurement blockage
   outside a handful of OSS-purist buyers. The population of
   prospects who accept BSL but reject SSPL is large.
4. **Reversibility.** BSL's automatic Change License is a promise
   to the community that the code becomes Apache 2.0 after the
   window expires. This preserves the "we're a primitive" moral
   framing even while gating near-term monetization.

### Why split, not monolithic

Putting the whole repo under BSL would cost us the primitive
positioning: developers would be reluctant to `import dendra`
into their production codebase if the license blocked
"commercial production use" at any interpretation. The split
preserves `pip install dendra` as a no-friction adoption path:

- **Client SDK stays Apache 2.0.** The code that ships into a
  customer's production process is unambiguously free for any
  commercial use. This is what gets imported, cited, embedded,
  and trained on.
- **Server / analyzer / cloud is BSL.** The code that runs
  *for* customers (rather than *inside* customers) is what
  needs monetization protection. It is also the code that
  naturally scales as our commercial offering, so licensing it
  differently creates no developer-facing friction.

This is the modern "SDK Apache, server BSL" split — the same
pattern Sentry and Plausible Analytics use. Cal.com uses a
similar client/server split via AGPL → commercial dual license,
which we considered and rejected as procurement-unfriendly.

---

## Mechanics — which files go where

Mapping based on current `src/dendra/` layout as of 2026-04-22.
The principle: **if the code runs inside a customer process, it
stays Apache; if Dendra runs it for a customer, it becomes BSL.**

### Apache 2.0 (customer-embedded — unchanged from today)

These modules live inside a customer's Python process when they
`pip install dendra` and call `@ml_switch`:

- `src/dendra/__init__.py` — top-level surface.
- `src/dendra/core.py` — `Phase` enum, `SwitchConfig`, switch
  construction.
- `src/dendra/decorator.py` — the `@ml_switch` entry point.
- `src/dendra/wrap.py` — wrapping / binding helpers.
- `src/dendra/storage.py` — append-only outcome log with
  rotation (runs inside customer process).
- `src/dendra/llm.py` — LLM-adapter interface invoked from
  customer code.
- `src/dendra/ml.py` — ML-head interface invoked from customer
  code.
- `src/dendra/telemetry.py` — telemetry emitter (runs inside
  customer process; customer controls where metrics ship).
- `src/dendra/viz.py` — Figure-1 transition-curve plotter
  (primarily used for the paper and for customer's own post-hoc
  analysis; Apache for scientific reproducibility).
- `src/dendra/benchmarks/**` — public-benchmark loaders and
  rule registries (Apache for paper reproducibility).
- `src/dendra/py.typed` — marker file.
- `tests/**` for the above.

### BSL 1.1 (Dendra-operated surfaces — change from today)

These modules form the commercial product surface — the
analyzer, the ROI reporter, the CLI that drives paid features:

- `src/dendra/analyzer.py` — the static+dynamic analyzer.
  Corresponds to Candidate B in the patent. This is the
  lead-gen scanner that compounds into the corpus moat; it is
  also the natural paid product ("Dendra Insight").
- `src/dendra/roi.py` — self-measured ROI reporter.
- `src/dendra/research.py` — research / graduation
  recommendation tooling.
- `src/dendra/cli.py` — the CLI. Currently dispatches to both
  Apache and BSL functions; during the split, we'll either
  (a) leave the dispatch shim Apache 2.0 and gate BSL commands
  at runtime, or (b) split into `dendra-cli` (BSL) and a
  minimal `dendra` Apache shim. Preferred option: (a) —
  simpler, and the dispatch shim itself is trivial. The BSL
  grant in the per-file header is what controls.
- Future hosted / server components (Dendra Cloud, hosted
  analyzer, domain-pack distribution service) — all BSL from
  creation.

### Edge cases noted for the implementation pass

- **`src/dendra/research.py`** — unclear-purpose file; verify
  whether its functions are imported from customer process
  (Apache) or only from CLI / analyzer (BSL) before finalizing
  its license bucket.
- **Tests** follow the license of the code they test. Tests
  for `analyzer.py` are BSL; tests for `core.py` are Apache.
- **Domain packs** (year 1 ships `support-triage`, `content-
  moderation`): client-embeddable packs ship Apache 2.0; the
  training pipelines and the curated evaluation corpora are
  **proprietary / commercial-licensed only** — neither Apache
  nor BSL. Domain-pack distribution is the revenue floor.
- **Benchmarks (`src/dendra/benchmarks/`)** — Apache 2.0. Paper
  reproducibility is load-bearing for the primitive endgame.
- **Docs and marketing** (`docs/**`) — current working-doc
  headers are "Apache 2.0 licensed" or "internal only." Keep
  both — internal strategy docs stay internal; published docs
  (README, API reference) stay Apache-adjacent-CC.

---

## The Change Date and Change License

BSL requires two fields beyond the license grant:

- **Change Date: 2030-05-01** — four years from launch,
  minimum permissible under BSL terms. Picked as the *shortest*
  conversion window rather than the longest; the point is to
  gate hyperscaler competition during the moat-build window, not
  to hoard the code in perpetuity.
- **Change License: Apache 2.0** — after the Change Date, each
  commit reverts to Apache 2.0 automatically. This is a promise
  to the community that we are not taking OSS-adjacent code
  private; we are taking a time-limited commercial gate on the
  commercial-product-surface code.

Each BSL-licensed file gets a header block:

```
Licensed under the Business Source License 1.1 (the "License").
You may not use this file except in compliance with the License.
You may obtain a copy of the License at docs/licenses/BSL.txt.

Change Date:    2030-05-01
Change License: Apache License, Version 2.0

Additional Use Grant: You may make production use of the
Licensed Work, provided that you do not offer a commercial
product or service that is substantially similar to Dendra's
hosted analyzer, hosted outcome store, or hosted
graduation-recommendation service.
```

The **Additional Use Grant** narrows "non-production" (BSL's
default restriction) to something compatible with developers
running the analyzer against their own code in production — the
thing we *want* them to do. The only use restricted is running a
*competing* hosted analyzer service.

---

## What this changes in existing docs

Updates required before public launch:

Implementation status as of 2026-04-22 (branch
`chore/split-license`):

- [x] `LICENSE-APACHE` — Apache 2.0 text at repo root (preserved
      verbatim from prior `LICENSE`).
- [x] `LICENSE-BSL` — BSL 1.1 at repo root. Canonical MariaDB
      Notice/Terms text preserved from Terraform's LICENSE as
      the template; Dendra-specific Parameters (Licensor,
      Licensed Work, Additional Use Grant, Change Date, Change
      License) filled in. No separate `docs/licenses/BSL.txt` —
      consolidated into `LICENSE-BSL` to avoid duplication.
- [x] `LICENSE.md` — top-level split explainer pointing at
      `LICENSE-APACHE` and `LICENSE-BSL`.
- [x] `LICENSING.md` — developer-facing plain-English Q&A on
      "can I use this?"
- [x] Per-file BSL headers on `src/dendra/{analyzer,roi,research,
      cli}.py` and their test files
      `tests/test_{analyzer,roi,cli}.py`.
- [x] `pyproject.toml` — PEP 639 SPDX expression
      `Apache-2.0 AND LicenseRef-BSL-1.1`, `license-files` glob
      covers all five license files.
- [x] `NOTICE` — split-aware notice pointing at LICENSE.md.
- [x] `README.md` — "## Licensing" section replacing the old
      "## IP" section; footer updated to reflect split.
- [x] `docs/marketing/entry-with-end-in-mind.md` §4 — bullets
      updated (no-closed-source + SSPL-only exclusion).
- [x] `docs/working/patent-strategy.md` §9 — 2026-04-22 update
      note prepended; text revised to reflect split-license
      mechanics; HashiCorp / CockroachDB / Sentry identified
      as end-state analog.
- [x] `docs/marketing/business-model-and-moat.md` §3.1 — OSS
      library row clarifies Apache SDK + BSL analyzer/server.
- [ ] **Follow-up:** split `tests/test_telemetry_and_research.py`
      into `test_telemetry.py` (Apache, tests `telemetry.py`)
      and `test_research.py` (BSL, tests `research.py`).
      Currently left intact as a mixed-license file — it stays
      Apache-header-only and tests a BSL module; this is a
      pragmatic compromise pending follow-up.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Developer backlash on HN day one ("BSL is not open source!") | Medium | Pre-write a FAQ entry; point to HashiCorp / Sentry / CockroachDB as well-adopted precedents; note the automatic Apache 2.0 conversion |
| Enterprise procurement rejects BSL | Low–medium | BSL has a track record in F500; offer commercial licensing (remove BSL restrictions) at the Enterprise tier |
| Client SDK and BSL server drift apart due to maintenance neglect | Low | Single repo, shared CI, shared release process; keep the split at the file/module level rather than the repo level |
| Confusion about "can I use this for my own business?" | Medium | The Additional Use Grant explicitly allows production use — the only prohibited use is a *competing hosted service*. Make this prominent in `LICENSING.md` |
| We change our minds later and want to relicense | Low | All contributors required to sign an ICLA (see Month-1 work on CLA in the roadmap); B-Tree Ventures retains assignment, so relicensing is always possible if facts change |

---

## What this does NOT decide

Explicitly left open for later:

- **Trademark strategy** — see `trademark-strategy.md` (new doc
  being drafted in parallel).
- **Contributor License Agreement (CLA)** — needed before
  taking external contributions. Use the Apache ICLA template;
  flesh out in a Month-1 work item.
- **Commercial-license terms for Enterprise** — a separate
  agreement layered on top of BSL. Covers SOC 2 artifacts,
  indemnity, priority support; drafted closer to first
  Enterprise deal.
- **Export-control review** (ITAR / EAR) for the signed
  outcome log — preserved from `patent-strategy.md` §11.
  Not license-blocking but a year-2 item for regulated
  customers.

---

## Decision log

| Date | Change | Author |
|---|---|---|
| 2026-04-20 | Original plan: Apache 2.0 throughout | Ben |
| 2026-04-22 | Switch to split-license Apache + BSL | Ben |

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Internal strategy document. This document describes the
licensing intent and is itself licensed under CC-BY 4.0 once
published alongside `LICENSING.md` in the public repo._
