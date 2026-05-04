// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";

interface PlanOption {
  tier_id: string;
  label: string;
  price: string;
  features: string;
}

const PLANS: PlanOption[] = [
  {
    tier_id: "hosted_pro",
    label: "Pro",
    price: "$99/mo",
    features: "250K classifications/mo, 30-day retention, audit-chain export.",
  },
  {
    tier_id: "hosted_scale",
    label: "Scale",
    price: "$399/mo",
    features: "5M classifications/mo, webhooks, SSO, priority email.",
  },
  {
    tier_id: "hosted_business",
    label: "Business",
    price: "$1,499/mo",
    features: "25M classifications/mo, SOC 2, 99.9% SLA, BAA available.",
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

      <section>
        <h2 className="text-lg font-medium">Available plans</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-3">
          {PLANS.map((p) => {
            const isCurrent =
              (p.tier_id === "hosted_pro" && currentTier === "pro") ||
              (p.tier_id === "hosted_scale" && currentTier === "scale") ||
              (p.tier_id === "hosted_business" && currentTier === "business");
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
