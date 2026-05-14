// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /insights/tuned-defaults.json — public, unauthenticated, KV-backed.
// The aggregator nightly writes the JSON into KV_INSIGHTS; this route
// is the read path the landing site (and the Python CLI) hit at
// https://postrule.ai/insights/tuned-defaults.json.

import { describe, it, expect, beforeEach } from 'vitest';
import { env, SELF } from 'cloudflare:test';

const BASE = 'https://api.test';
const KEY = 'tuned-defaults.json';

beforeEach(async () => {
  await env.KV_INSIGHTS.delete(KEY);
});

describe('GET /insights/tuned-defaults.json', () => {
  it('returns 200 with the JSON body when KV holds the key', async () => {
    const payload = {
      version: 4,
      cohort_size: 12,
      generated_at: '2026-05-07T03:00:00Z',
      defaults: { temperature: 0.4 },
    };
    await env.KV_INSIGHTS.put(KEY, JSON.stringify(payload));

    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(payload);
  });

  it('sets Content-Type: application/json on hit', async () => {
    await env.KV_INSIGHTS.put(KEY, JSON.stringify({ version: 1 }));
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.headers.get('content-type') ?? '').toMatch(/application\/json/);
  });

  it('sets Cache-Control: public, max-age=300 on hit', async () => {
    await env.KV_INSIGHTS.put(KEY, JSON.stringify({ version: 1 }));
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.headers.get('cache-control')).toBe('public, max-age=300');
  });

  it('sets X-Postrule-Source: kv on hit (lets cutover verify origin)', async () => {
    await env.KV_INSIGHTS.put(KEY, JSON.stringify({ version: 1 }));
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.headers.get('x-postrule-source')).toBe('kv');
  });

  it('returns 404 when KV has no value yet (pre-aggregator-run)', async () => {
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.status).toBe(404);
  });

  it('does not cache 404s (Cache-Control: no-store)', async () => {
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('is unauthenticated (no Bearer token required)', async () => {
    await env.KV_INSIGHTS.put(KEY, JSON.stringify({ ok: true }));
    // No Authorization header.
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(res.status).toBe(200);
  });

  it('passes the KV value through verbatim (no re-serialization)', async () => {
    // The aggregator is the source of truth for the JSON shape; the
    // route should not parse + re-stringify, since that would change
    // key ordering and break any consumer that hashes the body.
    const raw = '{"version":4,"cohort_size":7,"defaults":{"a":1}}';
    await env.KV_INSIGHTS.put(KEY, raw);
    const res = await SELF.fetch(`${BASE}/insights/tuned-defaults.json`);
    expect(await res.text()).toBe(raw);
  });
});
