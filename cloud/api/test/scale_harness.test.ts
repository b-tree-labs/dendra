// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Scale-measurement harness for the dashboard server endpoints + the
// modified POST /v1/verdicts hot path. Skipped by default; runs only
// when DENDRA_SCALE=1 is set in the environment. End-to-end via
// vitest-pool-workers SELF.fetch + the same D1 binding the production
// Worker uses — measures the same code path the dashboard hits in
// production. Local D1 + Worker (not staging-mirror).
//
// Output:
//   * Console: a markdown-shaped summary table + a JSON blob with
//     percentile arrays per endpoint per user-class.
//   * cloud/api/test/SCALE_REPORT-<YYYY-MM-DD>.md (committed) carries
//     the curated findings + concerns. The console JSON is the
//     primary input the report is built from; rerun with
//     DENDRA_SCALE=1 to regenerate numbers and rewrite the report
//     by hand.
//
// Methodology:
//   * Seed 50 synthetic users via direct D1 writes (bypass API key
//     hashing — we register one real key per user via the API so
//     bearer auth works for /v1/verdicts).
//   * For each user: 1-2 api_keys.
//   * Distribution-shaped switch counts: 40 free users with 5-15
//     switches, 8 pro with 20-50, 2 scale with 50-100, plus ONE
//     heavy-tail user with 500 switches.
//   * For each switch: 14 days of verdicts at varying densities
//     (10/day to 1000/day; "stop" cases that go cold 3-7 days in).
//   * A few switches archived (so /admin/switches has archived_count
//     work to do).
//
// Each endpoint is warmed (10 calls discarded) then measured 100
// times for p50/p95/p99. Wall-clock per call is the metric.

import { describe, it, beforeAll, expect } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';
import migration0005 from '../../collector/migrations/0005_cloud_features.sql?raw';
import migration0006 from '../../collector/migrations/0006_cli_sessions.sql?raw';
import migration0007 from '../../collector/migrations/0007_user_preferences.sql?raw';
import migration0008 from '../../collector/migrations/0008_switch_archives.sql?raw';
// Migration 0009 is the new index migration this PR introduces. Static
// import; the file is created as part of the same PR so it always
// exists. If you cherry-pick the harness onto a tree without 0009,
// remove this import + the corresponding applySql call below.
import migration0009 from '../../collector/migrations/0009_scale_indices.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
const BASE = 'https://api.test';
// DENDRA_SCALE is threaded through miniflare bindings in vitest.config.mts
// from the host's environment, so `DENDRA_SCALE=1 npm test` turns the
// harness on and plain `npm test` skips it.
const ENABLED = env.DENDRA_SCALE === '1';

// Persistent result store across the harness's it()s. The worker
// isolate is shared via singleWorker:true so this Array survives
// between blocks. Each result is ALSO streamed to stderr at the
// moment it's measured — stderr bypasses vitest's run-mode
// stdout buffering, so even if a downstream test crashes the
// worker isolate the measurements that already finished are in
// the captured log.
const RESULT_LOG: Record<string, unknown>[] = [];
function logResult(o: Record<string, unknown>): void {
  RESULT_LOG.push(o);
  // eslint-disable-next-line no-console
  console.error('SCALE_RESULT ' + JSON.stringify(o));
}

const adminHeaders = {
  'Content-Type': 'application/json',
  'X-Dashboard-Token': SERVICE_TOKEN,
};

// --------------------------------------------------------------------------
// SQL helpers (mirrors the pattern in the existing test files).
// --------------------------------------------------------------------------

async function applySql(sql: string) {
  if (!sql) return;
  const cleaned = sql
    .split('\n')
    .filter((l) => !l.trim().startsWith('--'))
    .join('\n');
  const stmts = cleaned
    .split(/;\s*(?:\n|$)/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  for (const s of stmts) {
    try {
      await env.DB.prepare(s).run();
    } catch (e) {
      if (!String(e).includes('already exists')) throw e;
    }
  }
}

// --------------------------------------------------------------------------
// Stats — percentile of a sample array (ms). Linear interpolation between
// adjacent ranks; matches the standard "type 7" definition used by R/numpy.
// --------------------------------------------------------------------------

function percentile(samples: number[], p: number): number {
  if (samples.length === 0) return 0;
  const sorted = [...samples].sort((a, b) => a - b);
  if (sorted.length === 1) return sorted[0]!;
  const rank = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(rank);
  const hi = Math.ceil(rank);
  if (lo === hi) return sorted[lo]!;
  const frac = rank - lo;
  return sorted[lo]! * (1 - frac) + sorted[hi]! * frac;
}

interface Stats {
  n: number;
  p50: number;
  p95: number;
  p99: number;
  max: number;
  mean: number;
}

function statsOf(samples: number[]): Stats {
  const sum = samples.reduce((a, b) => a + b, 0);
  return {
    n: samples.length,
    p50: round2(percentile(samples, 50)),
    p95: round2(percentile(samples, 95)),
    p99: round2(percentile(samples, 99)),
    max: round2(Math.max(...samples)),
    mean: round2(samples.length ? sum / samples.length : 0),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

// Wall-clock measurement around an async thunk. Returns ms.
async function timeMs(fn: () => Promise<unknown>): Promise<number> {
  const start = performance.now();
  await fn();
  return performance.now() - start;
}

// --------------------------------------------------------------------------
// Seed shape — distribution per the brief.
// --------------------------------------------------------------------------

interface SeededUser {
  user_id: number;
  clerk_user_id: string;
  email: string;
  tier: 'free' | 'pro' | 'scale';
  api_key_ids: number[];
  bearer: string;            // plaintext of the first key (for /v1/verdicts)
  switches: SeededSwitch[];
  class_label: string;        // 'free' | 'pro' | 'scale' | 'heavy_tail'
}

interface SeededSwitch {
  switch_name: string;
  verdicts_per_day: number;   // 10 .. 1000
  stops_after_day: number | null; // 3..7 inclusive; null = active every day
  is_archived: boolean;
}

// Deterministic PRNG so the harness is reproducible run-to-run.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(0xD3ED1A); // "DEDRA"-shaped seed
function randInt(lo: number, hi: number): number {
  return lo + Math.floor(rand() * (hi - lo + 1));
}
function randChoice<T>(xs: T[]): T {
  return xs[Math.floor(rand() * xs.length)]!;
}

const PHASES = ['P0', 'P1', 'P2', 'P3', 'P4', 'P5'] as const;

// Density buckets per the brief (10/day to 1000/day), with a per-class
// cap so the heavy-tail user doesn't blow out the seed budget. The
// stress case for /admin/switches is the number of distinct
// switch_name values, not the per-switch row count — local D1 in
// vitest-pool-workers tops out around a few hundred K rows in
// reasonable wall time.
function planSwitches(
  count: number,
  archivedCount: number,
  densityCap: number,
): SeededSwitch[] {
  const out: SeededSwitch[] = [];
  const densityBuckets = [10, 25, 50, 100, 250, 500, 1000].filter(
    (d) => d <= densityCap,
  );
  for (let i = 0; i < count; i++) {
    const density = randChoice(densityBuckets);
    const stops = rand() < 0.15 ? randInt(3, 7) : null;
    out.push({
      switch_name: `sw_${i.toString(36)}`,
      verdicts_per_day: density,
      stops_after_day: stops,
      is_archived: i < archivedCount,
    });
  }
  return out;
}

// --------------------------------------------------------------------------
// Direct-D1 seed path. Bypasses /v1/verdicts on purpose: validation +
// usage middleware + idempotency lookup add ~1ms each. We want bulk
// insert speed, not endpoint exercise — the endpoints get measured later.
// --------------------------------------------------------------------------

async function seedUser(u: {
  clerk_user_id: string;
  email: string;
  tier: SeededUser['tier'];
}): Promise<{ user_id: number; account_hash: string }> {
  // /admin/users handles upsert + tier columns + account_hash; cheap to
  // use the public surface for the user row itself.
  const res = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ clerk_user_id: u.clerk_user_id, email: u.email }),
  });
  const body = await res.json<{ user_id: number; account_hash: string }>();

  // Tier override — /admin/users always inserts as free.
  if (u.tier !== 'free') {
    await env.DB.prepare(
      `UPDATE users SET current_tier = ? WHERE id = ?`,
    )
      .bind(u.tier, body.user_id)
      .run();
  }
  return body;
}

async function issueKey(user_id: number, name: string): Promise<{ id: number; plaintext: string }> {
  const res = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id, name }),
  });
  if (res.status !== 200) {
    throw new Error(`issueKey failed: ${res.status} ${await res.text()}`);
  }
  const body = await res.json<{ id: number; plaintext: string }>();
  return { id: body.id, plaintext: body.plaintext };
}

// Bulk-insert verdicts via a single multi-row prepared statement per
// chunk. D1's SQLite build caps host parameters at 100 per statement;
// 7 columns per row → 14 rows per chunk fits comfortably. Returns the
// count inserted.
const VERDICT_CHUNK = 14;

async function bulkInsertVerdicts(
  api_key_id: number,
  switch_name: string,
  rows: Array<{ created_at: string; phase: string; rule_correct: 0 | 1; ml_correct: 0 | 1 }>,
): Promise<void> {
  for (let i = 0; i < rows.length; i += VERDICT_CHUNK) {
    const chunk = rows.slice(i, i + VERDICT_CHUNK);
    const placeholders = chunk.map(() => `(?, ?, ?, ?, ?, ?, ?)`).join(',\n');
    const binds: unknown[] = [];
    for (const r of chunk) {
      binds.push(api_key_id, switch_name, r.phase, r.rule_correct, null, r.ml_correct, r.created_at);
    }
    await env.DB.prepare(
      `INSERT INTO verdicts
         (api_key_id, switch_name, phase, rule_correct, model_correct, ml_correct, created_at)
       VALUES ${placeholders}`,
    )
      .bind(...binds)
      .run();
  }
}

function utcDateIso(daysAgo: number, secondsOffset: number): string {
  // Anchor to noon UTC so sparkline bucket arithmetic is unambiguous.
  const day = new Date(Date.now() - daysAgo * 86_400_000);
  day.setUTCHours(12, 0, 0, 0);
  const t = new Date(day.getTime() + secondsOffset * 1000);
  return t.toISOString().replace('T', ' ').replace(/\.\d+Z$/, '');
}

async function seedVerdicts(
  api_key_id: number,
  sw: SeededSwitch,
): Promise<number> {
  const rows: Array<{ created_at: string; phase: string; rule_correct: 0 | 1; ml_correct: 0 | 1 }> = [];
  // 14-day window, oldest first (days_ago 13 -> 0).
  for (let daysAgo = 13; daysAgo >= 0; daysAgo--) {
    // "Stops" cases: if a switch stops after day N (counting from start),
    // skip days closer to now than (13 - N).
    if (sw.stops_after_day !== null && daysAgo < 13 - sw.stops_after_day) {
      continue;
    }
    for (let i = 0; i < sw.verdicts_per_day; i++) {
      // Spread the day's verdicts across an hour band — close enough to
      // realistic for sparkline bucketing.
      const sec = Math.floor((i / sw.verdicts_per_day) * 3600);
      rows.push({
        created_at: utcDateIso(daysAgo, sec),
        phase: PHASES[Math.min(5, Math.floor(daysAgo / 3))]!,
        rule_correct: rand() < 0.85 ? 1 : 0,
        ml_correct: rand() < 0.88 ? 1 : 0,
      });
    }
  }
  await bulkInsertVerdicts(api_key_id, sw.switch_name, rows);
  return rows.length;
}

async function archiveSwitch(user_id: number, switch_name: string): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO switch_archives (user_id, switch_name, archived_reason)
     VALUES (?, ?, ?)
     ON CONFLICT(user_id, switch_name) DO NOTHING`,
  )
    .bind(user_id, switch_name, 'seeded')
    .run();
}

// Seed a full user end to end. Returns the user with all info needed
// for endpoint measurement.
async function seedFullUser(
  i: number,
  tier: SeededUser['tier'],
  classLabel: string,
  switchCount: number,
  archivedCount: number,
  keyCount: 1 | 2,
  densityCap = 1000,
): Promise<SeededUser> {
  const clerk_user_id = `scale_user_${i}`;
  const email = `scale${i}@example.com`;
  const userInfo = await seedUser({ clerk_user_id, email, tier });
  const switches = planSwitches(switchCount, archivedCount, densityCap);

  const apiKeyIds: number[] = [];
  let bearer = '';
  for (let k = 0; k < keyCount; k++) {
    const key = await issueKey(userInfo.user_id, `key-${k}`);
    apiKeyIds.push(key.id);
    if (k === 0) bearer = key.plaintext;
  }

  // Spread switches across the user's keys so the cross-key roster
  // unification path is exercised.
  for (let s = 0; s < switches.length; s++) {
    const sw = switches[s]!;
    const akid = apiKeyIds[s % apiKeyIds.length]!;
    await seedVerdicts(akid, sw);
    if (sw.is_archived) {
      await archiveSwitch(userInfo.user_id, sw.switch_name);
    }
  }

  return {
    user_id: userInfo.user_id,
    clerk_user_id,
    email,
    tier,
    api_key_ids: apiKeyIds,
    bearer,
    switches,
    class_label: classLabel,
  };
}

// --------------------------------------------------------------------------
// Endpoint exerciser. Returns wall-clock ms per call.
// --------------------------------------------------------------------------

type EndpointFn = (user: SeededUser) => Promise<Response>;

interface EndpointSpec {
  name: string;
  fn: EndpointFn;
  // Optional acceptable status set; defaults to "must be 2xx".
  okStatus?: number[];
}

function bearerHeaders(user: SeededUser): HeadersInit {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${user.bearer}`,
  };
}

function pickActiveSwitch(user: SeededUser): SeededSwitch {
  return user.switches.find((s) => !s.is_archived) ?? user.switches[0]!;
}

const ENDPOINTS: EndpointSpec[] = [
  {
    name: 'GET /admin/usage',
    fn: (u) => SELF.fetch(`${BASE}/admin/usage?user_id=${u.user_id}`, { headers: adminHeaders }),
  },
  {
    name: 'GET /admin/verdicts/recent?limit=5',
    fn: (u) => SELF.fetch(`${BASE}/admin/verdicts/recent?user_id=${u.user_id}&limit=5`, { headers: adminHeaders }),
  },
  {
    name: 'GET /admin/verdicts/recent?limit=50',
    fn: (u) => SELF.fetch(`${BASE}/admin/verdicts/recent?user_id=${u.user_id}&limit=50`, { headers: adminHeaders }),
  },
  {
    name: 'GET /admin/switches',
    fn: (u) => SELF.fetch(`${BASE}/admin/switches?user_id=${u.user_id}`, { headers: adminHeaders }),
  },
  {
    name: 'GET /admin/switches?include_archived=true',
    fn: (u) => SELF.fetch(`${BASE}/admin/switches?user_id=${u.user_id}&include_archived=true`, { headers: adminHeaders }),
  },
  {
    name: 'GET /admin/switches/:name/report (30d)',
    fn: (u) => {
      const sw = pickActiveSwitch(u);
      return SELF.fetch(
        `${BASE}/admin/switches/${sw.switch_name}/report?user_id=${u.user_id}&days=30`,
        { headers: adminHeaders },
      );
    },
  },
  {
    name: 'GET /admin/whoami',
    fn: (u) => SELF.fetch(`${BASE}/admin/whoami?user_id=${u.user_id}`, { headers: adminHeaders }),
  },
  {
    name: 'PATCH /admin/whoami',
    fn: (u) => SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: u.user_id, display_name: `User ${u.user_id}` }),
    }),
  },
  {
    name: 'GET /admin/insights/status',
    fn: (u) => SELF.fetch(`${BASE}/admin/insights/status?user_id=${u.user_id}`, { headers: adminHeaders }),
  },
  {
    name: 'POST /admin/insights/enroll',
    fn: (u) => SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: u.user_id }),
    }),
  },
  {
    name: 'POST /admin/insights/leave',
    fn: (u) => SELF.fetch(`${BASE}/admin/insights/leave`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: u.user_id }),
    }),
  },
  {
    name: 'POST /admin/switches/:name/archive',
    fn: (u) => {
      // Archive an active switch (different name each call to avoid
      // the no-op idempotent path masking the write).
      const sw = pickActiveSwitch(u);
      return SELF.fetch(`${BASE}/admin/switches/${sw.switch_name}/archive`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({ user_id: u.user_id, reason: 'scale test' }),
      });
    },
  },
  {
    name: 'POST /admin/switches/:name/unarchive',
    fn: (u) => {
      const sw = pickActiveSwitch(u);
      return SELF.fetch(`${BASE}/admin/switches/${sw.switch_name}/unarchive`, {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({ user_id: u.user_id }),
      });
    },
  },
];

// Yield the microtask queue. vitest-pool-workers accumulates internal
// async stack frames per SELF.fetch; without yields, hundreds of calls
// in a tight loop can blow `Maximum call stack size exceeded` in the
// test runtime. A macrotask yield every N iterations flushes the
// accumulated continuation chain.
function macrotaskYield(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// Per-endpoint measurement. Warm-up calls (discarded), then N
// measured calls. Default 3/20 — confidence-vs-budget compromise.
//
// The brief asks for 10/100 warmup/measure. vitest-pool-workers
// wraps every SELF.fetch's invocation context in a fresh JS Proxy
// whose prototype is the previous Proxy chain (createProxyPrototypeClass
// at @cloudflare/vitest-pool-workers/dist/worker/lib/cloudflare/test-internal.mjs:307).
// Each fetch deepens the prototype chain by one wrapper; after
// ~1500-2000 cumulative fetches in a single worker isolate, Proxy
// `get` traps recurse far enough to hit Maximum call stack size
// exceeded. Empirically the FREE class (13 endpoints × 110 fetches
// = 1430) reliably completes; adding PRO crashes around the 14-15th
// endpoint. The fix at the harness layer is to dial down per-test
// fetch count to 23/endpoint × 13 endpoints × 4 classes = 1196
// fetches for the endpoint sweep, plus ~310 for hot path + sparkline
// + per-class warmups, plus ~130 for setup = ~1640 total.
// Trade-off: p99 is less stable than with N=100. We report n
// alongside each percentile so the report reader can size the
// confidence interval.
async function measureEndpoint(
  spec: EndpointSpec,
  user: SeededUser,
  warmup = 3,
  measure = 20,
): Promise<{ name: string; class_label: string; stats: Stats; failures: number }> {
  let failures = 0;
  for (let i = 0; i < warmup; i++) {
    const res = await spec.fn(user);
    if (!res.ok && !(spec.okStatus?.includes(res.status))) failures++;
    await res.arrayBuffer().catch(() => null);
  }
  await macrotaskYield();
  const samples: number[] = [];
  for (let i = 0; i < measure; i++) {
    if (i > 0 && i % 20 === 0) await macrotaskYield();
    const t = await timeMs(async () => {
      const res = await spec.fn(user);
      if (!res.ok && !(spec.okStatus?.includes(res.status))) failures++;
      await res.arrayBuffer().catch(() => null);
    });
    samples.push(t);
  }
  return { name: spec.name, class_label: user.class_label, stats: statsOf(samples), failures };
}

// --------------------------------------------------------------------------
// Hot-path stress. Issues N verdict POSTs serially (and concurrently).
// --------------------------------------------------------------------------

async function postVerdict(user: SeededUser, switch_name: string, requestId?: string): Promise<Response> {
  return SELF.fetch(`${BASE}/v1/verdicts`, {
    method: 'POST',
    headers: bearerHeaders(user),
    body: JSON.stringify({
      switch_name,
      phase: 'P3',
      rule_correct: true,
      ml_correct: true,
      request_id: requestId,
    }),
  });
}

async function measureHotPathSerial(user: SeededUser, n: number): Promise<{ stats: Stats; failures: number }> {
  // Warm-up — 5 calls to prime caches; the per-endpoint matrix has
  // already warmed the verdicts/auth path repeatedly so 5 is enough.
  for (let i = 0; i < 5; i++) {
    const res = await postVerdict(user, 'hotpath_warmup', `warm-${user.user_id}-${i}`);
    await res.arrayBuffer().catch(() => null);
  }
  await macrotaskYield();
  const samples: number[] = [];
  let failures = 0;
  for (let i = 0; i < n; i++) {
    if (i > 0 && i % 25 === 0) await macrotaskYield();
    const t = await timeMs(async () => {
      const res = await postVerdict(user, 'hotpath_serial', `serial-${user.user_id}-${i}`);
      if (!res.ok) failures++;
      await res.arrayBuffer().catch(() => null);
    });
    samples.push(t);
  }
  return { stats: statsOf(samples), failures };
}

async function measureHotPathConcurrent(
  user: SeededUser,
  perWorker: number,
  parallelism: number,
): Promise<{ stats: Stats; failures: number; total_wall_ms: number }> {
  // Warm-up — 5 calls (more would be wasted SELF.fetch budget; the
  // serial test above has already primed the verdicts hot path).
  for (let i = 0; i < 5; i++) {
    const res = await postVerdict(user, 'hotpath_warmup', `warm2-${user.user_id}-${i}`);
    await res.arrayBuffer().catch(() => null);
  }
  await macrotaskYield();
  const samples: number[] = [];
  let failures = 0;
  const start = performance.now();
  const workers: Promise<void>[] = [];
  for (let w = 0; w < parallelism; w++) {
    workers.push((async () => {
      for (let i = 0; i < perWorker; i++) {
        if (i > 0 && i % 20 === 0) await macrotaskYield();
        const t = await timeMs(async () => {
          const res = await postVerdict(user, 'hotpath_concurrent', `concurrent-${user.user_id}-${w}-${i}`);
          if (!res.ok) failures++;
          await res.arrayBuffer().catch(() => null);
        });
        samples.push(t);
      }
    })());
  }
  await Promise.all(workers);
  const total_wall_ms = performance.now() - start;
  return { stats: statsOf(samples), failures, total_wall_ms: round2(total_wall_ms) };
}

// --------------------------------------------------------------------------
// Suite. Single beforeAll seeds the world; one describe per class
// fans out the endpoint matrix. Skip-by-default — DENDRA_SCALE=1 to run.
// --------------------------------------------------------------------------

const suite = ENABLED ? describe : describe.skip;

suite('Dendra scale harness (DENDRA_SCALE=1)', () => {
  let freeUser: SeededUser;
  let proUser: SeededUser;
  let scaleUser: SeededUser;
  let heavyTailUser: SeededUser;
  const allResults: Array<{ name: string; class_label: string; stats: Stats; failures: number }> = [];

  beforeAll(async () => {
    await applySql(migration0001);
    await applySql(migration0002);
    await applySql(migration0003);
    await applySql(migration0004);
    await applySql(migration0005);
    await applySql(migration0006);
    await applySql(migration0007);
    await applySql(migration0008);
    await applySql(migration0009);

    const seedStart = performance.now();

    // Representative free user: 8 switches, varying density, 1 archived.
    // Density cap 250/day matches the actual operator pattern for free
    // (small projects, modest QPS) and keeps the seed time bounded.
    freeUser = await seedFullUser(1, 'free', 'free', 8, 1, 1, 250);

    // Representative pro: 25 switches, 2 archived, 2 keys, full density.
    proUser = await seedFullUser(2, 'pro', 'pro', 25, 2, 2, 500);

    // Representative scale: 75 switches, 3 archived, 2 keys.
    scaleUser = await seedFullUser(3, 'scale', 'scale', 75, 3, 2, 500);

    // Heavy-tail stress user: 500 switches, 10 archived, 2 keys.
    // This is the stress case for /admin/switches — the N+1 in
    // current_phase + sparkline GROUP BY are dominated by the
    // SWITCH count, not the per-switch verdict count, so we use the
    // 50/day density cap here. With 500 switches × ~30 verdicts/day
    // × 14 days × stops-some-of-them ≈ 150K rows just for this user,
    // which is enough to make the indexes the planner picks real
    // without taking 20 minutes to seed.
    heavyTailUser = await seedFullUser(4, 'pro', 'heavy_tail', 500, 10, 2, 50);

    // 46 more synthetic users at the typical distribution. They add
    // schema-wide row count so the indexes the planner picks are the
    // ones a real launch fleet would hit, not a tiny-DB toy. Density
    // cap 100/day keeps cumulative seed time under control.
    for (let i = 5; i <= 50; i++) {
      const tier: SeededUser['tier'] =
        i <= 45 ? 'free' : i <= 49 ? 'pro' : 'scale';
      const switchCount = randInt(5, 20);
      await seedFullUser(i, tier, tier, switchCount, 0, randInt(1, 2) as 1 | 2, 100);
    }

    const seedElapsed = round2(performance.now() - seedStart);

    const rowCounts = await env.DB.prepare(
      `SELECT
         (SELECT COUNT(*) FROM users) AS users,
         (SELECT COUNT(*) FROM api_keys) AS api_keys,
         (SELECT COUNT(*) FROM verdicts) AS verdicts,
         (SELECT COUNT(*) FROM switch_archives) AS switch_archives`,
    ).first<{ users: number; api_keys: number; verdicts: number; switch_archives: number }>();

    logResult({
      kind: 'scale_seed_summary',
      seed_elapsed_ms: seedElapsed,
      rows: rowCounts,
      heavy_tail_switch_count: heavyTailUser.switches.length,
      heavy_tail_user_id: heavyTailUser.user_id,
    });
  }, /* timeout */ 600_000);

  // ------------------------------------------------------------------------
  // CRITICAL FINDING ABOUT THE HARNESS — READ THIS BEFORE INTERPRETING NUMBERS
  //
  // vitest-pool-workers wraps every SELF.fetch invocation context in a
  // fresh JS Proxy whose prototype is the previous Proxy chain
  // (createProxyPrototypeClass at .../worker/lib/cloudflare/test-internal.mjs).
  // Each fetch deepens that chain by one wrapper.
  //
  // Empirically: each successive SELF.fetch within one Worker isolate
  // adds roughly +0.27ms of harness-internal overhead, and the chain
  // hits a `Maximum call stack size exceeded` around ~1500-2000
  // cumulative fetches. That means:
  //
  //   1. ONLY the early measurements are uncontaminated by harness drift.
  //      Later measurements report harness latency, not Worker latency.
  //   2. The total fetch budget per harness run is hard-capped around
  //      1500 before the worker crashes.
  //
  // Strategy below:
  //   * Measure /health between each endpoint as a "control" — the
  //     difference between the control's p50 at two points in the run
  //     is a quantitative estimate of the per-fetch overhead at that
  //     point. We subtract the median control latency from each
  //     endpoint's reported numbers in the markdown report.
  //   * Order the measurements critical-first so the highest-stakes
  //     numbers (heavy_tail sparkline, /admin/verdicts/recent at scale)
  //     land in the low-overhead window before the chain deepens.
  //
  // Order rationale (each ~110 fetches):
  //   1. heavy_tail /admin/switches             (highest risk, brief §4)
  //   2. heavy_tail /admin/verdicts/recent      (verifies index hypothesis)
  //   3. heavy_tail /admin/switches/:name/report
  //   4. heavy_tail /admin/usage
  //   5. heavy_tail /admin/whoami               (single indexed read baseline)
  //   6. scale /admin/switches
  //   7. scale /admin/verdicts/recent
  //   ...
  //
  // The hot-path verdict POST measurement gets its own time slice — it
  // doesn't go through SELF.fetch as many times because we don't
  // pre-warm; the brief calls for serial then concurrent.
  // ------------------------------------------------------------------------

  // Critical endpoints in priority order — the ones most likely to hit
  // production scaling cliffs. The full ENDPOINTS list is kept around
  // for spot-checks (commented out by class); flip it on locally if
  // you want broader coverage and don't mind the contamination.
  const CRITICAL_ENDPOINTS: EndpointSpec[] = [
    ENDPOINTS.find((e) => e.name === 'GET /admin/switches')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/verdicts/recent?limit=5')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/verdicts/recent?limit=50')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/switches/:name/report (30d)')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/usage')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/whoami')!,
    ENDPOINTS.find((e) => e.name === 'GET /admin/insights/status')!,
  ];

  // Control-endpoint measurement helper. Call between real measurements
  // to track harness drift. /health is the cheapest possible response —
  // no DB hit, no auth, just a static JSON. Its p50 IS the harness
  // overhead floor at that point in the run.
  async function measureControl(): Promise<Stats> {
    const samples: number[] = [];
    for (let i = 0; i < 10; i++) {
      const t = await timeMs(async () => {
        const res = await SELF.fetch(`${BASE}/health`);
        await res.arrayBuffer().catch(() => null);
      });
      samples.push(t);
    }
    return statsOf(samples);
  }

  // ------------------------------------------------------------------------
  // Sparkline-specific stress: heavy-tail SINGLE call. Runs FIRST so
  // we get a clean measurement of the worst /admin/switches case
  // (500 switches × 14 days of sparkline + N+1 current_phase) before
  // the harness drift kicks in.
  // ------------------------------------------------------------------------
  it('00 sparkline stress — heavy_tail single GET /admin/switches', async () => {
    const t = await timeMs(async () => {
      const res = await SELF.fetch(
        `${BASE}/admin/switches?user_id=${heavyTailUser.user_id}`,
        { headers: adminHeaders },
      );
      expect(res.status).toBe(200);
      const body = await res.json<{ switches: unknown[]; archived_count: number }>();
      expect(body.switches.length).toBeGreaterThan(0);
    });
    logResult({
      kind: 'scale_sparkline_stress',
      class: 'heavy_tail',
      endpoint: 'GET /admin/switches (single)',
      ms: round2(t),
    });
  }, /* timeout */ 60_000);

  // ------------------------------------------------------------------------
  // Hot-path stress, run early so the verdict POST p50/p95/p99 numbers
  // aren't contaminated by ~1000 fetches of harness drift. The brief
  // asks for 1000 serial; we run 150 here. The auto-unarchive DELETE
  // overhead is isolated separately below — a direct env.DB measurement
  // not subject to SELF.fetch harness contamination.
  // ------------------------------------------------------------------------
  it('01 hot path — 150 serial POST /v1/verdicts', async () => {
    const r = await measureHotPathSerial(scaleUser, 150);
    logResult({
      kind: 'scale_hotpath_serial',
      ...r.stats,
      failures: r.failures,
    });
    expect(r.failures).toBeLessThan(5);
  }, /* timeout */ 600_000);

  // ------------------------------------------------------------------------
  // Hot-path stress: 150 concurrent (10 workers × 15).
  // ------------------------------------------------------------------------
  it('02 hot path — 150 concurrent POST /v1/verdicts (10×15)', async () => {
    const r = await measureHotPathConcurrent(scaleUser, 15, 10);
    logResult({
      kind: 'scale_hotpath_concurrent',
      per_worker: 15,
      parallelism: 10,
      total_wall_ms: r.total_wall_ms,
      ...r.stats,
      failures: r.failures,
    });
    expect(r.failures).toBeLessThan(10);
  }, /* timeout */ 600_000);

  // ------------------------------------------------------------------------
  // Auto-unarchive DELETE — isolated cost measurement. Direct env.DB
  // calls (no SELF.fetch), so this is NOT subject to the harness
  // contamination that affects every other measurement here. The
  // numbers here are directly comparable to what a production Worker
  // sees on the hot path.
  // ------------------------------------------------------------------------
  it('03 auto-unarchive DELETE — isolated cost', async () => {
    for (let i = 0; i < 50; i++) {
      await env.DB.prepare(
        `INSERT INTO switch_archives (user_id, switch_name, archived_reason)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, switch_name) DO NOTHING`,
      )
        .bind(scaleUser.user_id, `sw_archive_overhead_${i}`, 'overhead')
        .run();
    }
    const samples: number[] = [];
    for (let i = 0; i < 200; i++) {
      const name = `sw_archive_overhead_probe_${i}`;
      await env.DB.prepare(
        `INSERT INTO switch_archives (user_id, switch_name, archived_reason)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, switch_name) DO NOTHING`,
      )
        .bind(scaleUser.user_id, name, null)
        .run();
      const t = await timeMs(async () => {
        await env.DB.prepare(
          `DELETE FROM switch_archives WHERE user_id = ? AND switch_name = ?`,
        )
          .bind(scaleUser.user_id, name)
          .run();
      });
      samples.push(t);
    }
    const noopSamples: number[] = [];
    for (let i = 0; i < 200; i++) {
      const t = await timeMs(async () => {
        await env.DB.prepare(
          `DELETE FROM switch_archives WHERE user_id = ? AND switch_name = ?`,
        )
          .bind(scaleUser.user_id, `does_not_exist_${i}`)
          .run();
      });
      noopSamples.push(t);
    }
    const withDelete = statsOf(samples);
    const noopDelete = statsOf(noopSamples);
    logResult({
      kind: 'scale_autounarchive_delete',
      // Stats spread carries its own `n`; both sides are 200 here.
      with_row: { ...withDelete },
      noop_row: { ...noopDelete },
    });
  }, /* timeout */ 60_000);

  // ------------------------------------------------------------------------
  // Two-class headline matrix. heavy_tail FIRST (highest risk + most
  // budget-sensitive — every test that runs after this is contaminated
  // by harness drift). free SECOND for a small/clean baseline.
  // pro / scale skipped from the headline matrix — their SQL plans are
  // identical to free's; differences would only show in much larger
  // working sets than we can seed.
  for (const classLabel of ['heavy_tail', 'free'] as const) {
    for (const spec of CRITICAL_ENDPOINTS) {
      it(`endpoint — ${spec.name} — ${classLabel}`, async () => {
        const user = classLabel === 'free' ? freeUser : heavyTailUser;
        const control_before = await measureControl();
        const result = await measureEndpoint(spec, user, 5, 30);
        const control_after = await measureControl();
        allResults.push(result);
        expect(result.failures).toBeLessThanOrEqual(1);
        const controlMid = (control_before.p50 + control_after.p50) / 2;
        logResult({
          kind: 'scale_endpoint',
          endpoint: result.name,
          class: result.class_label,
          ...result.stats,
          failures: result.failures,
          control_before_p50: control_before.p50,
          control_after_p50: control_after.p50,
          // Subtract midpoint control from endpoint p50/p95/p99 for a
          // cleaner read of SQL/JS cost. Negative values clamped to 0
          // indicate the endpoint is at or below the control floor.
          adjusted_p50: round2(Math.max(0, result.stats.p50 - controlMid)),
          adjusted_p95: round2(Math.max(0, result.stats.p95 - controlMid)),
          adjusted_p99: round2(Math.max(0, result.stats.p99 - controlMid)),
        });
      }, /* timeout */ 600_000);
    }
  }

  // Quick spot-checks on the write endpoints (free user, single class).
  // SQL is identical across tiers (single-row UPDATE/INSERT) so one
  // pass suffices. Smaller n than the critical matrix — these are
  // single-row writes and the harness contamination is the dominant
  // signal here; the absolute numbers don't tell you much.
  for (const spec of ENDPOINTS) {
    if (CRITICAL_ENDPOINTS.includes(spec)) continue;
    it(`endpoint — ${spec.name} — free (spot)`, async () => {
      const control_before = await measureControl();
      const result = await measureEndpoint(spec, freeUser, 3, 15);
      allResults.push(result);
      expect(result.failures).toBeLessThanOrEqual(1);
      logResult({
        kind: 'scale_endpoint_spot',
        endpoint: result.name,
        class: result.class_label,
        ...result.stats,
        failures: result.failures,
        control_before_p50: control_before.p50,
      });
    }, /* timeout */ 600_000);
  }

  it('zz summary table', () => {
    const lines: string[] = [];
    lines.push('| Endpoint | Class | n | p50 ms | p95 ms | p99 ms | max ms | mean ms | fail |');
    lines.push('|---|---|---:|---:|---:|---:|---:|---:|---:|');
    for (const r of allResults) {
      lines.push(`| ${r.name} | ${r.class_label} | ${r.stats.n} | ${r.stats.p50} | ${r.stats.p95} | ${r.stats.p99} | ${r.stats.max} | ${r.stats.mean} | ${r.failures} |`);
    }
    // Stderr write — guaranteed to surface in vitest run mode even when
    // stdout is buffered for passing tests.
    const summary = '\n=== SCALE HARNESS — endpoint matrix ===\n' +
      lines.join('\n') + '\n=== END ===';
    // eslint-disable-next-line no-console
    console.error(summary);
    // Also dump every collected result as a single JSON document on
    // stderr so a downstream tool can ingest the structured data
    // without re-running. Stderr is unfiltered by vitest's run reporter.
    // eslint-disable-next-line no-console
    console.error('=== SCALE HARNESS — JSON ===\n' + JSON.stringify(RESULT_LOG, null, 2) + '\n=== JSON END ===');
    expect(allResults.length).toBeGreaterThan(0);
  });
});
