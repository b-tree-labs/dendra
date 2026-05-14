# Postrule · palette

Postrule inherits the B-Tree Labs palette exactly. Every color is
already defined and documented in the parent system at
`b-tree-labs/.github/brand/palette.md`. This file exists to
confirm Postrule uses the same values and to document any
Postrule-specific usage rules on top of the parent.

## Primary palette

| Role | Name | Hex |
|---|---|---|
| Ink | Graphite | `#1a1a1f` |
| Ground | Warm off-white | `#f8f6f1` |
| Accent | Burnt orange | `#BF5700` |

## Extended palette

| Role | Name | Hex |
|---|---|---|
| Ink soft | Graphite 70 | `#6a6a72` |
| Ground soft | Sand | `#efece6` |
| Rule line | Dust | `#d8d3c9` |
| Accent deep | Ember deep | `#8a3d00` |
| Accent wash | Ember wash | `#f4e4d8` |

## Postrule-specific usage

**The accent carries the theorem.** In the Postrule mark (D2' ·
Node), the burnt orange accent stroke is the evidence — the thing
that crosses the rule floor and passes through the phase gate.
Everywhere the accent appears, it is doing *semantic* work:
marking the thing being measured, the thing advancing, the thing
earning its graduation. It is never decoration.

**One accent per composition.** Same rule as the parent. Never
more than a single accent element in any Postrule asset.

**Accent on dark ground.** `#BF5700` holds its reading at a
contrast ratio of ~3.2:1 on `#1a1a1f` — WCAG-AA for non-text,
sufficient for brand elements. Do not substitute a brighter
dark-mode orange in asset exports without updating the brand
kit as a whole; `#BF5700` is the canonical accent in every mode.

## CSS tokens

```css
:root {
  --ink:          #1a1a1f;
  --ground:       #f8f6f1;
  --accent:       #BF5700;
  --ink-soft:     #6a6a72;
  --ground-soft:  #efece6;
  --rule:         #d8d3c9;
  --accent-deep:  #8a3d00;  /* accent hover / pressed */
  --accent-wash:  #f4e4d8;  /* background tints beneath accent */
}
```

## Contrast reference

| Foreground | Background | Ratio | WCAG |
|---|---|---|---|
| `#1a1a1f` | `#f8f6f1` | 15.3:1 | AAA (everything) |
| `#1a1a1f` | `#efece6` | 13.1:1 | AAA |
| `#BF5700` | `#f8f6f1` | 4.3:1 | AA (large text only) |
| `#BF5700` | `#1a1a1f` | ~3.2:1 | AA non-text only |
| `#6a6a72` | `#f8f6f1` | 4.8:1 | AA |

Body text is always graphite on warm off-white. Burnt orange is
an accent *shape*, never a text color outside display contexts.
