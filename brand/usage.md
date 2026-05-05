# Dendra · usage rules

Dendra-specific rules for the mark, wordmark, and brand assets.
Inherits all non-specified rules from `b-tree-labs/.github/brand/usage.md`.

## The mark

Dendra's mark is the **D2' · Node** glyph: a rule-floor (parted
at the accent), two gate posts, a lintel, a hollow 28-r ink ring
at the threshold-crossing point, and an accent-orange vertical
stroke rising from below the floor through the gate.

Composition semantics:

- **Rule floor** = the hand-written rule that always exists as the
  safety floor.
- **Gate** (posts + lintel) = the statistical test that gates phase
  advancement.
- **Ring at the crossing** = the threshold-crossing moment — the
  McNemar rejection event. Hollow so the accent passes through,
  not covered.
- **Accent stroke** = evidence; the thing being measured; the
  thing that rises through the gate when the threshold is cleared.

The ring uses the same 28-r measurement as the B-Tree Labs origin
mark's center node — this is the portfolio-sibling kinship tie.
Do not resize the ring independent of the rest of the mark; it
carries a specific structural relationship.

## Clear space

Minimum clear space around the mark = the height of the mark's
threshold-crossing ring (~56 px on a 512 viewBox, or ~11% of the
mark's total height). No typography, image, or edge may enter
this zone.

## Minimum size

| Use | Min size |
|---|---|
| Favicon | 16 × 16 px |
| UI avatar | 32 × 32 px |
| Print | 0.25 inch across |

At sizes below 16 px, use the `dendra-favicon.svg` (rounded tile)
variant — it's vertically recentered and sized for pixel density
at small sizes.

## Mark vs wordmark

| Context | Use |
|---|---|
| GitHub avatar, app icon, favicon | `dendra-favicon.svg` (rounded tile) |
| Website header, README hero, slide titles | `dendra-wordmark-horizontal.svg` |
| Book cover, poster, square social | `dendra-wordmark-stacked.svg` |
| Running text | Never use the mark inline. Write "Dendra" in the body font. |
| On a dark ground (e.g. terminal hero, night-mode doc) | Use the `-dark` variant of the asset |

## Mark on dark ground

Use `dendra-mark-dark.svg` (or the `-dark` variant of any
composite asset). Structure strokes invert to warm off-white
(`#f8f6f1`); the threshold-crossing ring also inverts. The accent
stays `#BF5700` in both modes — do not switch to a brighter
dark-mode orange without updating the canonical palette.

## Monochrome

For print, embroidery, single-color rendering contexts:

- `dendra-mark-mono-light.svg` — all graphite, no accent
- `dendra-mark-mono-dark.svg` — all warm off-white, no accent

Monochrome loses the accent-as-evidence semantic layer — the mark
still reads as a gate-with-a-crossing, but without the
accent-vs-structure argument. This is an accepted trade-off per
B-Tree Labs precedent. Do not substitute a second color (e.g.
accent-in-gray-tone) to try to preserve the distinction — mono
means mono.

## Don'ts

- **Don't rotate the mark.** It has a meaningful orientation —
  the accent rises from below the floor to above the lintel.
  Upside down is a different mark.
- **Don't recolor the mark outside the palette.** Graphite on
  off-white is the default; inverted on graphite is the alternate;
  monochrome versions are for single-color contexts.
- **Don't fill the threshold-crossing ring.** It's hollow for a
  reason — a filled dot would cover the accent and freeze the
  rising gesture.
- **Don't place the mark on a busy photograph without a scrim.**
  The accent's contrast can be swallowed by competing warm tones.
- **Don't resize the ring relative to the rest of the mark.** The
  28-r measurement is structural, not decorative.
- **Don't add a drop shadow, bevel, or glow.** The mark is flat.
- **Don't crop the mark.** Use the masters at
  `brand/logo/dendra-mark*.svg`.
- **Don't reconstruct the mark from primitives in downstream
  tools** (Keynote, PowerPoint, Word). Import the SVG or PNG;
  never redraw.

## Mark-in-running-text conventions

In body prose, refer to the product as "Dendra" (body font, no
styling). The first mention in a document may include the ™
symbol if registration hasn't completed; post-registration it
becomes ®. Current: pre-registration, use ™.

**Correct:** Dendra is a classification primitive...
**Also correct (first mention):** Dendra™ is a classification primitive...
**Incorrect:** **DENDRA** is a classification primitive... (wordmark treatment doesn't belong in running text)

## Relationship to the parent brand

Dendra is a product of **B-Tree Labs**, which is the commercial
vehicle of B-Tree Ventures, LLC. The Dendra mark is a distinct
glyph in B-Tree Labs' visual language — same palette, same
34-px square-capped stroke weight, same 28-r node measurement
(used here as a ring rather than a dot). The two marks share
ancestry but are not variations of one another.

When the two brands appear together (co-branded content,
portfolio pages), use the horizontal wordmark for Dendra and the
B-Tree Labs horizontal wordmark at the same baseline, with a
minimum 2× clear space between them.

## Trademarks

DENDRA and B-TREE LABS are trademarks (or pending trademarks) of
B-Tree Ventures, LLC. The mark and wordmark are subject to the
trademark policy at `TRADEMARKS.md` in the repository root.
