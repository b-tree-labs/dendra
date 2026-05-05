// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/device/* — RFC 8628 OAuth 2.0 Device Authorization Grant for the
// dendra-login flow. Anonymous; rate-limited at the platform layer.
//
//   POST /v1/device/code   — CLI starts the flow; returns (device_code,
//                            user_code, verification_uri, expires_in,
//                            interval).
//   POST /v1/device/token  — CLI polls; returns the freshly minted API key
//                            once the user has authorized.
//
// Companion handlers in admin.ts:
//
//   GET    /admin/cli-sessions/:user_code            — dashboard lookup
//   POST   /admin/cli-sessions/:user_code/authorize  — dashboard authorize
//   POST   /admin/cli-sessions/:user_code/deny       — dashboard deny

import { Hono } from 'hono';
import type { ApiEnv } from './auth';
import { generateKey } from './keys';

export interface DeviceEnv extends ApiEnv {
  // Where the CLI tells the user to go. Defaults to app.dendra.run for
  // production; tests + staging override.
  DENDRA_DASHBOARD_URL?: string;
}

// User-code alphabet excludes ambiguous glyphs (0/O, 1/I/L). 32 chars total.
const USER_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const USER_CODE_LEN = 8; // 32^8 ≈ 1.1e12 keyspace; format XXXX-XXXX
const DEVICE_CODE_BYTES = 32; // 256 bits via base64url

const TTL_SECONDS = 15 * 60; // 15 min — matches the 'slow' end of RFC 8628 §6.1
const POLL_INTERVAL_SECONDS = 5;

const MAX_DEVICE_NAME_LEN = 64;

function genUserCode(): string {
  const bytes = new Uint8Array(USER_CODE_LEN);
  crypto.getRandomValues(bytes);
  let out = '';
  for (let i = 0; i < USER_CODE_LEN; i++) {
    out += USER_CODE_ALPHABET[bytes[i] % USER_CODE_ALPHABET.length];
    if (i === 3) out += '-'; // XXXX-XXXX
  }
  return out;
}

function genDeviceCode(): string {
  const bytes = new Uint8Array(DEVICE_CODE_BYTES);
  crypto.getRandomValues(bytes);
  // base64url: + → -, / → _, drop padding
  return btoa(String.fromCharCode(...bytes))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '');
}

function dashboardUrl(env: DeviceEnv): string {
  return (env.DENDRA_DASHBOARD_URL ?? 'https://app.dendra.run').replace(/\/$/, '');
}

export const device = new Hono<{ Bindings: DeviceEnv }>();

// ---------------------------------------------------------------------------
// POST /v1/device/code
// Body: { device_name?: string }
// Returns: {
//   device_code, user_code, verification_uri, expires_in, interval,
//   verification_uri_complete (convenience: includes user_code in URL)
// }
// ---------------------------------------------------------------------------
device.post('/code', async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as { device_name?: unknown };
  let deviceName: string | null = null;
  if (typeof body.device_name === 'string' && body.device_name.trim()) {
    deviceName = body.device_name.trim().slice(0, MAX_DEVICE_NAME_LEN);
  }

  // Try up to 3× — collision on user_code (1.1e12 keyspace, low birthday risk)
  // is theoretically possible if two requests land in the same second.
  let inserted = false;
  let deviceCode = '';
  let userCode = '';
  for (let attempt = 0; attempt < 3 && !inserted; attempt++) {
    deviceCode = genDeviceCode();
    userCode = genUserCode();
    try {
      await c.env.DB.prepare(
        `INSERT INTO cli_sessions
           (device_code, user_code, state, device_name, expires_at)
         VALUES (?, ?, 'pending', ?, datetime('now', '+' || ? || ' seconds'))`,
      )
        .bind(deviceCode, userCode, deviceName, TTL_SECONDS)
        .run();
      inserted = true;
    } catch (e) {
      // UNIQUE-violation retry; otherwise rethrow.
      if (!String(e).includes('UNIQUE')) throw e;
    }
  }
  if (!inserted) {
    return c.json({ error: 'code_generation_failed' }, 500);
  }

  const dash = dashboardUrl(c.env);
  return c.json({
    device_code: deviceCode,
    user_code: userCode,
    verification_uri: `${dash}/cli-auth`,
    verification_uri_complete: `${dash}/cli-auth?user_code=${encodeURIComponent(userCode)}`,
    expires_in: TTL_SECONDS,
    interval: POLL_INTERVAL_SECONDS,
  });
});

// ---------------------------------------------------------------------------
// POST /v1/device/token
// Body: { device_code: string }
// Returns:
//   200 { api_key, email, expires_in: null }   on consumed
//   400 { error: "authorization_pending" }     while user hasn't acted
//   400 { error: "expired_token" }             after TTL
//   400 { error: "access_denied" }             user denied
//   400 { error: "invalid_grant" }             unknown / already-consumed
// ---------------------------------------------------------------------------
device.post('/token', async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as { device_code?: unknown };
  if (typeof body.device_code !== 'string' || !body.device_code) {
    return c.json({ error: 'invalid_request' }, 400);
  }

  // Single SELECT to read state. Note: we do NOT update state here on
  // expiration — kept additive in the schema (see migration 0006 comment).
  const row = await c.env.DB.prepare(
    `SELECT id, state, user_id, expires_at FROM cli_sessions WHERE device_code = ? LIMIT 1`,
  )
    .bind(body.device_code)
    .first<{
      id: number;
      state: string;
      user_id: number | null;
      expires_at: string;
    }>();

  if (!row) return c.json({ error: 'invalid_grant' }, 400);

  // Expiration check: pending + past expires_at = expired_token. Also
  // applies if state is 'authorized' but the user dawdled and the row
  // expired before the CLI polled — RFC 8628 says expired wins.
  const now = new Date().toISOString().replace('T', ' ').replace(/\..*$/, '');
  if (row.expires_at < now) {
    return c.json({ error: 'expired_token' }, 400);
  }

  if (row.state === 'pending') {
    return c.json({ error: 'authorization_pending' }, 400);
  }
  if (row.state === 'denied') {
    return c.json({ error: 'access_denied' }, 400);
  }
  if (row.state === 'consumed') {
    // Already consumed — security: each device_code is single-use.
    return c.json({ error: 'invalid_grant' }, 400);
  }
  if (row.state !== 'authorized' || row.user_id === null) {
    return c.json({ error: 'invalid_grant' }, 400);
  }

  // State == authorized + within TTL + user_id set. Mint a fresh
  // dndr_live_… key and atomically transition to consumed.
  const issued = await generateKey(c.env.API_KEY_PEPPER, 'live');

  // Atomic: insert key, link to cli_session row, transition state.
  // Use a single statement chain so a concurrent poll can't double-mint.
  const updateResult = await c.env.DB.prepare(
    `UPDATE cli_sessions
        SET state = 'consumed', consumed_at = datetime('now')
      WHERE id = ? AND state = 'authorized'
     RETURNING id`,
  )
    .bind(row.id)
    .first<{ id: number }>();

  if (!updateResult) {
    // Lost the race — another poll already consumed this row.
    return c.json({ error: 'invalid_grant' }, 400);
  }

  // Now insert the api_key row + link it back to cli_sessions.
  const keyRow = await c.env.DB.prepare(
    `INSERT INTO api_keys (user_id, key_prefix, key_suffix, key_hash, name)
     VALUES (?, ?, ?, ?, ?)
     RETURNING id`,
  )
    .bind(
      row.user_id,
      issued.prefix,
      issued.suffix,
      issued.hash,
      'cli-device-login',
    )
    .first<{ id: number }>();

  if (keyRow) {
    await c.env.DB.prepare(`UPDATE cli_sessions SET api_key_id = ? WHERE id = ?`)
      .bind(keyRow.id, row.id)
      .run();
  }

  // Look up email for the response (CLI displays "Signed in as <email>").
  const userRow = await c.env.DB.prepare(`SELECT email FROM users WHERE id = ?`)
    .bind(row.user_id)
    .first<{ email: string }>();

  return c.json({
    api_key: issued.plaintext,
    email: userRow?.email ?? null,
  });
});
