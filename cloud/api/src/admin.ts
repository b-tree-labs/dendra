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
import type { ApiEnv } from './auth';

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
