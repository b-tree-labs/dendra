# Dendra Insights collector

Cloudflare Worker that ingests anonymized cohort telemetry events
into a D1 database. Two routes: `POST /v1/events` and `GET /health`.

Privacy posture per
[`docs/working/telemetry-program-design-2026-04-28.md`](../../docs/working/telemetry-program-design-2026-04-28.md):
shape-only, no source code, no labels, no prompt content. Server-side
key whitelist enforces the schema even if a client sends extra fields.

## Layout

```
cloud/collector/
├── README.md                  # this file
├── wrangler.toml              # deploy config; staging + production envs
├── package.json               # Wrangler + TS types
├── tsconfig.json
├── src/
│   └── index.ts               # the Worker (one fetch handler, two routes)
└── migrations/
    └── 0001_initial.sql       # D1 events table; managed by wrangler d1 migrations
```

## One-time setup

Done once per environment, before first deploy.

### 1. Create the D1 databases

```bash
cd cloud/collector
wrangler d1 create dendra-events-staging
wrangler d1 create dendra-events
```

Each command prints a `database_id`. Paste them into the corresponding
`database_id = "..."` lines in `wrangler.toml` (currently commented out
with `TODO-fill-in-after-create`).

### 2. Apply the migrations

```bash
wrangler d1 migrations apply dendra-events-staging
wrangler d1 migrations apply dendra-events --env production --remote
```

Wrangler tracks applied migrations in a `d1_migrations` table inside
the database itself. Re-running is safe; it skips applied migrations.

### 3. (Optional) Add a Sentry DSN

```bash
wrangler secret put SENTRY_DSN
wrangler secret put SENTRY_DSN --env production
```

Worker reads `env.SENTRY_DSN` at runtime. If unset, errors only land
in `wrangler tail` / Cloudflare Workers Analytics. v1 ships without
Sentry; the secret slot is reserved.

## Deploy

```bash
# Staging — runs at staging-collector.dendra.run
wrangler deploy

# Production — runs at collector.dendra.run
wrangler deploy --env production
```

Wrangler reads `wrangler.toml` and binds the Worker to the configured
custom domain. First deploy provisions TLS automatically (~2 min).

## Verify

```bash
# Health
curl -sS https://staging-collector.dendra.run/health | jq

# Sample POST (synthetic event)
curl -sS -X POST https://staging-collector.dendra.run/v1/events \
  -H 'content-type: application/json' \
  -d '{
    "schema_version": 1,
    "events": [
      {
        "event_type": "analyze",
        "timestamp": "2026-04-30T12:00:00+00:00",
        "schema_version": 1,
        "site_fingerprint": null,
        "payload": {
          "files_scanned": 100,
          "total_sites": 12,
          "already_dendrified_count": 0,
          "pattern_histogram": {"P1": 8, "P4": 4},
          "regime_histogram": {"narrow": 10, "medium": 2},
          "lift_status_histogram": {"auto_liftable": 7},
          "hazard_category_histogram": {}
        }
      }
    ]
  }'
```

Expected response:

```json
{ "status": "ok", "inserted": 1, "rejected": 0 }
```

## Tail logs

```bash
wrangler tail                        # staging
wrangler tail --env production       # prod
```

## Schema migrations

```bash
# Create a new migration
wrangler d1 migrations create dendra-events-staging <description>

# Apply
wrangler d1 migrations apply dendra-events-staging
wrangler d1 migrations apply dendra-events --env production --remote
```

Migrations are SQL-only, up-only, and tracked in
`migrations/NNNN_<name>.sql` with state stored in D1's
`d1_migrations` system table. Manual rollback is a new "down"
migration applied as another up step. v1.0 ships one migration
(`0001_initial.sql`); subsequent schema changes land as `0002_*.sql`,
etc.

## What this Worker does NOT do (yet)

These are deliberately out of scope for v1.0; some land in v1.1.

- **No authentication** on `POST /v1/events`. Cloudflare's free DDoS
  protection + the schema whitelist + payload-size cap are the
  defense lines. Phase B adds API-key auth via the account system.
- **No rate limiting** beyond Cloudflare's platform-wide. Phase B
  introduces per-account-hash quotas.
- **No real-time aggregation**. Events accumulate in `events`; the
  nightly aggregator job (under `cloud/aggregator/`) reads and
  rolls up.
- **No Sentry integration in code yet** — the env var slot is
  reserved but `index.ts` only logs to Cloudflare console.
- **No GDPR Article 15 export endpoint**. Phase B adds
  `GET /v1/account/<hash>/export`.
- **No abuse-metadata cleanup job**. The `request_country` /
  `request_asn` / `request_user_agent` columns retain forever in
  v1.0; Phase B adds a 30-day TTL via a scheduled cleanup job.

## Cost projection

| Item | Free tier | Cost above tier | At launch scale |
|---|---|---|---|
| Worker requests | 100K/day free | $0.50/M | $0 (well below) |
| Worker CPU time | 10ms-day free | $30/M ms | $0 |
| D1 row reads | 25M/day free | $0.001/1K | $0 |
| D1 row writes | 50K/day free | $1/M | $0 (10K events/day fits) |
| D1 storage | 5GB free | $0.75/GB-month | $0 (estimated <100MB at 1Y) |

At projected launch volume (100 customers × ~30 events/day = 3K
events/day) we're 1-2 orders of magnitude below every free-tier
threshold. Even a 100x growth scenario fits in <$10/month.
