# Dendra · motion guidelines

How Dendra animates. Which moves are on-brand and which aren't.

The Axiom Labs `usage.md` rule is "no animation beyond hover."
Dendra extends this narrowly: the mark has exactly **one
on-brand animation** — the accent rising through the gate — and
it is reserved for contexts where the animation does semantic
work. Everywhere else, the mark is static.

## The one animation: the rising accent

The accent orange stroke of the Dendra mark rises from below the
rule floor, parts the floor, passes through the phase gate, and
settles above the lintel. It is the theorem in motion.

**Timing:** 700 ms total, from first pixel to settled.
**Easing:** `cubic-bezier(0.2, 0.6, 0.2, 1)` — accelerates out
  of rest, then eases into the terminal position. Feels like
  "evidence accumulating and then arriving," not like a bouncing
  UI element.
**Hold:** 200 ms at the settled position before either restarting
  (loading state) or fading (success state).
**Reversal:** none. The accent never retreats. Dendra does not
  animate a phase going backward.

The canonical animated SVG is
`brand/logo/dendra-mark-animated.svg`. SMIL-based for universal
rendering — works in img src, object, inline embed, and CSS
backgrounds without any JavaScript dependency.

## When to animate

Animate only when the animation reinforces what the interface is
saying:

- **Loading state** for long-running Dendra operations — the
  analyzer running against a large repo, `dendra bench` running
  a benchmark, a phase-transition evaluation. The rising accent
  loops silently in the corner; the user's eye catches "something
  is happening, specifically something that ends with a phase
  transition."
- **First-render of the mark on the landing page's hero.**
  One play, then hold. Gives the mark a single quiet moment of
  life on first arrival, then stays static for the rest of the
  visit.
- **Phase-advancement confirmation in the Cloud dashboard.** When
  a switch advances to a new phase, the mark in the header plays
  the animation once as a subtle confirmation that the thing the
  product is fundamentally about just happened.

## When NOT to animate

- **In running text / inline.** Mark-in-prose is always static;
  a reader should not be distracted by motion while reading docs.
- **In the favicon / rounded tile.** Tabs and home screens are
  animation-hostile; a moving favicon is a dark pattern.
- **In paper figures, PDFs, or LaTeX output.** The paper is a
  static artifact. Animation does not belong there.
- **In logos embedded in third-party content** (conference
  slides, customer case-study decks) unless specifically licensed.
- **On hover over UI elements.** Hover states should use color
  or weight changes, not mark animation. The mark is not a
  button.
- **On scroll or in parallax.** Scroll-triggered mark animation
  reads as marketing theater. Dendra is not a landing-page
  animation exhibit.

The single rule to remember: **the rising accent means "a phase
transition is happening."** If that isn't what the UI is saying,
don't play it.

## Canonical easing curves

All Dendra UI motion (the mark's rise, button hover transitions,
section reveals, etc.) uses one of three curves:

| Name | CSS | Use |
|---|---|---|
| `dendra-rise` | `cubic-bezier(0.2, 0.6, 0.2, 1)` | The accent rising. Any "advancement" animation. |
| `dendra-settle` | `cubic-bezier(0.4, 0, 0.2, 1)` | Button hover, link underline. Symmetric in/out. |
| `dendra-snap` | `cubic-bezier(0.4, 0, 1, 1)` | Dismiss, close, collapse. Quick exit, no anticipation. |

## Durations

- **Micro-interaction** (hover color, button press): 120 ms
- **Transition** (panel open/close, section reveal): 240 ms
- **Mark animation** (full rising-accent cycle): 700 ms
- **Loading loop** (if looping the mark animation): 1500 ms total
  per loop (700 rise + 200 hold + 600 fade-and-reset)

No motion ever runs longer than 1500 ms. Anything that needs
to persist uses a stop-state, not a continuing animation.

## Reduced motion

Respect `prefers-reduced-motion`. When set, the mark animation
renders as a static first-frame or jump-to-settled. The
canonical animated SVG includes a `@media (prefers-reduced-motion)`
fallback inside a `<style>` block.

```svg
<style>
  @media (prefers-reduced-motion: reduce) {
    .dendra-accent-rising { animation: none; transform: none; }
  }
</style>
```

All CSS-driven motion on the landing page should respect the
same rule:

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

## Audio

Dendra does not have a sonic identity. The mark has no
accompanying sound effect. Video and product demos may include
spoken narration; they do not include a Dendra chime, whoosh,
or click.

## Motion debt — things we'll revisit after a designer engages

- Hand-tuned Bezier for the accent rise (the current curve is
  mechanically sensible but not designer-tuned).
- Frame-by-frame examination of the rise at 16 px favicon size
  (does the animation read? does it just look like jitter?).
- A separate "error / circuit-breaker-tripped" motion — what
  does it look like when the ML head fails and the rule takes
  back over? A reverse rise? A shake? Currently undefined.
- Video brand — opening and closing frames for screencast demos.
  Consistent enough to be recognizable without a logo ident at
  the start.
