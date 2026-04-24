# Feature: circuit-breaker recovery policies

**Status:** Designed 2026-04-23. Target ship: v0.3.
**Owner:** Benjamin Booth.

## Claim

Every breaker policy does the same baseline: trip → route to
rule → emit event to configured signal sinks → surface state for
observability. What differs is *how recovery happens*: manual
(operator resets explicitly) or self-healing (probes ML, resets
automatically when healthy).

## Configuration

```python
breaker = CircuitBreakerConfig(
    trip_after=3,                    # consecutive ML failures before tripping
    recovery=Recovery.MANUAL,        # MANUAL | SELF_HEAL
    signal_sink=SlackSink(webhook_url=...),
    self_heal=SelfHealPolicy(
        probe_cadence_seconds=30,    # start
        backoff_max_seconds=1800,    # cap at 30 min
        min_consecutive_ok=3,        # require hysteresis before reset
        window_size=10,              # rolling probe window
        flap_window_seconds=600,     # trip + reset + trip within 10 min
        flap_action=FlapAction.PROMOTE_TO_MANUAL,
    ),
)

config = SwitchConfig(
    starting_phase=Phase.ML_WITH_FALLBACK,
    breaker=breaker,
)
```

## Policies

### `Recovery.MANUAL` (default)

Trip → stay tripped → await explicit operator reset. Notification
is immediate via `signal_sink`. Escalation via exponential backoff:

- T+0: warn-level alert
- T+10 min (no reset): error-level alert
- T+30 min: page escalation chain (if PagerDutySink configured)

### `Recovery.SELF_HEAL`

Trip → probe ML head at exponentially-backed-off cadence (30s →
1min → 2min → 5min → 15min → 30min cap). Reset when rolling
probe window hits `min_consecutive_ok` healthy probes. Flap
detection: if trip/reset/trip cycle happens within
`flap_window_seconds`, apply `flap_action` (by default: promote
to MANUAL policy for this breaker until operator resets).

### Why no separate MONITOR_ONLY

All policies emit events and surface state. "Monitor-only" was
redundant with MANUAL minus the notification urgency, which is
a signal-sink config not a policy distinction.

## How MANUAL reset happens (three interfaces)

**1. CLI** — local / dev / single-node production:
```bash
dendra breaker reset <switch-name>
```
Authenticates via local file-system permissions (OSS) or
signed-token HTTP (Cloud).

**2. Signal-sink reply loop** — most operator-friendly:
- Breaker trips, emits alert via `SlackSink` to a configured channel.
- Operator reviews ML logs, decides to reset.
- Replies `/dendra-reset triage` (or `ack` via PagerDuty) in the original alert thread.
- The signal sink's reply webhook routes the command back to the running Dendra instance; breaker resets.

**3. HTTP admin endpoint** — Cloud-tier:
```
POST /switches/{name}/breaker/reset
Authorization: Bearer <signed-token>
```

All three interfaces are on Solo tier and above — breaker reset
is a safety feature, not a premium differentiator. Premium
differentiation lives in audit trails, multi-user approval, and
automated-policy authoring.

## Exponential backoff applied elsewhere

Same mechanism used in three places:

| Where | Cadence |
|---|---|
| SELF_HEAL probe cadence | 30s → 1min → 2min → 5min → 15min → 30min cap |
| MANUAL notification escalation | warn → error (T+10min) → page (T+30min) |
| LLM retry within a single classify call | 100ms → 300ms → 1s → 3s (max 3 retries) |

Safety-critical switches can disable self-heal entirely
(`probe_cadence=None` disables probing; MANUAL-only).

## Brand motion implication

The error-state animation for the mark (per `brand/motion.md`):
when a breaker trips, the accent stroke retreats *below* the
rule floor — inverse of the rising animation. One-shot, no
auto-reset of the animation. Semiotically consistent with "the
floor holds; evidence is below it." Reset fires the rising
animation again on success.

## Pricing implication

Adjustment to `docs/marketing/business-model-and-moat.md` §3.1
tier ladder:

| Feature | Free hosted | Solo ($19) | Team ($99) | Pro ($499) | Scale ($2499) |
|---|---|---|---|---|---|
| CLI breaker reset | ✓ | ✓ | ✓ | ✓ | ✓ |
| Signal-sink reply reset (Slack/PagerDuty) | — | ✓ | ✓ | ✓ | ✓ |
| HTTP admin endpoint | — | ✓ | ✓ | ✓ | ✓ |
| Multi-user approval workflow | — | — | ✓ | ✓ | ✓ |
| Breaker-event immutable audit log | — | — | — | ✓ | ✓ |
| Automated reset-policy authoring UI | — | — | — | ✓ | ✓ |

## Tasks to ship

1. `CircuitBreakerConfig` dataclass (Rust core + Python / TS hosts).
2. `Recovery` enum (MANUAL, SELF_HEAL).
3. State machine in Rust core implementing both policies with exponential backoff.
4. `SignalSink` protocol + implementations: `SlackSink`, `PagerDutySink`, `WebhookSink`, `LoggingSink`.
5. Flap-detection with `FlapAction` enum.
6. CLI subcommand `dendra breaker reset <name>`.
7. Signal-sink reply webhook receiver (Cloud-tier feature).
8. HTTP admin endpoint (Cloud-tier feature).
9. Error-state animation SVG (`brand/logo/dendra-mark-breaker-tripped.svg`) per motion spec.
10. Pricing-tier table update.
