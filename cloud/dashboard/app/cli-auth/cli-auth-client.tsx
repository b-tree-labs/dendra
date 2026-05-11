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
    } catch {
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
        <label
          className="block"
          style={{
            fontSize: "var(--size-caption)",
            color: "var(--ink-soft)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
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
          className="input-text input-code"
          style={{ fontSize: "1.5rem", textAlign: "center" }}
        />
        <button type="submit" className="btn btn-primary">
          Look up
        </button>
      </form>
    );
  }

  if (view.kind === "loading") {
    return (
      <div className="mt-8 surface-card surface-card--muted">
        <p
          style={{
            margin: 0,
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          Looking up the session…
        </p>
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
      <div className="mt-8 surface-card space-y-5">
        <DataRow label="Code">
          <span className="font-mono" style={{ fontSize: "1.5rem", letterSpacing: "0.18em" }}>
            {view.data.user_code}
          </span>
        </DataRow>
        <DataRow label="Device">
          {view.data.device_name ?? (
            <span style={{ color: "var(--ink-soft)" }}>unnamed</span>
          )}
        </DataRow>
        <DataRow label="Expires">
          in <span style={{ fontWeight: 500 }}>{minutesLeft}</span>{" "}
          minute{minutesLeft === 1 ? "" : "s"}
        </DataRow>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={() => decide("authorize")}
            disabled={submitting}
            className="btn btn-primary"
          >
            {submitting ? "Authorizing…" : "Authorize"}
          </button>
          <button
            onClick={() => decide("deny")}
            disabled={submitting}
            className="btn btn-secondary"
          >
            Deny
          </button>
        </div>

        <p
          className="pt-2"
          style={{
            fontSize: "var(--size-caption)",
            color: "var(--ink-soft)",
            margin: 0,
          }}
        >
          Only authorize if the device name + code matches what&apos;s shown
          in your terminal right now.
        </p>
      </div>
    );
  }

  if (view.kind === "success-authorize") {
    return (
      <div className="mt-8 surface-card surface-card--success">
        <p style={{ fontWeight: 500, margin: 0 }}>
          Authorized. You can close this tab.
        </p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          Your terminal will pick up the new credentials within a few seconds
          and continue running.
        </p>
      </div>
    );
  }

  if (view.kind === "success-deny") {
    return (
      <div className="mt-8 surface-card surface-card--muted">
        <p style={{ fontWeight: 500, margin: 0 }}>Denied.</p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          The CLI request was rejected. The terminal will report the error
          shortly. You can close this tab.
        </p>
      </div>
    );
  }

  if (view.kind === "expired") {
    return (
      <div className="mt-8 surface-card surface-card--muted">
        <p style={{ fontWeight: 500, margin: 0 }}>That code has expired.</p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          Codes are valid for 15 minutes. Run{" "}
          <code
            className="font-mono"
            style={{
              background: "var(--ground)",
              padding: "0.1em 0.35em",
              borderRadius: "4px",
            }}
          >
            dendra login
          </code>{" "}
          again from your terminal to get a fresh one.
        </p>
      </div>
    );
  }

  if (view.kind === "denied") {
    return (
      <div className="mt-8 surface-card surface-card--muted">
        <p style={{ fontWeight: 500, margin: 0 }}>
          This session was already denied.
        </p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          Run{" "}
          <code
            className="font-mono"
            style={{
              background: "var(--ground)",
              padding: "0.1em 0.35em",
              borderRadius: "4px",
            }}
          >
            dendra login
          </code>{" "}
          again from your terminal to start a new session.
        </p>
      </div>
    );
  }

  if (view.kind === "consumed") {
    return (
      <div className="mt-8 surface-card surface-card--muted">
        <p style={{ fontWeight: 500, margin: 0 }}>
          Already authorized and redeemed.
        </p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          The CLI already received its API key for this session. If your
          terminal still shows &quot;Waiting for confirmation,&quot; restart
          it.
        </p>
      </div>
    );
  }

  if (view.kind === "authorized") {
    return (
      <div className="mt-8 surface-card surface-card--success">
        <p style={{ fontWeight: 500, margin: 0 }}>Already authorized.</p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          Your terminal should pick up the credentials within a few seconds.
        </p>
      </div>
    );
  }

  // view.kind === "error"
  return (
    <div className="mt-8 space-y-4">
      <div className="surface-card surface-card--error">
        <p style={{ fontWeight: 500, margin: 0 }}>Something went wrong.</p>
        <p
          className="mt-2"
          style={{ margin: 0, fontSize: "var(--size-caption)" }}
        >
          {view.message}
        </p>
      </div>
      <button
        onClick={() => setView({ kind: "form" })}
        className="btn btn-secondary"
      >
        Try a different code
      </button>
    </div>
  );
}

function DataRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p
        className="eyebrow"
        style={{ marginBottom: "var(--space-1)" }}
      >
        {label}
      </p>
      <p style={{ margin: 0 }}>{children}</p>
    </div>
  );
}
