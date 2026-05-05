// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
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
let apiKeyId: number;

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);

  const u = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ clerk_user_id: 'report_user', email: 'report@example.com' }),
  });
  const userId = (await u.json<{ user_id: number }>()).user_id;

  const k = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: userId, name: 'report-test' }),
  });
  const issued = await k.json<{ id: number; plaintext: string }>();
  bearer = issued.plaintext;
  apiKeyId = issued.id;

  // Seed a deterministic verdict pattern for the "intent_classifier" switch:
  //   12 verdicts total, all paired (rule + ml both reported)
  //   rule: 8 correct (P0..P3 era, rule wins early)
  //   ml:   10 correct (ml is better overall)
  //   discordant pairs: b=1 (rule right, ml wrong)
  //                     c=3 (rule wrong, ml right)
  // Plus 5 verdicts on a different switch we shouldn't see in the report.
  const fixtures = [
    // [rule, ml, phase]
    [1, 1, 'P3'], [1, 1, 'P3'], [1, 1, 'P3'], [1, 1, 'P3'],
    [1, 1, 'P4'], [1, 1, 'P4'], [1, 1, 'P4'],
    [1, 0, 'P3'],   // b
    [0, 1, 'P3'],   // c
    [0, 1, 'P4'],   // c
    [0, 1, 'P5'],   // c
    [0, 0, 'P5'],
  ];
  for (const [rule, ml, phase] of fixtures) {
    await env.DB.prepare(
      `INSERT INTO verdicts (api_key_id, switch_name, phase, rule_correct, ml_correct)
       VALUES (?, 'intent_classifier', ?, ?, ?)`,
    ).bind(apiKeyId, phase, rule, ml).run();
  }
  // Other switch — shouldn't pollute report.
  await env.DB.prepare(
    `INSERT INTO verdicts (api_key_id, switch_name, rule_correct, ml_correct)
     VALUES (?, 'other', 1, 0), (?, 'other', 1, 1), (?, 'other', 0, 1),
            (?, 'other', 1, 1), (?, 'other', 0, 0)`,
  ).bind(apiKeyId, apiKeyId, apiKeyId, apiKeyId, apiKeyId).run();
});

const authedHeaders = () => ({ Authorization: `Bearer ${bearer}` });

describe('GET /v1/switches/:name/report — JSON format', () => {
  it('returns aggregated stats for the named switch only', async () => {
    const res = await SELF.fetch(
      `${BASE}/v1/switches/intent_classifier/report?format=json`,
      { headers: authedHeaders() },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{
      switch_name: string;
      days: number;
      agg: Record<string, number | string | null>;
      phases: Array<{ phase: string | null; n: number }>;
      mcnemar_p_two_sided: number | null;
    }>();

    expect(body.switch_name).toBe('intent_classifier');
    expect(body.days).toBe(30);
    expect(body.agg.total).toBe(12);
    expect(body.agg.rule_total).toBe(12);
    expect(body.agg.rule_correct).toBe(8);
    expect(body.agg.ml_total).toBe(12);
    expect(body.agg.ml_correct).toBe(10);
    expect(body.agg.paired_total).toBe(12);
    expect(body.agg.b).toBe(1);
    expect(body.agg.c).toBe(3);
    // 12 verdicts on this switch; the 'other' switch (5 more) excluded.
    expect(body.phases.length).toBeGreaterThan(0);
  });

  it('McNemar p-value matches the closed-form for b=1, c=3', async () => {
    const res = await SELF.fetch(
      `${BASE}/v1/switches/intent_classifier/report?format=json`,
      { headers: authedHeaders() },
    );
    const body = await res.json<{ mcnemar_p_two_sided: number }>();
    // Exact: 2 * P(X<=1 | Bin(4, 0.5)) = 2 * (C(4,0)+C(4,1))/2^4 = 2 * 5/16 = 0.625
    expect(body.mcnemar_p_two_sided).toBeGreaterThan(0.62);
    expect(body.mcnemar_p_two_sided).toBeLessThan(0.63);
  });

  it('clamps days to [1, 365] and accepts default 30', async () => {
    const r1 = await SELF.fetch(
      `${BASE}/v1/switches/intent_classifier/report?format=json&days=9999`,
      { headers: authedHeaders() },
    );
    expect((await r1.json<{ days: number }>()).days).toBe(365);

    const r2 = await SELF.fetch(
      `${BASE}/v1/switches/intent_classifier/report?format=json&days=-5`,
      { headers: authedHeaders() },
    );
    expect((await r2.json<{ days: number }>()).days).toBe(30);
  });
});

describe('GET /v1/switches/:name/report — Markdown format (default)', () => {
  it('returns text/markdown content-type', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches/intent_classifier/report`, {
      headers: authedHeaders(),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toMatch(/text\/markdown/);
  });

  it('includes the headline figures + McNemar verdict', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches/intent_classifier/report`, {
      headers: authedHeaders(),
    });
    const md = await res.text();
    expect(md).toContain('# Report card — `intent_classifier`');
    expect(md).toContain('Total verdicts: **12**');
    expect(md).toMatch(/Rule.*\b8\b/);
    expect(md).toMatch(/ML.*\b10\b/);
    expect(md).toContain('McNemar two-sided exact p');
    expect(md).toMatch(/does not clear α = 0.05/); // p≈0.625
  });
});

describe('GET /v1/switches/:name/report — validation', () => {
  it('rejects bad switch_name', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches/has spaces/report`, {
      headers: authedHeaders(),
    });
    // Hono won't even match the route with a space in :name; but
    // URL-encoded ones with disallowed chars hit our validation path.
    expect([400, 404]).toContain(res.status);
  });

  it('rejects without Bearer', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches/intent_classifier/report`);
    expect(res.status).toBe(401);
  });

  it('returns empty stats for unknown switch_name (zero rows)', async () => {
    const res = await SELF.fetch(
      `${BASE}/v1/switches/never_seen/report?format=json`,
      { headers: authedHeaders() },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{ agg: { total: number } }>();
    expect(body.agg.total).toBe(0);
  });
});
