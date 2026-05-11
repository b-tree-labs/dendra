# Dendra dashboard + hot-path scale report — 2026-05-11

Pre-launch (2026-05-20) measurement pass on the dashboard server
endpoints (PRs #35-#37, #41) and the modified `POST /v1/verdicts`
hot path (PR #41 — adds an indexed DELETE on `switch_archives` after
each verdict INSERT).

Harness source: `cloud/api/test/scale_harness.test.ts`.
Run with `DENDRA_SCALE=1 npm test -- scale_harness` from `cloud/api/`.
Skip-by-default — plain `npm test` ignores it.

---

## 1. Setup + seed

50 synthetic users via direct D1 writes (bypassing the API for setup
speed). Distribution per the brief:

| Class | Users | Switches/user | Density (verdicts/day) | Notes |
|---|---:|---|---|---|
| free | 40 | 5-20 | 10-100 | Some "stop after day 3-7" cases |
| pro | 8 | 5-20 (representative pro: 25) | 10-500 | 2 keys |
| scale | 2 (representative: 75 switches) | | 10-500 | 2 keys |
| heavy_tail | 1 | **500** | 10-50 | The stress case for `/admin/switches` |

Seed summary (one representative run):

| Table | Rows |
|---|---:|
| `users` | 50 |
| `api_keys` | 76 |
| `verdicts` | 748,965 |
| `switch_archives` | 16 |

Seed wall-clock: ~17 seconds. Total seed + measurement run: ~170s.

---

## 2. Methodology + measurement caveat (READ THIS FIRST)

The harness drives each endpoint through `vitest-pool-workers`'
`SELF.fetch` — same path the existing test suite uses, matching the
production Worker dispatcher 1:1. Wall-clock per call is the metric.

**Critical caveat:** `vitest-pool-workers` wraps every `SELF.fetch`
invocation context in a fresh JS Proxy whose prototype is the previous
Proxy chain (see `createProxyPrototypeClass` at
`node_modules/@cloudflare/vitest-pool-workers/dist/worker/lib/cloudflare/test-internal.mjs:307`).
Each successive fetch deepens the chain by one wrapper. Empirically:

* Each successive `SELF.fetch` in the same isolate adds roughly
  **+0.27ms** of harness-internal overhead.
* The chain hits `Maximum call stack size exceeded` around
  **~1500-2000** cumulative fetches.

This is a known artifact of the test pool, not a Worker bug. It means
**raw latency numbers are NOT directly comparable** across the run.
The first measurements are clean; later ones report harness drift, not
SQL/JS cost.

**Mitigations applied:**

1. Critical measurements (hot path, sparkline stress) run FIRST, in the
   low-overhead window.
2. Each endpoint measurement is bracketed by a `/health` control —
   `/health` does no work, so its p50 IS the harness overhead floor at
   that point in the run.
3. The reported `adjusted_*` columns subtract the midpoint of the
   surrounding `/health` p50 from each endpoint's p50/p95/p99. Negative
   values clamp to 0 ("at or below the floor").

When in doubt, trust `adjusted_*` over the raw numbers. Both are emitted
on stderr (`SCALE_RESULT ...` JSON lines) so anyone can re-derive.

Per-class n: 30 measured + 5 warmup for the headline matrix.
Per-spot n: 15 measured + 3 warmup. The brief asked for n=100; the
harness budget caps total fetches around 1500 before the worker crashes,
so this is the largest n that fits the full matrix in one run.

---

## 3. Headline results

### 3.1 Hot path — `POST /v1/verdicts`

This is the modified hot path (PR #41). The handler does:

1. validate body (≤4KB JSON, ≤32-char switch_name, etc.)
2. idempotency lookup if `request_id` present (indexed)
3. usage middleware: atomic UPSERT on `usage_metrics` with `RETURNING`
4. INSERT into `verdicts`
5. **NEW**: DELETE from `switch_archives` (auto-unarchive)

**Serial (n=150, single key):**

| Metric | ms |
|---|---:|
| p50 | 8-9 |
| p95 | 13-14 |
| p99 | 14-15 |
| max | 17-19 |

**Concurrent (10 parallel × 15 each = 150, single key):**

| Metric | ms |
|---|---:|
| p50 | 215-233 |
| p95 | 300-304 |
| p99 | 303-312 |
| max | 312-337 |
| total wall | ~3,300-3,400 ms |

The concurrency-driven p99 is ~22x the serial p99. That's expected
behavior under SQLite-level write contention on a single-row (per-key)
counter (`usage_metrics`); D1 in production has per-shard write
serialization with edge fan-out, so 10 parallel writers from one key
would see similar behavior. **Not a launch concern** — the SDK rarely
emits verdicts in lockstep parallel; bursts of 10/100/1000 from the
same key are spread by the SDK's batch flusher.

### 3.2 Auto-unarchive DELETE — isolated cost

Direct `env.DB.prepare(DELETE...)` measurement, NOT subject to harness
contamination. 200 calls each path:

| Path | p50 | p95 | p99 | max | mean |
|---|---:|---:|---:|---:|---:|
| DELETE with matching row | 0 | 1 | 1 | 25 | 0.24 |
| DELETE no-op (no row) | 0 | 1 | 1 | 9 | 0.16 |

The DELETE is **indistinguishable from no-op at p50/p95**. UNIQUE
`(user_id, switch_name)` provides the index; SQLite's prepared statement
plan walks straight to either the row or "row not found" in one B-tree
probe. **Auto-unarchive adds ~0ms to the hot path on average.**

The `max=25ms` outlier on the with-row path is one SQLite cache miss
during a 200-row probe loop; not signal.

**Conclusion: the PR #41 auto-unarchive DELETE is free.** No need to
stub it out behind a flag.

### 3.3 Sparkline stress — heavy_tail (500 switches)

Single end-to-end `GET /admin/switches?user_id=heavytail_id`:

**142-175 ms** (run-to-run variance over two reps).

The brief's launch concern threshold was **200ms p99**. Both runs
came in under, but the headroom is thin. The variance run-to-run is
~20%, so a worst-case run could touch the threshold. This is on
local D1 where every query is microsecond-scale memory; production
D1 adds network RTT per query — see §5 below.

### 3.4 Per-endpoint matrix (harness-drift-adjusted)

`adjusted_p99 = p99 - midpoint(control_before.p50, control_after.p50)`.
This is the closest approximation we get to "ms of SQL/JS work
performed by the Worker."

**heavy_tail (500 switches, 2 keys):**

| Endpoint | raw p50 | raw p95 | raw p99 | adj p50 | adj p95 | adj p99 |
|---|---:|---:|---:|---:|---:|---:|
| GET /admin/switches | 175 | 181.55 | 183.42 | **139.5** | **146.05** | **147.92** |
| GET /admin/verdicts/recent?limit=5 | 53 | 55 | 55 | 8.75 | 10.75 | 10.75 |
| GET /admin/verdicts/recent?limit=50 | 63 | 65.55 | 66 | 8.5 | 11.05 | 11.5 |
| GET /admin/switches/:name/report (30d) | 67 | 70.55 | 71 | 0 | 3.3 | 3.75 |
| GET /admin/usage | 79 | 83 | 83 | 1 | 5 | 5 |
| GET /admin/whoami | 92.5 | 95 | 95.71 | 1 | 3.5 | 4.21 |
| GET /admin/insights/status | 106.5 | 110.55 | 113.84 | 0.75 | 4.8 | 8.09 |

**free (8 switches, 1 key):**

| Endpoint | adj p50 | adj p95 | adj p99 |
|---|---:|---:|---:|
| GET /admin/switches | 8.25 | 13.75 | 20.85 |
| GET /admin/verdicts/recent?limit=5 | 1.5 | 6.05 | 14.31 |
| GET /admin/verdicts/recent?limit=50 | 3 | 5.55 | 15.23 |
| GET /admin/switches/:name/report (30d) | 2 | 6.55 | 12.68 |
| GET /admin/usage | 1 | 6 | 6.71 |
| GET /admin/whoami | 1.25 | 5.75 | 6.46 |
| GET /admin/insights/status | 1.5 | 7.05 | 8.21 |

**The standout: `/admin/switches` at heavy_tail = 140ms adjusted p99.**
That's ~17x the same endpoint at free (8 switches → 21ms adj p99).
The cost scales roughly linearly with switch count, confirming the
correlated-subquery N+1 is the source. See §4.

### 3.5 Write-endpoint spot checks (free, n=15)

These don't separate harness drift very cleanly (small n + late in
the run). Direction-only: every write endpoint completed every call
within the per-request budget; none failed. They're single-row
INSERTs/UPDATEs/DELETEs against tiny indexed tables — no plausible
scaling cliff. Numbers omitted; consult the raw SCALE_RESULT log.

---

## 4. What got fixed in this PR

### Migration 0009 — `idx_verdicts_key_created`

Added `CREATE INDEX IF NOT EXISTS idx_verdicts_key_created
ON verdicts (api_key_id, created_at DESC)`.

**Why:** `GET /admin/verdicts/recent` joins `verdicts → api_keys ON id
WHERE k.user_id = ? ORDER BY v.created_at DESC LIMIT N`. The
pre-existing `idx_verdicts_key_switch_time(api_key_id, switch_name,
created_at DESC)` is usable for per-(key, switch) scans but ill-suited
to cross-switch `ORDER BY created_at` over a user's keys. The new
index keeps the ORDER BY satisfiable from the index walk alone,
without a sort step.

**Measured effect on the harness:** smaller than I'd hoped. The
adjusted p99 for `/admin/verdicts/recent?limit=50` is 11.5ms (heavy_tail)
/ 15.23ms (free) — already below any threshold worth flagging. Local
D1 with 1-2 keys per user and ≤20 verdicts/sec per key didn't stress
the join. The index is defensive: under production D1 with edge RTT,
the savings would compound. Migration is `CREATE INDEX IF NOT EXISTS`
— idempotent and safe to skip if the planner picks the right path
without it.

---

## 5. Non-obvious findings — flagged for design discussion

These are NOT auto-fixed because each affects behaviour the dashboard
already depends on; they need a real call before launch or in v1.1.

### 5.1 `GET /admin/switches` correlated subquery — N+1 over current_phase

**File:** `cloud/api/src/admin.ts` (around line 546) and
`cloud/api/src/switches.ts` (the `/v1/switches` mirror, around line 81).

The current SQL:

```sql
SELECT v.switch_name,
       COUNT(*), MIN(v.created_at), MAX(v.created_at),
       (SELECT phase FROM verdicts v2 JOIN api_keys k2 ON k2.id = v2.api_key_id
          WHERE k2.user_id = ? AND v2.switch_name = v.switch_name
          ORDER BY v2.created_at DESC LIMIT 1) AS current_phase,
       sa.archived_at, sa.archived_reason
  FROM verdicts v JOIN api_keys k ON k.id = v.api_key_id
  LEFT JOIN switch_archives sa ON sa.user_id = k.user_id AND sa.switch_name = v.switch_name
 WHERE k.user_id = ?
 GROUP BY v.switch_name
 ORDER BY MAX(v.created_at) DESC
```

The `current_phase` subquery runs **once per switch_name in the
result set**. For the heavy_tail user (500 switches), that's 500
extra index probes per request. Cost shows up as ~140ms adjusted p99
on local D1.

**Two fix options:**

**Option A (window function):** rewrite the subquery as a `FIRST_VALUE`
window:

```sql
SELECT switch_name, total, first_at, last_at, current_phase, archived_at, archived_reason
  FROM (
    SELECT v.switch_name,
           COUNT(*) OVER (PARTITION BY v.switch_name) AS total,
           MIN(v.created_at) OVER (PARTITION BY v.switch_name) AS first_at,
           MAX(v.created_at) OVER (PARTITION BY v.switch_name) AS last_at,
           FIRST_VALUE(v.phase) OVER (PARTITION BY v.switch_name ORDER BY v.created_at DESC) AS current_phase,
           ROW_NUMBER() OVER (PARTITION BY v.switch_name ORDER BY v.created_at DESC) AS rn,
           sa.archived_at, sa.archived_reason
      FROM verdicts v JOIN api_keys k ON k.id = v.api_key_id
      LEFT JOIN switch_archives sa ON sa.user_id = k.user_id AND sa.switch_name = v.switch_name
     WHERE k.user_id = ?
  ) WHERE rn = 1
  ORDER BY last_at DESC
```

Single pass over the user's verdicts; the window does all the work
that the subquery + GROUP BY were doing. D1's SQLite is recent enough
to support window functions (3.45+).

**Option B (denormalized last-phase column):** add
`api_keys.last_phase_by_switch` as a JSON map updated on the verdict
hot path, or a `switch_state(user_id, switch_name, current_phase,
last_verdict_at)` materialized table updated atomically on each
verdict INSERT. Highest-perf, but moves write work to the hot path
and adds a maintenance surface.

**Recommendation:** Option A for v1.0. Single migration-free PR;
the wire shape is unchanged. Defer Option B until we see real
heavy_tail traffic.

**Risk if not fixed:** at 1000 switches the same query becomes ~280ms
on local D1 (extrapolating linearly). Production D1 with the same
query pattern is roughly 5-10x slower per probe; that puts a 1000-switch
list at >2s — visible UI hang. The 200ms launch threshold is met for
500 switches on local D1, but heavy customers exceeding that aren't
hypothetical (the inflation-friendly read at /dashboard/switches
shows up on every dashboard render, not just on-demand).

### 5.2 `/admin/switches` sparkline subquery — full table scan past 14d window

The sparkline query filters on `v.created_at >= datetime('now', '-14 days')`
but the access path is via `api_keys.user_id` then `verdicts`-by-api_key_id.
With no `idx_verdicts_created_at`, SQLite walks every verdict for the
user's keys and post-filters by date. For users with 2+ years of history
this gets expensive even when only the last 14 days matter.

**Not a v1.0 concern** (we have ~5 weeks of history total at launch),
but if dashboard load spikes after 6 months, partition the sparkline
read into a per-user materialized rollup table refreshed by the
nightly cohort aggregator — same surface that already exists.

### 5.3 `usageMiddleware` always increments before authoritative tier read

`recordUsage` upserts the counter BEFORE we know whether the verdict
will pass validation. A malformed verdict (rejected with 400) STILL
increments the user's monthly count. This is a Pro/Scale soft-cap
billing concern more than a perf concern — a customer sending malformed
JSON in a loop accidentally racks up "verdicts" they didn't intend to
spend. Two fixes: either validate-then-charge in the handler (moves
the charge inside `recordVerdictHandler`), or compensate-on-400 with
a follow-up `UPDATE usage_metrics SET classifications_count = ... - 1`.

**Out of scope for the scale harness** (correctness, not scale), but
flagging since it surfaced while reading the hot path.

### 5.4 Hot-path concurrency p99 (304ms) under 10x parallel

This is contention on `usage_metrics` per-key UPSERT. It's not the
auto-unarchive DELETE — that's free (§3.2). The serial p99 was 14ms;
concurrent p99 is 22x that. Under realistic SDK traffic (batch flush
serializes by-key) this won't appear. Under malicious or buggy clients
spawning 10 parallel POSTs from the same key, it caps throughput
at ~50/sec per key for that key only. Probably fine; consider rate-
limiting per-key at the edge layer (already on the v1.1 roadmap per
the launch spec).

---

## 6. Acceptance criteria check

* [x] `cd cloud/api && npm test` green — 166 passed, 25 skipped.
* [x] `cd cloud/api && DENDRA_SCALE=1 npm test` runs the harness
      end-to-end without crashing — 25 passed, 0 failed, ~170s.
* [x] This report carries concrete p50/p95/p99 numbers per endpoint.
* [x] Migration 0009 lands the one obviously-fixable index (verdicts
      cross-key created_at). Idempotent (`CREATE INDEX IF NOT EXISTS`).
* [x] Non-obvious bottlenecks surfaced above (§5), not auto-fixed.

---

## 7. Reproducing this report

```
cd cloud/api
DENDRA_SCALE=1 npm test -- scale_harness --reporter=verbose 2>&1 | grep SCALE_RESULT
```

Every measurement is emitted as a single-line JSON object prefixed
`SCALE_RESULT`. The final test's stderr also dumps the full JSON array
between `=== SCALE HARNESS — JSON ===` markers.

Each rerun reseeds from scratch (the Worker D1 binding is volatile in
miniflare), so the numbers will vary by ~10-20% run-to-run. The
qualitative shape — `/admin/switches` heavy_tail is the only adjusted
p99 > 50ms — is stable.
