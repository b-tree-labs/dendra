// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";
import type { InsightsStatus } from "../../../lib/postrule-api";

// One-line copy keyed off the cohort-size + enrollment state combo.
// Mirrors the "Empty/transition states" spec in the launch task brief:
//   - Not-enrolled, cohort_size = 0: "You'll be one of the first."
//   - Not-enrolled, cohort_size > 0: "Join N other deployments."
//   - Enrolled                    : last-sync timestamp (rendered separately).
function ctaCopy(status: InsightsStatus): string {
  if (status.enrolled) return "";
  if (status.cohort_size === 0) return "You'll be one of the first.";
  return `Join ${status.cohort_size.toLocaleString()} other deployment${
    status.cohort_size === 1 ? "" : "s"
  }.`;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  // The api Worker stores SQLite datetime('now') as "YYYY-MM-DD HH:MM:SS"
  // (UTC, no tz suffix). Render as-is + the UTC indicator so the user
  // doesn't have to guess at the timezone — matches the keys page
  // rendering of `created_at` / `last_used_at` for consistency.
  return `${iso} UTC`;
}

export default function InsightsClient({ initial }: { initial: InsightsStatus }) {
  const [status, setStatus] = useState<InsightsStatus>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/insights", {
        method: status.enrolled ? "DELETE" : "POST",
      });
      if (!r.ok) {
        setError(`Toggle failed (${r.status}).`);
        return;
      }
      const next = (await r.json()) as InsightsStatus;
      setStatus(next);
    } catch {
      setError("Network error. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="surface-card mt-8 space-y-5">
      {/* --- Status block ----------------------------------------------- */}
      <div>
        <p
          className="eyebrow"
          style={{ marginBottom: "var(--space-1)" }}
        >
          Status
        </p>
        <p style={{ margin: 0, fontWeight: 500 }}>
          {status.enrolled ? "Enrolled" : "Not enrolled"}
        </p>
      </div>

      <div>
        <p
          className="eyebrow"
          style={{ marginBottom: "var(--space-1)" }}
        >
          Cohort size
        </p>
        <p style={{ margin: 0 }}>
          <span className="font-mono">{status.cohort_size.toLocaleString()}</span>{" "}
          deployment{status.cohort_size === 1 ? "" : "s"}
        </p>
      </div>

      {status.enrolled && (
        <div>
          <p
            className="eyebrow"
            style={{ marginBottom: "var(--space-1)" }}
          >
            Last sync
          </p>
          <p
            className="font-mono"
            style={{ margin: 0, fontSize: "var(--size-caption)" }}
          >
            {formatTimestamp(status.last_sync_at)}
          </p>
        </div>
      )}

      {/* --- Toggle + transition note ---------------------------------- */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="button"
          onClick={toggle}
          disabled={busy}
          className={status.enrolled ? "btn btn-secondary" : "btn btn-primary"}
        >
          {busy
            ? status.enrolled
              ? "Leaving…"
              : "Enrolling…"
            : status.enrolled
              ? "Leave cohort"
              : "Enroll"}
        </button>
        {!status.enrolled && (
          <p
            style={{
              margin: 0,
              fontSize: "var(--size-caption)",
              color: "var(--ink-soft)",
            }}
          >
            {ctaCopy(status)}
          </p>
        )}
      </div>

      {error && (
        <div className="surface-card surface-card--error">
          <p style={{ margin: 0, fontSize: "var(--size-caption)" }}>{error}</p>
        </div>
      )}
    </section>
  );
}
