# Feature: multi-LLM comparison

**Status:** Designed 2026-04-23. Target ship: v0.3.
**Owner:** Benjamin Booth.

## Claim

Dendra already logs the data needed to tell you which LLM wins
for your specific classification problem. Make this a first-class
feature: accept `llm=` as a list, run all configured LLMs in
parallel at `Phase.LLM_SHADOW`, emit a scorecard via `dendra
compare`.

## User-facing API

```python
switch = LearnedSwitch(
    name="triage",
    rule=rule,
    author="@triage:support",
    llm=[
        AnthropicAdapter("claude-sonnet-4-5"),
        OpenAIAdapter("gpt-5-mini"),
        OllamaAdapter("llama-3.3-8b", base_url="http://localhost:11434"),
    ],
    config=SwitchConfig(starting_phase=Phase.LLM_SHADOW),
)
```

At `LLM_SHADOW`, every classification runs all N LLMs in parallel
(asyncio.gather internally). All predictions, confidences,
latencies, and estimated costs are recorded per-call in the
outcome record's `llm_outputs: dict[str, LLMPrediction]` field.

At `LLM_PRIMARY`, one LLM is explicitly designated as the
decider; the others continue to shadow until cost or latency
concerns retire them.

## "Which LLM is winning" — `dendra compare`

```bash
dendra compare runtime/dendra/triage/ --output markdown
```

Produces a scorecard:

| LLM | Agreement vs. ground truth | p50 latency | $/1k calls | McNemar vs rule | McNemar vs winner |
|---|---|---|---|---|---|
| claude-sonnet-4-5 | 92.4% | 680 ms | $3.10 | p < 0.001 | — (winner) |
| gpt-5-mini | 89.1% | 310 ms | $0.40 | p < 0.001 | p = 0.02 |
| llama-3.3-8b (local) | 84.7% | 45 ms | $0.00 | p < 0.001 | p < 0.001 |

Three questions answered: which is most accurate, which is
cheapest, which is fastest — with statistical significance
markers distinguishing real differences from sampling variance.

## Category-specific routing recommendations

`dendra compare --by-category` partitions the outcome log by
input category (keyword clustering of titles, or explicit user-
provided category tags) and emits per-category winners:

```yaml
# dendra-route.yml
categories:
  billing:
    winner: gpt-5-mini     # wins on cost-accuracy for short tickets
    confidence: 0.91
  crash_report:
    winner: claude-sonnet  # highest accuracy on multi-line stack traces
    confidence: 0.86
default:
  winner: llama-3.3-8b     # cheapest, good enough for the long tail
```

This YAML can be fed back into `LearnedSwitch` as routing
config (future API): `llm_router=RouterFromYAML("dendra-route.yml")`.

## Implementation notes for the Rust + WASM core refactor

The core doesn't need to know about multiple LLMs per se — it
receives pre-computed LLM predictions and routes. The multi-LLM
parallelism is a host-layer concern (asyncio in Python, Promise.all
in TypeScript). The host-layer wrapper orchestrates the parallel
calls, then feeds the results to the core's routing logic.

`dendra compare` is a host-layer CLI that reads the outcome log
and runs the scorecard computation (which is shared Rust core
code — statistical tests + aggregation).

## Patent alignment

`docs/working/patent-strategy.md` §14.8 ("ensemble / interpolated
/ hybrid decision-makers") and §14.2 ("LLM-managed phase") both
anticipate this. Building it moves the claim from "anticipated"
to "shipped" — strengthens the infringement-reach story.

## Positioning

Opens a distinct tagline alongside the primary:

> "Pick the right LLM with statistical significance."

Not the primary framing (which stays on graduated-autonomy), but
a compelling adjacent capability that earns Dendra a second
audience: teams who don't care about ML graduation but DO care
about choosing LLMs rigorously.

## Tasks to ship (after Rust + WASM refactor)

1. Extend `LearnedSwitch` to accept `llm: LLMClassifier | list[LLMClassifier]`.
2. Parallel dispatch in classify() when list is present.
3. Extend `OutcomeRecord` with `llm_outputs: dict[str, LLMPrediction]` (keyed by adapter name).
4. Extend `dendra bench` to record per-LLM metrics when multi-LLM is used.
5. New `dendra compare` CLI.
6. Example `examples/08_llm_comparison.py`.
7. Landing-page section demonstrating the scorecard output.
8. Update `brand/messaging.md` with the second tagline.
