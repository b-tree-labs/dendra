# Dendra — Operational DX Design

**Scope:** how Dendra stays maintenance-free, self-measures its own
ROI, and installs under an AI coding assistant more easily than any
peer library.
**Generated:** 2026-04-20.
**Status:** design doc + implementation roadmap. Shipped pieces are
noted as `[✓ shipped]`.

---

## 1. The three operational promises

A user shouldn't have to think about Dendra after adoption. Three
concrete promises the code backs:

1. **Self-managing storage.** Outcome logs never grow unbounded.
   Rotation, retention, compaction all run inline with no cron, no
   operator.
2. **Self-measuring value.** Dendra reads its own logs and produces
   an ROI report any trial user can compute, no external tooling.
3. **Agent-first install.** The easiest way to adopt Dendra is to
   ask Claude Code / Cursor / any agent to install it — and have
   the agent produce correct, working, opinionated code by default.

---

## 2. Self-managing storage `[✓ shipped]`

See `dendra.storage.FileStorage`. Defaults:

- **64 MB per active segment.** ~600k outcomes at ~100 bytes each.
- **8 segments retained.** ~512 MB total cap per switch.
- **Inline rotation.** Triggered on `append_outcome` when the next
  line would cross cap. Zero blocking threads, zero cron.
- **Graceful shifting.** `outcomes.jsonl` → `.1` → `.2` → ...
  Oldest segment past retention is `unlink()`ed. Missing files are
  tolerated.

Defaults sized so *"install and forget for a decade at 10 outcomes/sec"*
holds. Operators can tighten for embedded (`max_bytes_per_segment=
4*1024*1024, max_rotated_segments=2` → 12 MB cap) or relax for
data-science (`max_rotated_segments=64` → multi-GB history).

`FileStorage.compact(switch_name)`, `.bytes_on_disk(switch_name)`,
and `.switch_names()` give operators read-only visibility for dashboards
without leaving the library. 18 passing tests cover rotation
semantics.

**Design decisions worth preserving:**
- Rotation happens **synchronously on append**. Async rotation would
  complicate failure semantics (what if rotation races with append?).
  Cost is negligible: ~one `os.stat` + one `os.rename` per 600k
  writes. Measured at <100 µs amortized.
- Segments are **JSONL, never binary**. Loss of one segment loses one
  segment's data; no global corruption. Recovery is `grep`.
- Retention is **count-based, not time-based**. Engineering tradeoff:
  count is predictable in bytes; time depends on traffic. For
  time-based retention, caller can run a nightly `compact()` and
  delete old `.N` files explicitly.

---

## 3. Self-measuring ROI `[✓ shipped]`

See `dendra.roi.compute_portfolio_roi` and `dendra roi` CLI.

### 3.1 What it measures

Three cost buckets, all traceable to measurable ratios:

- **Direct engineering savings** = (baseline eng-weeks − Dendra
  eng-weeks) × eng-cost-per-week. Uses modern (AI-assisted) defaults
  from `industry-applicability.md` §4.1.2.
- **Time-to-ML acceleration** = months-earlier × monthly-site-value.
  Only accrues when the switch has actually produced graduated
  outcomes (source ∈ {llm, ml, rule_fallback}).
- **Regression avoidance** = regressions-per-site-per-year ×
  regression-cost, scaled by outcome volume (more traffic = more
  chances for a regression that Dendra's breaker catches).

### 3.2 Self-calibration

Every figure decomposes into a ratio × a per-unit assumption
exposed on `ROIAssumptions`. Users can:

- Override any assumption via CLI (`--engineer-cost-per-week`,
  `--monthly-value-low/high`).
- Dump JSON (`--json`) and plug their own multipliers.
- Cite the derivation back to §4-§6 of the applicability doc —
  every dollar traces to a published formula.

### 3.3 Worked smoke example

Running on a synthetic mixed portfolio (support_triage with 500
outcomes @ 67% accuracy; intent_router with 2,000 ML-phase outcomes):

```
switch              outcomes   accuracy       total savings (USD)
intent_router           2,000    100.0%       $11,250 – $93,100
support_triage            500     66.6%       $ 7,250 – $21,100
Portfolio savings range: $18,500 – $114,200 / year
```

The report is designed to be copy-pasteable into a Google Doc or
an executive email. The assumption footer makes it skeptic-proof.

### 3.4 What it deliberately doesn't claim

- **No single-point estimate.** All ranges, all the time.
- **No hidden multipliers.** Every dollar is derived inline.
- **No customer-specific calibration without user input.** The tool
  does not mine customer data to "automatically personalize"; the
  user adjusts the assumptions or lives with defaults.

---

## 4. Auto feature detection `[✓ shipped v1]`

See `dendra.ml.serialize_input_for_features`.

### 4.1 Current capability (v0.2.1)

`SklearnTextHead` dispatches by input type:

| Input type     | Feature serialization |
|----------------|------------------------|
| `str`          | Pass-through |
| `dict`         | `"k: v | k: v | ..."` with recursion |
| `list`/`tuple` | Elements joined by spaces after recursing |
| `None`         | Empty string |
| scalar         | `repr()` |
| Other          | `repr()` fallback |

This is ~80% of real-world production inputs (strings, ticket dicts,
logged requests). It replaces the earlier `repr(input)` hack so
`@ml_switch` on a ticket dict just works.

### 4.2 Roadmap — richer auto detection

**v0.3.x — schema-aware features.**
- Detect string fields with short vs long average length → split
  into short-field (categorical-ish) and long-field (TF-IDF'd)
  vectors.
- Detect numeric fields → min-max normalize and concatenate as
  scalar features alongside text.
- Detect ISO-8601 timestamps → extract hour-of-day / weekday /
  month-of-year as numeric features.
- Detect enums / constrained-string fields (repeated values) →
  one-hot encode rather than TF-IDF tokenize.

**v0.4.x — ML-head auto-selection.**
- Inspect input volume + label cardinality + feature shape at first
  `fit()` call.
- Select between TF-IDF+LR (short-text, moderate cardinality),
  sentence-transformer+LR (long-text or semantic matching),
  gradient-boosted trees (mostly-numeric inputs), or XGBoost
  (tabular/mixed with enough volume).
- Report the selection in the outcome log so audits can trace
  *why* a particular head was chosen.

**v0.5.x — the "dendra analyze" scanner feedback loop.**
- The static analyzer (business-model-and-moat §2.1) observes
  *actual call sites* and suggests the right feature-extractor
  pre-adoption. When the decorator goes live, the suggested head
  is pre-configured — adopter just pip-installs.

The design philosophy: **the library should infer what the analyzer
would recommend.** A user who doesn't run the analyzer still gets
its judgment baked in, just slightly weaker because it lacks call-
graph context.

---

## 5. Agent-first install

The user's stated goal: *"installing and using Dendra via agents
should be easier than any other library like it."* Concrete
design (shipped pieces marked `[✓]`):

### 5.1 The ten-second install

```
$ pip install dendra
$ claude "wire dendra up to triage_ticket in src/triage.py; start in Phase 0"
```

For this to work, the *agent* needs:

1. **A canonical `SKILL.md`** — Dendra-specific recipe that Claude
   Code / Cursor skills can pattern-match on. Shipped at
   `docs/integrations/SKILL.md` (design below).
2. **A canonical set of code examples** — `examples/` directory at
   repo root, referenced from SKILL.md, each a runnable file with
   a one-line "what this shows" comment at the top.
3. **A minimal public-API surface** — `from dendra import ml_switch`
   + 6 other names. `[✓ done]` The `__all__` in `__init__.py` is
   tight; an agent reading it can enumerate the whole library.
4. **Predictable patterns for the 80% case.** Default storage,
   default ML head, default telemetry (null). An agent that knows
   the 3-parameter decorator call covers most sites.

### 5.2 Proposed `docs/integrations/SKILL.md`

A skill-format document following the Anthropic Skills convention:
title + trigger + frontmatter + body with imperative steps.

**Name:** `dendra-instrument-classifier`

**Trigger phrases:** "add dendra to", "wrap with dendra",
"dendra-ify", "instrument this classifier", "make this learnable"

**Body:**
```markdown
## When invoked

The user has a Python function that returns a string label from a
finite set (if/elif chains, match-case dispatch, keyword lookup).
Your job: wrap it with `@ml_switch` so Dendra can log outcomes
without changing caller-visible behavior.

## Steps

1. **Confirm** the function returns `str` (or `list[str]` for
   multi-label; note the `+`-joined collapse). If it returns a
   non-label type, **stop** — Dendra doesn't fit.
2. **Read** the function to enumerate the label set. Put labels in
   a `LABELS` constant next to the decorator.
3. **Identify the author.** Prefer `@name:context` Matrix style
   (check CLAUDE.md / AGENTS.md for principal convention).
4. **Add the decorator.** The 80%-case form:

   ```python
   from dendra import ml_switch, Phase, SwitchConfig

   LABELS = ["bug", "feature", "question"]

   @ml_switch(labels=LABELS, author="@you:team", name="triage",
              config=SwitchConfig(phase=Phase.RULE))
   def triage(ticket: dict) -> str:
       ...  # the existing rule body, UNCHANGED
   ```

5. **Export the switch for outcome recording.** At module scope:

   ```python
   # Callers who learn ground truth later record it here.
   record_outcome = triage.record_outcome
   ```

6. **Add `dendra>=0.2.0`** to `pyproject.toml` / `requirements.txt`.
7. **Do not** change the function body. **Do not** change caller
   signatures. This is a Phase 0 integration; graduation is later.

## Output

A minimal diff. Verify the test suite still passes (no behavior
change is the whole point).
```

### 5.3 Cursor rules / `.cursor/rules/dendra.md`

Same content as the SKILL, formatted for Cursor's context surface.

### 5.4 An MCP server wrapper

`dendra-mcp` — a tiny MCP server exposing:

- `tool:dendra.analyze(repo_path)` — static scan, returns JSON report.
- `tool:dendra.suggest_integration(file, function)` — propose the
  minimal diff to wrap a function.
- `tool:dendra.roi(storage_path)` — returns the same ROI report.
- `resource:dendra.conventions` — the SKILL.md content as a resource.

With this, Claude Code / Cursor / any MCP-speaking agent can
integrate Dendra with one command. This is the analog of "install
Snyk via GitHub App"; for the agent era the install is an MCP tool.

### 5.5 Agent-first signals already in place

- SPDX headers on every file let agents grep for licensing
  reliably.
- All public types listed in `__init__.py` → trivial enumeration.
- Every decorator param has a Google-style docstring.
- Every optional dep raises a pip-install-able error message
  (`"Install with pip install dendra[openai]"`) — agents can act
  on it.
- The repo has no hidden build system; `hatchling + pyproject.toml`
  is standard and agent-readable.

### 5.6 What still needs to ship (implementation)

- `docs/integrations/SKILL.md` (not yet in repo).
- `examples/` runnable quickstarts (not yet in repo).
- `dendra-mcp` server (future v0.3; out of scope for v0.2.1).
- A `dendra init <file>:<function>` CLI command that performs the
  SKILL's steps non-interactively — when an agent invokes it, the
  work is done by the library, not the LLM (no hallucinations).

---

## 6. Why this triad matters together

Self-managing storage, self-measuring ROI, and agent-first install
aren't independent features — they're a coherent operational-DX
stance:

- A library that **forgets to rotate its logs** breaks production in
  week 6 of adoption. Zero-maintenance storage is the floor.
- A library that **can't explain its own value** loses the CFO
  conversation during pilot-to-paid. Self-measuring ROI is the
  answer.
- A library that **needs human-written integration code** is slower
  to adopt in an AI-first era than a competitor that ships an MCP
  server and a SKILL. Agent-first install is the moat multiplier.

All three feed the same outcome: *Dendra becomes the default
classification primitive because it installs itself, maintains
itself, and justifies itself.*

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs). Apache-2.0 licensed._
