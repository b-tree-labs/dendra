// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Admin endpoints backing /dashboard/settings and /dashboard/insights.
// Mounted at /admin/* under the same service-token auth as the rest of
// the dashboard surface (cloud/api/src/admin.ts).
//
// Routes:
//   GET   /admin/whoami?user_id=N         → preferences for the dashboard
//   PATCH /admin/whoami                   → update display_name | telemetry_enabled
//   GET   /admin/insights/status?user_id=N → enrollment + cohort_size + last_sync
//   POST  /admin/insights/enroll          → enroll a user
//   POST  /admin/insights/leave           → leave the cohort
//
// Auth: every handler in this file MUST be mounted behind
// serviceTokenAuth() (see admin.ts). The exported `preferences` Hono
// instance does NOT install the middleware itself — admin.ts does so
// once for the entire /admin surface.
//
// Storage: writes to migration 0007 columns (users.display_name,
// users.telemetry_enabled) and the insights_enrollments table.
// Co-located on the users row by design so /v1/whoami stays one
// indexed read.

import { Hono } from 'hono';
import type { ApiEnv } from './auth';

const TUNED_DEFAULTS_KEY = 'tuned-defaults.json';

export interface PreferencesEnv extends ApiEnv {
  KV_INSIGHTS: KVNamespace;
}

export const preferences = new Hono<{ Bindings: PreferencesEnv }>();

// ---------------------------------------------------------------------------
// GET /admin/whoami?user_id=N
//
// Returns the preference + identity shape the dashboard's /dashboard/settings
// page renders. Includes email so the page can show it read-only without
// a second round trip to Clerk on the dashboard server.
// ---------------------------------------------------------------------------
preferences.get('/whoami', async (c) => {
  const uid = Number(c.req.query('user_id'));
  if (!Number.isInteger(uid) || uid <= 0) {
    return c.json({ error: 'missing_or_invalid_user_id' }, 400);
  }

  const row = await c.env.DB.prepare(
    `SELECT id, email, display_name, telemetry_enabled, current_tier, account_hash
       FROM users
      WHERE id = ?
      LIMIT 1`,
  )
    .bind(uid)
    .first<{
      id: number;
      email: string;
      display_name: string | null;
      telemetry_enabled: number;
      current_tier: string;
      account_hash: string;
    }>();

  if (!row) return c.json({ error: 'user_not_found' }, 404);

  return c.json({
    user_id: row.id,
    email: row.email,
    display_name: row.display_name,
    // SQLite stores booleans as integers; normalize for the JSON surface.
    telemetry_enabled: row.telemetry_enabled === 1,
    tier: row.current_tier,
    account_hash: row.account_hash,
  });
});

// ---------------------------------------------------------------------------
// PATCH /admin/whoami
// Body: { user_id: number, display_name?: string | null, telemetry_enabled?: boolean }
//
// Each field is optional; an absent field is left untouched. Sending
// display_name: null clears it (lets the user "unset" a custom name to
// fall back to the Clerk-provided one). display_name caps at 64 chars
// server-side — defense in depth against UI bypass.
// ---------------------------------------------------------------------------
preferences.patch('/whoami', async (c) => {
  const body = await c.req.json<{
    user_id?: number;
    display_name?: string | null;
    telemetry_enabled?: boolean;
  }>().catch(() => null);

  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  const sets: string[] = [];
  const binds: unknown[] = [];

  if (Object.prototype.hasOwnProperty.call(body, 'display_name')) {
    let dn: string | null = null;
    if (typeof body.display_name === 'string') {
      const trimmed = body.display_name.trim();
      // Cap at 64 chars to match the cli_sessions.device_name convention
      // (operator-supplied text; we treat all client-supplied strings the
      // same way).
      dn = trimmed.length === 0 ? null : trimmed.slice(0, 64);
    } else if (body.display_name === null) {
      dn = null;
    } else {
      return c.json({ error: 'invalid_display_name' }, 400);
    }
    sets.push('display_name = ?');
    binds.push(dn);
  }

  if (Object.prototype.hasOwnProperty.call(body, 'telemetry_enabled')) {
    if (typeof body.telemetry_enabled !== 'boolean') {
      return c.json({ error: 'invalid_telemetry_enabled' }, 400);
    }
    sets.push('telemetry_enabled = ?');
    binds.push(body.telemetry_enabled ? 1 : 0);
  }

  if (sets.length === 0) {
    return c.json({ error: 'no_fields_to_update' }, 400);
  }

  sets.push("updated_at = datetime('now')");
  binds.push(body.user_id);

  const result = await c.env.DB.prepare(
    `UPDATE users SET ${sets.join(', ')} WHERE id = ?`,
  )
    .bind(...binds)
    .run();

  if (!result.meta.changes) {
    return c.json({ error: 'user_not_found' }, 404);
  }

  const row = await c.env.DB.prepare(
    `SELECT id, email, display_name, telemetry_enabled
       FROM users WHERE id = ? LIMIT 1`,
  )
    .bind(body.user_id)
    .first<{
      id: number;
      email: string;
      display_name: string | null;
      telemetry_enabled: number;
    }>();

  if (!row) return c.json({ error: 'user_not_found_after_update' }, 500);

  return c.json({
    user_id: row.id,
    email: row.email,
    display_name: row.display_name,
    telemetry_enabled: row.telemetry_enabled === 1,
  });
});

// ---------------------------------------------------------------------------
// Cohort size helper — read the KV-backed tuned-defaults JSON, surface
// the `cohort_size` field. Falls back to a count of currently-active
// insights_enrollments rows when KV is empty (pre-aggregator-run, dev
// envs). The fallback prevents the dashboard from rendering "Cohort
// size: 0" when there are clearly enrolled users.
//
// The KV read is bounded by KV_READ_TIMEOUT_MS so a slow KV tail does
// not dominate the response's p99. Findings from the 2026-05-11 chaos
// harness (PR #42, §5) showed that the other two response fields
// resolve in <5ms from D1; without a timeout, the full response
// blocks on whatever KV decides to do. On a timeout we treat the KV
// value as "absent" and fall through to the DB count — the same
// behavior as a genuinely-empty KV.
// ---------------------------------------------------------------------------
const KV_READ_TIMEOUT_MS = 100;

async function readCohortSize(env: PreferencesEnv): Promise<number> {
  const raw = await Promise.race([
    env.KV_INSIGHTS.get(TUNED_DEFAULTS_KEY),
    new Promise<null>((resolve) => setTimeout(() => resolve(null), KV_READ_TIMEOUT_MS)),
  ]);
  if (raw !== null) {
    try {
      const parsed = JSON.parse(raw) as { cohort_size?: unknown };
      if (typeof parsed.cohort_size === 'number' && parsed.cohort_size >= 0) {
        return parsed.cohort_size;
      }
    } catch {
      // Fall through to DB count — KV value is malformed.
    }
  }
  const row = await env.DB.prepare(
    `SELECT COUNT(*) AS n
       FROM insights_enrollments
      WHERE left_at IS NULL`,
  ).first<{ n: number }>();
  return row?.n ?? 0;
}

// ---------------------------------------------------------------------------
// GET /admin/insights/status?user_id=N
//
// Companion to the `postrule insights status` CLI command. The dashboard
// renders three lines:
//   - Status: enrolled / not-enrolled
//   - Cohort size: N deployments
//   - Last sync: <timestamp>  (only if enrolled)
// ---------------------------------------------------------------------------
preferences.get('/insights/status', async (c) => {
  const uid = Number(c.req.query('user_id'));
  if (!Number.isInteger(uid) || uid <= 0) {
    return c.json({ error: 'missing_or_invalid_user_id' }, 400);
  }

  // Active enrollment row (if any).
  const row = await c.env.DB.prepare(
    `SELECT id, enrolled_at, last_sync_at
       FROM insights_enrollments
      WHERE user_id = ?
        AND left_at IS NULL
      ORDER BY enrolled_at DESC
      LIMIT 1`,
  )
    .bind(uid)
    .first<{ id: number; enrolled_at: string; last_sync_at: string | null }>();

  const cohort_size = await readCohortSize(c.env);

  return c.json({
    enrolled: row !== null,
    enrolled_at: row?.enrolled_at ?? null,
    last_sync_at: row?.last_sync_at ?? null,
    cohort_size,
  });
});

// ---------------------------------------------------------------------------
// POST /admin/insights/enroll
// Body: { user_id: number, consent_text_sha256?: string }
//
// Idempotent: re-enrolling a currently-enrolled user is a no-op (returns
// the existing row). After a previous leave, this inserts a fresh row;
// the historical rows stay for audit.
// ---------------------------------------------------------------------------
preferences.post('/insights/enroll', async (c) => {
  const body = await c.req.json<{
    user_id?: number;
    consent_text_sha256?: string;
  }>().catch(() => null);
  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  // Sanity: the user must exist. FK insert below would catch this too,
  // but the explicit check returns a more useful error.
  const user = await c.env.DB.prepare(`SELECT id FROM users WHERE id = ?`)
    .bind(body.user_id)
    .first();
  if (!user) return c.json({ error: 'user_not_found' }, 404);

  // Idempotency: if a row with left_at IS NULL already exists, return it.
  const existing = await c.env.DB.prepare(
    `SELECT id, enrolled_at, last_sync_at
       FROM insights_enrollments
      WHERE user_id = ?
        AND left_at IS NULL
      LIMIT 1`,
  )
    .bind(body.user_id)
    .first<{ id: number; enrolled_at: string; last_sync_at: string | null }>();

  if (existing) {
    return c.json({
      enrolled: true,
      enrolled_at: existing.enrolled_at,
      last_sync_at: existing.last_sync_at,
    });
  }

  const inserted = await c.env.DB.prepare(
    `INSERT INTO insights_enrollments (user_id, consent_text_sha256)
     VALUES (?, ?)
     RETURNING id, enrolled_at, last_sync_at`,
  )
    .bind(body.user_id, body.consent_text_sha256 ?? null)
    .first<{ id: number; enrolled_at: string; last_sync_at: string | null }>();

  if (!inserted) return c.json({ error: 'insert_failed' }, 500);

  return c.json({
    enrolled: true,
    enrolled_at: inserted.enrolled_at,
    last_sync_at: inserted.last_sync_at,
  });
});

// ---------------------------------------------------------------------------
// POST /admin/insights/leave
// Body: { user_id: number }
//
// Stamps left_at on every currently-active row for the user (there should
// be at most one, but we set them all in case of a prior race). Idempotent:
// calling on an already-left user is a no-op.
// ---------------------------------------------------------------------------
preferences.post('/insights/leave', async (c) => {
  const body = await c.req.json<{ user_id?: number }>().catch(() => null);
  if (!body?.user_id || !Number.isInteger(body.user_id)) {
    return c.json({ error: 'missing_user_id' }, 400);
  }

  await c.env.DB.prepare(
    `UPDATE insights_enrollments
        SET left_at = datetime('now')
      WHERE user_id = ?
        AND left_at IS NULL`,
  )
    .bind(body.user_id)
    .run();

  return c.json({ enrolled: false });
});
