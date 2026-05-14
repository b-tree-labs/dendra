// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/device/* + /admin/cli-sessions/* integration tests.
// Exercises the full RFC 8628 device-grant flow end to end.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';
import migration0005 from '../../collector/migrations/0005_cloud_features.sql?raw';
import migration0006 from '../../collector/migrations/0006_cli_sessions.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard'; // pragma: allowlist secret
const BASE = 'https://api.test';

const adminHeaders = {
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

let userId: number;

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);
  await applySql(migration0005);
  await applySql(migration0006);

  // A user the dashboard would authorize device sessions to.
  const u = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      clerk_user_id: 'device_flow_user',
      email: 'devflow@example.com',
    }),
  });
  userId = (await u.json<{ user_id: number }>()).user_id;
});

describe('POST /v1/device/code — start the flow', () => {
  it('returns device_code, user_code, and verification URIs', async () => {
    const res = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'test-laptop' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{
      device_code: string;
      user_code: string;
      verification_uri: string;
      verification_uri_complete: string;
      expires_in: number;
      interval: number;
    }>();
    expect(body.device_code).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(body.user_code).toMatch(/^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/);
    expect(body.verification_uri).toContain('/cli-auth');
    expect(body.verification_uri_complete).toContain(encodeURIComponent(body.user_code));
    expect(body.expires_in).toBe(900);
    expect(body.interval).toBe(5);
  });

  it('accepts empty body (no device_name)', async () => {
    const res = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    expect(res.status).toBe(200);
  });

  it('caps device_name at 64 chars (silent truncate, not reject)', async () => {
    const longName = 'x'.repeat(200);
    const res = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: longName }),
    });
    expect(res.status).toBe(200);
    // Verify via the admin lookup; device_name should be truncated.
    const body = await res.json<{ user_code: string }>();
    const lookup = await SELF.fetch(`${BASE}/admin/cli-sessions/${body.user_code}`, {
      method: 'GET',
      headers: adminHeaders,
    });
    const data = await lookup.json<{ device_name: string }>();
    expect(data.device_name?.length).toBeLessThanOrEqual(64);
  });

  it('does not require auth (anonymous endpoint)', async () => {
    // No Bearer token — should still succeed.
    const res = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    expect(res.status).toBe(200);
  });
});

describe('POST /v1/device/token — poll', () => {
  it('returns authorization_pending while session is fresh', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'pending-test' }),
    });
    const { device_code } = await start.json<{ device_code: string }>();

    const poll = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code }),
    });
    expect(poll.status).toBe(400);
    expect(await poll.json()).toEqual({ error: 'authorization_pending' });
  });

  it('returns invalid_grant for unknown device_code', async () => {
    const res = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code: 'totally-bogus-code' }),
    });
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: 'invalid_grant' });
  });

  it('returns invalid_request when device_code missing', async () => {
    const res = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: 'invalid_request' });
  });

  it('returns access_denied after deny', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'deny-test' }),
    });
    const { device_code, user_code } = await start.json<{
      device_code: string;
      user_code: string;
    }>();

    await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/deny`, {
      method: 'POST',
      headers: adminHeaders,
    });

    const poll = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code }),
    });
    expect(poll.status).toBe(400);
    expect(await poll.json()).toEqual({ error: 'access_denied' });
  });
});

describe('happy path — full device flow', () => {
  it('CLI gets a fresh prul_live_ key after dashboard authorizes', async () => {
    // 1. CLI starts the flow.
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'happy-path-laptop' }),
    });
    const { device_code, user_code } = await start.json<{
      device_code: string;
      user_code: string;
    }>();

    // 2. CLI's first poll: pending.
    const polled1 = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code }),
    });
    expect(polled1.status).toBe(400);

    // 3. Dashboard authorizes for our test user.
    const auth = await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/authorize`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(auth.status).toBe(200);
    expect(await auth.json()).toEqual({ ok: true });

    // 4. CLI's next poll: success, returns api_key + email.
    const polled2 = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code }),
    });
    expect(polled2.status).toBe(200);
    const success = await polled2.json<{ api_key: string; email: string }>();
    expect(success.api_key).toMatch(/^prul_live_[A-Za-z0-9]{32}$/);
    expect(success.email).toBe('devflow@example.com');

    // 5. Replay protection: polling again with the same device_code fails.
    const polled3 = await SELF.fetch(`${BASE}/v1/device/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code }),
    });
    expect(polled3.status).toBe(400);
    expect(await polled3.json()).toEqual({ error: 'invalid_grant' });
  });
});

describe('GET /admin/cli-sessions/:user_code', () => {
  it('returns session metadata for the dashboard pre-authorize view', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'lookup-test' }),
    });
    const { user_code } = await start.json<{ user_code: string }>();

    const res = await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}`, {
      method: 'GET',
      headers: adminHeaders,
    });
    expect(res.status).toBe(200);
    const body = await res.json<{
      state: string;
      device_name: string;
      created_at: string;
      expires_at: string;
    }>();
    expect(body.state).toBe('pending');
    expect(body.device_name).toBe('lookup-test');
    // Critical: must NOT leak device_code to the dashboard view.
    expect((body as Record<string, unknown>).device_code).toBeUndefined();
  });

  it('returns 404 for unknown user_code', async () => {
    const res = await SELF.fetch(`${BASE}/admin/cli-sessions/UNKNOWN-CODE`, {
      method: 'GET',
      headers: adminHeaders,
    });
    expect(res.status).toBe(404);
  });

  it('rejects unauthenticated requests (no service token)', async () => {
    const res = await SELF.fetch(`${BASE}/admin/cli-sessions/ANY-CODE`, {
      method: 'GET',
      // no X-Dashboard-Token
    });
    expect(res.status).toBe(401);
  });
});

describe('POST /admin/cli-sessions/:user_code/authorize', () => {
  it('refuses to authorize already-denied session', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'denied-then-authorize' }),
    });
    const { user_code } = await start.json<{ user_code: string }>();

    await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/deny`, {
      method: 'POST',
      headers: adminHeaders,
    });

    const auth = await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/authorize`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });
    expect(auth.status).toBe(409);
    expect((await auth.json<{ error: string }>()).error).toContain('denied');
  });

  it('rejects missing user_id', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const { user_code } = await start.json<{ user_code: string }>();

    const auth = await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/authorize`, {
      method: 'POST',
      headers: adminHeaders,
      body: '{}',
    });
    expect(auth.status).toBe(400);
  });

  it('rejects unauthenticated requests', async () => {
    const res = await SELF.fetch(`${BASE}/admin/cli-sessions/ANY/authorize`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    });
    expect(res.status).toBe(401);
  });
});

describe('POST /admin/cli-sessions/:user_code/deny', () => {
  it('returns 404 if denying an already-authorized session', async () => {
    const start = await SELF.fetch(`${BASE}/v1/device/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const { user_code } = await start.json<{ user_code: string }>();

    await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/authorize`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });

    const deny = await SELF.fetch(`${BASE}/admin/cli-sessions/${user_code}/deny`, {
      method: 'POST',
      headers: adminHeaders,
    });
    expect(deny.status).toBe(404);
  });
});

// ---------------------------------------------------------------------------
// passesRateLimit — unit-tests the helper that gates anonymous endpoints.
// The handlers fail open when the binding is absent (tests/dev) and gate
// at the platform layer in prod via the wrangler.toml ratelimit binding.
// ---------------------------------------------------------------------------
describe('passesRateLimit', () => {
  it('returns true when no limiter binding is provided (fail open)', async () => {
    const { passesRateLimit } = await import('../src/device');
    expect(await passesRateLimit(undefined, '1.2.3.4')).toBe(true);
  });

  it('returns true when the limiter says success', async () => {
    const { passesRateLimit } = await import('../src/device');
    const limiter = { limit: async () => ({ success: true }) };
    expect(await passesRateLimit(limiter, '1.2.3.4')).toBe(true);
  });

  it('returns false when the limiter says failure', async () => {
    const { passesRateLimit } = await import('../src/device');
    const limiter = { limit: async () => ({ success: false }) };
    expect(await passesRateLimit(limiter, '1.2.3.4')).toBe(false);
  });

  it('passes the IP through as the rate-limit key', async () => {
    const { passesRateLimit } = await import('../src/device');
    let captured = '';
    const limiter = {
      limit: async ({ key }: { key: string }) => {
        captured = key;
        return { success: true };
      },
    };
    await passesRateLimit(limiter, '203.0.113.42');
    expect(captured).toBe('203.0.113.42');
  });
});
