// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/switches list endpoint + cross-account data-isolation tests.

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

let aliceBearer: string;
let aliceUserId: number;
let aliceKeyId: number;
let aliceSecondKeyId: number;
let bobBearer: string;
let bobUserId: number;
let bobKeyId: number;

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);

  // Alice — has two keys (a "live" and a "test" key) so we can verify
  // the dashboard sees a unified roster across her keys.
  const aUser = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ clerk_user_id: 'switches_alice', email: 'alice@example.com' }),
  });
  aliceUserId = (await aUser.json<{ user_id: number }>()).user_id;
  const aKey1 = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: aliceUserId, name: 'live', environment: 'live' }),
  });
  const a1 = await aKey1.json<{ id: number; plaintext: string }>();
  aliceBearer = a1.plaintext;
  aliceKeyId = a1.id;
  const aKey2 = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: aliceUserId, name: 'test', environment: 'test' }),
  });
  aliceSecondKeyId = (await aKey2.json<{ id: number }>()).id;

  // Bob — separate account; we'll prove Alice cannot read Bob's switches.
  const bUser = await SELF.fetch(`${BASE}/admin/users`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ clerk_user_id: 'switches_bob', email: 'bob@example.com' }),
  });
  bobUserId = (await bUser.json<{ user_id: number }>()).user_id;
  const bKey = await SELF.fetch(`${BASE}/admin/keys`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({ user_id: bobUserId, name: 'live' }),
  });
  const bk = await bKey.json<{ id: number; plaintext: string }>();
  bobBearer = bk.plaintext;
  bobKeyId = bk.id;

  // Alice's live key — 3 verdicts on intent_classifier across two phases.
  // Backdate two so the most-recent ends up on 'P5' (ML_PRIMARY).
  await env.DB.prepare(
    `INSERT INTO verdicts (api_key_id, switch_name, phase, rule_correct, ml_correct, created_at)
     VALUES
       (?, 'intent_classifier', 'P0', 1, NULL, datetime('now', '-10 days')),
       (?, 'intent_classifier', 'P3', 0, 1,    datetime('now', '-5 days')),
       (?, 'intent_classifier', 'P5', 1, 1,    datetime('now', '-1 day'))`,
  )
    .bind(aliceKeyId, aliceKeyId, aliceKeyId)
    .run();

  // Alice's test key — 1 verdict on a SECOND switch 'severity_classifier'
  // so the list endpoint must return both switches under one user roster.
  await env.DB.prepare(
    `INSERT INTO verdicts (api_key_id, switch_name, phase, rule_correct, ml_correct, created_at)
     VALUES (?, 'severity_classifier', 'P1', 1, 0, datetime('now', '-2 hours'))`,
  )
    .bind(aliceSecondKeyId)
    .run();

  // Bob's key — one verdict on 'bobs_private_switch'. Alice must NOT see this.
  await env.DB.prepare(
    `INSERT INTO verdicts (api_key_id, switch_name, phase, rule_correct, ml_correct)
     VALUES (?, 'bobs_private_switch', 'P2', 1, 0)`,
  )
    .bind(bobKeyId)
    .run();
});

const headersFor = (bearer: string) => ({ Authorization: `Bearer ${bearer}` });

describe('GET /v1/switches — list', () => {
  it('rejects without Bearer', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches`);
    expect(res.status).toBe(401);
  });

  it('returns empty list (200) for a user who has never emitted a verdict', async () => {
    // Fresh user with a key but no verdicts.
    const u = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ clerk_user_id: 'switches_empty', email: 'empty@example.com' }),
    });
    const uid = (await u.json<{ user_id: number }>()).user_id;
    const k = await SELF.fetch(`${BASE}/admin/keys`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: uid }),
    });
    const bearer = (await k.json<{ plaintext: string }>()).plaintext;

    const res = await SELF.fetch(`${BASE}/v1/switches`, { headers: headersFor(bearer) });
    expect(res.status).toBe(200);
    const body = await res.json<{ switches: unknown[] }>();
    expect(body.switches).toEqual([]);
  });

  it('returns Alice both switches across her two keys, sorted by recent activity', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches`, { headers: headersFor(aliceBearer) });
    expect(res.status).toBe(200);
    const body = await res.json<{
      switches: Array<{
        switch_name: string;
        current_phase: string | null;
        total_verdicts: number;
        sparkline: number[];
        last_activity: string;
      }>;
      sparkline_window_days: number;
    }>();

    expect(body.sparkline_window_days).toBe(14);
    expect(body.switches.length).toBe(2);
    // severity_classifier was the most recent (2 hours ago) so it sorts first.
    expect(body.switches[0].switch_name).toBe('severity_classifier');
    expect(body.switches[0].total_verdicts).toBe(1);
    expect(body.switches[0].current_phase).toBe('P1');
    // intent_classifier has 3 verdicts; current phase is the most recent (P5).
    expect(body.switches[1].switch_name).toBe('intent_classifier');
    expect(body.switches[1].total_verdicts).toBe(3);
    expect(body.switches[1].current_phase).toBe('P5');

    // Sparkline shape: always 14 buckets.
    for (const s of body.switches) {
      expect(s.sparkline.length).toBe(14);
    }
  });

  it('does NOT include another user\'s switches', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches`, { headers: headersFor(aliceBearer) });
    const body = await res.json<{ switches: Array<{ switch_name: string }> }>();
    const names = body.switches.map((s) => s.switch_name);
    expect(names).not.toContain('bobs_private_switch');
  });

  it('Bob sees only his own switches', async () => {
    const res = await SELF.fetch(`${BASE}/v1/switches`, { headers: headersFor(bobBearer) });
    const body = await res.json<{ switches: Array<{ switch_name: string }> }>();
    expect(body.switches.length).toBe(1);
    expect(body.switches[0].switch_name).toBe('bobs_private_switch');
  });
});

describe('GET /v1/switches/:name/report — data isolation', () => {
  it('returns 404 when a user requests another user\'s switch', async () => {
    // Alice has a valid key, and bobs_private_switch is a real switch
    // name in the system — but it does not belong to her. The data-
    // isolation guarantee is that this looks identical to a typo: 404,
    // never 200-empty, never 403 (which would leak existence).
    const res = await SELF.fetch(
      `${BASE}/v1/switches/bobs_private_switch/report?format=json`,
      { headers: headersFor(aliceBearer) },
    );
    expect(res.status).toBe(404);
  });

  it('returns 200 with the owner\'s data when Bob asks for his own switch', async () => {
    const res = await SELF.fetch(
      `${BASE}/v1/switches/bobs_private_switch/report?format=json`,
      { headers: headersFor(bobBearer) },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{ switch_name: string; current_phase: string }>();
    expect(body.switch_name).toBe('bobs_private_switch');
    expect(body.current_phase).toBe('P2');
  });

  it('unifies across multiple keys: Alice can pull her test-key switch via her live key', async () => {
    // severity_classifier was reported under Alice's TEST key, but the
    // user_id scoping means her live-key bearer can still read it.
    const res = await SELF.fetch(
      `${BASE}/v1/switches/severity_classifier/report?format=json`,
      { headers: headersFor(aliceBearer) },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{ agg: { total: number } }>();
    expect(body.agg.total).toBe(1);
  });
});

describe('GET /admin/switches — dashboard proxy', () => {
  it('rejects without service token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/switches?user_id=${aliceUserId}`);
    expect(res.status).toBe(401);
  });

  it('returns the user\'s roster when called with service token', async () => {
    const res = await SELF.fetch(
      `${BASE}/admin/switches?user_id=${aliceUserId}`,
      { headers: { 'X-Dashboard-Token': SERVICE_TOKEN } },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{
      switches: Array<{ switch_name: string; current_phase_label: string | null }>;
    }>();
    const names = body.switches.map((s) => s.switch_name);
    expect(names).toContain('intent_classifier');
    expect(names).toContain('severity_classifier');
    // Bob's switch must not appear.
    expect(names).not.toContain('bobs_private_switch');
    // Phase label translation (P5 → ML_PRIMARY).
    const ic = body.switches.find((s) => s.switch_name === 'intent_classifier');
    expect(ic?.current_phase_label).toBe('ML_PRIMARY');
  });

  it('GET /admin/switches/:name/report returns 404 for another user\'s switch', async () => {
    const res = await SELF.fetch(
      `${BASE}/admin/switches/bobs_private_switch/report?user_id=${aliceUserId}`,
      { headers: { 'X-Dashboard-Token': SERVICE_TOKEN } },
    );
    expect(res.status).toBe(404);
  });

  it('GET /admin/switches/:name/report returns 200 + structured payload for the owner', async () => {
    const res = await SELF.fetch(
      `${BASE}/admin/switches/intent_classifier/report?user_id=${aliceUserId}`,
      { headers: { 'X-Dashboard-Token': SERVICE_TOKEN } },
    );
    expect(res.status).toBe(200);
    const body = await res.json<{
      switch_name: string;
      current_phase: string;
      current_phase_label: string;
      transitions: Array<{ phase: string; first_seen: string; last_seen: string; n: number }>;
      agg: { total: number };
    }>();
    expect(body.switch_name).toBe('intent_classifier');
    expect(body.current_phase).toBe('P5');
    expect(body.current_phase_label).toBe('ML_PRIMARY');
    expect(body.transitions.length).toBeGreaterThan(0);
    // We seeded P0, P3, P5 — first transition should be P0.
    expect(body.transitions[0].phase).toBe('P0');
  });
});
