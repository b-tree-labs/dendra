// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Dendra hosted API — Cloudflare Worker.
//
// Routes:
//   GET  /health                    — liveness probe (unauthenticated)
//   GET  /v1/whoami                 — auth probe; returns tier + account_hash
//   POST /v1/verdicts               — record outcome (week 2)
//   GET  /v1/switches/:name/report  — report-card render (week 2)
//   POST /v1/judge                  — LLM-as-judge (week 2, conditional)
//
// Auth: every /v1/* route requires `Authorization: Bearer dndr_live_…`.
// The auth middleware resolves the key to a user + tier and attaches
// the AuthContext to c.var.auth for downstream handlers.

import { Hono } from 'hono';
import { authMiddleware, requireAuth, type ApiEnv } from './auth';

const app = new Hono<{ Bindings: ApiEnv }>();

// ---------------------------------------------------------------------------
// Public: liveness probe. Used by Better Stack + smoke tests. No auth.
// ---------------------------------------------------------------------------
app.get('/health', (c) => {
  return c.json({
    status: 'ok',
    service: 'dendra-api',
    environment: c.env.ENVIRONMENT,
    timestamp: new Date().toISOString(),
  });
});

// ---------------------------------------------------------------------------
// Authenticated routes. Every /v1/* path runs the auth middleware first.
// ---------------------------------------------------------------------------
const v1 = new Hono<{ Bindings: ApiEnv }>();
v1.use('*', authMiddleware());

v1.get('/whoami', (c) => {
  const auth = requireAuth(c);
  return c.json({
    tier: auth.tier,
    account_hash: auth.account_hash,
    rate_limit_rps: auth.rate_limit_rps,
  });
});

// Week 2 will land /verdicts, /switches/:name/report, /judge here.
// Stubs return 501 so SDKs hitting them get a recognizable signal.
v1.post('/verdicts', (c) => c.json({ error: 'not_implemented' }, 501));
v1.get('/switches/:name/report', (c) => c.json({ error: 'not_implemented' }, 501));
v1.post('/judge', (c) => c.json({ error: 'not_implemented' }, 501));

app.route('/v1', v1);

// ---------------------------------------------------------------------------
// Catch-all: 404 with a recognizable shape so client SDKs can surface it.
// ---------------------------------------------------------------------------
app.notFound((c) =>
  c.json({ error: 'not_found', path: c.req.path }, 404),
);

app.onError((err, c) => {
  console.error('unhandled error:', err);
  return c.json({ error: 'internal_error' }, 500);
});

export default app;
