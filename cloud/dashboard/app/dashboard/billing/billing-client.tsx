// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";

interface PlanOption {
  tier_id: string;
  label: string;
  price: string;
  features: string;
  upgrade_summary: string;
}

// Tier ids here mirror landing/data/pricing-tiers.json `id` fields. The
// Stripe-coupling layer (cloud/api/src/webhook.ts TIER_MAP,
// cloud/dashboard/lib/stripe.ts priceIdForTier, wrangler.toml
// STRIPE_PRICE_ID_<TIER>) keys off these same tier ids; rename here only
// in lockstep with those. Per the 2026-05-11 pricing restructure, the
// metering unit is "Verdicts / mo" — a verdict is one classification
// Dendra logs to your account; it feeds your report card and the cohort.
const PLANS: PlanOption[] = [
  {
    tier_id: "pro",
    label: "Pro",
    price: "$99/mo",
    features:
      "250K verdicts/mo, cohort-tuned BYOK judge orchestration, audit-chain export, unlimited dashboard users, 30-day retention, priority email support.",
    upgrade_summary:
      "Adds the BYOK judge orchestration layer (cohort-tuned prompts + audit-chain export) on top of Free, with 25× the verdict cap and unlimited dashboard users.",
  },
  {
    tier_id: "scale",
    label: "Scale",
    price: "$399/mo",
    features:
      "5M verdicts/mo, everything in Pro, plus webhooks, SSO, 90-day retention, priority email.",
    upgrade_summary:
      "Adds webhooks, SSO, and 90-day retention to Pro, with 20× the verdict cap for high-volume ML platforms.",
  },
  {
    tier_id: "business",
    label: "Business",
    price: "$1,499/mo",
    features:
      "25M verdicts/mo, everything in Scale, plus SOC 2, 99.9% SLA, BAA available, dedicated Slack.",
    upgrade_summary:
      "Adds SOC 2, 99.9% SLA, BAA, and dedicated Slack to Scale, with a 5× verdict cap for regulated workloads.",
  },
];

export default function BillingClient({
  currentTier,
  returnStatus,
}: {
  currentTier: string;
  returnStatus: string | null;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout(tier_id: string) {
    setBusy(tier_id);
    setError(null);
    try {
      const r = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier_id }),
      });
      const body = (await r.json()) as { url?: string; error?: string };
      if (!r.ok || !body.url) {
        setError(body.error ?? `Checkout failed (${r.status})`);
        return;
      }
      window.location.href = body.url;
    } finally {
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setError(null);
    try {
      const r = await fetch("/api/billing/portal", { method: "POST" });
      const body = (await r.json()) as { url?: string; error?: string; message?: string };
      if (!r.ok || !body.url) {
        setError(body.message ?? body.error ?? `Portal failed (${r.status})`);
        return;
      }
      window.location.href = body.url;
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-8 space-y-6">
      {returnStatus === "success" && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          Subscription started. It may take a few seconds for your plan to update — refresh
          the page if your tier still says &quot;free&quot;.
        </div>
      )}
      {returnStatus === "canceled" && (
        <div className="rounded-md border border-neutral-300 bg-neutral-50 p-3 text-sm text-neutral-700">
          Checkout canceled.
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <p className="text-sm text-neutral-600">
        Metered on <span className="font-medium">Verdicts / mo</span>. A verdict is one
        classification Dendra logs to your account — feeds your report card and the cohort.
      </p>

      <section>
        <h2 className="text-lg font-medium">Available plans</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => {
            const isCurrent = p.tier_id === currentTier;
            return (
              <div
                key={p.tier_id}
                className="rounded-lg border border-neutral-200 p-5 text-sm"
              >
                <div className="flex items-baseline justify-between">
                  <h3 className="text-lg font-medium">{p.label}</h3>
                  <span className="text-neutral-700">{p.price}</span>
                </div>
                <p className="mt-2 text-neutral-600">{p.features}</p>
                <p className="mt-3 text-xs text-neutral-500">
                  <span className="font-medium text-neutral-700">What you get:</span>{" "}
                  {p.upgrade_summary}
                </p>
                <button
                  type="button"
                  onClick={() => startCheckout(p.tier_id)}
                  disabled={busy !== null || isCurrent}
                  className="mt-4 w-full rounded-md bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
                >
                  {isCurrent
                    ? "Current plan"
                    : busy === p.tier_id
                      ? "Redirecting…"
                      : "Subscribe"}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">Manage subscription</h2>
        <p className="mt-2 text-sm text-neutral-600">
          Update payment method, change plan, view invoices, or cancel via Stripe&apos;s
          hosted portal.
        </p>
        <button
          type="button"
          onClick={openPortal}
          disabled={busy !== null}
          className="mt-4 rounded-md border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-50 disabled:opacity-50"
        >
          {busy === "portal" ? "Opening…" : "Open billing portal"}
        </button>
      </section>
    </div>
  );
}
