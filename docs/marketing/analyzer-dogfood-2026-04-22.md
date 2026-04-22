# What `dendra analyze` finds in Sentry, PostHog, HuggingFace Transformers, and LangChain

**Date:** 2026-04-22.
**Author:** Dendra team.
**Status:** Launch-week blog post. Snapshots taken 2026-04-22 from
`--depth=1` clones of each repository's default branch. File paths
and line numbers reflect the snapshot; they drift as the
repositories evolve.

---

## TL;DR

We ran Dendra's static analyzer against five of the most-watched
Python codebases in developer infrastructure. In four hours of
wall-clock time we identified **394 classification sites** across
**4 heavy-hitters** — Sentry, PostHog, HuggingFace Transformers,
and LangChain — where a hand-maintained rule quietly decides
something consequential: how an error is grouped, what kind of
analysis an LLM should perform, which SDK bootstrap wrapper a
serverless layer uses, which inference provider owns a model name
prefix.

Every one of these is a candidate to graduate from "grep the code
and hope nobody forgets to update the if/elif" to a
statistically-gated transition from rule to ML, with the rule
preserved as the architectural safety floor.

### Scan totals

| Repo | Python files | Sites found | Density |
|---|---:|---:|---:|
| [`getsentry/sentry`](https://github.com/getsentry/sentry) | 4,635 | **107** | 2.3% |
| [`PostHog/posthog`](https://github.com/PostHog/posthog) | 4,541 | **133** | 2.9% |
| [`huggingface/transformers`](https://github.com/huggingface/transformers) | 2,615 | **126** | 4.8% |
| [`langchain-ai/langchain`](https://github.com/langchain-ai/langchain) | 1,580 | **28** | 1.8% |
| [`airbytehq/airbyte`](https://github.com/airbytehq/airbyte) (CDK) | ~300 | 0 | 0.0% |
| [`dbt-labs/dbt-core`](https://github.com/dbt-labs/dbt-core) | 220 | 5 | 2.3% |

The bottom two rows are a calibration contrast: infra-framework
code (Airbyte's Python CDK, dbt-core's transformation graph)
doesn't contain many classification sites because their design
centre is DAG traversal, not branching decisions. The top four
are exactly the kind of *product* code Dendra is for.

Commands used:

```bash
pip install dendra
dendra analyze /path/to/sentry/src/sentry --format markdown
```

---

## 1. Sentry — issue grouping, error type dispatch, SDK-version routing

**107 classification sites across 4,635 Python files.** Sentry's
server is a mature Django codebase that makes dozens of little
"which kind is it?" decisions per request. A handful of them are
textbook Dendra cases.

### 1.1 `match_type` — how Sentry decides what part of an event a fingerprint rule applies to

[`src/sentry/grouping/fingerprinting/matchers.py:57`](https://github.com/getsentry/sentry/blob/master/src/sentry/grouping/fingerprinting/matchers.py)

```python
@property
def match_type(self) -> str:
    if self.key == "message":
        return "toplevel"
    if self.key in ("logger", "level"):
        return "log_info"
    if self.key in ("type", "value"):
        return "exceptions"
    if self.key.startswith("tags."):
        return "tags"
    if self.key == "sdk":
        return "sdk"
    if self.key == "family":
        return "family"
    if self.key == "release":
        return "release"
    return "frames"
```

Eight labels. Narrow-domain. Drives the grouping engine's decision
about which part of an incoming event a fingerprint rule should
inspect. Fit score: **5/5**.

**Why Dendra.** Every new SDK version tends to introduce new event
fields (e.g., trace, profile, replay, feature-flag context). The
rule quietly falls through to `"frames"` when it hits an unknown
key — a silent mis-classification that downstream grouping code
has no way to detect. Wrapping this with `@ml_switch` at
Phase.RULE means every classification gets logged; over time
Sentry's team can measure how often the `"frames"` fallback is
actually correct on novel keys, and advance to LLM-shadow or ML
only when the evidence clears a statistical gate.

### 1.2 `get_node_options_for_layer` — SDK-version → bootstrap-wrapper classification

[`src/sentry/integrations/aws_lambda/utils.py:206`](https://github.com/getsentry/sentry/blob/master/src/sentry/integrations/aws_lambda/utils.py)

```python
def get_node_options_for_layer(layer_name: str, layer_version: int | None) -> str:
    # Lambda layers for v7 of our AWS SDK use the older `@sentry/serverless` SDK
    if layer_name == "SentryNodeServerlessSDKv7" or (
        layer_name == "SentryNodeServerlessSDK"
        and layer_version is not None
        and layer_version <= 235
    ):
        return "-r @sentry/serverless/dist/awslambda-auto"

    # Lambda layers for v8 and above...
    if (
        layer_name == "SentryNodeServerlessSDK"
        or layer_name == "SentryNodeServerlessSDKv8"
        or layer_name == "SentryNodeServerlessSDKv9"
        or (
            layer_name == "SentryNodeServerlessSDKv10"
            and layer_version is not None
            and layer_version <= 13
        )
    ):
        return "-r @sentry/aws-serverless/awslambda-auto"

    # Lambda layers for v10.6.0 and above can use `--import`...
    return "--import @sentry/aws-serverless/awslambda-auto"
```

Three labels. Branches on both a name prefix *and* a version
number. The complexity growth is linear in SDK majors: every new
SDK release needs a new branch in this function, and the comments
already hedge ("and any other layer with a version suffix above").

**Why Dendra.** This is the kind of rule that costs one engineer
an afternoon every quarter. The safety of the rule (getting the
bootstrap wrapper wrong breaks the customer's serverless
instrumentation) plus its obvious-but-recurring maintenance cost
make it a textbook candidate for graduation: start at Phase.RULE,
record outcomes (customer reports + internal tests), advance to
Phase.ML_WITH_FALLBACK when the outcome data justifies it.

### 1.3 `as_str` — integration feature enum to slug

[`src/sentry/integrations/models/integration_feature.py:55`](https://github.com/getsentry/sentry/blob/master/src/sentry/integrations/models/integration_feature.py)

```python
@classmethod
def as_str(cls, feature: int) -> str:
    if feature == cls.ISSUE_LINK:
        return "integrations-issue-link"
    if feature == cls.STACKTRACE_LINK:
        return "integrations-stacktrace-link"
    # … 10 more branches …
    return "integrations-api"
```

Twelve labels, medium cardinality, narrow domain. The tail
`return "integrations-api"` is exactly the "silent fallthrough"
that Dendra's outcome-log exposes by recording every
classification including the fallthrough cases.

### Other Sentry highlights

- `incidents/endpoints/serializers/alert_rule_trigger_action.py:10 human_desc` — alert description dispatch.
- `data_export/writers.py:{74,80,86} get_file_type / get_content_type / get_file_extension` — export-format classification that naturally moves together.
- `integrations/messaging/message_builder.py:318 get_color` — severity → color mapping for notifications.
- `hybridcloud/outbox/category.py:349 get_tag_name` — five-label outbox category tagging.

---

## 2. PostHog — event-property classification, query-type → analysis-style routing

**133 classification sites across 4,541 Python files.** Highest
site density of the four heavy-hitters. PostHog's mix of
user-facing analytics plus an internal AI layer (their
"PostHog AI" assistant) produces a lot of both traditional
classification and LLM-adjacent dispatch.

### 2.1 `get_query_specific_instructions` — PostHog AI's prompt dispatcher

[`posthog/api/insight_suggestions.py:161`](https://github.com/PostHog/posthog/blob/master/posthog/api/insight_suggestions.py)

```python
def get_query_specific_instructions(kind: str) -> str:
    if kind == "TrendsQuery":
        return (
            "Focus on identifying significant changes in volume, growth trends, and seasonality. "
            "Compare the current period to the start. Identify which breakdown segment (if any) is driving the trend."
        )
    elif kind == "FunnelsQuery":
        return (
            "Focus on conversion rates between steps. When there are three or more steps, name the step-to-step "
            "transition with the largest loss. When there are only two steps (one transition), describe the single "
            "drop-off directly without superlatives like 'the biggest' or 'the main bottleneck' — there is nothing "
            "to compare it against. Compare conversion across breakdown segments if available."
        )
    elif kind == "RetentionQuery":
        return (...)
    elif kind == "StickinessQuery":
        return "Focus on how frequently users engage. Identify if there is a core group of power users."
    elif kind == "LifecycleQuery":
        return "Focus on the balance between new, returning, resurrecting, and dormant users..."
    return "Focus on the most significant patterns and anomalies in the data."
```

Six labels. This function is the *seam between a user's query and
an LLM's analysis*. When PostHog adds a new insight type (PathsQuery,
CohortQuery, …), the LLM silently falls through to the generic
last-line instruction — degrading output quality without anyone
noticing.

**Why Dendra.** The safety-critical version of this with
`safety_critical=True` would refuse to construct in the final
phase, but at Phase.LLM_SHADOW it would log every (query_kind,
selected_instructions, llm_output_quality_signal) tuple — giving
PostHog a clean outcome record to graduate *which* query kinds
get ML-selected instructions and *which* should stay rule-based
because the hand-crafted text is genuinely better.

### 2.2 `_detect_actor_type` — actor-shape classification for autocomplete

[`posthog/api/insight_metadata.py:315`](https://github.com/PostHog/posthog/blob/master/posthog/api/insight_metadata.py)

Two-label classifier at a site that autocompletion decisions
route through. Narrow domain.

### 2.3 `convert_field_or_table_to_type_string` — HogQL type system

[`posthog/hogql/autocomplete.py:164`](https://github.com/PostHog/posthog/blob/master/posthog/hogql/autocomplete.py)

Nine labels, narrow domain. Maps a HogQL type object to its
string representation. This is the kind of site where adding a
new HogQL type (say, a new date/time variant) means remembering
to update this function — and forgetting means the autocomplete
silently omits the new type from hints.

### Other PostHog highlights

- `hogql_queries/ai/actors_property_taxonomy_query_runner.py:82 _actor_type` — binary actor classification in the AI query runner.
- `api/advanced_activity_logs/field_discovery.py:306 _get_field_type` — 7-label field-type classification for activity logging.
- `api/object_media_preview.py:35 get_media_type` — binary media classification driving preview rendering.

---

## 3. HuggingFace Transformers — framework inference, quantization dispatch, tokenizer ops

**126 classification sites across 2,615 Python files.** The
highest site density (4.8%) of any repo we scanned. Transformers'
abundance of model-specific subclasses produces a lot of
"which framework?" / "which variant?" / "which tokenizer?"
decisions.

### 3.1 `infer_framework_from_repr` — three-label framework detector

[`src/transformers/utils/generic.py:101`](https://github.com/huggingface/transformers/blob/main/src/transformers/utils/generic.py)

```python
def infer_framework_from_repr(x) -> str | None:
    """
    Tries to guess the framework of an object `x` from its repr
    (brittle but will help in `is_tensor` to try the frameworks
    in a smart order, without the need to import the frameworks).
    """
    representation = str(type(x))
    if representation.startswith("<class 'torch."):
        return "pt"
    elif representation.startswith("<class 'numpy."):
        return "np"
    elif representation.startswith("<class 'mlx."):
        return "mlx"
```

The docstring says the quiet part out loud: **"brittle but will
help."** When a user passes a tensor from a framework that
wasn't in the if/elif (TensorFlow, JAX, cupy, tinygrad…), the
function returns `None` and downstream code falls back to
exception-based probing — slower and harder to diagnose.

**Why Dendra.** Every new ML-framework release is a potential
gap in this function. A Phase.LLM_SHADOW wrap would record the
`repr` prefix alongside the rule's decision; the LLM (or, later,
a small ML head trained on accumulated outcomes) could learn to
recognize "<class 'jax." as `jax`, `"<class 'tensorflow."` as
`tf`, etc., without requiring a Transformers maintainer to ship
a PR every time.

### 3.2 `quantization_method` — four-way quantization dispatcher

[`src/transformers/utils/quantization_config.py:556`](https://github.com/huggingface/transformers/blob/main/src/transformers/utils/quantization_config.py)

```python
def quantization_method(self):
    if self.load_in_8bit:
        return "llm_int8"
    elif self.load_in_4bit and self.bnb_4bit_quant_type == "fp4":
        return "fp4"
    elif self.load_in_4bit and self.bnb_4bit_quant_type == "nf4":
        return "nf4"
    else:
        return None
```

Three labels plus `None`. Branches on two flags plus a nested
config value. The kind of function that has to be edited every
time `bitsandbytes` adds a new quantization variant — right now
the world of 4-bit quantization alone has fp4, nf4, bnb-4bit,
gptq-4bit, awq, plus exllama/kernel-specific variants that this
function doesn't cover at all.

### Other Transformers highlights

- `models/bertweet/tokenization_bertweet.py:264 normalizeToken` — tweet token normalization (2 labels, P1).
- `models/clvp/number_normalizer.py:69 number_to_words` — a textbook rule candidate; numeric-to-word conversion in CLVP's TTS frontend.
- `models/videomt/convert_videomt_to_hf.py:170 infer_backbone_model_name` — backbone detection at model conversion time.
- `utils/auto_docstring.py:3467 _get_base_kwargs_class_from_name` — docstring-generation dispatch by class name (5 labels).

---

## 4. LangChain — THE textbook case, in one function

**28 classification sites across 1,580 Python files.** Fewer
sites than the others, but one of them is so Dendra-shaped we
could have written the paper around it.

### 4.1 `_attempt_infer_model_provider` — eleven-label model-name → provider classifier

[`libs/langchain/langchain_classic/chat_models/base.py:534`](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain_classic/chat_models/base.py)

```python
def _attempt_infer_model_provider(model_name: str) -> str | None:
    model_lower = model_name.lower()

    # OpenAI models (including newer models and aliases)
    if any(
        model_lower.startswith(pre)
        for pre in ("gpt-", "o1", "o3", "chatgpt", "text-davinci")
    ):
        return "openai"

    # Anthropic models
    if model_lower.startswith("claude"):
        return "anthropic"

    # Cohere models
    if model_lower.startswith("command"):
        return "cohere"

    # Fireworks models
    if model_name.startswith("accounts/fireworks"):
        return "fireworks"

    # Google models
    if model_lower.startswith("gemini"):
        return "google_vertexai"

    # AWS Bedrock models
    if model_name.startswith("amazon.") or model_lower.startswith(...):
        return "bedrock"

    # ... five more providers ...
```

Eleven labels. Medium cardinality. Hand-coded string prefix
matching that has to be updated every time a provider ships a
new model family. The LangChain team explicitly annotates
"(including newer models and aliases)" — the comment is already
conceding that this rule is a living document.

**Why Dendra.** This is the **ATIS-like benchmark** from the paper,
literally. A narrow-domain, small-label-set rule sitting in front
of a classifier the whole ecosystem depends on. Wrap it at
Phase.RULE today, ship it unchanged; by the time someone files
an issue asking "why did my new-provider model hit the wrong
adapter?", the outcome log already has the data to diagnose
(and, a few hundred outcomes later, to graduate past).

### Other LangChain highlights

- `agents/react/base.py:108 lookup` — tool-name dispatch in the classic ReAct agent (2 labels, 5/5 fit).
- `chains/natbot/crawler.py:219 convert_name` — DOM element name normalization in natbot's browser agent (5 labels, 5/5 fit).

---

## What doesn't fit (and why that's useful to know)

Two of the repos we scanned had essentially zero classification
sites:

- **Airbyte CDK** (`airbyte-cdk`): 0 sites. Airbyte's Python CDK
  is predominantly abstract-class and stream-protocol code —
  it's the shape of a framework, not a classifier.
- **dbt-core**: 5 sites across 220 files. dbt's design centre is
  the DAG of SQL transformations, not branching Python decisions.

Dendra is for codebases that make **branching decisions about
data** — which bucket, which route, which label, which severity.
Codebases that primarily **transform data through a fixed
topology** (Airbyte's source→stream→record protocol, dbt's
DAG-of-models execution engine) naturally surface fewer sites.

If you run `dendra analyze` on your codebase and it finds two
sites, that's a signal your codebase isn't mostly
classification — not a failure mode.

---

## What comes after `dendra analyze`

The analyzer's job is to find the sites. After that, the typical
path for a team that decides to try Dendra:

1. **Wrap the highest-fit site with `@ml_switch` at Phase.RULE.**
   Zero behavior change. Outcome log starts accumulating.
   ```bash
   dendra init path/to/file.py:target_function --author "@you:team"
   ```
2. **Ship it. Wait.** A few weeks of production traffic gets you
   enough outcomes to know whether the rule is as accurate as
   you think it is.
3. **Run `dendra roi`** to see what an LLM-shadow or ML graduation
   would cost and save for the specific site.
4. **Advance the phase** when a paired-proportion statistical
   test (McNemar's exact) rejects the null hypothesis that the
   higher-tier classifier is no better than the rule.

The [paper](https://dendra.dev/paper) explains why the statistical
gate exists (and what goes wrong without one); the
[examples/](https://github.com/axiom-labs-os/dendra/tree/main/examples)
directory has five runnable demos for the most-common patterns.

---

## Try it on your own repo

```bash
pip install dendra
dendra analyze /path/to/your/python/code --format markdown > report.md
```

If the report looks interesting and you'd like to discuss how to
approach the top-fit sites in your codebase, we're running a
small design-partner program — see
[SUPPORT.md](../../SUPPORT.md#design-partner-program) in the
repo. Tier-1 slots are for teams already running production
classifiers at non-trivial scale; we'll offer 6-month priority
access to Dendra Cloud when it ships in exchange for case-study
rights and direct founder Slack.

Methodology note for those who want to reproduce: snapshots of
each repo were taken via `git clone --depth=1` on 2026-04-22;
the analyzer was invoked as `dendra analyze <path> --format
markdown` with no other flags. Full scan reports (not just the
excerpts above) are in the companion gist linked from the Dendra
launch post.

---

_Copyright (c) 2026 B-Tree Ventures, LLC (dba Axiom Labs).
Licensed CC-BY 4.0. DENDRA, TRANSITION CURVES, and AXIOM LABS
are trademarks of B-Tree Ventures, LLC._
