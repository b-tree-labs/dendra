# Dendra · typography

Dendra inherits the Axiom Labs typography system exactly.
`axiom-labs-os/.github/brand/typography.md` defines the source of
truth; this file documents Dendra's use of that system plus any
Dendra-specific overrides (none currently).

## Type stacks

**Display** (wordmarks, headings, figure titles):

```css
font-family: "Space Grotesk", system-ui, -apple-system, sans-serif;
```

- Weights: 400, 500, 700
- Wordmark: Medium (500), all caps, tracked 0.18em (`letter-spacing: 0.18em`)

**Body** (prose, captions, UI):

```css
font-family:
  -apple-system,
  "SF Pro Text",
  system-ui,
  "Segoe UI",
  Roboto,
  "Helvetica Neue",
  Arial,
  sans-serif;
```

Body intentionally uses the OS stack. A second display face would
add rendering weight without proportionate design value.

**Monospace** (code, numeric displays, diagnostics):

```css
font-family: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
```

## Type scale

Base 16 px. Ratio 1.25 (major third).

| Role | Size | Line-height | Weight |
|---|---|---|---|
| Display | 64 | 1.05 | 500 |
| H1 | 48 | 1.1 | 500 |
| H2 | 32 | 1.2 | 500 |
| H3 | 24 | 1.3 | 500 |
| H4 | 20 | 1.35 | 500 |
| Body | 16 | 1.55 | 400 |
| Caption | 13 | 1.45 | 400 |
| Micro | 11 | 1.4 | 500 tracked 0.05em |

## Wordmark typography

The DENDRA wordmark is Space Grotesk Medium (500), all caps,
tracked 0.18em. Identical treatment to the Axiom Labs wordmark
— same weight, same tracking. This is load-bearing for the
portfolio-sibling read: at a glance, "DENDRA" and "AXIOM LABS"
should feel like members of the same typographic family.

**Never:**

- Stretch, slant, or outline the wordmark typography.
- Use a weight other than Medium (500) for the wordmark.
- Reset the tracking. `0.18em` is what makes "DENDRA" look like
  the wordmark and not just the word.

**Do:**

- Outline text in production SVG exports (Inkscape: Path → Object
  to Path). Rendering-device font substitution is the #1 cause
  of wordmark drift.

## Paper / LaTeX

Dendra papers use the Axiom Labs preamble at
`axiom-labs-os/.github/brand/templates/axiom-labs-preamble.tex`
— serif body in TeX Gyre Pagella, Space Grotesk for figure labels
and titles. Academic-convention-compliant body + branded display.

## Matplotlib

See `brand/templates/dendra.mplstyle` when it lands. Figure 1 of
the paper and `dendra plot` outputs should adopt this style so
the transition curves rendered in the paper match the transition
curves rendered by the CLI.
