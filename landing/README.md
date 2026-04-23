# Dendra landing page (`dendra.dev`)

Static single-page site. No build step. Deploy the `landing/`
directory as-is to any static host.

## Files

```
landing/
├── index.html              # the page
├── style.css               # layout (imports brand-tokens.css)
├── brand-tokens.css        # Axiom Labs design system — palette, type, scale
├── _headers                # Cloudflare Pages / Netlify security + caching
├── README.md               # this file
└── assets/
    ├── favicon.svg                     # Dendra rounded-tile favicon
    ├── dendra-mark.svg                 # site-header mark, light
    ├── dendra-mark-dark.svg            # site-header mark, dark
    ├── social-card.png                 # 1200×630 OG / Twitter card
    └── figure-1-transition-curves.svg  # paper results figure
```

## Design system

Tokens and type-scale come from the Axiom Labs brand kit at
[`axiom-labs-os/.github/brand/`](https://github.com/axiom-labs-os/.github/tree/main/brand).
See `brand-tokens.css` for the semantic CSS-variable expression.

The Dendra mark is finalized — the **D2' · Node** glyph (a rule
floor parted by a rising accent stroke that crosses through a
phase-gate lintel, with a hollow 28-r ink ring at the threshold-
crossing point). Canonical assets live at
[`brand/logo/`](../brand/logo/) with SVG masters + PNG exports;
the landing page's `assets/favicon.svg`, `assets/dendra-mark.svg`,
and `assets/social-card.png` are production copies from that kit
ready for deploy.

## Deploy — Cloudflare Pages (recommended)

```bash
npm i -g wrangler
cd landing
wrangler pages deploy . --project-name=dendra-dev
```

Or drag-and-drop the `landing/` directory into the Cloudflare
dashboard. Point the project at the `dendra.dev` domain under
Custom Domains.

Cloudflare Pages auto-picks up `_headers` and `_redirects`.

## Deploy — Vercel / Netlify

```bash
# Vercel
cd landing && vercel deploy --prod

# Netlify
cd landing && netlify deploy --prod --dir=.
```

Both providers honor `_headers` (Netlify natively; Vercel via
`vercel.json` if you prefer the JSON format).

## Deploy — GitHub Pages

Works, but loses the `_headers` security policy. Use Cloudflare
Pages unless there's a specific reason not to.

## Local preview

```bash
cd landing && python3 -m http.server 8765
# open http://127.0.0.1:8765
```

## Design patterns borrowed

Explicit attribution so the aesthetic choices are auditable:

- **Code-above-copy hero** — Modal, Temporal, Tailscale, Supabase.
- **Install-command as primary CTA** — Clerk, Supabase, Resend.
- **Sub-microsecond latency stat above the fold** — Honeycomb,
  Sentry, Temporal.
- **Terminal-styled example output** — Modal, Vercel CLI docs.
- **Inline architecture diagram** (phase flow) —
  Temporal (workflow model), Stripe (payment flow).
- **Transparent pricing table with no "contact us" below
  Enterprise** — Stripe, Clerk, Plausible, Supabase.
- **Quiet technical aesthetic, no animations beyond hover** —
  Linear, Tailscale, Cal.com.
- **Multi-column dense footer** — Resend, Cal.com.

Intentionally NOT copied:

- Dark-mode-only designs (our brand is ground + graphite).
- Animated code blocks / WebGL hero (brand forbids animation
  beyond hover).
- "Schedule a demo" above the fold (`entry-with-end-in-mind.md`
  §4 rules out outbound sales motion in year 1).
- Customer-logo wall (we don't have public logos yet; brand
  rules forbid using them before sign-on).

## Future enhancements

Not blocking deploy:

- Dendra mark — replace the placeholder favicon when the real
  glyph is designed.
- Open Graph social card (1200×630) — placeholder left; needs
  the finalized mark first.
- Launch-day announcement banner (thin bar at top) with arXiv
  link — add once arXiv ID assigned.
- Code-copy button on the install-cmd blocks — triggers a small
  JS dependency; `navigator.clipboard.writeText` with
  graceful fallback. Skip unless analytics show users want it.
- Optional: convert to Astro or Next.js static build if
  server-rendered blog posts or docs pages need to live on the
  same domain. The flat HTML stays as the landing route.

## Update cadence

The landing page is a living artifact. Review quarterly:

- Are the stats still the current measured numbers?
  (Check `tests/test_latency.py` and the paper results.)
- Are the pricing tiers still accurate?
  (Check `docs/marketing/business-model-and-moat.md` §3.1.)
- Is the license language accurate?
  (Check `LICENSE.md` top-level split map.)
- Any broken links in the resources footer?

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Licensed CC-BY 4.0; site content copy-safe for adaptation._
