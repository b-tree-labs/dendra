# Dendra brand-mark critic assessments

**Date:** 2026-04-22.
**Context:** 14 concept marks shipped in `feat/brand-concepts` PR #6
(4 original directions × 2-4 variants each). Three AI design critics
with distinct perspectives were asked to give their sharpest
assessment.

---

## Consensus in one paragraph

Three critics agree the **Gate** direction is strongest. Two pick
D1 (the original Gate) for craft and system-coherence reasons; one
picks D2 (Gate · Rising) for the semiotic argument the parted floor
carries. Unanimous vetoes on **A3 (Canopy)**, **C1 (Curve · 5 dots)**,
and **C3 (Curve · tick marks)**. The semiotics critic proposes a
fifth direction none of the four explored: **a 2×2 contingency
table** — the paper's actual McNemar matrix, one cell accent —
which pairs orthogonally with the B-Tree Labs cross and is the only
concept in the set whose geometry is the product's literal math.

Round 3 (applied after these assessments): a refined D1 with
Critic 2's three specific fixes, a refined D2 with its parted-floor
gap narrowed to exactly the accent stroke-width, and a new E ·
Contingency mark built from Critic 3's proposal.

---

## Critic 1 · Brand strategy + system coherence

**Top pick: D1 (Gate · original).**

> "The only mark in the set that reads as *architectural
> infrastructure* — a threshold, a ground, a passage — at 16 px, at
> 200 px, and five years from now when 'AI-branching-tree' marks
> look like a generation-tagged cliché."

**Specific refinements requested:**

1. Widen the posts — pull the lintel up ~40 px (y=160) and the
   accent tick up to ~y=72 so the gate has taller proportions
   (more torii, less TV-set).
2. Break the lintel-post joint perception — either inset the lintel
   by one stroke-width on each side, or commit to a butt-join with
   a tiny pin at each corner (echoing B-Tree Labs' center-node
   vocabulary). The latter gives Dendra *its own joint grammar*
   while staying in the family.
3. Thin the accent stroke by ~20% — currently reads as heavy as
   the structure. Make the passage feel like a *value being
   measured*, not a third post.

**Active vetoes:** A1 (the original Y — "every designer at a
due-diligence meeting will flag it"), A3 (canopy — "one clipart
step away from a wellness-brand logo"), C1 + C3 (curve variants —
"strung beads on a line is a sparkline, not a mark").

**On the exercise itself:**

> "The whole round is operating inside a narrow interpretation of
> 'graduated autonomy' and producing *literal diagrams* rather than
> marks. A, B, C are all essentially figure-1-of-the-paper redrawn
> with different art direction — and marks that illustrate the
> thing they're for age badly. Stripe's mark isn't a payment flow;
> Cloudflare's isn't a proxy cloud; Temporal's isn't a state
> machine. They're abstract containers that *earn meaning through
> the product*. The Dendra set is trying to pre-load meaning into
> the glyph, which is exactly the move mature infra brands don't
> make."

> "There's no designer in the loop. These are Claude-authored SVGs
> with `<line>` primitives at integer coordinates, 34 px stroke, no
> optical corrections, no kerning logic for the wordmark, no
> consideration of how the mark behaves in a favicon stack next to
> Chrome's rounded corners, no monochrome/inverse tests, no
> embroidery/etch test. You're A/B'ing fourteen *sketches*, not
> fourteen marks. Pick a direction here, then spend $6-12k with an
> identity designer — Hoodzpah, Character, or a solo like Mackey
> Saturday — for two weeks of refinement."

**Portfolio-fit ranking (best to worst fit alongside B-Tree Labs):**

1. D1 — Gate · original
2. D2 — Gate · rising
3. B3 — Ascend · stack
4. D3 — Gate · open
5. A4 — Dendrite · rooted
6. C2 — Curve · minimal
7. A2 — Dendrite · symmetric
8. B1 — Ascend · original
9. B2 — Ascend · compact
10. C4 — Curve · step-function
11. A3 — Dendrite · canopy
12. C3 — Curve · tick marks
13. C1 — Curve · original
14. A1 — Dendrite · original

---

## Critic 2 · Execution + craft

**Top pick: D1 (Gate · original).**

> "The only mark in the set that is architecturally defensible as a
> standalone glyph. The Π form is closed, symmetrical, and legible
> as a single silhouette — it owns a shape the way the B-Tree Labs
> cross owns a shape."

**Three specific production-readiness fixes:**

1. **Tighten the accent.** The orange tick runs from y=200 to y=96
   (104 px) — the same length as the posts' upper half. Shorten to
   ~72 px (y=200 → y=128) so it reads as "a short extension past
   threshold," matching the B-Tree Labs origin's +30 px accent
   proportion. Right now the tick over-dominates.
2. **Resolve the corner joins.** At the four inside corners where
   posts meet lintel, three 34-px square-capped strokes butt
   against each other and produce 17-px square nubs on the outside
   of each corner. Solve by merging the three strokes into a single
   polyline with `stroke-linejoin="miter"`.
3. **Add a 28 r graphite center node at the lintel midpoint.** The
   B-Tree Labs origin has a 28 r center dot; Dendra's brief insists
   on "same visual language." A node at (256, 200) becomes the
   threshold-crossing point and gives the accent tick something to
   emerge from instead of floating on the lintel stroke. This
   single addition ties Dendra to Axiom visually while keeping the
   glyphs distinct (cross vs gate).

**Small-size survivors (16 px):** D1, D3, A4, A2.
**Collapse into noise (16 px):** A3 (thorn bush), C1 (fuzzy worm
with TV-static dots), C3 (ticks disappear under ~24 px, leaving a
bare curve), B1/B2/B3 (banding), D2 (gate with vertical smear).

**Specific construction issues called out:**

- **A1:** accent runs at 45° not 30° — "reads as 'branch
  continues' rather than 'tip flares,' which makes the asymmetry
  look like an error, not an emphasis."
- **A2:** 32 r orange dot is visually heavier than the origin's
  28 r graphite node. "At 16 px this reads as a pie chart."
- **A3:** secondary branch angles aren't harmonic — one is ~53°,
  the other ~72°. "Looks computed because it was."
- **B* all:** dust-grey floor line at stroke-width 34 is the same
  weight as the content strokes. "It's not 'faint reference' —
  it's a full structural element pretending to be a hint. Halve
  the stroke (17) or drop to a 1-2 px hairline."
- **C1:** dot diameter (40) is larger than the curve's stroke
  (34), which inverts the figure/ground relationship.
- **C3:** "20-px ticks against a 34-px curve — 1.7:1 is the
  uncanny valley. Either match (both 34) or commit to 2:1 (17 vs
  34)."
- **C4:** miter joins at 34 px produce visible corner overshoots
  at every inside bend.
- **D2:** parting the floor at x=232/280 creates a 48 px gap that's
  wider than the 34 px accent passing through it — "the accent
  doesn't 'pierce' the floor, it walks through a doorway."
- **D3:** the orange tick endpoints (y=368 to y=128) aren't
  anchored to anything. "The tick floats."

**Scrap entirely:** A3, B3, C1, C3, D2.

---

## Critic 3 · Semiotics + meaning

**Top pick: D2 (Gate · Rising).**

> "The mark's argument: 'A floor exists, a threshold exists, and
> the thing that advances is evidence — a single stroke that begins
> below the floor, punctures it, and crosses the gate.' That is,
> almost literally, the theorem. The rule-floor is parted *by* the
> accent — the geometry asserts that the floor is not broken but
> crossed at a measured point, which is exactly what a McNemar
> rejection does to the null."

**First-read signification of each direction (what a cold viewer
actually reads, not what Ben intends):**

- **A · Dendrite:** Tree, Y, neural-net branching. "A cold VP Eng
  reads 'AI / decision tree / chatbot flow.' The etymological
  argument (δένδρον) is invisible to everyone who doesn't already
  know the name's origin — which is everyone outside the repo."
- **B · Ascend:** Bar chart. Progress. "'Number go up.' Reads as a
  KPI slide before it reads as a lifecycle. The six-ness is not
  legible at a glance; viewers count only if they're already
  primed."
- **C · Curve:** Hockey stick. J-curve. Growth. "The most
  culturally saturated shape in the entire tech-startup visual
  vocabulary — even readers who know Figure 1 will read 'growth
  chart' first and 'transition curve' second."
- **D · Gate:** Architecture. Threshold. Π / pi / portal /
  goalpost. "The only one of the four whose primary semantic field
  is *passage* rather than *progress* — and passage is what Dendra
  is actually about."

**Cliché risk per concept:**

- **Dendrite:** high and worsening. "In 2026 a branching node-graph
  mark reads 'LLM orchestration startup' before anything else, and
  the Canopy variant is two hops from a LangChain logo."
- **Ascend:** terminal. "A staircase of ascending bars is the most
  generic 'we grew' icon in SaaS, indistinguishable from a
  bar-chart favicon."
- **Curve:** severe. "An up-and-to-the-right arc with a dot at the
  peak is the literal platonic form of 'VC pitch deck.'"
- **Gate:** moderate. "Π-shapes risk reading as Stonehenge /
  Greek-temple / 'classical authority' kitsch, but the referent (a
  gate) is specific enough to Dendra's mechanism that the cliché is
  survivable."

**Which marks earn their specificity (are un-swappable with
generic AI branding):**

Only two of the fourteen couldn't be lifted wholesale into another
AI company's identity:

- **D2 · Gate · Rising** — "The parted floor is the mark's
  signature and it encodes a specific claim (evidence crosses a
  threshold, the floor is not removed). Swap it into a
  competitor's deck and it stops making sense."
- **A4 · Dendrite · Rooted** — distant second. "The *root splay*
  is the specific bit: it says 'the rule is under the ground, the
  ascent is above it.' Most viewers won't read that, but it's at
  least an argument."

**A fifth direction not explored (the one that might be strongest
of all):**

> "The contingency table. Dendra's entire mechanism is a
> paired-proportion test — a 2×2 of {rule_correct, rule_wrong} ×
> {ml_correct, ml_wrong}, where advancement depends on a specific
> asymmetry between the off-diagonal cells (b and c in McNemar's
> notation). *No one* in AI branding has claimed this shape. A mark
> built from a small square partitioned into four cells — three
> cells graphite, one cell (the b-cell: 'ml correct where rule was
> wrong') accent orange — would be the only logo in the category
> whose geometry is the product's actual math. It reads as a
> window, a pixel, a confusion matrix, a crosshair. It's distinctly
> *not* a tree, a chart, or a neural net. It pairs beautifully with
> the Axiom cross (both are orthogonal-axis marks with one accent
> cell off-center). And critically: a first-time viewer doesn't
> need to know McNemar to read it as 'four possibilities, one of
> them is what we're betting on' — which is, fundamentally, the
> pitch."

Built as `05-contingency-mark.svg` in response.

---

## Synthesis — what to do with this

**Three-critic math:**

| Critic | Top pick | Vetoes |
|---|---|---|
| 1 · Strategy | D1 | A1, A3, C1, C3 |
| 2 · Craft | D1 | A3, B3, C1, C3, D2 |
| 3 · Meaning | D2 | (implicit: A1-4, B1-3, C1-4, D1 all swappable) |

Unanimous vetoes: **A3, C1, C3.**
Near-unanimous on direction: **Gate.**
Real disagreement: D1 (craft-mature, silhouette-holds) vs D2
(carries-the-theorem, but construction issues).

**Round-3 moves (shipped in the same branch):**

- `04-gate-refined-mark.svg` — D1 with Critic 2's three fixes
  (shorter accent / polyline joins / center node at lintel midpoint).
- `04-gate-rising-refined-mark.svg` — D2 with the floor-gap
  narrowed to exactly the accent stroke-width (34 px), fixing
  Critic 2's construction complaint while preserving Critic 3's
  semiotic argument.
- `05-contingency-mark.svg` + `05-contingency-wordmark.svg` —
  Critic 3's proposed fifth direction built fresh.

**Recommended for Ben's decision:**

1. **D2-refined** if the mark should carry the theorem — semiotically
   strongest, now also production-clean.
2. **D1-refined** if the mark should prioritize craft and
   portfolio-sibling-grammar — most system-coherent with B-Tree Labs.
3. **E · Contingency** if the mark should be genuinely
   category-defining — the only one of the set whose geometry is
   the product's actual math.

Then spend real money on an identity designer to take the chosen
direction from sketch to production mark. Critic 1's estimate —
$6-12k for two weeks — is the right order of magnitude for any of
the three.

---

_Full critic transcripts available in git history; this file is the
summary of record._
