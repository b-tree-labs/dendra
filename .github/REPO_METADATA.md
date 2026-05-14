# GitHub repo metadata — copy-paste targets for the public launch

This file is the source of truth for the GitHub-side repo metadata that
isn't tracked in code: description, topics, website, social-preview,
pinned items. Apply via **Settings → General** and the **About** sidebar
on the public repo landing page.

Last reviewed: 2026-05-11 (drafted during the public-faces polish pass
for the 2026-05-20 launch).

---

## Description

Paste into **About → Description** (the field under the repo title on
`github.com/b-tree-labs/postrule`). 120-char ceiling; this is what shows
in search results and on the org page card.

> Graduated-autonomy classification primitive — rule today, ML tomorrow, paired-McNemar gate decides when.

(118 chars.)

Three alternates if the above reads off:

1. _Python primitive that graduates rule-based classifiers to ML through a paired-McNemar evidence gate._ (108 chars)
2. _Wrap a classifier. The rule stays as the safety floor; the ML head graduates when the evidence justifies it._ (110 chars)
3. _Self-taught classifiers. The graduated-autonomy primitive for production classification._ (95 chars)

---

## Website

Paste into **About → Website**:

> https://postrule.ai

---

## Topics

Paste into **About → Topics**. GitHub allows up to 20; this is 18,
ordered by discoverability — `python` first, the differentiators after,
the long tail at the end.

```
python
machine-learning
classifier
classification
llm
rule-based
mcnemar-test
statistical-tests
graduated-autonomy
ab-testing
mlops
ai-safety
shadow-deployment
audit-trail
observability
apache-2
business-source-license
patent-pending
```

Notes on the picks:

- `python` first — broadest top-of-funnel discoverability tag.
- `mcnemar-test` and `statistical-tests` are uncommon enough that we
  rank well for them; they're load-bearing for the paper-driven crowd.
- `graduated-autonomy` is a project-specific term; including it ties
  the topic chain to the paper's framing.
- `shadow-deployment` is a search anchor for the platform-eng audience
  evaluating canary / shadow strategies.
- `apache-2` + `business-source-license` make the split license
  discoverable to license-conscious procurement scanners.
- Avoid: `ai`, `artificial-intelligence`, `framework`, `tool` — too
  generic to rank, dilutes the topic chain.

---

## Social preview image

GitHub renders this when the repo is shared on Twitter / X / LinkedIn
/ Slack / Discord. Currently NOT set — falls back to the default
"username/repo" card.

The asset already exists in the repo at:

> `brand/logo/postrule-github-social-preview.png` (1280×640)

Apply via **Settings → General → Social preview → Edit → Upload an
image**. GitHub will compress it; the SVG master at
`brand/logo/postrule-github-social-preview.svg` is the regenerate source
if you ever need to tweak it.

After upload, verify by opening
<https://opengraph.githubassets.com/0/b-tree-labs/postrule> in an
incognito tab — should show the new card.

---

## Pinned items

Repos can pin up to **6** items on the org profile and the repo's
landing page. Suggestions (in priority order — pin the top 3):

1. **Repo: `b-tree-labs/postrule`** — pin on the org profile.
2. **Repo: `b-tree-labs/axiom-os`** — the second active product per
   `b-tree-labs/profile/README.md`.
3. **Discussion (optional, v1.1):** "v1.1 roadmap — what would you
   want next?" — opens the feedback loop for the post-launch month.

Do **not** pin pre-launch:

- Issues — none of the current issues are flagship-worthy public
  artifacts (mostly internal tracking).
- Discussions — none exist yet.

---

## Settings checks (verify before launch)

These are configured but worth eyeballing once the repo goes public:

- [ ] **Features → Issues:** enabled. (Currently enabled.)
- [ ] **Features → Discussions:** decide. Recommend enabling at
      launch — the FAQ + support routing is currently via
      `SUPPORT.md` only; Discussions gives a clean "ask a question"
      surface that Issues doesn't.
- [ ] **Features → Sponsorships:** off (no funding.yml). Leave off
      unless / until B-Tree Labs accepts sponsorship.
- [ ] **Code & automation → Branches → main:** branch protection
      enabled, require PR + status checks. (Already enforced.)
- [ ] **Security → Code security and analysis:** Dependabot alerts +
      secret scanning + push protection all on. (Already on per the
      pre-launch security audit, PR #46.)
- [ ] **General → Pull Requests → Allow auto-merge:** decide.
      Recommend on (solo founder, frequent green PRs).
- [ ] **General → Pull Requests → Automatically delete head branches:**
      on. (Currently on.)

---

## Org-profile note (separate repo, surface only)

The org profile rendered at <https://github.com/b-tree-labs> is
sourced from `b-tree-labs/.github/profile/README.md` — a separate
repo. That file currently reads:

> Postrule v1.0 launching 2026-05-13

That date is stale (launch is 2026-05-20, per PR #51's bump). Ben
should update that file directly in the `b-tree-labs/.github` repo
before launch — out of scope for this PR since it lives in a different
repo. Two-line patch:

```diff
- | **[Postrule](https://postrule.ai)** | Graduated-autonomy classification primitive (rule → LLM → ML in six phases, library-first) | v1.0 launching 2026-05-13 |
+ | **[Postrule](https://postrule.ai)** | Graduated-autonomy classification primitive (rule → LLM → ML in six phases, library-first) | v1.1.0 — 2026-05-20 |
```

(v1.1.0 skips 1.0.0 deliberately per PR #51 / [CHANGELOG.md][changelog].)

[changelog]: ../CHANGELOG.md
