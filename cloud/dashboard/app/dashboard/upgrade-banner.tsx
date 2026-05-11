// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// A7 earned-upgrade banner — surfaces once a Free-tier account has used
// >= 80% of their monthly cap. Dismissable per-account-per-period via
// localStorage so it doesn't nag after one acknowledgement.
//
// Per the 2026-05-08 Q8 decision, this is the ONLY launch channel for
// the earned-upgrade nudge (no email at v1.0). Banner-only keeps the
// surface honest: it appears precisely where someone is using the
// product, and goes away the moment they say "got it".
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Props {
  /** "free" | "pro" | "scale" | "business" — banner only shows for free. */
  tier: string;
  /** Verdicts the user has spent this billing period. */
  used: number;
  /** Monthly cap; null = unlimited (no banner). */
  cap: number | null;
  /** "YYYY-MM" key for localStorage so dismissals don't leak across months. */
  periodKey: string;
}

const THRESHOLD = 0.8; // 80% of cap → banner surfaces

export default function UpgradeBanner({ tier, used, cap, periodKey }: Props) {
  // Hydration-safe: start hidden, then reveal once we know whether the
  // user has already dismissed this period. Avoids a flash-of-banner.
  const [ready, setReady] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const storageKey = `dendra:upgrade-banner-dismissed:${periodKey}`;

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(storageKey) === "1");
    } catch {
      // localStorage can throw in private-mode Safari etc; treat as not-dismissed.
    }
    setReady(true);
  }, [storageKey]);

  if (!ready || dismissed) return null;
  if (tier !== "free" || cap == null || cap <= 0) return null;
  if (used / cap < THRESHOLD) return null;

  function dismiss() {
    try {
      localStorage.setItem(storageKey, "1");
    } catch {
      // Best-effort; if write fails, the banner just reappears on next visit.
    }
    setDismissed(true);
  }

  // Number formatting — tabular nums for the count, comma-grouped for
  // legibility ("8,243 of your 10,000").
  const usedFmt = used.toLocaleString("en-US");
  const capFmt = cap.toLocaleString("en-US");

  return (
    <section
      className="surface-card"
      style={{
        borderColor: "color-mix(in oklab, var(--accent) 45%, var(--rule))",
        background: "color-mix(in oklab, var(--accent-wash) 60%, var(--ground))",
        padding: "var(--space-5)",
      }}
    >
      <div
        style={{
          display: "flex",
          gap: "var(--space-4)",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: "1 1 24rem", minWidth: 0 }}>
          <p
            className="eyebrow eyebrow--accent"
            style={{ margin: 0 }}
          >
            You&apos;re close to the Free cap
          </p>
          <p
            className="mt-2"
            style={{
              color: "var(--ink)",
              fontSize: "var(--size-body)",
              lineHeight: "var(--lh-body)",
              margin: 0,
            }}
          >
            You&apos;ve used{" "}
            <span
              className="font-mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {usedFmt}
            </span>{" "}
            of your{" "}
            <span
              className="font-mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {capFmt}
            </span>{" "}
            free verdicts this month. Pro is 25× the volume, the
            cohort-tuned BYOK judge orchestration layer, and audit-chain
            export.
          </p>
        </div>
        <div
          style={{
            display: "flex",
            gap: "var(--space-2)",
            flexShrink: 0,
            alignItems: "center",
          }}
        >
          <Link href="/dashboard/billing" className="btn btn-primary">
            See plans
          </Link>
          <button
            type="button"
            onClick={dismiss}
            className="btn btn-secondary"
            aria-label="Dismiss upgrade banner"
          >
            Dismiss
          </button>
        </div>
      </div>
    </section>
  );
}
