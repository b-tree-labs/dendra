// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import { useState } from "react";
import type { ApiKeyMeta, IssuedKey } from "../../../lib/dendra-api";

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
    <div className="mt-8 space-y-8">
      {/* --- Just-issued plaintext, shown once ----------------------------- */}
      {justIssued && (
        <section className="rounded-lg border border-emerald-300 bg-emerald-50 p-6">
          <h2 className="text-lg font-medium text-emerald-900">New key created</h2>
          <p className="mt-1 text-sm text-emerald-900">
            Copy it now — you won&apos;t see the full value again.
          </p>
          <pre className="mt-3 overflow-x-auto rounded bg-white p-3 font-mono text-sm">
            {justIssued.plaintext}
          </pre>
          <button
            type="button"
            className="mt-3 text-sm font-medium text-emerald-900 underline"
            onClick={() => navigator.clipboard.writeText(justIssued.plaintext)}
          >
            Copy to clipboard
          </button>
          <button
            type="button"
            className="ml-4 mt-3 text-sm text-emerald-900 underline"
            onClick={() => setJustIssued(null)}
          >
            I&apos;ve saved it, dismiss
          </button>
        </section>
      )}

      {/* --- Create a new key ---------------------------------------------- */}
      <section className="rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">Create a new key</h2>
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="Name (optional, e.g. production)"
            className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm"
            disabled={busy !== null}
          />
          <button
            type="button"
            onClick={createKey}
            disabled={busy !== null}
            className="rounded-md bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {busy === "create" ? "Creating…" : "Create"}
          </button>
        </div>
      </section>

      {/* --- Active keys --------------------------------------------------- */}
      <section className="rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">Active keys</h2>
        {active.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-600">No active keys.</p>
        ) : (
          <ul className="mt-3 divide-y divide-neutral-200">
            {active.map((k) => (
              <li key={k.id} className="flex items-center justify-between py-3 text-sm">
                <div>
                  <div className="font-mono">
                    dndr_live_{k.key_prefix}…{k.key_suffix}
                  </div>
                  <div className="mt-1 text-neutral-600">
                    {k.name ?? "(unnamed)"} · created {k.created_at}
                    {k.last_used_at ? ` · last used ${k.last_used_at}` : " · never used"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => revoke(k.id)}
                  disabled={busy !== null}
                  className="rounded-md border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
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
        <section className="rounded-lg border border-neutral-200 p-6 opacity-75">
          <h2 className="text-lg font-medium">Revoked</h2>
          <ul className="mt-3 divide-y divide-neutral-200 text-sm">
            {revoked.map((k) => (
              <li key={k.id} className="py-2 text-neutral-600">
                <span className="font-mono">
                  dndr_live_{k.key_prefix}…{k.key_suffix}
                </span>{" "}
                ({k.name ?? "unnamed"}) — revoked {k.revoked_at}
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
