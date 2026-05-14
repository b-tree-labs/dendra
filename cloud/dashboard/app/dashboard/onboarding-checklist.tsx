// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// M5 onboarding checklist — shown until all three install steps are
// observed-complete, then collapses to a single "you're set up" line
// pointing at the surfaces a new user should explore next.
//
// Per the launch brief (M5), step-completion observation is simplified
// for v1.0:
//
//   Steps 1+2  ←  has the user issued any API key yet?
//                 (proves install + working credentials, since either
//                  `pip install postrule` + `postrule login` device-flow or
//                  manual /dashboard/keys issuance lands a key row)
//   Step 3     ←  has any verdict been emitted to this account?
//
// This is intentionally a "reasonable approximation" rather than a
// rigorous event-history correlation — the panel is for orientation,
// not for metering, so cheap is better than precise.
//
// Server-rendered initial-prop pattern means we don't flash any "loading"
// state on the dashboard root. The component is "use client" only so we
// can wire copy-to-clipboard on the command rows without a separate file.
"use client";

import { useState } from "react";
import Link from "next/link";

interface Props {
  hasApiKey: boolean;
  hasVerdict: boolean;
}

interface Step {
  n: number;
  label: string;
  command: string;
  done: boolean;
}

export default function OnboardingChecklist({
  hasApiKey,
  hasVerdict,
}: Props) {
  // For v1.0: steps 1 and 2 are gated on "has any key" together — see
  // the file-header rationale. We render them as separate rows so the
  // M5 brief's three-line layout still reads correctly.
  const steps: Step[] = [
    {
      n: 1,
      label: "Install the CLI",
      command: "pip install postrule",
      done: hasApiKey,
    },
    {
      n: 2,
      label: "Connect this account",
      command: "postrule login",
      done: hasApiKey,
    },
    {
      n: 3,
      label: "Analyze your first repo",
      command: "postrule analyze .",
      done: hasVerdict,
    },
  ];

  const allDone = steps.every((s) => s.done);

  // All-done state replaces the checklist outright.
  if (allDone) {
    return (
      <section className="surface-card" style={{ padding: "var(--space-5)" }}>
        <p
          className="eyebrow eyebrow--accent"
          style={{ margin: 0 }}
        >
          You&apos;re set up
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
          Open a report card from{" "}
          <Link
            href="/dashboard/switches"
            style={{
              color: "var(--ink)",
              textDecoration: "underline",
              textDecorationColor: "var(--accent)",
              textUnderlineOffset: "3px",
            }}
          >
            Switches
          </Link>
          , or enroll in{" "}
          <Link
            href="/dashboard/insights"
            style={{
              color: "var(--ink)",
              textDecoration: "underline",
              textDecorationColor: "var(--accent)",
              textUnderlineOffset: "3px",
            }}
          >
            cohort tuned-defaults
          </Link>
          .
        </p>
      </section>
    );
  }

  return (
    <section className="surface-card" style={{ padding: "var(--space-5)" }}>
      <p
        className="eyebrow eyebrow--accent"
        style={{ margin: 0 }}
      >
        Get started
      </p>
      <ol
        style={{
          marginTop: "var(--space-4)",
          marginBottom: 0,
          paddingLeft: 0,
          listStyle: "none",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-3)",
        }}
      >
        {steps.map((s) => (
          <ChecklistRow key={s.n} step={s} />
        ))}
      </ol>
    </section>
  );
}

function ChecklistRow({ step }: { step: Step }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(step.command);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      // No clipboard? Quietly fail — the command is selectable in the UI.
    }
  }

  return (
    <li
      style={{
        display: "flex",
        gap: "var(--space-3)",
        alignItems: "center",
        flexWrap: "wrap",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "1.25rem",
          height: "1.25rem",
          borderRadius: "999px",
          border: "1px solid var(--rule)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          background: step.done ? "var(--accent-deep)" : "transparent",
          color: step.done ? "var(--ground)" : "transparent",
          fontSize: "0.75rem",
          fontWeight: 600,
          lineHeight: 1,
        }}
      >
        {step.done ? "✓" : ""}
      </span>
      <span
        style={{
          color: step.done ? "var(--ink-soft)" : "var(--ink)",
          textDecoration: step.done ? "line-through" : "none",
          fontSize: "var(--size-body)",
        }}
      >
        {step.n}. {step.label}:
      </span>
      <code
        onClick={copy}
        title="Click to copy"
        style={{
          fontFamily: "var(--font-mono)",
          background: "var(--ground-soft)",
          padding: "0.15em 0.45em",
          borderRadius: "4px",
          fontSize: "0.95em",
          cursor: "pointer",
          userSelect: "all",
        }}
      >
        {step.command}
      </code>
      {copied && (
        <span
          aria-live="polite"
          style={{
            fontSize: "var(--size-caption)",
            color: "var(--accent-deep)",
          }}
        >
          Copied
        </span>
      )}
    </li>
  );
}
