"use client";

// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Client-side state machine for /cli-auth. Renders one of:
//
//   "form"      — user hasn't typed (or pasted from the URL) a code yet
//   "loading"   — looking up the session on the server
//   "confirm"   — pending session found; show device name + buttons
//   "expired"   — session expired (15-min TTL elapsed)
//   "denied"    — already denied (this user or a previous attempt)
//   "consumed"  — already-redeemed key — usually a duplicate Authorize
//   "authorized"— already authorized; CLI may not have polled yet
//   "success-authorize" — user just clicked Authorize successfully
//   "success-deny"      — user just clicked Deny
//   "error"     — unexpected error; show retry

import { useEffect, useState, useCallback } from "react";

type ServerSessionState =
  | "pending"
  | "authorized"
  | "denied"
  | "consumed"
  | "expired";

interface SessionData {
  user_code: string;
  state: ServerSessionState;
  device_name: string | null;
  created_at: string;
  expires_at: string;
  authorized_at: string | null;
}

type View =
  | { kind: "form" }
  | { kind: "loading" }
  | { kind: "confirm"; data: SessionData }
  | { kind: "expired"; userCode: string }
  | { kind: "denied"; userCode: string }
  | { kind: "consumed"; userCode: string }
  | { kind: "authorized"; userCode: string }
  | { kind: "success-authorize" }
  | { kind: "success-deny" }
  | { kind: "error"; message: string };

const USER_CODE_RE = /^[A-HJ-NP-Z2-9]{4}-?[A-HJ-NP-Z2-9]{4}$/;

function normalize(raw: string): string {
  const s = raw.trim().toUpperCase().replace(/\s+/g, "").replace(/-/g, "");
  if (s.length !== 8) return raw.toUpperCase().trim();
  return `${s.slice(0, 4)}-${s.slice(4)}`;
}

export default function CliAuthClient({ initialCode }: { initialCode: string }) {
  const [code, setCode] = useState(normalize(initialCode));
  const [view, setView] = useState<View>(
    initialCode ? { kind: "loading" } : { kind: "form" },
  );
  const [submitting, setSubmitting] = useState(false);

  const lookup = useCallback(async (userCode: string) => {
    setView({ kind: "loading" });
    try {
      const res = await fetch(
        `/api/cli-auth?user_code=${encodeURIComponent(userCode)}`,
        { cache: "no-store" },
      );
      if (res.status === 404) {
        setView({
          kind: "error",
          message:
            "We couldn't find a CLI session with that code. Double-check the terminal output and try again.",
        });
        return;
      }
      if (!res.ok) {
        setView({
          kind: "error",
          message: `Lookup failed (HTTP ${res.status}). Try again, or restart \`dendra login\`.`,
        });
        return;
      }
      const data = (await res.json()) as SessionData;
      switch (data.state) {
        case "pending":
          setView({ kind: "confirm", data });
          return;
        case "authorized":
          setView({ kind: "authorized", userCode });
          return;
        case "denied":
          setView({ kind: "denied", userCode });
          return;
        case "consumed":
          setView({ kind: "consumed", userCode });
          return;
        case "expired":
          setView({ kind: "expired", userCode });
          return;
        default:
          setView({ kind: "error", message: "Unknown session state." });
      }
    } catch (e) {
      setView({
        kind: "error",
        message: "Network error. Check your connection and try again.",
      });
    }
  }, []);

  // Auto-look-up if the URL pre-filled a code.
  useEffect(() => {
    if (initialCode) {
      const normalized = normalize(initialCode);
      if (USER_CODE_RE.test(normalized)) {
        lookup(normalized);
      } else {
        setView({ kind: "form" });
      }
    }
  }, [initialCode, lookup]);

  const submitForm = (e: React.FormEvent) => {
    e.preventDefault();
    const normalized = normalize(code);
    if (!USER_CODE_RE.test(normalized)) {
      setView({
        kind: "error",
        message:
          "Enter the 8-character code from your terminal (e.g. ABCD-2345).",
      });
      return;
    }
    setCode(normalized);
    lookup(normalized);
  };

  const decide = async (action: "authorize" | "deny") => {
    if (view.kind !== "confirm") return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/cli-auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_code: view.data.user_code, action }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        if (res.status === 410 || body.error === "expired") {
          setView({ kind: "expired", userCode: view.data.user_code });
          return;
        }
        setView({
          kind: "error",
          message: `Could not ${action} the session: ${body.error ?? `HTTP ${res.status}`}.`,
        });
        return;
      }
      setView({
        kind: action === "authorize" ? "success-authorize" : "success-deny",
      });
    } catch {
      setView({
        kind: "error",
        message: "Network error. Try again.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // ─── views ────────────────────────────────────────────────────────────

  if (view.kind === "form") {
    return (
      <form onSubmit={submitForm} className="mt-8 space-y-4">
        <label className="block text-sm font-medium text-neutral-700">
          Code from your terminal
        </label>
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          autoFocus
          autoComplete="off"
          spellCheck={false}
          placeholder="ABCD-2345"
          className="w-full rounded-md border border-neutral-300 px-4 py-3 font-mono text-2xl tracking-widest uppercase focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
        />
        <button
          type="submit"
          className="rounded-md bg-black px-5 py-2 text-sm text-white hover:bg-neutral-800"
        >
          Look up
        </button>
      </form>
    );
  }

  if (view.kind === "loading") {
    return (
      <div className="mt-8 rounded-md border border-neutral-200 bg-neutral-50 p-6">
        <p className="text-sm text-neutral-600">Looking up the session…</p>
      </div>
    );
  }

  if (view.kind === "confirm") {
    const expiresAt = new Date(view.data.expires_at + "Z");
    const minutesLeft = Math.max(
      0,
      Math.round((expiresAt.getTime() - Date.now()) / 60000),
    );
    return (
      <div className="mt-8 space-y-6 rounded-lg border border-neutral-200 p-6">
        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Code
          </p>
          <p className="mt-1 font-mono text-2xl tracking-widest">
            {view.data.user_code}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Device
          </p>
          <p className="mt-1 text-base">
            {view.data.device_name ?? (
              <span className="text-neutral-400">unnamed</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Expires
          </p>
          <p className="mt-1 text-base">
            in <span className="font-medium">{minutesLeft}</span>{" "}
            minute{minutesLeft === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={() => decide("authorize")}
            disabled={submitting}
            className="rounded-md bg-black px-5 py-2 text-sm text-white hover:bg-neutral-800 disabled:opacity-50"
          >
            {submitting ? "Authorizing…" : "Authorize"}
          </button>
          <button
            onClick={() => decide("deny")}
            disabled={submitting}
            className="rounded-md border border-neutral-300 px-5 py-2 text-sm hover:bg-neutral-50 disabled:opacity-50"
          >
            Deny
          </button>
        </div>

        <p className="pt-2 text-xs text-neutral-500">
          Only authorize if the device name + code matches what's shown in
          your terminal right now.
        </p>
      </div>
    );
  }

  if (view.kind === "success-authorize") {
    return (
      <div className="mt-8 rounded-lg border border-green-200 bg-green-50 p-6">
        <p className="text-base font-medium text-green-900">
          Authorized. You can close this tab.
        </p>
        <p className="mt-2 text-sm text-green-800">
          Your terminal will pick up the new credentials within a few
          seconds and continue running.
        </p>
      </div>
    );
  }

  if (view.kind === "success-deny") {
    return (
      <div className="mt-8 rounded-lg border border-neutral-200 bg-neutral-50 p-6">
        <p className="text-base font-medium">Denied.</p>
        <p className="mt-2 text-sm text-neutral-700">
          The CLI request was rejected. The terminal will report the error
          shortly. You can close this tab.
        </p>
      </div>
    );
  }

  if (view.kind === "expired") {
    return (
      <div className="mt-8 rounded-lg border border-amber-200 bg-amber-50 p-6">
        <p className="text-base font-medium text-amber-900">
          That code has expired.
        </p>
        <p className="mt-2 text-sm text-amber-800">
          Codes are valid for 15 minutes. Run <code className="rounded bg-amber-100 px-1">dendra login</code>{" "}
          again from your terminal to get a fresh one.
        </p>
      </div>
    );
  }

  if (view.kind === "denied") {
    return (
      <div className="mt-8 rounded-lg border border-neutral-200 bg-neutral-50 p-6">
        <p className="text-base font-medium">This session was already denied.</p>
        <p className="mt-2 text-sm text-neutral-700">
          Run <code className="rounded bg-neutral-100 px-1">dendra login</code>{" "}
          again from your terminal to start a new session.
        </p>
      </div>
    );
  }

  if (view.kind === "consumed") {
    return (
      <div className="mt-8 rounded-lg border border-neutral-200 bg-neutral-50 p-6">
        <p className="text-base font-medium">
          Already authorized and redeemed.
        </p>
        <p className="mt-2 text-sm text-neutral-700">
          The CLI already received its API key for this session. If your
          terminal still shows "Waiting for confirmation," restart it.
        </p>
      </div>
    );
  }

  if (view.kind === "authorized") {
    return (
      <div className="mt-8 rounded-lg border border-green-200 bg-green-50 p-6">
        <p className="text-base font-medium text-green-900">
          Already authorized.
        </p>
        <p className="mt-2 text-sm text-green-800">
          Your terminal should pick up the credentials within a few seconds.
        </p>
      </div>
    );
  }

  // view.kind === "error"
  return (
    <div className="mt-8 space-y-4">
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-base font-medium text-red-900">Something went wrong.</p>
        <p className="mt-2 text-sm text-red-800">{view.message}</p>
      </div>
      <button
        onClick={() => setView({ kind: "form" })}
        className="rounded-md border border-neutral-300 px-5 py-2 text-sm hover:bg-neutral-50"
      >
        Try a different code
      </button>
    </div>
  );
}
