// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Server-only Stripe client. Used by the dashboard's billing route
// handlers to create Checkout sessions and Customer Portal sessions.

import Stripe from "stripe";

const SECRET_KEY = process.env.STRIPE_SECRET_KEY;

let _stripe: Stripe | null = null;

export function stripe(): Stripe {
  if (typeof window !== "undefined") {
    throw new Error("stripe lib is server-only");
  }
  if (!SECRET_KEY) {
    throw new Error("STRIPE_SECRET_KEY env var is not set");
  }
  if (!_stripe) {
    _stripe = new Stripe(SECRET_KEY);
  }
  return _stripe;
}

/** Map Postrule tier id → STRIPE_PRICE_ID_<TIER> env var. */
export function priceIdForTier(tierId: string): string {
  const envName = `STRIPE_PRICE_ID_${tierId.toUpperCase()}`;
  const v = process.env[envName];
  if (!v) {
    throw new Error(`${envName} not configured (run scripts/sync-stripe-products.ts first)`);
  }
  return v;
}

/** Where Stripe redirects after Checkout success / cancel. */
export function checkoutReturnUrls(baseUrl: string) {
  return {
    success_url: `${baseUrl}/dashboard/billing?status=success&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${baseUrl}/dashboard/billing?status=canceled`,
  };
}
