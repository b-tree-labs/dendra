// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";
import type { ApiKeyMeta, IssuedKey } from "../../../lib/postrule-api";

export default function KeysClient({ initialKeys }: { initialKeys: ApiKeyMeta[] }) {
  const [keys, setKeys] = useState<ApiKeyMeta[]>(initialKeys);
  const [newKeyName, setNewKeyName] = useState("");
  const [justIssued, setJustIssued] = useState<IssuedKey | null>(null);
  const [busy, setBusy] = useState<"create" | "revoke" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const r = await fetch("/api/keys", { cache: "no-store" });
    if (!r.ok) return;
    const body = (await r.json()) as { keys: ApiKeyMeta[] };
    setKeys(body.keys);
  }

  async function createKey() {
    setBusy("create");
    setError(null);
    try {
      const r = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName || null }),
      });
      if (!r.ok) {
        setError(`Create failed: ${r.status}`);
        return;
      }
      const issued = (await r.json()) as IssuedKey;
      setJustIssued(issued);
      setNewKeyName("");
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  async function revoke(id: number) {
    if (!confirm(`Revoke key #${id}? This cannot be undone.`)) return;
    setBusy("revoke");
    setError(null);
    try {
      const r = await fetch(`/api/keys/${id}`, { method: "DELETE" });
      if (!r.ok) {
        setError(`Revoke failed: ${r.status}`);
        return;
      }
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  const active = keys.filter((k) => !k.revoked_at);
  const revoked = keys.filter((k) => k.revoked_at);

  return (
    <div className="mt-8 space-y-6">
      {/* --- Just-issued plaintext, shown once ----------------------------- */}
      {justIssued && (
        <section className="surface-card surface-card--success">
          <h2
            style={{
              fontSize: "var(--size-h4)",
              lineHeight: "var(--lh-h4)",
              marginBottom: "var(--space-2)",
            }}
          >
            New key created
          </h2>
          <p
            style={{
              fontSize: "var(--size-caption)",
              color: "var(--ink)",
              marginBottom: "var(--space-3)",
            }}
          >
            Copy it now — you won&apos;t see the full value again.
          </p>
          <pre
            className="font-mono"
            style={{
              background: "var(--ground)",
              border: "var(--border)",
              borderRadius: "var(--radius)",
              padding: "var(--space-3) var(--space-4)",
              overflowX: "auto",
              fontSize: "0.875rem",
              margin: 0,
            }}
          >
            {justIssued.plaintext}
          </pre>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={() => navigator.clipboard.writeText(justIssued.plaintext)}
            >
              Copy to clipboard
            </button>
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={() => setJustIssued(null)}
            >
              I&apos;ve saved it, dismiss
            </button>
          </div>
        </section>
      )}

      {/* --- Create a new key ---------------------------------------------- */}
      <section className="surface-card">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Create a new key
        </h2>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="Name (optional, e.g. production)"
            aria-label="API key name (optional)"
            className="input-text"
            style={{ flex: 1, minWidth: "240px" }}
            disabled={busy !== null}
          />
          <button
            type="button"
            onClick={createKey}
            disabled={busy !== null}
            className="btn btn-primary"
          >
            {busy === "create" ? "Creating…" : "Create"}
          </button>
        </div>
      </section>

      {/* --- Active keys --------------------------------------------------- */}
      <section className="surface-card">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Active keys
        </h2>
        {active.length === 0 ? (
          <p
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-caption)",
              margin: 0,
            }}
          >
            No active keys yet. Create one above, or run{" "}
            <code
              style={{
                fontFamily: "var(--font-mono)",
                background: "var(--ground-soft)",
                padding: "0.1em 0.35em",
                borderRadius: "4px",
              }}
            >
              postrule login
            </code>{" "}
            in your terminal.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {active.map((k, i) => (
              <li
                key={k.id}
                className="flex items-center justify-between py-3"
                style={{
                  borderTop:
                    i === 0 ? "none" : "1px solid var(--rule)",
                  fontSize: "var(--size-caption)",
                }}
              >
                <div>
                  <div
                    className="font-mono"
                    style={{ color: "var(--ink)", fontSize: "0.9375rem" }}
                  >
                    prul_live_{k.key_prefix}…{k.key_suffix}
                  </div>
                  <div
                    className="mt-1"
                    style={{ color: "var(--ink-soft)" }}
                  >
                    {k.name ?? "(unnamed)"} · created {k.created_at}
                    {k.last_used_at ? ` · last used ${k.last_used_at}` : " · never used"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => revoke(k.id)}
                  disabled={busy !== null}
                  className="btn btn-sm btn-danger"
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* --- Revoked keys (audit history) --------------------------------- */}
      {revoked.length > 0 && (
        <section className="surface-card" style={{ opacity: 0.75 }}>
          <h2
            style={{
              fontSize: "var(--size-h4)",
              lineHeight: "var(--lh-h4)",
              marginBottom: "var(--space-3)",
            }}
          >
            Revoked
          </h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {revoked.map((k, i) => (
              <li
                key={k.id}
                style={{
                  padding: "var(--space-2) 0",
                  borderTop: i === 0 ? "none" : "1px solid var(--rule)",
                  fontSize: "var(--size-caption)",
                  color: "var(--ink-soft)",
                }}
              >
                <span className="font-mono">
                  prul_live_{k.key_prefix}…{k.key_suffix}
                </span>{" "}
                ({k.name ?? "unnamed"}) — revoked {k.revoked_at}
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <div className="surface-card surface-card--error">
          <p style={{ margin: 0, fontSize: "var(--size-caption)" }}>{error}</p>
        </div>
      )}
    </div>
  );
}
