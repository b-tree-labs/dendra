# Dendra · brand governance

How the Dendra brand is maintained, who can change it, and how
to add a new asset. This doc lives inside the brand kit because
the kit is the artifact — if you're editing a file in `brand/`,
you're working within this process.

## What counts as "the brand"

Everything in the `brand/` directory:

- **SVG masters** at `brand/logo/*.svg` — canonical; hand-edited.
- **PNG exports** at `brand/logo/*.png` — derived; regenerated
  by `_export.py`.
- **Brand docs** (`palette.md` / `typography.md` / `usage.md` /
  `voice.md` / `messaging.md` / `motion.md` / `sub-brands.md` /
  `accessibility.md` / this file) — authoritative rules.
- **Templates** (`brand/templates/*.mplstyle` / `*.tex`) —
  applied style for paper + figure consistency.

Plus the installed copies in `landing/assets/` (favicon, mark,
social-card) which are *production copies* of the canonical
kit.

## Who can change it

- **Benjamin Booth** (sole maintainer, owner). All brand changes
  require his sign-off.
- **Commits touching `brand/**/*`** go through the same review
  process as code — on a feature branch, opened as a PR, with
  CI green, before merging to `main`.
- **When an identity designer is engaged** for the production
  refinement pass (Hoodzpah / Character / Mackey Saturday, per
  Critic 1's advice), they'll work on a dedicated branch and
  hand off via PR. Their commits are signed via the same DCO
  sign-off process as any other contributor.

## How to add a new asset

1. **Decide whether the asset is new or a variant.** A new social
   banner for a different platform is a variant of the existing
   banner system and should use the same typographic treatment.
   A new product launch sub-brand is a variant of the sub-brand
   lockup system (`brand/sub-brands.md`) and must follow its rules.
2. **Write the SVG master** in `brand/logo/` with the canonical
   `dendra-<name>.svg` naming convention. Include a comment
   header explaining what the asset is, what sizes it targets,
   and where it's used.
3. **Add to `brand/logo/_export.py`** if it needs PNG exports.
   The dictionary `EXPORTS` maps stems to output sizes (`None`
   for native size, integers for square output dimensions).
4. **Add to `brand/logo/_preview.html`** so the asset renders
   in the preview page alongside the rest of the kit.
5. **Update `brand/usage.md`** if the asset introduces a new
   usage context (new clear-space rule, new minimum size, new
   don't rule).
6. **Regenerate PNGs** by running `python brand/logo/_export.py`.
7. **Smoke-test** by opening `brand/logo/_preview.html` in a
   browser and checking the new asset renders alongside the
   existing ones at representative sizes.
8. **Commit** on a feature branch, push, open PR.

## How to change an existing asset

1. **Never edit a PNG directly.** PNGs are derived from SVGs via
   `_export.py`. If a PNG is wrong, fix the SVG, then regenerate.
2. **SVG edits** should preserve the coordinate system (viewBox,
   stroke-width, square linecaps, palette values) unless the
   change is explicitly about one of those parameters. Read the
   existing SVG's comment header before editing.
3. **Commit the SVG change and the regenerated PNG together** in
   one commit. Don't split them — someone bisecting later should
   see them as atomic.
4. **Update the brand doc** if the change affects a rule in
   `usage.md`, `palette.md`, etc.

## Version history

The brand kit doesn't maintain explicit version numbers. Each
commit touching `brand/**` is a version-of-record. `git log
brand/` shows the full history. If a specific pre-production
version needs to be restored (e.g., a marketing piece went out
with an older mark and needs to be regenerated), use `git
checkout <sha>` on `brand/` files directly.

The one exception: if the Dendra mark itself changes in a
visually significant way (not a minor refinement — a new glyph
decision), tag the commit with `brand-v2` / `brand-v3` etc. and
document the change in `CHANGELOG.md` under a new top-level
section. This is a once-in-several-years event.

## Attribution + external use

### For third parties using the Dendra name or mark

See `TRADEMARKS.md` in the repository root. In short:

- **Descriptive / nominative use** ("my project uses Dendra") —
  no permission needed.
- **Embedding the mark in a product name or UI** ("Dendra Plus"
  / "Powered by Dendra" badge) — requires a trademark license.
- **Swag, merch, unofficial product** — requires permission.

Email `trademarks@b-treeventures.com` for anything uncertain.

### Fair-use references to other brands within Dendra content

When Dendra's own content references other brands (e.g., the
dogfood blog post discusses Sentry / PostHog / HuggingFace /
LangChain source code):

- Always link to the source on first mention.
- Never use another brand's logo or wordmark in Dendra-authored
  content without permission.
- Quote code and public docs; credit correctly.
- Keep the tone neutral / analytical, not comparative-marketing.

### When someone asks "can I use the Dendra logo for X?"

- Conference talk about Dendra: **yes** — point them at
  `brand/logo/` for clean assets.
- Integration partner's "works with" badge: **maybe** — depends
  on their offering; ask for details; usually yes with a
  one-paragraph attribution agreement.
- A competitor's comparison chart: **no**.
- Merchandise / T-shirts / stickers: **no without permission** —
  swag is how brands get diluted; keep tight control until
  B-Tree Labs has an officially-licensed merch program.

## Asset request process (for internal users)

If you're working on a pitch deck, paper, blog post, or talk and
need a brand asset that isn't in the kit:

1. **Check the kit first** — chances are what you need already
   exists.
2. **If it's a missing variant of an existing asset** (e.g., a
   different social-media platform banner, a specific aspect
   ratio for a conference slide template), file an issue with
   the `brand` label describing the dimensions and context.
3. **If it's a new concept** (sub-brand, new product lockup,
   video identity), open a discussion thread first before a PR
   — brand decisions are directional.

Turnaround for kit additions: 1-2 working days for a missing
variant, longer for new concepts.

## Dependencies + tooling

- **SVG editing** — text-editor based. No Illustrator / Inkscape
  required; every asset is readable and editable in any text
  editor.
- **PNG export** — `cairosvg` (Python). Installed in a local
  venv, not a system dependency. `pip install cairosvg`.
- **Font availability** — Space Grotesk and JetBrains Mono are
  installed from Google Fonts at asset-render time via the
  `fontTools` fallback, or from system fonts if present. For
  production-quality wordmark PNGs, text should be outlined
  (converted to paths) in Inkscape or Illustrator — the cairosvg
  output uses font fallback if the canonical fonts aren't
  installed.

## Open questions / deferred decisions

- **Identity-designer refinement pass.** Current kit is
  Claude-drafted; a pro refinement (~2 weeks, ~$6-12k) is on
  the post-launch roadmap.
- **Sonic identity.** Dendra has no sound. If video content (a
  product demo, conference talk with screencast) ever needs a
  sonic brand element, add a discussion thread and this doc
  gets a new section.
- **Video brand.** See `brand/motion.md`. Currently undefined
  beyond the rising-accent animation.
- **Animated mark — error / circuit-breaker state.** The current
  rising-accent animation is a "success" / "advancement" motion.
  What does it look like when an ML head fails and the rule takes
  back over? Undefined; see `brand/motion.md` final section.

---

**Maintaining this doc.** Update whenever the brand-kit workflow
changes. If a new tool replaces cairosvg, or a new review process
is introduced, document it here. The `brand/` directory is
self-documenting; this file is its process layer.
