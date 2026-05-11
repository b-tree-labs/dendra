// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";
import type { DendraPreferences } from "../../../lib/dendra-api";

// Mailto template for the manual self-serve account deletion flow
// (saas-launch-tech-spec-2026-05-02.md §Scope: "Self-serve account
// deletion (manual support email at first)"). When the support inbox
// receives this, the operator runs the deletion script and replies.
const DELETE_MAILTO =
  "mailto:support@b-treeventures.com?subject=Delete+account+request";

export default function SettingsClient({
  initial,
  clerkDisplayName,
}: {
  initial: DendraPreferences;
  clerkDisplayName: string | null;
}) {
  const [prefs, setPrefs] = useState<DendraPreferences>(initial);
  const [error, setError] = useState<string | null>(null);

  // Inline edit state for the display_name field.
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(
    initial.display_name ?? clerkDisplayName ?? "",
  );
  const [savingName, setSavingName] = useState(false);

  const [savingTelemetry, setSavingTelemetry] = useState(false);

  async function patch(
    body: { display_name?: string | null; telemetry_enabled?: boolean },
  ): Promise<boolean> {
    const r = await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      setError(`Save failed (${r.status}).`);
      return false;
    }
    const next = (await r.json()) as DendraPreferences;
    setPrefs(next);
    setError(null);
    return true;
  }

  async function saveName() {
    setSavingName(true);
    try {
      const trimmed = nameDraft.trim();
      // Empty string clears the display_name override (server treats
      // null as "fall back to the Clerk default").
      const ok = await patch({ display_name: trimmed.length === 0 ? null : trimmed });
      if (ok) setEditingName(false);
    } finally {
      setSavingName(false);
    }
  }

  function cancelName() {
    setNameDraft(prefs.display_name ?? clerkDisplayName ?? "");
    setEditingName(false);
    setError(null);
  }

  async function toggleTelemetry() {
    setSavingTelemetry(true);
    try {
      await patch({ telemetry_enabled: !prefs.telemetry_enabled });
    } finally {
      setSavingTelemetry(false);
    }
  }

  // Display name shown in the row: the server-side value, or — when the
  // user has never set a custom one — whatever Clerk had at sign-up.
  const effectiveName =
    prefs.display_name ?? clerkDisplayName ?? "(not set)";

  return (
    <div className="mt-8 space-y-6">
      {error && (
        <div className="surface-card surface-card--error">
          <p style={{ margin: 0, fontSize: "var(--size-caption)" }}>{error}</p>
        </div>
      )}

      {/* --- Profile ---------------------------------------------------- */}
      <section className="surface-card space-y-4">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            margin: 0,
          }}
        >
          Profile
        </h2>

        <div>
          <p className="eyebrow" style={{ marginBottom: "var(--space-1)" }}>
            Email
          </p>
          <p className="font-mono" style={{ margin: 0 }}>
            {prefs.email}
          </p>
          <p
            className="mt-1"
            style={{
              fontSize: "var(--size-caption)",
              color: "var(--ink-soft)",
              margin: 0,
            }}
          >
            Managed by your identity provider — change it in Clerk.
          </p>
        </div>

        <div>
          <p className="eyebrow" style={{ marginBottom: "var(--space-1)" }}>
            Display name
          </p>
          {editingName ? (
            <div className="flex flex-wrap items-center gap-3 mt-1">
              <input
                type="text"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="input-text"
                style={{ flex: 1, minWidth: "240px" }}
                placeholder={clerkDisplayName ?? "Your display name"}
                disabled={savingName}
                maxLength={64}
                autoFocus
              />
              <button
                type="button"
                onClick={saveName}
                disabled={savingName}
                className="btn btn-sm btn-primary"
              >
                {savingName ? "Saving…" : "Save"}
              </button>
              <button
                type="button"
                onClick={cancelName}
                disabled={savingName}
                className="btn btn-sm btn-secondary"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3 mt-1">
              <p style={{ margin: 0 }}>{effectiveName}</p>
              <button
                type="button"
                onClick={() => {
                  setNameDraft(prefs.display_name ?? clerkDisplayName ?? "");
                  setEditingName(true);
                }}
                className="btn btn-sm btn-secondary"
              >
                Edit
              </button>
            </div>
          )}
        </div>
      </section>

      {/* --- Telemetry --------------------------------------------------- */}
      <section className="surface-card space-y-3">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            margin: 0,
          }}
        >
          Telemetry
        </h2>

        <div className="flex items-start gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={prefs.telemetry_enabled}
            onClick={toggleTelemetry}
            disabled={savingTelemetry}
            className={
              prefs.telemetry_enabled ? "btn btn-sm btn-primary" : "btn btn-sm btn-secondary"
            }
          >
            {savingTelemetry
              ? "Saving…"
              : prefs.telemetry_enabled
                ? "On"
                : "Off"}
          </button>
          <p style={{ margin: 0 }}>
            Send count-only verdict telemetry to dendra.run.
          </p>
        </div>

        <p
          style={{
            margin: 0,
            fontSize: "var(--size-caption)",
            color: "var(--ink-soft)",
          }}
        >
          {prefs.telemetry_enabled
            ? "Currently ON — count-only verdict events flowing. Disable to stop emissions from new authenticated runs (existing data retained per privacy contract)."
            : "Currently OFF — Dendra is collecting nothing from your runs."}
        </p>
      </section>

      {/* --- Account ---------------------------------------------------- */}
      <section className="surface-card space-y-3">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            margin: 0,
          }}
        >
          Account
        </h2>

        <a href={DELETE_MAILTO} className="btn btn-danger btn-sm inline-flex">
          Delete account
        </a>

        <p
          style={{
            margin: 0,
            fontSize: "var(--size-caption)",
            color: "var(--ink-soft)",
          }}
        >
          We process deletion requests within 5 business days. Your verdict
          history and audit chain are removed; cohort contributions are
          retained anonymously.
        </p>
      </section>
    </div>
  );
}
