// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/verdicts integration tests. Exercises validation, idempotency,
// and the persistence path against a real D1 binding.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';
import migration0008 from '../../collector/migrations/0008_switch_archives.sql?raw';

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

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);
  await applySql(migration0008);

  // Set up a user + key so we can authenticate /v1/verdicts calls.
  const u = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      clerk_user_id: 'verdicts_user',
      email: 'verdicts@example.com',
    }),
  });
  const userId = (await u.json<{ user_id: number }>()).user_id;

  const k = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: userId, name: 'verdicts-test' }),
  });
  bearer = (await k.json<{ plaintext: string }>()).plaintext;
});

const authedHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${bearer}`,
});

describe('POST /v1/verdicts — happy path', () => {
  it('accepts a minimal verdict and returns 201 with id', async () => {
    const res = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({ switch_name: 'intent_classifier' }),
    });
    expect(res.status).toBe(201);
    const body = await res.json<{ id: number; accepted_at: string }>();
    expect(body.id).toBeGreaterThan(0);
    expect(typeof body.accepted_at).toBe('string');
  });

  it('persists all the optional fields', async () => {
    const res = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        switch_name: 'intent_classifier',
        phase: 'P3',
        rule_correct: true,
        model_correct: false,
        ml_correct: true,
        ground_truth: 'book_flight',
        metadata: { user_segment: 'beta' },
      }),
    });
    expect(res.status).toBe(201);
    const body = await res.json<{ id: number }>();
    const row = await env.DB.prepare(
      `SELECT phase, rule_correct, model_correct, ml_correct,
              ground_truth, metadata_json
         FROM verdicts WHERE id = ?`,
    )
      .bind(body.id)
      .first();
    expect(row).toMatchObject({
      phase: 'P3',
      rule_correct: 1,
      model_correct: 0,
      ml_correct: 1,
      ground_truth: 'book_flight',
    });
    expect(JSON.parse(row?.metadata_json as string)).toEqual({ user_segment: 'beta' });
  });
});

describe('POST /v1/verdicts — idempotency', () => {
  it('returns the original row on retry with the same request_id', async () => {
    const reqId = 'req_test_1';
    const r1 = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        switch_name: 'intent_classifier',
        request_id: reqId,
        rule_correct: true,
      }),
    });
    expect(r1.status).toBe(201);
    const b1 = await r1.json<{ id: number }>();

    const r2 = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: authedHeaders(),
      body: JSON.stringify({
        switch_name: 'intent_classifier',
        request_id: reqId,
        rule_correct: false, // even with different payload, idempotent
      }),
    });
    expect(r2.status).toBe(200);
    const b2 = await r2.json<{ id: number; duplicate: boolean }>();
    expect(b2.id).toBe(b1.id);
    expect(b2.duplicate).toBe(true);
  });
});

describe('POST /v1/verdicts — validation', () => {
  const cases: Array<[string, object, RegExp]> = [
    ['missing switch_name', {}, /switch_name/],
    ['empty switch_name', { switch_name: '' }, /switch_name/],
    ['switch_name with spaces', { switch_name: 'has spaces' }, /switch_name/],
    ['switch_name too long', { switch_name: 'a'.repeat(65) }, /switch_name/],
    ['bad phase', { switch_name: 'x', phase: 'P9' }, /phase/],
    [
      'rule_correct not boolean',
      { switch_name: 'x', rule_correct: 'yes' },
      /rule_correct/,
    ],
    [
      'ground_truth too long',
      { switch_name: 'x', ground_truth: 'a'.repeat(513) },
      /ground_truth/,
    ],
    [
      'metadata not object',
      { switch_name: 'x', metadata: ['a', 'b'] },
      /metadata/,
    ],
    [
      'request_id too long',
      { switch_name: 'x', request_id: 'a'.repeat(129) },
      /request_id/,
    ],
  ];

  for (const [name, body, errPattern] of cases) {
    it(name, async () => {
      const res = await SELF.fetch(`${BASE}/v1/verdicts`, {
        method: 'POST',
        headers: authedHeaders(),
        body: JSON.stringify(body),
      });
      expect(res.status).toBe(400);
      const b = await res.json<{ error: string }>();
      expect(b.error).toMatch(errPattern);
    });
  }
});

describe('POST /v1/verdicts — auth', () => {
  it('returns 401 without bearer', async () => {
    const res = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ switch_name: 'x' }),
    });
    expect(res.status).toBe(401);
  });

  it('returns 401 with malformed bearer', async () => {
    const res = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer junk' },
      body: JSON.stringify({ switch_name: 'x' }),
    });
    expect(res.status).toBe(401);
  });
});

describe('POST /v1/verdicts — auto-unarchive on revival', () => {
  it('removes the switch_archives row when a verdict arrives for an archived switch', async () => {
    // Set up a fresh user + key for isolation. Then emit one verdict so
    // the user has ownership of the switch_name, archive it, fire a
    // second verdict, and assert the archive row is gone.
    const u = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({
        clerk_user_id: 'auto_unarchive_user',
        email: 'auto-unarchive@example.com',
      }),
    });
    const userId = (await u.json<{ user_id: number }>()).user_id;
    const k = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });
    const userBearer = (await k.json<{ plaintext: string }>()).plaintext;
    const userHeaders = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${userBearer}`,
    };

    // First verdict establishes ownership of the switch name.
    await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: userHeaders,
      body: JSON.stringify({ switch_name: 'revival_switch' }),
    });

    // Archive the switch via the admin endpoint.
    const arc = await SELF.fetch(
      `${BASE}/admin/switches/revival_switch/archive`,
      {
        method: 'POST',
        headers: adminHeaders,
        body: JSON.stringify({ user_id: userId, reason: 'commented out' }),
      },
    );
    expect(arc.status).toBe(200);

    // Confirm archive row exists.
    const before = await env.DB.prepare(
      `SELECT id FROM switch_archives WHERE user_id = ? AND switch_name = ?`,
    )
      .bind(userId, 'revival_switch')
      .first();
    expect(before).not.toBeNull();

    // Fire a fresh verdict for the same switch — the customer
    // un-commented their @ml_switch.
    const v2 = await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: userHeaders,
      body: JSON.stringify({ switch_name: 'revival_switch', phase: 'P3' }),
    });
    expect(v2.status).toBe(201);

    // Archive row should be gone — switch is alive again.
    const after = await env.DB.prepare(
      `SELECT id FROM switch_archives WHERE user_id = ? AND switch_name = ?`,
    )
      .bind(userId, 'revival_switch')
      .first();
    expect(after).toBeNull();
  });

  it('verdict-emit for a non-archived switch is a no-op against switch_archives', async () => {
    // Sanity guard against the new DELETE accidentally affecting
    // unrelated archives. Set up two switches; archive switch A; fire
    // a verdict for switch B; assert A's archive row still exists.
    const u = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({
        clerk_user_id: 'auto_unarchive_isolation',
        email: 'iso-unarchive@example.com',
      }),
    });
    const userId = (await u.json<{ user_id: number }>()).user_id;
    const k = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });
    const userBearer = (await k.json<{ plaintext: string }>()).plaintext;
    const userHeaders = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${userBearer}`,
    };

    // Seed verdicts on both switches.
    await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: userHeaders,
      body: JSON.stringify({ switch_name: 'switch_a' }),
    });
    await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: userHeaders,
      body: JSON.stringify({ switch_name: 'switch_b' }),
    });

    // Archive switch_a only.
    await SELF.fetch(`${BASE}/admin/switches/switch_a/archive`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId }),
    });

    // New verdict for switch_b — should NOT touch switch_a's archive.
    await SELF.fetch(`${BASE}/v1/verdicts`, {
      method: 'POST',
      headers: userHeaders,
      body: JSON.stringify({ switch_name: 'switch_b' }),
    });

    const a = await env.DB.prepare(
      `SELECT id FROM switch_archives WHERE user_id = ? AND switch_name = ?`,
    )
      .bind(userId, 'switch_a')
      .first();
    expect(a).not.toBeNull();
  });
});
