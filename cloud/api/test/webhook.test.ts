// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Stripe webhook receiver tests. Uses Stripe.webhooks.generateTestHeaderString
// to sign synthetic events with the same whsec_… that the Worker is
// configured with, exercising the constructEventAsync verification path.

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import Stripe from 'stripe';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
const WEBHOOK_SECRET = 'whsec_dummy'; // pragma: allowlist secret
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

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
});

/** Build a signed Stripe webhook request matching the configured whsec_. */
async function signedRequest(payloadObj: object, secret = WEBHOOK_SECRET): Promise<RequestInit> {
  const payload = JSON.stringify(payloadObj);
  const stripe = new Stripe('sk_test_dummy', {
    httpClient: Stripe.createFetchHttpClient(),
  });
  // Async variant: SubtleCrypto-backed signing in Workers context.
  const header = await stripe.webhooks.generateTestHeaderStringAsync({
    payload,
    secret,
    timestamp: Math.floor(Date.now() / 1000),
  });
  return {
    method: 'POST',
    headers: { 'stripe-signature': header, 'Content-Type': 'application/json' },
    body: payload,
  };
}

describe('webhook /webhook/stripe', () => {
  let userId: number;

  beforeAll(async () => {
    // Create a user and link a stripe_customer_id directly. In production,
    // the Checkout flow writes stripe_customer_id at first-checkout time.
    const u = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({
        clerk_user_id: 'wh_user',
        email: 'wh@example.com',
      }),
    });
    userId = (await u.json<{ user_id: number }>()).user_id;
    await env.DB.prepare(`UPDATE users SET stripe_customer_id = ? WHERE id = ?`)
      .bind('cus_test_001', userId)
      .run();
  });

  it('rejects requests without stripe-signature', async () => {
    const res = await SELF.fetch(`${BASE}/webhook/stripe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    expect(res.status).toBe(400);
  });

  it('rejects requests with bad signature', async () => {
    const res = await SELF.fetch(`${BASE}/webhook/stripe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'stripe-signature': 'bogus' },
      body: '{}',
    });
    expect(res.status).toBe(400);
  });

  it('ignores unrelated events with 200', async () => {
    const event = {
      id: 'evt_test_1',
      object: 'event',
      type: 'invoice.paid',
      data: { object: {} },
    };
    const res = await SELF.fetch(`${BASE}/webhook/stripe`, await signedRequest(event));
    expect(res.status).toBe(200);
  });

  it('customer.subscription.created with unknown customer is a no-op (not an error)', async () => {
    const event = {
      id: 'evt_test_unknown_cust',
      object: 'event',
      type: 'customer.subscription.created',
      data: {
        object: {
          id: 'sub_x',
          object: 'subscription',
          customer: 'cus_does_not_exist',
          status: 'active',
          items: { data: [] },
        },
      },
    };
    const res = await SELF.fetch(`${BASE}/webhook/stripe`, await signedRequest(event));
    expect(res.status).toBe(200);
    // Should NOT have created a subscriptions row.
    const row = await env.DB.prepare(
      `SELECT id FROM subscriptions WHERE stripe_subscription_id = ?`,
    )
      .bind('sub_x')
      .first();
    expect(row).toBeNull();
  });

  // Note: full-fidelity testing of the create/update path would require
  // mocking stripe.prices.retrieve, which the SDK doesn't expose a clean
  // hook for. We test that hook indirectly via integration when hitting
  // the staging Stripe API; the signature-verification + customer-resolution
  // logic above is the testable surface from in-process unit tests.
});
