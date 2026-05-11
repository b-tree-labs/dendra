// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /admin/whoami + /admin/insights/* — service-token-authenticated admin
// surface backing the /dashboard/settings and /dashboard/insights pages.
// Uses the in-Workers vitest pool with a real D1 binding; migrations
// 0001..0007 are applied at suite start.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0007 from '../../collector/migrations/0007_user_preferences.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
const BASE = 'https://api.test';
const TUNED_DEFAULTS_KEY = 'tuned-defaults.json';

const headers = {
  'Content-Type': 'application/json',
  'X-Dashboard-Token': SERVICE_TOKEN,
};

async function applySql(sql: string) {
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
      const msg = String(e);
      // ALTER TABLE ADD COLUMN throws "duplicate column name" on re-apply;
      // CREATE … IF NOT EXISTS is already covered by "already exists".
      if (!msg.includes('already exists') && !msg.includes('duplicate column')) {
        throw e;
      }
    }
  }
}

async function newUser(suffix: string): Promise<number> {
  const res = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      clerk_user_id: `user_pref_${suffix}`,
      email: `pref-${suffix}@example.com`,
    }),
  });
  const body = await res.json<{ user_id: number }>();
  return body.user_id;
}

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0007);
});

// ---------------------------------------------------------------------------
// /admin/whoami
// ---------------------------------------------------------------------------

describe('GET /admin/whoami', () => {
  it('returns the user shape with telemetry_enabled defaulting to true', async () => {
    const userId = await newUser('whoami-default');
    const res = await SELF.fetch(`${BASE}/admin/whoami?user_id=${userId}`, { headers });
    expect(res.status).toBe(200);
    const body = await res.json<{
      user_id: number;
      email: string;
      display_name: string | null;
      telemetry_enabled: boolean;
      tier: string;
    }>();
    expect(body.user_id).toBe(userId);
    expect(body.email).toBe('pref-whoami-default@example.com');
    expect(body.display_name).toBeNull();
    expect(body.telemetry_enabled).toBe(true);
    expect(body.tier).toBe('free');
  });

  it('rejects missing user_id', async () => {
    const res = await SELF.fetch(`${BASE}/admin/whoami`, { headers });
    expect(res.status).toBe(400);
  });

  it('returns 404 for an unknown user', async () => {
    const res = await SELF.fetch(`${BASE}/admin/whoami?user_id=99999`, { headers });
    expect(res.status).toBe(404);
  });

  it('rejects requests without the service token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/whoami?user_id=1`);
    expect(res.status).toBe(401);
  });
});

describe('PATCH /admin/whoami', () => {
  it('persists a display_name update', async () => {
    const userId = await newUser('pn-update');
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, display_name: 'Ben Booth' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ display_name: string | null }>();
    expect(body.display_name).toBe('Ben Booth');

    const after = await SELF.fetch(`${BASE}/admin/whoami?user_id=${userId}`, { headers });
    const got = await after.json<{ display_name: string | null }>();
    expect(got.display_name).toBe('Ben Booth');
  });

  it('trims whitespace and caps display_name at 64 chars', async () => {
    const userId = await newUser('pn-cap');
    const longName = '  ' + 'x'.repeat(100) + '  ';
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, display_name: longName }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ display_name: string }>();
    expect(body.display_name).toHaveLength(64);
  });

  it('null display_name clears it', async () => {
    const userId = await newUser('pn-clear');
    await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, display_name: 'Temp' }),
    });
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, display_name: null }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ display_name: string | null }>();
    expect(body.display_name).toBeNull();
  });

  it('persists a telemetry_enabled toggle', async () => {
    const userId = await newUser('tel-toggle');
    const off = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, telemetry_enabled: false }),
    });
    expect(off.status).toBe(200);
    expect((await off.json<{ telemetry_enabled: boolean }>()).telemetry_enabled).toBe(false);

    const on = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, telemetry_enabled: true }),
    });
    expect(on.status).toBe(200);
    expect((await on.json<{ telemetry_enabled: boolean }>()).telemetry_enabled).toBe(true);
  });

  it('rejects an invalid telemetry_enabled value', async () => {
    const userId = await newUser('tel-bad');
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId, telemetry_enabled: 'yes' }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects an empty patch (no fields to update)', async () => {
    const userId = await newUser('empty-patch');
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(res.status).toBe(400);
  });

  it('returns 404 for an unknown user', async () => {
    const res = await SELF.fetch(`${BASE}/admin/whoami`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ user_id: 99999, display_name: 'noone' }),
    });
    expect(res.status).toBe(404);
  });
});

// ---------------------------------------------------------------------------
// /admin/insights/*
// ---------------------------------------------------------------------------

describe('insights enrollment round-trip', () => {
  it('round-trip: enroll → status → leave → status', async () => {
    const userId = await newUser('insights-rt');

    // Starts not enrolled.
    let s = await SELF.fetch(`${BASE}/admin/insights/status?user_id=${userId}`, { headers });
    expect(s.status).toBe(200);
    let body = await s.json<{ enrolled: boolean; cohort_size: number }>();
    expect(body.enrolled).toBe(false);
    expect(body.cohort_size).toBeGreaterThanOrEqual(0);

    // Enroll.
    const enroll = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(enroll.status).toBe(200);
    const eBody = await enroll.json<{ enrolled: boolean; enrolled_at: string }>();
    expect(eBody.enrolled).toBe(true);
    expect(eBody.enrolled_at).toBeTruthy();

    // Status now reads enrolled with the same enrolled_at.
    s = await SELF.fetch(`${BASE}/admin/insights/status?user_id=${userId}`, { headers });
    body = await s.json<{ enrolled: boolean; enrolled_at?: string }>();
    expect(body.enrolled).toBe(true);
    expect((body as { enrolled_at: string }).enrolled_at).toBe(eBody.enrolled_at);

    // Leave.
    const leave = await SELF.fetch(`${BASE}/admin/insights/leave`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(leave.status).toBe(200);

    // Status reads not-enrolled again.
    s = await SELF.fetch(`${BASE}/admin/insights/status?user_id=${userId}`, { headers });
    body = await s.json<{ enrolled: boolean }>();
    expect(body.enrolled).toBe(false);
  });

  it('enroll is idempotent — repeat returns the same enrollment', async () => {
    const userId = await newUser('insights-idem');

    const first = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    const firstBody = await first.json<{ enrolled_at: string }>();

    const second = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(second.status).toBe(200);
    const secondBody = await second.json<{ enrolled_at: string }>();
    expect(secondBody.enrolled_at).toBe(firstBody.enrolled_at);
  });

  it('re-enroll after leave inserts a fresh row', async () => {
    const userId = await newUser('insights-reenroll');

    const first = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    const firstAt = (await first.json<{ enrolled_at: string }>()).enrolled_at;

    await SELF.fetch(`${BASE}/admin/insights/leave`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });

    // Sleep a beat so datetime('now') ticks at least one second — SQLite's
    // resolution is one second.
    await new Promise((r) => setTimeout(r, 1100));

    const second = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    const secondAt = (await second.json<{ enrolled_at: string }>()).enrolled_at;
    expect(secondAt).not.toBe(firstAt);

    // Two rows on disk: one active, one historical.
    const rows = await env.DB.prepare(
      `SELECT COUNT(*) AS n FROM insights_enrollments WHERE user_id = ?`,
    )
      .bind(userId)
      .first<{ n: number }>();
    expect(rows?.n).toBe(2);
  });

  it('leave is idempotent on a not-enrolled user', async () => {
    const userId = await newUser('leave-noop');
    const res = await SELF.fetch(`${BASE}/admin/insights/leave`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(res.status).toBe(200);
  });

  it('cohort_size prefers the KV tuned-defaults value when present', async () => {
    await env.KV_INSIGHTS.put(
      TUNED_DEFAULTS_KEY,
      JSON.stringify({ version: 1, cohort_size: 42 }),
    );
    const userId = await newUser('cohort-kv');
    const res = await SELF.fetch(
      `${BASE}/admin/insights/status?user_id=${userId}`,
      { headers },
    );
    const body = await res.json<{ cohort_size: number }>();
    expect(body.cohort_size).toBe(42);
    await env.KV_INSIGHTS.delete(TUNED_DEFAULTS_KEY);
  });

  it('cohort_size falls back to active-enrollment count when KV is empty', async () => {
    await env.KV_INSIGHTS.delete(TUNED_DEFAULTS_KEY);
    const userId = await newUser('cohort-db');
    await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });

    const res = await SELF.fetch(
      `${BASE}/admin/insights/status?user_id=${userId}`,
      { headers },
    );
    const body = await res.json<{ cohort_size: number }>();
    // We don't know exactly how many enrollments the other suites
    // created; just assert at least one (this user).
    expect(body.cohort_size).toBeGreaterThanOrEqual(1);
  });

  it('enroll rejects unknown user_id', async () => {
    const res = await SELF.fetch(`${BASE}/admin/insights/enroll`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: 99999 }),
    });
    expect(res.status).toBe(404);
  });

  it('rejects requests without the service token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/insights/status?user_id=1`);
    expect(res.status).toBe(401);
  });
});
