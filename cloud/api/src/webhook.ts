// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Stripe webhook receiver. Mounted at POST /webhook/stripe.
//
// Auth is via Stripe-Signature header verification (HMAC-SHA-256 with
// the shared whsec_… secret). Replay-safe: every mutating event we
// care about includes the Stripe event_id which we record in
// subscriptions.last_event_id; duplicate deliveries are no-ops.
//
// Events handled:
//   customer.subscription.created   → subscription row + users.current_tier upgrade
//   customer.subscription.updated   → status / period change, possibly tier change
//   customer.subscription.deleted   → set status='canceled', drop tier to 'free'
//
// Mapping Stripe price → Dendra tier: we look up the price's metadata.tier_id
// (set by scripts/sync-stripe-products.ts at price-creation time).

import { Hono } from 'hono';
import Stripe from 'stripe';
import type { ApiEnv, AuthContext } from './auth';

export interface WebhookEnv extends ApiEnv {
  STRIPE_SECRET_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
}

// Map Stripe price metadata tier_id (lookup_key id) → users.current_tier value.
const TIER_MAP: Record<string, AuthContext['tier']> = {
  hosted_pro: 'pro',
  hosted_scale: 'scale',
  hosted_business: 'business',
};

export const webhook = new Hono<{ Bindings: WebhookEnv }>();

webhook.post('/stripe', async (c) => {
  const sig = c.req.header('stripe-signature');
  if (!sig) return c.json({ error: 'missing_signature' }, 400);

  const raw = await c.req.text();
  const stripe = new Stripe(c.env.STRIPE_SECRET_KEY, {
    httpClient: Stripe.createFetchHttpClient(),
  });

  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      raw,
      sig,
      c.env.STRIPE_WEBHOOK_SECRET,
    );
  } catch (e) {
    console.error('webhook signature verification failed:', e);
    return c.json({ error: 'invalid_signature' }, 400);
  }

  console.log(`stripe webhook: ${event.type} (id=${event.id})`);

  switch (event.type) {
    case 'customer.subscription.created':
    case 'customer.subscription.updated':
    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription;
      await handleSubscriptionEvent(c.env.DB, stripe, event, sub);
      break;
    }
    default:
      // Stripe sends many events; we only care about subscription state.
      break;
  }

  return c.json({ received: true });
});

async function handleSubscriptionEvent(
  db: D1Database,
  stripe: Stripe,
  event: Stripe.Event,
  sub: Stripe.Subscription,
) {
  // Resolve the user via stripe_customer_id (set on first checkout).
  const customerId = typeof sub.customer === 'string' ? sub.customer : sub.customer.id;
  const userRow = await db
    .prepare(`SELECT id FROM users WHERE stripe_customer_id = ? LIMIT 1`)
    .bind(customerId)
    .first<{ id: number }>();

  if (!userRow) {
    console.warn(`subscription event for unknown customer ${customerId}`);
    return;
  }

  // Idempotency: if last_event_id already matches, skip.
  const existing = await db
    .prepare(
      `SELECT id, last_event_id FROM subscriptions WHERE stripe_subscription_id = ? LIMIT 1`,
    )
    .bind(sub.id)
    .first<{ id: number; last_event_id: string | null }>();
  if (existing?.last_event_id === event.id) {
    console.log(`webhook idempotent skip (event ${event.id} already applied)`);
    return;
  }

  // Determine the tier and period from the first item. Stripe API version
  // 2025+ moved current_period_{start,end} from the Subscription onto each
  // SubscriptionItem; we read item-level fields and treat the subscription
  // as having a single billing item (which our Pro/Scale/Business products do).
  const item = sub.items.data[0];
  const priceId = item?.price.id;
  let tier: AuthContext['tier'] = 'free';
  if (priceId) {
    const price = await stripe.prices.retrieve(priceId);
    const productLookup =
      price.lookup_key?.replace(/_monthly_usd$/, '') ?? price.metadata?.lookup_key;
    if (productLookup && TIER_MAP[productLookup]) {
      tier = TIER_MAP[productLookup]!;
    }
  }

  const status = sub.status;
  const isActive = status === 'active' || status === 'trialing';
  const effectiveTier = isActive ? tier : 'free';

  const periodStart = item?.current_period_start
    ? new Date(item.current_period_start * 1000).toISOString()
    : new Date().toISOString();
  const periodEnd = item?.current_period_end
    ? new Date(item.current_period_end * 1000).toISOString()
    : new Date().toISOString();

  await db
    .prepare(
      `INSERT INTO subscriptions
         (user_id, stripe_subscription_id, tier, status,
          current_period_start, current_period_end, last_event_id)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(stripe_subscription_id) DO UPDATE SET
         tier = excluded.tier,
         status = excluded.status,
         current_period_start = excluded.current_period_start,
         current_period_end = excluded.current_period_end,
         last_event_id = excluded.last_event_id,
         updated_at = datetime('now')`,
    )
    .bind(userRow.id, sub.id, tier, status, periodStart, periodEnd, event.id)
    .run();

  await db
    .prepare(`UPDATE users SET current_tier = ?, updated_at = datetime('now') WHERE id = ?`)
    .bind(effectiveTier, userRow.id)
    .run();

  console.log(
    `applied ${event.type} for user=${userRow.id} sub=${sub.id} tier=${effectiveTier}`,
  );
}
