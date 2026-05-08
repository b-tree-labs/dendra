// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /insights/* — public read path for cohort wisdom written by the
// nightly aggregator (cloud/aggregator/run.py) into the KV_INSIGHTS
// namespace. No auth: the Python CLI and the landing site both fetch
// these via plain HTTPS.
//
// The route is mounted on `dendra.run/insights/*` via a Cloudflare
// Worker Route override (see docs/working/aggregator-kv-cutover-2026-05-07.md),
// which keeps the consumer URL stable across the file→KV cutover.

import { Hono } from 'hono';

export type InsightsEnv = {
  KV_INSIGHTS: KVNamespace;
};

export const insights = new Hono<{ Bindings: InsightsEnv }>();

const TUNED_DEFAULTS_KEY = 'tuned-defaults.json';

insights.get('/tuned-defaults.json', async (c) => {
  const raw = await c.env.KV_INSIGHTS.get(TUNED_DEFAULTS_KEY);
  if (raw === null) {
    // Pre-aggregator-run state: respond 404 + don't cache absence,
    // so the first nightly write becomes visible immediately.
    return c.json(
      { error: 'not_yet_available' },
      404,
      { 'Cache-Control': 'no-store' },
    );
  }
  // Pass the body through verbatim — the aggregator is the source of
  // truth for shape + key ordering. Re-stringifying here would change
  // hashes for any consumer that signs the body.
  return new Response(raw, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
      'X-Dendra-Source': 'kv',
    },
  });
});
