# Externalization boundary

**Status:** Decided 2026-04-23. Architectural principle — informs
every future plugin decision.
**Owner:** Benjamin Booth.

## Principle

> The rule is always evaluated locally, in-process, trusting only
> local code. Everything that can be remote is remote. Nothing on
> the decision path is.

This is the architectural version of the "rule as safety floor"
claim from the paper. The safety floor's value depends on it
being locally evaluable — a remote-config flag that disables it
is a vulnerability, not a feature.

## What externalizes (plugin protocols, current or planned)

| Capability | Current | Planned |
|---|---|---|
| Storage backend | `Storage` protocol with `InMemoryStorage`, `FileStorage` | S3, Postgres, DynamoDB, hosted Dendra Cloud |
| LLM adapters | OpenAI, Anthropic, Ollama, Llamafile | Gemini, Mistral, any HTTP-protocol LLM |
| ML heads | `MLHead` protocol with `SklearnTextHead` | sentence-transformer, ONNX, custom |
| Telemetry emitters | `TelemetryEmitter` protocol | Datadog, Honeycomb, LangSmith, LogFire, OTel |
| Signal sinks | — | Slack, PagerDuty, Opsgenie, webhook, logging |
| Gate protocols | — | McNemar, AccuracyMargin, MinVolume, Composite |
| Config source | Constructor kwargs | Dendra Cloud remote config (signed) |
| Model registry | — | Dendra Cloud "which ML model versions can this switch graduate to" |
| Federation | — | Opt-in cross-org outcome-pattern aggregation (Y2+) |

## What does NOT externalize (keep local)

| Capability | Why not |
|---|---|
| **Rule evaluation** | The rule IS customer code; serializing for remote execution is unsafe (arbitrary-code risk) and breaks the "rule as safety floor" guarantee. |
| **Safety-critical construction check** | Must happen at Python `__post_init__` / LearnedSwitch `__init__` — unbypassable, visible in stack traces. A remote-config flag could be intercepted or delayed. |
| **Circuit breaker trip decision** | Local state; sub-millisecond response; distributed consensus introduces a new failure mode and adds latency to the safety-floor path. |
| **Phase-advancement state at runtime** | The switch must know its own phase instantly — can't make this a remote call per classification. |
| **Verdict log write path** | Local-first; async replication if desired. Never block a decision on remote log-write success. |
| **`safety_critical=True` enforcement** | Same reason as safety-critical construction check — must be unbypassable architecture. |
| **`phase_limit` enforcement at `advance()` time** | Must be local; a remote override of the ceiling undermines the operator's safety guarantee. |

## Security considerations

Three properties must hold regardless of which external services
Dendra is connected to:

1. **A compromised external service cannot bypass the rule floor.**
   If the hosted Dendra Cloud is breached, the worst the attacker
   can do is alter outcome log metadata or push bad remote config.
   The local rule keeps deciding, the local safety-critical check
   keeps refusing ML_PRIMARY, the local breaker keeps routing to
   the rule on ML failure.

2. **External config changes require signed/authenticated
   payloads.** No unsigned webhook can push new `phase_limit`
   values or disable `safety_critical`. A compromised signing key
   is a bigger incident than a compromised webhook, by design.

3. **The rule-floor property is enforceable locally.** A Dendra
   deployment with no network access should still:
   - Evaluate the rule on every call.
   - Refuse construction in safety-critical + ML_PRIMARY.
   - Fall back to rule on ML failure via the local breaker.

   All three above are true of the current implementation; keeping
   them true as we add remote surfaces is the architectural
   commitment.

## Data exfiltration boundary

Inputs to the classifier may contain PII (tickets, medical text,
legal documents). Dendra's design:

- **Storage** may ship outcome records to remote services IF the
  user has configured a remote `Storage` backend — this is
  opt-in, not default.
- **LLM adapters** send inputs to whatever provider the adapter
  is configured for — the user has explicitly chosen this by
  configuring the adapter.
- **Telemetry emitters** send metadata (latency, count, phase)
  but NEVER the raw classification input — this is an adapter-
  level invariant enforced by the TelemetryEmitter protocol.
- **Federation (Y2+)** sends *hashed input signatures* and
  *label distributions* — never raw inputs. The federation
  protocol cryptographically commits to that boundary.

## Patent alignment

The externalization-boundary principle is a durable brand
commitment, not a patent-adjacent claim. It's how we can sell
"safety floor" to regulated-industry buyers without being
accused of marketing-theater: the floor is local, measurable,
and unremovable.

## Applies to

Every future design decision in Dendra should be checked against
this boundary. If a feature proposes to put any row from the
"does NOT externalize" table onto a network call, the proposal
must articulate why the property can still hold, or the feature
is rejected.
