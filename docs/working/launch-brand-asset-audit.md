# Brand asset audit — launch readiness

Inventory + launch-day classification of every asset in `brand/`.
Categorized by:

- **LAUNCH** — needed for May 13. If missing or broken, blocks launch.
- **POST-LAUNCH** — useful but not required for launch day.
- **ROADMAP** — sub-brand assets for products that don't exist yet
  (DENDRA CLOUD / ANALYZE / INSIGHT / RESEARCH wordmarks). Keep in
  repo; surface only when the corresponding product surface ships.
- **VERIFY** — needs a real review before public-flip.

---

## Logos / marks

| Asset | Status | Notes |
|---|---|---|
| `brand/logo/dendra-mark.svg` | LAUNCH | Primary mark. Used in README header. |
| `brand/logo/dendra-mark-dark.svg` | LAUNCH | Dark-mode mark for README + landing. |
| `brand/logo/dendra-mark-color.svg` | LAUNCH | Full-color variant. Landing hero. |
| `brand/logo/dendra-mark-mono-light.svg` | LAUNCH | Mono variants. Embedded use. |
| `brand/logo/dendra-mark-mono-dark.svg` | LAUNCH | |
| `brand/logo/dendra-mark-1024.png` | LAUNCH | High-res export. |
| `brand/logo/dendra-mark-dark-1024.png` | LAUNCH | |
| `brand/logo/dendra-mark-mono-light-1024.png` | LAUNCH | |
| `brand/logo/dendra-mark-mono-dark-1024.png` | LAUNCH | |
| `brand/logo/dendra-mark-animated.svg` | LAUNCH | Hero animation. One-shot rising-accent on first scroll into view. |
| `brand/logo/dendra-mark-animated-loop.svg` | POST-LAUNCH | Loading-cycle variant. Use only when we have a long-running operation indicator (Wave 2 dashboards). |

## Wordmarks

| Asset | Status | Notes |
|---|---|---|
| `brand/logo/dendra-wordmark-horizontal.svg` | LAUNCH | README header (currently embedded). |
| `brand/logo/dendra-wordmark-horizontal-dark.svg` | LAUNCH | README dark-mode header. |
| `brand/logo/dendra-wordmark-stacked.svg` | LAUNCH | Reserved for landing-page hero or footer. |
| `brand/logo/dendra-wordmark-stacked-dark.svg` | LAUNCH | |
| Their corresponding PNGs | LAUNCH | |

**Audit:** the SVG-spacing-bug task (#53 in the task list — "Fix
SVG spacing bug — DENDRA + subword") is still marked pending.
**VERIFY** the wordmarks render correctly with appropriate
spacing between DENDRA and any sub-brand text. If broken, fix
before launch.

## Sub-brand wordmarks (DENDRA CLOUD / ANALYZE / INSIGHT / RESEARCH)

| Asset | Status | Notes |
|---|---|---|
| `brand/logo/dendra-cloud-wordmark.svg` + `.png` | ROADMAP | Cloud product hasn't launched yet. Keep in repo; don't surface in public docs until the hosted Cloud is live (Wave 2). |
| `brand/logo/dendra-analyze-wordmark.svg` + `.png` | ROADMAP | Analyzer-as-a-service, also Wave 2. |
| `brand/logo/dendra-insight-wordmark.svg` + `.png` | ROADMAP | Dashboards, Wave 2. |
| `brand/logo/dendra-research-wordmark.svg` + `.png` | ROADMAP | Future research-tier product. |

**Recommendation:** these stay in the repo (they're future
roadmap assets and the fact that we've already designed them
shows brand-system maturity). They do NOT appear on the launch-
day landing page or README. Don't link to them from any public
doc until the corresponding product ships.

## Favicons + manifest

| Asset | Status | Notes |
|---|---|---|
| `brand/logo/dendra-favicon.svg` | LAUNCH | Master favicon SVG. |
| `brand/logo/dendra-favicon-16.png` | LAUNCH | Favicon size variants. |
| `brand/logo/dendra-favicon-32.png` | LAUNCH | |
| `brand/logo/dendra-favicon-180.png` | LAUNCH | iOS / Android touch icon. |
| `brand/logo/dendra-favicon-512.png` | LAUNCH | PWA / large-format. |
| `brand/logo/site.webmanifest` | LAUNCH | PWA manifest. **VERIFY:** check theme + background colors match `palette.md`. |

## Social cards / banners

| Asset | Status | Notes |
|---|---|---|
| `brand/logo/dendra-github-social-preview.svg` + `.png` | LAUNCH | Upload to GitHub repo Settings → Social preview. 1280×640. |
| `brand/logo/dendra-twitter-banner.svg` + `.png` | LAUNCH | X / Twitter profile banner. 1500×500. **VERIFY** alignment when avatar circle overlays. |
| `brand/logo/dendra-linkedin-banner.svg` + `.png` | LAUNCH | LinkedIn company-page banner. 1128×191. |
| `brand/logo/dendra-social-card.svg` + `.png` | LAUNCH | OG share-card; default link-preview image. |
| `brand/logo/dendra-social-card-dark.svg` + `.png` | LAUNCH | Dark-mode variant. |

## Brand documentation

| File | Status | Notes |
|---|---|---|
| `brand/voice.md` | LAUNCH | Tone / word-use rules. **Internal — keep in repo but the rules apply to all public copy.** |
| `brand/messaging.md` | VERIFY | Canonical taglines + pitches. **Re-read for consistency with the autoresearch reframing in the talk script and FAQ.** Anything quoting the OLD universal "every team has the ticket" framing needs softening. |
| `brand/motion.md` | LAUNCH | Animation spec. Stays internal (designers' reference). |
| `brand/palette.md` | LAUNCH | Color spec. Internal designer reference. |
| `brand/typography.md` | LAUNCH | Typography spec. Internal. |
| `brand/usage.md` | LAUNCH | Usage rules. Internal. |
| `brand/sub-brands.md` | POST-LAUNCH | Sub-brand lockup pattern. References ROADMAP wordmarks; don't promote until Wave 2. |
| `brand/accessibility.md` | LAUNCH | Contrast ratios + a11y rules. **Internal but cite from the landing page footer if asked about a11y.** |
| `brand/governance.md` | LAUNCH | Asset-change governance. **Strictly internal.** |

## Templates

| Asset | Status | Notes |
|---|---|---|
| `brand/templates/dendra.mplstyle` | LAUNCH | Matplotlib style for paper figures. **Used in `dendra plot` CLI? Verify.** Public via the source tree. |
| `brand/templates/dendra-preamble.tex` | LAUNCH | LaTeX preamble for the paper. **Will be used by the BasicTeX pipeline once installed.** |

---

## Action items before launch (small list)

- [ ] **Fix the SVG-spacing bug** in wordmarks (task #53).
  Re-render all `*-wordmark-*.svg` + PNG variants if the spacing
  needs tweaking.
- [ ] **Verify `site.webmanifest`** has the correct theme colors.
- [ ] **Verify the X-banner safe area** doesn't get cropped by
  the avatar circle overlay when posted to a real X profile.
- [ ] **Re-read `brand/messaging.md`** for stale framing
  (specifically the "every team has the ticket" universal we
  softened in the talk script).
- [ ] **Sub-brand wordmarks**: confirm they're NOT linked from
  README, landing page, or any public doc that ships May 13.

## Action items deferrable to post-launch

- [ ] Audit all PNG exports for retina-resolution coverage. Some
  may be 1× only.
- [ ] Add light-mode variants of any dark-only assets.
- [ ] Document the 21+ asset inventory in `brand/usage.md` so
  external designers (if engaged later) have a master list.
- [ ] Animated mark loop variant — only surface when the
  Wave 2 hosted dashboards have a long-running operation
  indicator.

---

## Recommendation

**The brand kit is launch-ready** with three small follow-ups:

1. SVG-spacing fix on wordmarks (task #53)
2. messaging.md re-read for the autoresearch reframe
3. X-banner avatar-circle safe-area verification

None of those block launch on May 13 if the assets render OK
in their current form; they're polish items. **Sub-brand
wordmarks correctly stay invisible at launch** since the
products they label don't exist yet.

If you want me to execute the SVG-spacing fix (it's task #53,
been pending), tell me and I'll inspect the current wordmarks
and propose a fix. If you want to defer it, I'll mark the task
as launch-deferred.
