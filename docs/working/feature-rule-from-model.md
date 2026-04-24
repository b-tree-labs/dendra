# Feature: rule-from-model + self-describing actions

**Status:** Exploration 2026-04-24. Owner: Benjamin Booth.

## The idea

Today Dendra's stance is "you bring the rule." The counter-idea:
flip it for cold-start — the user brings *actions* (what should
happen for each label) plus a handful of example inputs, and the
LLM drafts the initial rule. The user inspects / edits / adopts the
rule, and from that point forward Dendra's "rule is yours, written
by you" invariant holds.

This doesn't displace the current story. It **enables** it for
users who don't have a rule yet. The hand-written rule stays the
architectural floor; we just reduce the cold-start friction of
writing it.

## Shape of the API

```python
from dendra import propose_rule, Label

draft = propose_rule(
    labels={
        "bug": Label("bug", on=send_to_engineering,
                     describe="Crashes, errors, stack traces, unexpected behavior."),
        "question": Label("question", on=send_to_support,
                          describe="User asks how to do something."),
        "feature_request": Label("feature_request", on=send_to_product,
                                 describe="User asks for new capability."),
    },
    examples=[
        ({"title": "app crashes on login"}, "bug"),
        ({"title": "how do I export data?"}, "question"),
        ({"title": "please add dark mode"}, "feature_request"),
    ],
    model=AnthropicAdapter("claude-sonnet-4-7"),
)

# draft is a ProposedRule: has `.source_code` (Python text of the
# function) and `.function` (the compiled callable)
print(draft.source_code)
#
# def triage_rule(ticket: dict) -> str:
#     """Proposed by @dendra-propose-rule at 2026-04-24T15:22:03Z.
#     Based on 3 examples; 2 rounds; accepted after 1 iteration.
#     Review before shipping — the rule is yours to own."""
#     title = (ticket.get("title") or "").lower()
#     if any(k in title for k in ("crash", "error", "exception", "fail")):
#         return "bug"
#     if title.endswith("?") or title.startswith(("how ", "can i ", "what ")):
#         return "question"
#     return "feature_request"

# Ship it as-is, or edit it. The decorator wraps whatever the
# user commits to the file.
```

## Components

1. **`Label.describe: str`** — new optional field on `Label`. A
   human-readable description of what the label means. Used by
   `propose_rule` as part of the prompt; invisible otherwise.

2. **`propose_rule(labels, examples, model, *, max_iterations=2, alpha=0.95)`**
   — new public function in `dendra.propose` module. Prompts the
   LLM with labels + descriptions + examples, asks for a rule
   function, syntactically validates the return, runs it against
   the provided examples, iterates if accuracy falls below
   `alpha`.

3. **`ProposedRule` dataclass** — returned by `propose_rule`.
   Fields: `source_code` (str), `function` (callable),
   `accepted_after_iterations` (int), `training_accuracy` (float),
   `prompt_hash` (str, for repro), `model_version` (str).

4. **CLI surface** — `dendra propose src/triage.py` prompts for
   labels + examples interactively, writes the proposed rule to
   the file, exits. Matches `dendra init` pattern.

## Self-describing actions

The second half of Ben's idea: actions with a `describe` string
(or docstring) the LLM can read. Two paths:

**Path A — `Label.describe`** (simpler): the `describe` field on
`Label` is the semantic description. The action callable's
docstring is optional. `propose_rule` uses only `label.describe`.

**Path B — action-docstring introspection** (richer): if
`label.on` is a function with a docstring, use that as the
description. Less for the user to type; more coupling between
the action's purpose and its semantic meaning.

My recommendation: **ship Path A only** for v0.3. Path B adds
introspection magic that's hard to audit; users who want it can
write `describe=send_to_engineering.__doc__` themselves. Keep
the path explicit.

## Risks / footguns

1. **The proposed rule looks plausible but is wrong.** LLMs
   generate plausible Python that passes 3 examples but fails on
   inputs the examples didn't cover. Mitigation: `propose_rule`
   runs the candidate against the examples and iterates; also
   prints the training accuracy loudly. Users MUST review the
   source — that's the whole point of keeping the rule
   user-owned.

2. **Prompt-injection via `Label.describe`**. An attacker who
   controls the label descriptions could inject system-prompt
   manipulation. Mitigation: descriptions are NOT read from
   user input at runtime — they're written by the switch author
   in source code. Same trust boundary as any function body.

3. **Supply-chain risk on the generated rule**. The rule can
   call anything Python can call. Dendra's current trust model
   assumes the rule is inspected; that assumption holds here
   because `propose_rule` writes Python source the user reads
   before committing.

4. **Cost** — LLM call per propose. For `dendra propose` this is
   one-shot; fine. Not on the hot path.

## When it fits / when it doesn't

**Fits:** brand-new projects, demo/onboarding, exploratory label
schemes, teaching the primitive.

**Doesn't fit:** regulated classifications where the rule must
be auditor-reviewed (they'll write it themselves regardless),
adversarial inputs where the LLM's sampled rule may include
bias / jailbreak patterns.

## Effort estimate

- `propose_rule` + `ProposedRule` + tests: ~200 LoC, 1 session.
- `Label.describe` field: ~10 LoC + docs + tests. 30 min.
- `dendra propose` CLI: ~80 LoC + integration test. Half-session.
- Docs + example `09_propose_rule.py`: half-session.

**Total: 2 sessions.** Not in v1.0; target v0.3 or v1.1
depending on launch pacing.

## v1 position

NOT v1. v1 ships the graduated-autonomy story with user-written
rules. `propose_rule` is a cold-start accelerator that fits the
"second tagline" strategy pattern — ship adjacent, let the
community discover it once the core thesis is grounded.
