// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Admin endpoints for the dashboard. Mounted at /admin/*. Auth is by
// shared service token (env.DASHBOARD_SERVICE_TOKEN) instead of Bearer
// API key — the dashboard's Clerk-authenticated route handlers are the
// only legitimate caller.
//
// Routes:
//   POST   /admin/users         — upsert a Clerk user; returns user_id
//   POST   /admin/keys          — issue a new API key for a user
//   GET    /admin/keys?user_id  — list a user's keys (metadata only)
//   DELETE /admin/keys/:id      — revoke (soft-delete) a key

import { Hono, type MiddlewareHandler } from 'hono';
import { generateKey, type KeyEnvironment } from './keys';
import { signLicense, type LicenseClaims } from './license';
import { TIER_MONTHLY_CAP, periodOf } from './usage';
import type { ApiEnv, AuthContext } from './auth';

export interface AdminEnv extends ApiEnv {
  DASHBOARD_SERVICE_TOKEN: string;
  LICENSE_SIGNING_PRIVATE_KEY?: string;
}

/**
 * Constant-time service-token comparison. The token is a fixed string
 * known to the dashboard; any timing leak would let an attacker probe
 * its bytes one at a time.
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

const serviceTokenAuth = (): MiddlewareHandler<{ Bindings: AdminEnv }> =>
  async (c, next) => {
    const expected = c.env.DASHBOARD_SERVICE_TOKEN;
    if (!expected) {
      console.error('DASHBOARD_SERVICE_TOKEN not configured');
      return c.json({ error: 'server_misconfigured' }, 500);
    }
    const got = c.req.header('X-Dashboard-Token') ?? '';
    if (!timingSafeEqual(got, expected)) {
      return c.json({ error: 'unauthorized' }, 401);
    }
    await next();
  };

/**
 * Stable HMAC-style hash of an email for `account_hash`. The collector
 * uses HMAC-SHA-256(email, pepper) for events; we keep the same shape
 * so the two systems stay correlatable.
 */
async function accountHash(email: string, pepper: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(pepper),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(email.toLowerCase()));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export const admin = new Hono<{ Bindings: AdminEnv }>();
admin.use('*', serviceTokenAuth());

// ---------------------------------------------------------------------------
// POST /v1/admin/users — upsert a Clerk user. Idempotent.
// ---------------------------------------------------------------------------
admin.post('/users', async (c) => {
  const body = await c.req.json<{ clerk_user_id?: string; email?: string }>().catch(() => null);
  if (!body?.clerk_user_id || !body.email) {
    return c.json({ error: 'missing_clerk_user_id_or_email' }, 400);
  }

  const ah = await accountHash(body.email, c.env.API_KEY_PEPPER);

  await c.env.DB.prepare(
    `INSERT INTO users (clerk_user_id, email, account_hash)
     VALUES (?, ?, ?)
     ON CONFLICT(clerk_user_id) DO UPDATE SET
       email = excluded.email,
       account_hash = excluded.account_hash,
       updated_at = datetime('now')`,
  )
    .bind(body.clerk_user_id, body.email, ah)
    .run();

  const row = await c.env.DB.prepare(
    `SELECT id, current_tier, account_hash FROM users WHERE clerk_user_id = ?`,
  )
    .bind(body.clerk_user_id)
    .first<{ id: number; current_tier: string; account_hash: string }>();

  if (!row) return c.json({ error: 'upsert_failed' }, 500);
  return c.json({
    user_id: row.id,
    tier: row.current_tier,
    account_hash: row.account_hash,
  });
});

// ---------------------------------------------------------------------------
// POST /v1/admin/keys — issue a new API key. Returns plaintext ONCE.
// Body: { user_id: number, name?: string, environment?: 'live' | 'test' }
// ---------------------------------------------------------------------------
admin.post('/keys', async (c) => {
  const body = await c.req.json<{
    user_id?: number;
    name?: string;
    environment?: KeyEnvironment;
  }>().catch(() => null);

  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  // Sanity: confirm the user exists. Otherwise FK insert below would fail
  // with a less-descriptive error.
  const user = await c.env.DB.prepare(`SELECT id FROM users WHERE id = ?`)
    .bind(body.user_id)
    .first();
  if (!user) return c.json({ error: 'user_not_found' }, 404);

  const env = body.environment ?? 'live';
  const issued = await generateKey(c.env.API_KEY_PEPPER, env);

  const result = await c.env.DB.prepare(
    `INSERT INTO api_keys (user_id, key_prefix, key_suffix, key_hash, name)
     VALUES (?, ?, ?, ?, ?)
     RETURNING id, created_at`,
  )
    .bind(body.user_id, issued.prefix, issued.suffix, issued.hash, body.name ?? null)
    .first<{ id: number; created_at: string }>();

  if (!result) return c.json({ error: 'insert_failed' }, 500);

  return c.json({
    id: result.id,
    plaintext: issued.plaintext, // shown once; client must persist
    prefix: issued.prefix,
    suffix: issued.suffix,
    name: body.name ?? null,
    environment: env,
    created_at: result.created_at,
  });
});

// ---------------------------------------------------------------------------
// GET /v1/admin/keys?user_id=N — list a user's keys (metadata only).
// ---------------------------------------------------------------------------
admin.get('/keys', async (c) => {
  const uid = Number(c.req.query('user_id'));
  if (!Number.isInteger(uid) || uid <= 0) {
    return c.json({ error: 'missing_or_invalid_user_id' }, 400);
  }

  const rows = await c.env.DB.prepare(
    `SELECT id, key_prefix, key_suffix, name, last_used_at, revoked_at, created_at
       FROM api_keys
      WHERE user_id = ?
      ORDER BY created_at DESC`,
  )
    .bind(uid)
    .all();

  return c.json({ keys: rows.results ?? [] });
});

// ---------------------------------------------------------------------------
// GET /admin/usage?user_id=N — return the user's current-period verdict
// usage + tier cap, summed across all of their api_keys.
//
// Used by the dashboard root page to render the tier+usage strip and to
// decide whether to surface the A7 earned-upgrade banner.
//
// Shape:
//   { tier, verdicts_this_period, cap, period_start, period_end }
//
// period_start / period_end are ISO 8601 timestamps for the current UTC
// calendar month (cap reset point). cap is null for unlimited tiers
// (none today — every tier has a cap — but the JSON shape supports it).
// ---------------------------------------------------------------------------
admin.get('/usage', async (c) => {
  const uid = Number(c.req.query('user_id'));
  if (!Number.isInteger(uid) || uid <= 0) {
    return c.json({ error: 'missing_or_invalid_user_id' }, 400);
  }

  const user = await c.env.DB.prepare(
    `SELECT current_tier FROM users WHERE id = ? LIMIT 1`,
  )
    .bind(uid)
    .first<{ current_tier: AuthContext['tier'] }>();
  if (!user) return c.json({ error: 'user_not_found' }, 404);

  // Defensive: an unknown tier shouldn't 500 the dashboard.
  const tier: AuthContext['tier'] = (user.current_tier in TIER_MONTHLY_CAP
    ? user.current_tier
    : 'free') as AuthContext['tier'];

  const now = new Date();
  const period = periodOf(now);

  // Sum the current period's classifications across every key the user
  // owns. usage_metrics is per-(api_key_id, period); the join via
  // api_keys.user_id keeps the SQL trivially indexed.
  const row = await c.env.DB.prepare(
    `SELECT COALESCE(SUM(m.classifications_count), 0) AS verdicts
       FROM usage_metrics m
       JOIN api_keys k ON k.id = m.api_key_id
      WHERE k.user_id = ?
        AND m.period_start = ?`,
  )
    .bind(uid, period)
    .first<{ verdicts: number }>();

  // Period bounds as ISO timestamps (start = first of current UTC month,
  // end = first of next UTC month). The dashboard renders "days left".
  const periodStart = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1, 0, 0, 0),
  );
  const periodEnd = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 0, 0, 0),
  );

  return c.json({
    tier,
    verdicts_this_period: row?.verdicts ?? 0,
    cap: TIER_MONTHLY_CAP[tier],
    period_start: periodStart.toISOString(),
    period_end: periodEnd.toISOString(),
  });
});

// ---------------------------------------------------------------------------
// GET /admin/verdicts/recent?user_id=N&limit=K — most-recent K verdicts
// across every api_key the user owns.
//
// Used by the dashboard root page to render the recent-activity feed.
// limit is clamped to [1, 50] so a misbehaving caller can't drain D1.
//
// Shape:
//   { verdicts: [{ id, switch_name, phase, rule_correct, model_correct,
//                  ml_correct, created_at }, ...] }
// ---------------------------------------------------------------------------
admin.get('/verdicts/recent', async (c) => {
  const uid = Number(c.req.query('user_id'));
  if (!Number.isInteger(uid) || uid <= 0) {
    return c.json({ error: 'missing_or_invalid_user_id' }, 400);
  }

  const rawLimit = Number(c.req.query('limit') ?? '5');
  const limit = Number.isFinite(rawLimit) && rawLimit > 0
    ? Math.min(Math.floor(rawLimit), 50)
    : 5;

  const rows = await c.env.DB.prepare(
    `SELECT v.id,
            v.switch_name,
            v.phase,
            v.rule_correct,
            v.model_correct,
            v.ml_correct,
            v.created_at
       FROM verdicts v
       JOIN api_keys k ON k.id = v.api_key_id
      WHERE k.user_id = ?
      ORDER BY v.created_at DESC, v.id DESC
      LIMIT ?`,
  )
    .bind(uid, limit)
    .all();

  return c.json({ verdicts: rows.results ?? [] });
});

// ---------------------------------------------------------------------------
// POST /admin/licenses/issue — sign a license token for a user.
// Body: { user_id: number, ttl_days?: number, max_seats?: number | null }
// Returns: { token, claims }. The plaintext token must be stored by the
// dashboard / handed to the customer; we don't persist it (only the
// license_id claim, which lets us revoke at lookup time later).
// ---------------------------------------------------------------------------
admin.post('/licenses/issue', async (c) => {
  const priv = c.env.LICENSE_SIGNING_PRIVATE_KEY;
  if (!priv) {
    return c.json({ error: 'license_signing_not_configured' }, 500);
  }

  const body = await c.req.json<{
    user_id?: number;
    ttl_days?: number;
    max_seats?: number | null;
  }>().catch(() => null);

  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }
  const ttlDays = Number.isFinite(body.ttl_days) && (body.ttl_days ?? 0) > 0
    ? Math.min(Math.floor(body.ttl_days as number), 365 * 3)
    : 30;
  const maxSeats =
    body.max_seats === undefined || body.max_seats === null
      ? null
      : Number.isInteger(body.max_seats) && (body.max_seats as number) > 0
        ? (body.max_seats as number)
        : null;

  const user = await c.env.DB.prepare(
    `SELECT id, current_tier, account_hash FROM users WHERE id = ? LIMIT 1`,
  )
    .bind(body.user_id)
    .first<{ id: number; current_tier: LicenseClaims['tier']; account_hash: string }>();
  if (!user) return c.json({ error: 'user_not_found' }, 404);

  const { token, claims } = await signLicense({
    privateKeyHex: priv,
    user_id: user.id,
    tier: user.current_tier,
    account_hash: user.account_hash,
    ttlSeconds: ttlDays * 86400,
    max_seats: maxSeats,
  });

  return c.json({ token, claims });
});

// ---------------------------------------------------------------------------
// DELETE /v1/admin/keys/:id — revoke (soft-delete) a key.
// Body: { user_id: number } — defense-in-depth, prevents cross-user revoke
// ---------------------------------------------------------------------------
admin.delete('/keys/:id', async (c) => {
  const id = Number(c.req.param('id'));
  if (!Number.isInteger(id) || id <= 0) {
    return c.json({ error: 'invalid_id' }, 400);
  }
  const body = await c.req.json<{ user_id?: number }>().catch(() => null);
  if (!body?.user_id) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  const result = await c.env.DB.prepare(
    `UPDATE api_keys
        SET revoked_at = datetime('now')
      WHERE id = ?
        AND user_id = ?
        AND revoked_at IS NULL`,
  )
    .bind(id, body.user_id)
    .run();

  if (!result.meta.changes) {
    return c.json({ error: 'not_found_or_already_revoked' }, 404);
  }
  return c.json({ revoked: true, id });
});

// ---------------------------------------------------------------------------
// CLI device-flow admin endpoints. Companion to /v1/device/* in device.ts.
//
// The dashboard's /cli-auth page calls these via the Clerk-authenticated
// dashboard route handler, which forwards using the service token.
// ---------------------------------------------------------------------------

// GET /admin/cli-sessions/:user_code — pre-authorize lookup.
// Returns metadata the dashboard renders for the user to confirm
// before they click Authorize. NEVER returns device_code (CLI's secret).
admin.get('/cli-sessions/:user_code', async (c) => {
  const userCode = c.req.param('user_code');
  if (!userCode) return c.json({ error: 'missing_user_code' }, 400);

  const row = await c.env.DB.prepare(
    `SELECT state, device_name, created_at, expires_at, authorized_at
       FROM cli_sessions WHERE user_code = ? LIMIT 1`,
  )
    .bind(userCode)
    .first<{
      state: string;
      device_name: string | null;
      created_at: string;
      expires_at: string;
      authorized_at: string | null;
    }>();
  if (!row) return c.json({ error: 'not_found' }, 404);

  // Treat past-expires_at + 'pending' as expired for the dashboard's sake.
  const now = new Date().toISOString().replace('T', ' ').replace(/\..*$/, '');
  const effectiveState = row.state === 'pending' && row.expires_at < now ? 'expired' : row.state;

  return c.json({
    state: effectiveState,
    device_name: row.device_name,
    created_at: row.created_at,
    expires_at: row.expires_at,
    authorized_at: row.authorized_at,
  });
});

// POST /admin/cli-sessions/:user_code/authorize — dashboard authorizes.
// Body: { user_id: number }
admin.post('/cli-sessions/:user_code/authorize', async (c) => {
  const userCode = c.req.param('user_code');
  if (!userCode) return c.json({ error: 'missing_user_code' }, 400);

  const body = await c.req.json<{ user_id?: number }>().catch(() => null);
  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  // Atomic state transition: only pending + non-expired sessions can be
  // authorized. The WHERE clause prevents race-double-authorize.
  const updated = await c.env.DB.prepare(
    `UPDATE cli_sessions
        SET state = 'authorized',
            user_id = ?,
            authorized_at = datetime('now')
      WHERE user_code = ?
        AND state = 'pending'
        AND expires_at > datetime('now')
     RETURNING id, state`,
  )
    .bind(body.user_id, userCode)
    .first<{ id: number; state: string }>();

  if (!updated) {
    // Either not found, already authorized/denied/consumed, or expired.
    // Look up to disambiguate for the dashboard's error message.
    const existing = await c.env.DB.prepare(
      `SELECT state, expires_at FROM cli_sessions WHERE user_code = ? LIMIT 1`,
    )
      .bind(userCode)
      .first<{ state: string; expires_at: string }>();
    if (!existing) return c.json({ error: 'not_found' }, 404);

    const now = new Date().toISOString().replace('T', ' ').replace(/\..*$/, '');
    if (existing.state === 'pending' && existing.expires_at < now) {
      return c.json({ error: 'expired' }, 410);
    }
    return c.json({ error: `cannot_authorize_in_state_${existing.state}` }, 409);
  }

  return c.json({ ok: true });
});

// POST /admin/cli-sessions/:user_code/deny — dashboard denies.
admin.post('/cli-sessions/:user_code/deny', async (c) => {
  const userCode = c.req.param('user_code');
  if (!userCode) return c.json({ error: 'missing_user_code' }, 400);

  const updated = await c.env.DB.prepare(
    `UPDATE cli_sessions
        SET state = 'denied'
      WHERE user_code = ?
        AND state = 'pending'
     RETURNING id`,
  )
    .bind(userCode)
    .first<{ id: number }>();

  if (!updated) return c.json({ error: 'not_found_or_already_decided' }, 404);
  return c.json({ ok: true });
});
