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
import { usageMiddleware } from './usage';
import { admin, type AdminEnv } from './admin';
import { webhook, type WebhookEnv } from './webhook';
import { recordVerdictHandler } from './verdicts';
import { renderReportHandler } from './report';
import {
  shareCorpusHandler,
  fetchCorpusHandler,
  contributeHandler,
} from './cloud_features';
import { device, type DeviceEnv } from './device';

type Env = AdminEnv & WebhookEnv & DeviceEnv;
const app = new Hono<{ Bindings: Env }>();

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

// /whoami is auth-gated but does NOT count toward usage — it's a probe,
// SDKs call it on connect to verify the key.
v1.get('/whoami', (c) => {
  const auth = requireAuth(c);
  return c.json({
    tier: auth.tier,
    account_hash: auth.account_hash,
    rate_limit_rps: auth.rate_limit_rps,
  });
});

// Billable routes — wrap with usageMiddleware so each call increments
// the monthly counter and enforces tier caps before reaching the
// (week 2) handlers.
const billable = new Hono<{ Bindings: ApiEnv }>();
billable.use('*', usageMiddleware());
billable.post('/verdicts', recordVerdictHandler);
billable.get('/switches/:name/report', renderReportHandler);
billable.post('/judge', (c) => c.json({ error: 'not_implemented' }, 501));
billable.post('/team-corpus', shareCorpusHandler);
billable.get('/team-corpus/:id', fetchCorpusHandler);
billable.post('/registry/contribute', contributeHandler);
v1.route('/', billable);

// Device-flow login (RFC 8628) — anonymous. Mounted BEFORE the
// auth-required /v1 group so the more-specific /v1/device prefix wins
// the route match and unauthenticated CLIs can kick off the flow.
app.route('/v1/device', device);

app.route('/v1', v1);

// ---------------------------------------------------------------------------
// Admin: dashboard-only endpoints (key issuance / revocation, user upsert).
// Mounted at /admin (not /v1/admin) to keep it unambiguously distinct
// from the Bearer-authenticated public surface. Auth is by service
// token; routes are defined in admin.ts.
// ---------------------------------------------------------------------------
app.route('/admin', admin);

// ---------------------------------------------------------------------------
// Stripe webhooks. POST /webhook/stripe — body verified via Stripe-Signature.
// Updates users.current_tier in response to subscription state changes.
// ---------------------------------------------------------------------------
app.route('/webhook', webhook);

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
