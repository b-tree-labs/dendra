// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Admin endpoint tests. Uses the in-Workers vitest pool with a real
// D1 binding; migration 0003 is applied at suite start.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
const BASE = 'https://api.test';

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
      if (!String(e).includes('already exists')) throw e;
    }
  }
}

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
});

describe('admin: service-token auth', () => {
  it('rejects requests without X-Dashboard-Token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys?user_id=1`);
    expect(res.status).toBe(401);
  });

  it('rejects requests with wrong token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys?user_id=1`, {
      headers: { 'X-Dashboard-Token': 'wrong' },
    });
    expect(res.status).toBe(401);
  });

  it('accepts requests with the correct token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys?user_id=1`, { headers });
    expect([200, 400, 404]).toContain(res.status);
  });
});

describe('admin: user upsert + key lifecycle', () => {
  let userId: number;

  it('POST /admin/users creates a new user', async () => {
    const res = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        clerk_user_id: 'user_test_001',
        email: 'test@example.com',
      }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ user_id: number; tier: string }>();
    expect(body.user_id).toBeGreaterThan(0);
    expect(body.tier).toBe('free');
    userId = body.user_id;
  });

  it('POST /admin/users is idempotent on the same clerk_user_id', async () => {
    const res = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        clerk_user_id: 'user_test_001',
        email: 'test@example.com',
      }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ user_id: number }>();
    expect(body.user_id).toBe(userId);
  });

  it('POST /admin/keys issues a new key', async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId, name: 'production' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{
      id: number;
      plaintext: string;
      prefix: string;
      suffix: string;
      name: string;
    }>();
    expect(body.plaintext).toMatch(/^dndr_live_[A-Za-z0-9]{32}$/);
    expect(body.prefix.length).toBe(8);
    expect(body.suffix.length).toBe(4);
    expect(body.name).toBe('production');
    expect(body.id).toBeGreaterThan(0);
  });

  it("GET /admin/keys lists the user's keys", async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys?user_id=${userId}`, { headers });
    expect(res.status).toBe(200);
    const body = await res.json<{
      keys: Array<{ name: string | null; revoked_at: string | null }>;
    }>();
    expect(body.keys.length).toBeGreaterThanOrEqual(1);
    expect(body.keys[0]?.revoked_at).toBeNull();
  });

  it('DELETE /admin/keys/:id revokes a key', async () => {
    const issueRes = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId, name: 'revokable' }),
    });
    const issued = await issueRes.json<{ id: number }>();

    const revokeRes = await SELF.fetch(`${BASE}/admin/keys/${issued.id}`, {
      method: 'DELETE',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(revokeRes.status).toBe(200);
    const body = await revokeRes.json<{ revoked: boolean; id: number }>();
    expect(body.revoked).toBe(true);
    expect(body.id).toBe(issued.id);
  });

  it('DELETE /admin/keys/:id rejects cross-user revoke', async () => {
    const u2 = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        clerk_user_id: 'user_test_002',
        email: 'attacker@example.com',
      }),
    });
    const u2body = await u2.json<{ user_id: number }>();

    const issued = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: userId }),
    });
    const k = await issued.json<{ id: number }>();

    const attackRes = await SELF.fetch(`${BASE}/admin/keys/${k.id}`, {
      method: 'DELETE',
      headers,
      body: JSON.stringify({ user_id: u2body.user_id }),
    });
    expect(attackRes.status).toBe(404);
  });

  it('POST /admin/keys rejects unknown user_id', async () => {
    const res = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_id: 99999 }),
    });
    expect(res.status).toBe(404);
  });
});
