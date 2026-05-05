// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/team-corpus, /v1/team-corpus/:id, /v1/registry/contribute integration tests.
// Exercises validation, server-side anonymization re-check, and the
// D1 persistence path.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';
import migration0005 from '../../collector/migrations/0005_cloud_features.sql?raw';

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

let bearer: string;

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);
  await applySql(migration0005);

  const u = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      clerk_user_id: 'cloud_features_user',
      email: 'cloud@example.com',
    }),
  });
  const userId = (await u.json<{ user_id: number }>()).user_id;

  const k = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: userId, name: 'cloud-features-test' }),
  });
  bearer = (await k.json<{ plaintext: string }>()).plaintext;
});

const authedHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${bearer}`,
});

describe('POST /v1/team-corpus — share', () => {
  it('persists the corpus and returns a server-canonical share_url', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        team_id: 'acme-eng',
        corpus: { rule: { v: 1 }, examples: [] },
      }),
    });
    expect(res.status).toBe(201);
    const body = await res.json<{ share_url: string }>();
    expect(body.share_url).toBe('https://api.test/v1/team-corpus/acme-eng');
  });

  it('rejects missing team_id', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ corpus: { rule: { v: 1 } } }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects malformed team_id', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        team_id: 'has spaces',
        corpus: { rule: { v: 1 } },
      }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects non-object corpus', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ team_id: 'acme', corpus: 'not an object' }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects payload exceeding 16 KB', async () => {
    const big = { padding: 'x'.repeat(17 * 1024) };
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ team_id: 'acme', corpus: big }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects unauthenticated requests', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_id: 'acme', corpus: { rule: { v: 1 } } }),
    });
    expect(res.status).toBe(401);
  });
});

describe('GET /v1/team-corpus/:id — fetch', () => {
  it('returns the most recent corpus for a team_id', async () => {
    // Share first.
    await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        team_id: 'fetch-test',
        corpus: { generation: 1 },
      }),
    });
    // Then a newer one. Most recent wins.
    await SELF.fetch(`${BASE}/v1/team-corpus`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        team_id: 'fetch-test',
        corpus: { generation: 2 },
      }),
    });

    const res = await SELF.fetch(`${BASE}/v1/team-corpus/fetch-test`, {
      method: 'GET',
      headers: authedHeaders(),
    });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ generation: 2 });
  });

  it('returns 404 for unknown team_id', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus/never-shared`, {
      method: 'GET',
      headers: authedHeaders(),
    });
    expect(res.status).toBe(404);
  });

  it('rejects malformed team_id in URL', async () => {
    const res = await SELF.fetch(`${BASE}/v1/team-corpus/has%20spaces`, {
      method: 'GET',
      headers: authedHeaders(),
    });
    expect(res.status).toBe(400);
  });
});

describe('POST /v1/registry/contribute — anonymized', () => {
  it('accepts a clean anonymized corpus', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ rule: { v: 1 }, examples: [{ text: 'hi' }] }),
    });
    expect(res.status).toBe(201);
    const body = await res.json<{ id: number; accepted_at: string }>();
    expect(body.id).toBeGreaterThan(0);
  });

  it('rejects corpora with top-level identifying keys', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ author: 'alice', rule: { v: 1 } }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects corpora with nested identifying keys (defense in depth)', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        rule: { v: 1, author: 'alice' },
        examples: [],
      }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects identifying keys deep inside lists', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        examples: [{ text: 'hi', email: 'leak@x' }],
      }),
    });
    expect(res.status).toBe(400);
  });

  it('rejects payload exceeding 32 KB', async () => {
    const big = { padding: 'x'.repeat(33 * 1024) };
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify(big),
    });
    expect(res.status).toBe(400);
  });

  it('rejects non-object body', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify(['not', 'an', 'object']),
    });
    expect(res.status).toBe(400);
  });

  it('rejects unauthenticated requests', async () => {
    const res = await SELF.fetch(`${BASE}/v1/registry/contribute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule: { v: 1 } }),
    });
    expect(res.status).toBe(401);
  });
});
