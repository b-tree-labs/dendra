# Postrule · accessibility

How the Postrule brand system holds up when accessibility matters.
This doc is a reference for designers, developers, and marketers
using the kit — if you're adding a new asset, check it against
the rules here before shipping.

## Contrast ratios

Every contrast ratio below is measured per
[WCAG 2.1 relative luminance](https://www.w3.org/WAI/GL/WCAG20/tests/test-contrast-ratio.html).
Body-text contrast targets AA minimum (4.5:1 for normal text,
3:1 for large text); non-text UI elements target 3:1 minimum.

### Primary palette pairings

| Foreground | Background | Ratio | WCAG result |
|---|---|---:|---|
| Graphite `#1a1a1f` | Off-white `#f8f6f1` | 15.3 : 1 | AAA for all text sizes ✓ |
| Off-white `#f8f6f1` | Graphite `#1a1a1f` | 15.3 : 1 | AAA for all text sizes ✓ |
| Accent `#BF5700` | Off-white `#f8f6f1` | 4.3 : 1 | AA for **large text** and **non-text** ✓ — **fails** AA for body text |
| Accent `#BF5700` | Graphite `#1a1a1f` | 3.5 : 1 | AA for **non-text UI** ✓ — **fails** AA for text |
| Ink-soft `#6a6a72` | Off-white `#f8f6f1` | 4.9 : 1 | AA for normal body text ✓ |
| Accent-deep `#8a3d00` | Off-white `#f8f6f1` | 7.6 : 1 | AAA for body text ✓ |
| Rule `#d8d3c9` | Off-white `#f8f6f1` | 1.3 : 1 | **For separators only** — not text |

### What the ratios mean in practice

- **Body copy is always graphite on off-white** or off-white on
  graphite. Both are AAA. No exceptions.
- **Accent `#BF5700` is a shape, not a text color.** Use it for
  the mark's accent, borders, icons, and the occasional large
  display text. For link text or body text where orange is
  needed, use **accent-deep `#8a3d00`** — it's AAA on light
  ground and 2.2 : 1 against dark, so still avoid on dark
  backgrounds.
- **Captions, metadata, labels** (anything secondary) use ink-soft
  `#6a6a72`. At 4.9 : 1 it passes AA for normal body text.
- **Rule `#d8d3c9`** is for hairlines and dividers only. It does
  not pass AA for any text size.

### Dark-mode notes

On graphite ground:
- The three structure cells of the mark render as off-white at
  15.3 : 1 contrast — visibly clear.
- The accent at 3.5 : 1 is below body-text AA but within non-text
  AA. That's adequate for brand elements. Do NOT put body text in
  `#BF5700` on graphite.
- For dark-mode body text that must be warm (rare), use
  accent-wash `#f4e4d8` or a brighter custom orange — document
  the choice here when introduced.

## Color-blindness behavior

Burnt orange `#BF5700` holds identity across the three common
color-vision deficiencies:

| Deficiency | Affected receptor | Accent appears as | Still distinguishable? |
|---|---|---|---|
| Deuteranopia (red-green) | M (green) | Muddy yellow-brown | Yes — the accent is still clearly different from graphite and off-white |
| Protanopia (red-green) | L (red) | Darker yellow | Yes — distinguishable |
| Tritanopia (blue-yellow) | S (blue) | Nearly unchanged | Yes |

The mark's semantic layer (structure cells vs accent) is preserved
for color-blind viewers — the accent is identifiable by its
position (top-right cell, or rising stroke through the gate) as
much as by its hue. This is load-bearing: **never rely on color
alone to communicate the accent's role**. The geometry does the
primary work.

### For charts + figures

When `postrule plot` or `matplotlib` outputs use the accent orange
for a data series:

- Use a distinct line style (dashed, dotted) in addition to color
  when ML-head and rule-baseline series are both plotted.
- In the paper's Figure 1 specifically, the ML line is solid
  orange and the rule baseline is a horizontal dashed graphite
  line — both the color AND the dash-pattern distinguish them.

## The mark at small sizes

At 16 px favicon:
- The rounded graphite tile carries the identity (most of what's
  legible at that size is the tile's silhouette + the orange
  accent cell).
- The gate structure is not individually resolvable — it reads as
  a dark tile with an orange dot / line near the center.
- This is intentional; the favicon is not meant to convey the
  full semantic. At 32 px and above, the gate structure resolves.

**Do not ship the mark without the rounded tile at favicon sizes.**
The plain `postrule-mark.svg` on a transparent background becomes
illegible below ~32 px. Use `postrule-favicon.svg` (the rounded
graphite tile variant) for anything under 32 px.

## Alt text conventions

All Postrule marks, wordmarks, and composite assets need alt text
when embedded in documents, emails, slides, and web pages.

| Asset | Recommended alt text |
|---|---|
| Mark alone | `Postrule mark` |
| Mark (decorative, with visible wordmark nearby) | `""` (empty — use `aria-hidden="true"` too) |
| Horizontal wordmark | `Postrule` |
| Stacked wordmark | `Postrule` |
| Sub-brand lockup (e.g. Cloud) | `Postrule Cloud` |
| Social card | `Postrule: self-taught classifiers — the graduated-autonomy primitive for production classification` |
| Favicon / tile | usually omitted (favicons are decorative context for the page title) |
| Animated mark | `Postrule mark (animated)` — include the (animated) hint for screen-reader users |

**Do NOT** use alt text like "logo," "icon," "image of mark," or
decorative descriptors. Alt text is meaning, not description.

### When to use `aria-hidden="true"`

When the mark appears *next to* a wordmark that is text (like in
the site header), the mark is decorative — the textual "POSTRULE"
is the actual content. In that case:

```html
<a href="/" class="wordmark" aria-label="Postrule home">
  <img src="./postrule-mark.svg" alt="" aria-hidden="true" />
  <span>POSTRULE</span>
</a>
```

The link's aria-label gives the screen-reader the meaning; the
mark is skipped as decorative chrome.

## Font accessibility

- **Space Grotesk** (primary display) — open-source, SIL OFL 1.1.
  Loads from Google Fonts or can be self-hosted. Has full Latin
  Extended character set. No RTL glyph set — for Arabic / Hebrew
  headings, the body-text stack's `system-ui` fallback is used.
- **System body stack** — inherits whatever the OS provides. This
  is a deliberate choice: users' own font preferences and
  accessibility settings (dyslexia fonts, increased character
  spacing, larger base size) apply naturally.
- **JetBrains Mono** — monospace with excellent legibility at
  small sizes and strong disambiguation between `l`, `1`, `I`,
  `0`, `O`. Open-source, SIL OFL 1.1.

### Font size minimum

Body text is 16 px base. Secondary text is 13 px. **Never use
smaller than 11 px** in Postrule interfaces — anything smaller
fails normal-vision reading at typical viewing distances and
cannot be rescued by Postrule's ink-soft color choice.

## Motion accessibility

The mark has one animation — `postrule-mark-animated.svg` —
triggered for specific UI states (loading, first-render,
phase-transition confirmation). All Postrule motion:

- Respects `prefers-reduced-motion: reduce` — reduced-motion
  viewers see the settled-state mark, not the rising animation.
- Runs at 700 ms or less per cycle; no slow "breathing" or
  persistent animations that demand attention.
- Never flashes / strobes — no motion exceeds 3 flashes per
  second (WCAG 2.3.1 photosensitive-seizures guideline).

See `brand/motion.md` for the full motion spec.

## Focus states

Interactive elements (buttons, links) in Postrule's web UI get
a visible focus ring. The landing page CSS uses `:focus-visible`
with a 2-px accent-orange outline — 3 : 1 against off-white,
3.5 : 1 against graphite. Always visible, never display:none.

## Touch-target size

On mobile: interactive elements in Postrule UIs (landing page
buttons, navigation links, install-command blocks) are minimum
48×48 px — matches the WCAG 2.5.5 target-size guideline and the
Apple/Android platform minimums.

## Documentation accessibility

Markdown docs in this repo target:
- Headings are nested, not skipped (h1 → h2 → h3, no h1 → h3).
- Code blocks have language tags for syntax highlighting.
- Tables have header rows.
- Images have alt text per the table above.
- Links are descriptive — "see the paper" not "click here."

---

**If you find an accessibility issue with a brand asset**, file
it at https://github.com/b-tree-labs/postrule/issues with the
`a11y` label. Explicit, reproducible bug reports are strongly
preferred over vague "this is hard to see" reports.
