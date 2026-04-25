# Why the SLM verifier benchmark exists

The SLM verifier benchmark
(`docs/working/benchmarks/slm-verifier-results.md`) is a small
research artifact that ships with Dendra. This doc captures
what it's for — beyond the immediate "pick the shipped default"
decision — so we don't accidentally treat it as scratch work.

## Primary use: defending the shipped default

The original purpose. Our `default_verifier()` ships pointing at
`llama3.2:3b`. That choice has to be defensible to a skeptical
reviewer. The benchmark gives us:

- A reproducible methodology (anyone can run the script and
  verify our numbers).
- A justification grounded in data, not vibes.
- A documented set of trade-offs (format-compliance vs accuracy
  vs latency vs disk).

Without this, the question "why llama3.2:3b instead of X?" gets
a hand-wavy answer. With this, the answer is a row in a table.

## Secondary uses (in priority order)

### 1. Public credibility on launch day

The benchmark is a **launch-day asset.** Most ML/MLOps libraries
don't transparently benchmark their own components. Saying
"here's why we picked this, here's our methodology, run it
yourself" puts Dendra in a smaller, more credible category.

**Concrete moves on launch:**
- Link the results doc from the README's "Where truth comes
  from" section.
- Reference it in the HN post body when answering "why
  llama3.2:3b?" / "why not GPT-4o-mini by default?" questions.
- Cite specific numbers in the talk script.

### 2. Community contribution magnet

The benchmark has a low-friction first-PR path:

> "Run `python scripts/run_slm_verifier_bench.py` against a model
> we haven't tested. Paste the JSON line into the table.
> Submit a PR."

That's an unusually inviting entry point for a project that
otherwise requires understanding statistical gates. We pin the
"to test next" list in the doc so contributors know what's
wanted.

### 3. Marketing — the "Dendra Verifier Leaderboard"

If we publish this as a recurring artifact (quarterly?
on-major-model-releases?), it becomes a reference resource.
"Llama 4 was released last week — here's how it does on the
Dendra verifier task" is a blog post + X thread that lands
because everyone in the agentic-LLM space is asking.

The framing: **we built the workload, we keep score.** That's
the defensible position. We're not claiming to be a general
LLM benchmark — we're the *graduated-classifier-deployment*
benchmark, which is a niche we own by definition (we built it).

**Concrete move:** every time a major model drops, we re-run
the bench, update the doc, post a one-page comparison. Easy
content. Easy social. Easy SEO.

### 4. Sales / enterprise conversations

When an enterprise prospect asks "is this production-ready?
how reliable is the verifier?" the answer is the doc. Not
hand-waving. Not "trust us." Real measured numbers.

When a compliance buyer asks "what's the false-positive rate of
your AI judge?" the answer is the accuracy-on-judged column +
the "what 50% accuracy means for the gate" explainer.

Both audiences respect data. Most vendors in this space don't
have it.

### 5. Differentiator vs cascade-routing tools

FrugalGPT, RouteLLM, GATEKEEPER — all the cascade-routing
literature — measure routing decisions, not verifier reliability
on a fixed verdict task. The Dendra verifier benchmark fills a
gap nobody else is filling. **Reviewers will notice.**

### 6. Internal feedback loop on shipped defaults

When Llama 4 / Qwen 3 / Phi 4 / Gemma 3 / etc. launch, we
re-run the bench in 5 minutes. If a new model materially
outperforms `llama3.2:3b`, we bump the default with a single-
line change + doc update. Decisions happen on data, not on
"someone tweeted that the new model is good."

### 7. Educational asset

The "what 50% accuracy means for the gate" section is genuine
teaching content. The math-of-noisy-verdicts → gate-graduation-
speed translation isn't obvious. The explainer:

- Could be a standalone blog post.
- Could be a talk segment at an MLOps / AI-eval conference.
- Builds Dendra's reputation as a thoughtful, transparent
  project that does the math.

## What this benchmark is NOT

- **Not a general LLM benchmark.** We measure ONE task —
  classification verdict ("did this label match this input?").
  Don't extrapolate to "model X is better at reasoning."
- **Not a competitive benchmark vs other libraries.** We're
  scoring models on Dendra's verdict task; comparable
  frameworks have different shapes.
- **Not statistically tight.** 30-row corpus. Variance
  run-to-run. We're picking ship defaults, not publishing
  conference results. Anyone using this for a paper claim
  needs to expand the corpus first.

## Scope discipline going forward

Tempting things to add to the benchmark — RESIST unless they
serve a use above:

- Multi-task benchmarks (off-topic; Dendra is a verdict task)
- Cost analysis (separate doc; bench shouldn't grow tendrils)
- Cloud model speedruns (one reference row each is enough)
- "Why our model is better than yours" comparisons (we're not
  selling models)

Keep the benchmark **focused, reproducible, transparent.**
Those three properties are what make it valuable for every
secondary use above.

## Maintenance

Owner: Ben (or whoever ships verifier defaults). Re-run cadence:

- **Major model launches** (Llama 4, Qwen 3, etc.) — add a row
  same week.
- **Quarterly** — re-run all rows on the latest Ollama; pin
  a date column so reviewers can see freshness.
- **Before any default-verifier change** — run the bench,
  update the decision section, ship together.

The script is intentionally tiny (~150 lines). Extending it
should be a 10-minute change in 90% of cases — adding a row to
`candidates`, pulling the model, running.
