# Launch repo hygiene triage

**Decisions needed from Ben.** Triage of every doc / asset that
appears in the repo today, classified into:

- **PUBLIC** — keep as-is, will be visible after the May 13 public-flip.
- **PROMOTE** — currently in `docs/working/` or `docs/marketing/`,
  should move to `docs/` (visible in the public docs index).
- **PRIVATE** — keep in repo but mark gitignored or move outside repo.
  Internal-only material that shouldn't be public.
- **DELETE** — superseded, redundant, or obsolete; safe to remove.
- **REVIEW** — needs your eyes before deciding.

Tick the column you want for each row. After your sign-off I
execute the moves/deletes in one commit.

---

## `docs/working/` — 28 files + 2 dirs

### Recommend: PROMOTE to `docs/`

| File | Reason |
|---|---|
| `launch-checklist-48hr.md` | The launch-day go/no-go checklist; useful as a public template too. |

### Recommend: PRIVATE (keep in `docs/working/` but flag gitignored or move to `notes/`)

| File | Reason |
|---|---|
| `dendra-axiom-decoupling-policy.md` | Internal architectural decision; references Axiom. Not for public consumption. |
| `enterprise-licensing-tiers.md` | Pricing/legal strategy. |
| `internal-use-cases-scan-2026-04-20.md` | Internal scan of own codebases. |
| `launch-talk-script.md` | The script you're about to record from. Public after recording goes live; private until then. |
| `launch-repo-hygiene-triage.md` | This file. Internal. |
| `license-strategy.md` | Strategy doc, supersedes itself by the public LICENSE files. |
| `multi-language-roadmap.md` | Forward-looking roadmap; risky to commit publicly. |
| `operational-dx-design.md` | Internal DX strategy. |
| `patent/` (dir) | All patent filing artifacts. **Definitely private.** |
| `patent-strategy.md` | Internal IP strategy. |
| `roadmap-2026-04-20.md` | Internal roadmap dated 2026-04-20. Likely stale. |
| `trademark-strategy.md` | Internal IP strategy. |
| `v1-readiness.md` | The internal v1 scope tracker. Mostly done. |
| `v1-audit-*.md` (7 files) | The pre-launch audit reports. Internal. |
| `wasm-browser-strategy.md` | Forward-looking architecture. Internal until v1.1+. |
| `benchmarks/` (dir) | Raw benchmark JSONL — already cited from the paper results dir; safe to keep here as private working data. |

### Recommend: PROMOTE to `docs/` after light edit

| File | Reason | Edit needed |
|---|---|---|
| `adapter-ecosystem.md` | Genuinely useful public reference for which adapters exist. | Strip any internal-roadmap notes. |
| `feature-gate-protocol.md` | Documents the Gate protocol — useful public extension reference. | Strip internal-discussion language. |
| `feature-llm-comparison.md` | Compares the shipped LLM adapters — useful public reference. | Verify current. |
| `feature-rule-from-model.md` | Extension pattern, public-friendly. | Verify current. |
| `feature-breaker-policies.md` | Circuit-breaker docs, public-friendly. | Verify current. |
| `externalization-boundary.md` | The "what stays local, what goes external" rationale — strong public-explainer material. | Light strip. |
| `llm-as-teacher.md` | The cold-start pattern — pairs with example 07. | Light strip. |

### Recommend: REVIEW — your call

| File | Why I'm punting |
|---|---|
| (none yet — flag any of the above if you disagree) |

---

## `docs/marketing/` — 11 files

### Recommend: PRIVATE (move to `marketing/` outside `docs/`)

| File | Reason |
|---|---|
| `analyzer-dogfood-2026-04-22.md` | Dated internal analysis. |
| `business-model-and-moat.md` | Strategic; not public. |
| `design-partner-agreement.md` | Legal template; private. |
| `entry-with-end-in-mind.md` | Internal go-to-market. |
| `industry-applicability.md` | Internal market sizing. |
| `pricing-deep-dive.md` | Internal pricing rationale. |
| `vc-pitch-deck.md` | Investor material, private. |

### Recommend: PROMOTE to `docs/` (or land on the public landing page)

| File | Reason |
|---|---|
| `dendra-one-pager.md` | Useful as a public quick-pitch. Could become `docs/elevator.md` or first section of landing copy. |
| `landing-page-copy.md` | This IS the landing page. **Move into landing-page repo** or use as source-of-truth for the Astro+Firebase build. |
| `launch-post-drafts.md` | Drafts of the HN / X / LinkedIn launch posts. **Move to a private launch-day-comms folder** so they don't leak the launch text early. |
| `outreach-templates.md` | Email templates for design-partner / reviewer outreach. **Private** until launch; public after as a community resource. |

---

## `docs/papers/2026-when-should-a-rule-learn/` — paper artifacts

### Recommend: ALL PUBLIC

| File / dir | Status |
|---|---|
| `outline.md` | Public — this is the paper outline. |
| `results/` | Public — JSONL benchmarks + figure + findings.md. |

The paper is the launch's anchor artifact; entire directory ships public.

---

## `docs/` (top-level) — already public-ready

| File | Status |
|---|---|
| `api-reference.md` | Public ✓ |
| `getting-started.md` | Public ✓ |
| `storage-backends.md` | Public ✓ |
| `verdict-sources.md` | Public ✓ |
| `async.md` | Public ✓ |
| `autoresearch.md` | Public ✓ (just landed) |
| `FAQ.md` | Public ✓ |
| `integrations/SKILL.md` | Public ✓ — the Claude Code skill. |

All current. No action needed.

---

## Other top-level concerns

### Recommend: VERIFY before public-flip

- [ ] **`README.md`** — the front door. Re-read for stale claims (we already updated latency numbers + test counts in Session 4).
- [ ] **`CHANGELOG.md`** — make sure v0.2.0 → v1.0.0 entry is written before launch.
- [ ] **`CONTRIBUTING.md`** — contributor guide; verify DCO + code-of-conduct + signed-off-by guidance is current.
- [ ] **`LICENSE.md` / `LICENSING.md` / `NOTICE` / `LICENSE-APACHE` / `LICENSE-BSL`** — legal surface. Verify links and dates current.
- [ ] **`SECURITY.md`** — disclosure policy. Verify present and points at a real contact.
- [ ] **`SUPPORT.md`** — community-vs-paid support contract.
- [ ] **`TRADEMARKS.md`** — DENDRA trademark notice.
- [ ] **`brand/`** — the brand kit. Audit which assets are needed at launch and which are roadmap (sub-brand lockups for products that don't exist yet).
- [ ] **`landing/index.html`** — what's in this? If it's a placeholder, decide: replace with Astro+Firebase build, or remove from repo (keep in a separate landing repo).

### Recommend: DELETE / MOVE OUT

- [ ] **`Payment Receipt - Submissions - Patent Center - USPTO.pdf`** in repo root — patent filing receipt. **Private. Move out.**

### Recommend: PRIVATE / GITIGNORED

- [ ] **`scripts/run_v1_benchmarks.py`** — keep public, it's the reproducible benchmark harness.
- [ ] **`notes/`** (already gitignored per `notes/sidequest-*.md`) — verify .gitignore covers what it should.

---

## Action sequence I'm proposing

Once you sign off on the columns above, I execute as a single
commit:

```
chore(repo): pre-launch hygiene — promote, privatize, prune

- promote: docs/working/{adapter-ecosystem, feature-gate-protocol,
  feature-llm-comparison, feature-rule-from-model,
  feature-breaker-policies, externalization-boundary,
  llm-as-teacher}.md → docs/
- privatize: move docs/marketing/* to marketing/ (outside docs/)
  except landing-page-copy.md → landing/, dendra-one-pager.md → docs/
- privatize: docs/working/{patent, internal, strategy} files →
  notes/working/ (gitignored) or marketing/private/
- delete: Payment Receipt PDF from repo root
- update: README.md scan for stale references
- update: CHANGELOG.md write v1.0.0 entry
```

---

## Your turn

Read each section above and either:

1. **Accept all my recommendations** — reply "go" and I execute.
2. **Disagree on specific rows** — tell me which to flip from my
   recommendation; I respect that and execute the rest.
3. **Add concerns** — anything I missed.

Estimated work after sign-off: ~1 hour to execute + verify the
test suite stays green + commit + push.
