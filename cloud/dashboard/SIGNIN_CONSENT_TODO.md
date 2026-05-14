# Sign-in consent UX — TODO

Status: pending, owned by the dashboard-UX agent (not this branch).

## Decision (2026-05-11)

Verdict telemetry for the hosted API is **default-on for signed-in
users** — but NOT silent. The sign-up flow must announce it at the
point of consent, and `/dashboard/settings` must surface an opt-out
toggle at any time.

This branch (`feat/telemetry-pipeline`) ships the SDK + server pipes
and the env-var / per-switch opt-outs. The user-facing announcement
is the missing piece this file is reserving.

## Required UX

### 1. Sign-up flow banner

After the user completes the device-flow authorization at
`/cli-auth?user_code=…` (or the dashboard's first-time setup
wizard), display a one-block consent banner BEFORE the
"You're signed in" success screen.

Two short lines, no marketing copy:

> **What we collect:** one event per verdict — switch name, phase,
> and which classifiers were correct. No inputs, no labels, no
> code, no metadata.
>
> **What you get:** a real dashboard, the earned-upgrade trigger,
> honest "verdicts / mo" metering on your tier.

Include a toggle, default-ON, labeled `Send verdict telemetry`.
The toggle controls the same setting as `/dashboard/settings`
and writes through to the user's account row in D1 (new column,
see schema TODO below).

### 2. Persistent control on `/dashboard/settings`

Add a `Telemetry` section with the same toggle and one paragraph
of context. When opted-out, the SDK respects the server's
`whoami` response (which already returns tier + account_hash —
extend to return `telemetry_enabled: bool`) and short-circuits.

### 3. SDK enforcement of the dashboard opt-out

Today the SDK honors `POSTRULE_NO_TELEMETRY=1` (env) and
`telemetry=NullEmitter()` (per-switch). To make the dashboard
toggle authoritative, on first `record_verdict` the cloud
emitter should call `GET /v1/whoami`, cache `telemetry_enabled`
in-memory for the process, and stop emitting if False.

Cache TTL: 1 hour. Network failure → assume the cached value
(or True if no cache yet). This is the "fail-open" choice and
matches the launch posture: overdeliver on value before asking
for payment.

## Schema TODO (not in this branch)

`users` table needs a `telemetry_enabled INTEGER NOT NULL DEFAULT 1`
column. Migration `0007_telemetry_opt_out.sql`. The `whoami`
response handler adds the field to its return shape; the dashboard
admin endpoint writes the column.

## Cross-references

- SDK side: `src/postrule/cloud/verdict_telemetry.py`,
  `src/postrule/telemetry.py` (env-var hook).
- Server side: `cloud/api/src/verdicts.ts`,
  `cloud/api/src/usage.ts` (cap enforcement),
  `cloud/collector/migrations/0004_verdicts.sql`.
- Decision context: launch is 2026-05-20; this UX work must land
  on `main` before the cloud emitter installs itself on a real
  signed-in user.

## Out of scope for this file

- Dashboard brand styling (owned elsewhere).
- The actual TypeScript/React diff (owned by the dashboard agent).
- Pricing-tier copy on the landing page (owned by another agent).
