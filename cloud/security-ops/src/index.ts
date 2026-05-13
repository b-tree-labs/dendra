// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Dendra security-ops Worker — entry point.
//
// Three exports:
//
//   - `email`     — invoked by Cloudflare Email Routing on every
//                   inbound mail to security@b-treeventures.com.
//   - `scheduled` — invoked by the cron trigger configured in
//                   wrangler.toml ("0 9 * * *" — daily 09:00 UTC).
//   - `fetch`     — a tiny /health probe so smoke tests can reach
//                   the Worker over HTTP. No /v1/* surface; this
//                   Worker is not customer-facing.
//
// Each handler is implemented in its own module; this file is the
// wiring layer that the runtime calls.

import type { Env } from './env';
import { handleInboundEmail, type InboundMessage } from './email-handler';
import { runScheduled } from './cron-handler';

export default {
  /** Inbound email — Cloudflare Email Routing route → this Worker. */
  async email(message: InboundMessage, env: Env, ctx: ExecutionContext): Promise<void> {
    // Workers Email handlers are short-lived; waitUntil keeps the
    // forwarding + side effects alive past the synchronous return.
    ctx.waitUntil(handleInboundEmail(message, env));
  },

  /** Daily 09:00 UTC cron. */
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runScheduled(env));
  },

  /** Liveness probe + 404 default. Worker has no public surface. */
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/health') {
      return new Response(
        JSON.stringify({
          status: 'ok',
          service: 'dendra-security-ops',
          environment: env.ENVIRONMENT,
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: { 'content-type': 'application/json; charset=utf-8' },
        },
      );
    }
    return new Response(
      JSON.stringify({ error: 'not_found', path: url.pathname }),
      {
        status: 404,
        headers: { 'content-type': 'application/json; charset=utf-8' },
      },
    );
  },
};
