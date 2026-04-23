# Dendra · sub-brand lockup system

Every named Dendra product uses the same typographic lockup
pattern: the DENDRA wordmark (Space Grotesk Medium 108 px,
tracking 0.18em, graphite) followed by the product name (Space
Grotesk Regular 88 px, tracking 0.15em, ink-soft). The mark
appears at the left in the horizontal form as usual.

## Current lockups

| Lockup | File | Context |
|---|---|---|
| DENDRA CLOUD | `brand/logo/dendra-cloud-wordmark.svg` | The hosted SaaS offering when it ships (Y1 H2). |
| DENDRA ANALYZE | `brand/logo/dendra-analyze-wordmark.svg` | The static analyzer CLI — shipped today, free. |
| DENDRA INSIGHT | `brand/logo/dendra-insight-wordmark.svg` | The paid dynamic-analyzer tier (per business-model-and-moat.md §2.2). |
| DENDRA RESEARCH | `brand/logo/dendra-research-wordmark.svg` | Academic-adjacent contexts — paper covers, arXiv blog, benchmark pages. |

## Lockup rules

### Typographic hierarchy

- **Parent wordmark** DENDRA: Space Grotesk Medium 500, 108 px,
  tracking 0.18em, `#1a1a1f`.
- **Sub-brand name**: Space Grotesk Regular 400, 88 px, tracking
  0.15em, `#6a6a72`.

Why Regular 400 for the sub-brand: it creates clear hierarchy
(parent is heavier and larger) without changing the typographic
family. The color step (graphite → ink-soft) reinforces the
hierarchy visually. At a glance, viewers read DENDRA first and
"CLOUD" / "ANALYZE" second, which is the correct
parent-product relationship.

### Horizontal spacing

The sub-brand name begins at x=850 in the 1400×300 canvas — a
constant that assumes "DENDRA" typeset with the above parameters.
Do not change the spacing per sub-brand; a consistent gap across
all lockups is how the system reads as a family.

For short sub-brand names (e.g. "CLOUD", "ANALYZE"), 1400×300
canvas is plenty. For longer names ("RESEARCH"), use 1500×300
canvas. Names longer than 9 characters should be reconsidered —
"DENDRA RELIABILITY ENGINEERING" is not on-brand.

### Sub-brand naming discipline

Rules for adding a new sub-brand to the system:

1. **One word only.** DENDRA CLOUD — fine. DENDRA HOSTED SERVICE
   — not fine. If the product needs two words, either (a) pick a
   different single word, or (b) don't use a sub-brand lockup —
   use the parent DENDRA wordmark and put the product name in
   the running text.
2. **All caps, same typographic treatment.** No lowercase, no
   camelCase, no hyphens ("DENDRA-CLOUD"), no version numbers.
3. **Uppercase acronyms count as one word.** DENDRA ML is allowed
   if we ever have a reason. DENDRA SDK is allowed. DENDRA
   ACTIONS is allowed. "DENDRA API V2" is not (version number).
4. **No descriptors or modifiers.** DENDRA FAST, DENDRA PRO,
   DENDRA LITE — all off-brand. Pricing tier names go in the
   pricing table, not in the logo.

### When NOT to use a sub-brand lockup

- **Running text.** "Dendra Cloud is the hosted tier" is body
  copy, not wordmark usage. The lockup SVG is for headers,
  slide titles, product-page hero, navigation chrome — places
  where the logo treatment matters.
- **Pricing pages.** Use the parent DENDRA wordmark and list
  tier names in the body. "DENDRA TEAM" / "DENDRA PRO" / etc.
  are pricing tiers of DENDRA CLOUD, not independent sub-brands,
  and should not get their own lockups.
- **The open-source library.** The parent DENDRA wordmark is
  the right treatment for the library and all of its
  documentation. Do not make a DENDRA SDK lockup — the
  library IS Dendra.
- **Generic "Dendra something" uses.** A blog post titled
  "Dendra Graduated-Autonomy" is body copy with title case, not
  a wordmark. Don't try to lockup every phrase.

## Dark-ground variants

All sub-brand lockups should also ship in dark-ground variants
when used on dark backgrounds. The transformation mirrors the
primary wordmark's dark variant:

- Graphite strokes → off-white (`#f8f6f1`)
- Accent stroke stays `#BF5700`
- Threshold-crossing ring → off-white outline
- Parent wordmark text → off-white
- Sub-brand text → mid-gray (`#a8a8ae` instead of `#6a6a72` for
  better contrast against graphite)
- Ground fill → `#1a1a1f`

Dark variants are not yet exported — produce them when a dark
surface actually needs them. Current sub-brand lockups ship in
light-ground only.

## The parent brand's role

When DENDRA alone is used (no sub-brand), it refers to:
- The library (`pip install dendra`)
- The primitive / the method / the theorem
- The company (as a proxy for Axiom Labs' Dendra division)

When the sub-brand is used, the product is named explicitly. The
typographic hierarchy makes the parent-product relationship
legible without requiring a sibling-explanation.

## Co-branding with Axiom Labs

When Dendra and Axiom Labs appear together (portfolio pages,
investor decks, press releases introducing Dendra as "from Axiom
Labs"), follow the parent-subsidiary convention:

- Use the Axiom Labs horizontal wordmark in the footer / masthead.
- Use the Dendra horizontal wordmark in the hero / product area.
- Do not combine them into a single lockup ("AXIOM LABS · DENDRA"
  or similar) — they are meant to read as parent + product, not
  as a joint entity.
- Minimum 2× the mark's height of clear space between them.

## Versioning this system

This doc is the source of truth for sub-brand lockup design. If
a new sub-brand is added, add an SVG, update the lockup table,
and commit together. The system holds when all lockups look
like they come from the same family — not when they all have
custom treatments.
