// Copyright (c) 2026 B-Tree Ventures, LLC
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Dendra Insights collector — Cloudflare Worker.
//
// Two routes:
//   POST /v1/events      — accept a batch of events, validate, persist to D1
//   GET  /health         — liveness / Better Stack heartbeat
//
// Privacy posture per docs/working/telemetry-program-design-2026-04-28.md:
// payload keys outside the whitelist are silently dropped server-side.
// The client also strips unknown keys; the Worker is defense-in-depth.

export interface Env {
  DB: D1Database;
  ENVIRONMENT: string;
  SENTRY_DSN?: string;
}

// ---------------------------------------------------------------------------
// Schema constants — must stay aligned with src/dendra/insights/events.py
// EVENT_TYPES + _PAYLOAD_KEY_WHITELIST. A change in either side without
// the other is a privacy bug; tests pin both sides to prevent drift.
// ---------------------------------------------------------------------------

const EVENT_TYPES = new Set(['analyze', 'init_attempt', 'bench_phase_advance']);

const PAYLOAD_KEY_WHITELIST: Record<string, Set<string>> = {
  analyze: new Set([
    'files_scanned',
    'total_sites',
    'already_dendrified_count',
    'pattern_histogram',
    'regime_histogram',
    'lift_status_histogram',
    'hazard_category_histogram',
  ]),
  init_attempt: new Set([
    'lifter',
    'outcome',
    'pattern',
    'regime',
    'label_cardinality',
    'time_to_action_seconds',
    'reverted_within_24h',
  ]),
  bench_phase_advance: new Set([
    'phase_before',
    'phase_after',
    'verdict_count',
    'cost_per_call_micros',
    'latency_p50_us',
    'latency_p95_us',
  ]),
};

const SCHEMA_VERSION_MAX = 10; // accept anything up to v10; bump when a new schema lands

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InsightsEvent {
  event_type: string;
  timestamp: string;
  schema_version: number;
  site_fingerprint: string | null;
  payload: Record<string, unknown>;
  account_hash?: string | null;
}

interface EventBatch {
  schema_version: number;
  events: InsightsEvent[];
  account_hash?: string | null;
}

interface ValidationResult {
  valid: InsightsEvent[];
  rejected: { event: unknown; reason: string }[];
}

// ---------------------------------------------------------------------------
// Top-level fetch handler
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'GET' && url.pathname === '/health') {
      return jsonResponse(200, {
        status: 'ok',
        environment: env.ENVIRONMENT,
        time: new Date().toISOString(),
      });
    }

    if (request.method === 'POST' && url.pathname === '/v1/events') {
      try {
        return await handleEventsPost(request, env);
      } catch (err) {
        return errorResponse(err, env);
      }
    }

    return jsonResponse(404, { error: 'not_found', path: url.pathname });
  },
};

// ---------------------------------------------------------------------------
// POST /v1/events
// ---------------------------------------------------------------------------

async function handleEventsPost(request: Request, env: Env): Promise<Response> {
  // Bound the request body so an attacker can't fill our D1 quota by
  // posting a multi-megabyte body. Client cap is FLUSH_BATCH_SIZE=64
  // events × ~500 bytes = 32 KB; allow 1 MB for headroom.
  const contentLength = parseInt(request.headers.get('content-length') ?? '0', 10);
  if (contentLength > 1_048_576) {
    return jsonResponse(413, { error: 'payload_too_large', limit_bytes: 1_048_576 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonResponse(400, { error: 'invalid_json' });
  }

  if (!isObject(body) || !('events' in body) || !Array.isArray(body.events)) {
    return jsonResponse(400, {
      error: 'invalid_batch_shape',
      hint: 'expected {schema_version: int, events: [...]}',
    });
  }

  const batch = body as EventBatch;

  if (typeof batch.schema_version !== 'number' || batch.schema_version > SCHEMA_VERSION_MAX) {
    return jsonResponse(400, {
      error: 'unsupported_schema_version',
      supplied: batch.schema_version,
      supported_max: SCHEMA_VERSION_MAX,
    });
  }

  // Hard cap on batch size — one Cloudflare D1 transaction has limits;
  // 100 inserts is well within them and matches the client batch cap.
  if (batch.events.length > 100) {
    return jsonResponse(400, {
      error: 'batch_too_large',
      supplied: batch.events.length,
      max: 100,
    });
  }

  const validation = validateAndStripBatch(batch);

  if (validation.valid.length === 0) {
    return jsonResponse(400, {
      error: 'no_valid_events',
      rejected_count: validation.rejected.length,
      reasons: validation.rejected.slice(0, 5).map((r) => r.reason),
    });
  }

  // Cloudflare metadata for abuse-triage stamping. Never used in
  // cohort analysis. Cleanup job (NYI) deletes columns >30 days old.
  const country = (request.cf as { country?: string })?.country ?? null;
  const asn = (request.cf as { asn?: number })?.asn ?? null;
  const userAgent = request.headers.get('user-agent') ?? null;

  // Insert all valid events in a single batch statement. D1 supports
  // batch() for atomic multi-statement transactions.
  const statements = validation.valid.map((event) => {
    const accountHash = event.account_hash ?? batch.account_hash ?? null;
    return env.DB.prepare(
      `INSERT INTO events (
        event_timestamp, event_type, schema_version, account_hash,
        site_fingerprint, payload_json,
        request_country, request_asn, request_user_agent
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      event.timestamp,
      event.event_type,
      event.schema_version,
      accountHash,
      event.site_fingerprint ?? null,
      JSON.stringify(event.payload),
      country,
      asn,
      userAgent
    );
  });

  const results = await env.DB.batch(statements);
  const insertedCount = results.reduce(
    (sum, r) => sum + (r.success ? r.meta?.changes ?? 1 : 0),
    0
  );

  return jsonResponse(200, {
    status: 'ok',
    inserted: insertedCount,
    rejected: validation.rejected.length,
  });
}

// ---------------------------------------------------------------------------
// Validation + payload-key whitelist enforcement
// ---------------------------------------------------------------------------

function validateAndStripBatch(batch: EventBatch): ValidationResult {
  const valid: InsightsEvent[] = [];
  const rejected: { event: unknown; reason: string }[] = [];

  for (const candidate of batch.events) {
    const result = validateAndStripEvent(candidate);
    if (result.error) {
      rejected.push({ event: candidate, reason: result.error });
    } else if (result.event) {
      valid.push(result.event);
    }
  }

  return { valid, rejected };
}

function validateAndStripEvent(
  candidate: unknown
): { event?: InsightsEvent; error?: string } {
  if (!isObject(candidate)) {
    return { error: 'event_not_object' };
  }
  const event = candidate as Record<string, unknown>;

  if (typeof event.event_type !== 'string' || !EVENT_TYPES.has(event.event_type)) {
    return { error: `invalid_event_type:${event.event_type}` };
  }
  if (typeof event.timestamp !== 'string' || !ISO_TIMESTAMP_RE.test(event.timestamp)) {
    return { error: 'invalid_timestamp' };
  }
  if (
    typeof event.schema_version !== 'number' ||
    event.schema_version < 1 ||
    event.schema_version > SCHEMA_VERSION_MAX
  ) {
    return { error: 'invalid_schema_version' };
  }

  // site_fingerprint is optional but if present must be a hex string.
  let siteFingerprint: string | null = null;
  if (event.site_fingerprint !== null && event.site_fingerprint !== undefined) {
    if (typeof event.site_fingerprint !== 'string' || !HEX_RE.test(event.site_fingerprint)) {
      return { error: 'invalid_site_fingerprint' };
    }
    siteFingerprint = event.site_fingerprint;
  }

  // Strip payload to the whitelist for this event_type. Keys outside
  // the whitelist are silently dropped — this is the privacy-defense
  // line.
  const allowedKeys = PAYLOAD_KEY_WHITELIST[event.event_type as string] ?? new Set();
  const payloadIn = isObject(event.payload) ? (event.payload as Record<string, unknown>) : {};
  const payloadOut: Record<string, unknown> = {};
  for (const k of Object.keys(payloadIn)) {
    if (allowedKeys.has(k)) {
      payloadOut[k] = payloadIn[k];
    }
  }

  // account_hash is optional; if present must be a hex string.
  let accountHash: string | null | undefined = undefined;
  if (event.account_hash !== undefined) {
    if (event.account_hash === null) {
      accountHash = null;
    } else if (typeof event.account_hash !== 'string' || !HEX_RE.test(event.account_hash)) {
      return { error: 'invalid_account_hash' };
    } else {
      accountHash = event.account_hash;
    }
  }

  return {
    event: {
      event_type: event.event_type as string,
      timestamp: event.timestamp as string,
      schema_version: event.schema_version as number,
      site_fingerprint: siteFingerprint,
      payload: payloadOut,
      ...(accountHash !== undefined ? { account_hash: accountHash } : {}),
    },
  };
}

// ---------------------------------------------------------------------------
// Tiny utilities
// ---------------------------------------------------------------------------

const ISO_TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
const HEX_RE = /^[0-9a-f]+$/i;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
      'cache-control': 'no-store',
    },
  });
}

function errorResponse(err: unknown, env: Env): Response {
  // Log to Cloudflare console; Worker logs are tail-able via wrangler tail.
  const message = err instanceof Error ? err.message : String(err);
  console.error(`[${env.ENVIRONMENT}] handler error:`, message);

  // In production, don't leak internal error messages. In staging,
  // include them so debugging is faster.
  const body =
    env.ENVIRONMENT === 'production'
      ? { error: 'internal_error' }
      : { error: 'internal_error', detail: message };

  return jsonResponse(500, body);
}
