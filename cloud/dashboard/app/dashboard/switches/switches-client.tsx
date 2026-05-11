// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { SwitchSummary } from "../../../lib/dendra-api";

type SortKey = "last_activity" | "switch_name" | "current_phase" | "total_verdicts";
type SortDir = "asc" | "desc";
const PAGE_SIZE = 50;

// Stable phase ordering so a "Phase" sort lines up with the SDK lifecycle.
const PHASE_ORDER: Record<string, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
  P3: 3,
  P4: 4,
  P5: 5,
};

const PHASE_LABELS: Record<string, string> = {
  P0: "RULE",
  P1: "MODEL_SHADOW",
  P2: "MODEL_PRIMARY",
  P3: "ML_SHADOW",
  P4: "ML_WITH_FALLBACK",
  P5: "ML_PRIMARY",
};

function compareSwitches(a: SwitchSummary, b: SwitchSummary, key: SortKey, dir: SortDir): number {
  let cmp = 0;
  if (key === "last_activity") {
    cmp = a.last_activity.localeCompare(b.last_activity);
  } else if (key === "switch_name") {
    cmp = a.switch_name.localeCompare(b.switch_name);
  } else if (key === "total_verdicts") {
    cmp = a.total_verdicts - b.total_verdicts;
  } else if (key === "current_phase") {
    const ai = a.current_phase ? (PHASE_ORDER[a.current_phase] ?? 99) : 100;
    const bi = b.current_phase ? (PHASE_ORDER[b.current_phase] ?? 99) : 100;
    cmp = ai - bi;
  }
  return dir === "asc" ? cmp : -cmp;
}

/**
 * 14-day verdict-per-day sparkline. Inline SVG, no chart-lib dep. Width is
 * fixed at 120; height 28. We use --accent for the path and --ground-soft
 * for the baseline so the sparkline reads on both the muted and standard
 * card backgrounds.
 */
function Sparkline({ data, label }: { data: number[]; label: string }) {
  const W = 120;
  const H = 28;
  const max = Math.max(1, ...data);
  if (data.length === 0) {
    return <span aria-hidden="true" style={{ display: "inline-block", width: W, height: H }} />;
  }
  const stepX = data.length > 1 ? W / (data.length - 1) : W;
  const points = data
    .map((n, i) => {
      const x = i * stepX;
      const y = H - (n / max) * H;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  // Area under the curve — we close back to baseline for a soft fill.
  const area = `M0,${H} L${points
    .split(" ")
    .map((p) => `L${p}`)
    .join(" ")
    .slice(1)} L${W},${H} Z`;
  const total = data.reduce((s, n) => s + n, 0);
  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${label}: ${total} verdicts over last 14 days`}
      style={{ display: "block" }}
    >
      <path d={area} fill="var(--accent-wash)" opacity={0.6} />
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PhaseBadge({ phase }: { phase: string | null }) {
  if (!phase) {
    return (
      <span
        className="font-mono"
        style={{ color: "var(--ink-soft)", fontSize: "var(--size-caption)" }}
      >
        —
      </span>
    );
  }
  const label = PHASE_LABELS[phase] ?? phase;
  // ML_PRIMARY graduations get the accent treatment; everything else stays muted.
  const isGraduated = phase === "P5";
  return (
    <span
      className="font-mono"
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        background: isGraduated ? "var(--accent-wash)" : "var(--ground-soft)",
        color: isGraduated ? "var(--accent-deep)" : "var(--ink-soft)",
        fontSize: "var(--size-micro)",
        letterSpacing: "0.04em",
      }}
    >
      {label}
    </span>
  );
}

function formatRelative(iso: string): string {
  const then = new Date(iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(then.getTime())) return iso;
  const diffSec = (Date.now() - then.getTime()) / 1000;
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 86400 * 30) return `${Math.floor(diffSec / 86400)}d ago`;
  return then.toISOString().slice(0, 10);
}

interface SwitchesClientProps {
  switches: SwitchSummary[];
  sparklineWindowDays: number;
  tier: string;
}

export default function SwitchesClient({
  switches,
  sparklineWindowDays,
  tier,
}: SwitchesClientProps) {
  const [sortKey, setSortKey] = useState<SortKey>("last_activity");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const copy = [...switches];
    copy.sort((a, b) => compareSwitches(a, b, sortKey, sortDir));
    return copy;
  }, [switches, sortKey, sortDir]);

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const visible = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function flip(k: SortKey) {
    if (k === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(k);
      // Sensible default direction per column: name asc, everything else desc.
      setSortDir(k === "switch_name" ? "asc" : "desc");
    }
    setPage(0);
  }

  if (switches.length === 0) {
    return (
      <div className="surface-card surface-card--muted mt-8">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          No switches yet
        </h2>
        <p className="prose-brand" style={{ margin: 0 }}>
          Wrap a call site with <code>@ml_switch</code> — it&apos;ll appear
          here once you record a verdict. The fastest path is to{" "}
          <Link
            href="/dashboard/keys"
            style={{
              color: "var(--ink)",
              textDecoration: "underline",
              textDecorationColor: "var(--accent)",
              textUnderlineOffset: "3px",
            }}
          >
            issue an API key
          </Link>{" "}
          and follow the <code>dendra init</code> walkthrough in your project.
        </p>
        <p
          className="mt-3"
          style={{
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
            margin: "var(--space-3) 0 0",
          }}
        >
          Your current plan: <span className="font-mono">{tier}</span>.
        </p>
      </div>
    );
  }

  const sortIndicator = (k: SortKey) =>
    sortKey === k ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="mt-8">
      <p
        className="prose-brand"
        style={{ color: "var(--ink-soft)", fontSize: "var(--size-caption)" }}
      >
        {sorted.length} switch{sorted.length === 1 ? "" : "es"}. Sparkline shows
        verdicts per day over the last {sparklineWindowDays} days.
      </p>

      <div
        className="surface-card mt-3"
        style={{ padding: 0, overflow: "hidden" }}
      >
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "var(--size-caption)",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--rule)",
                  background: "var(--ground-soft)",
                  textAlign: "left",
                }}
              >
                <SortHeader
                  label="Switch"
                  active={sortKey === "switch_name"}
                  indicator={sortIndicator("switch_name")}
                  onClick={() => flip("switch_name")}
                />
                <SortHeader
                  label="Phase"
                  active={sortKey === "current_phase"}
                  indicator={sortIndicator("current_phase")}
                  onClick={() => flip("current_phase")}
                />
                <SortHeader
                  label="Verdicts"
                  active={sortKey === "total_verdicts"}
                  indicator={sortIndicator("total_verdicts")}
                  align="right"
                  onClick={() => flip("total_verdicts")}
                />
                <SortHeader
                  label="Last activity"
                  active={sortKey === "last_activity"}
                  indicator={sortIndicator("last_activity")}
                  onClick={() => flip("last_activity")}
                />
                <th
                  scope="col"
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    color: "var(--ink-soft)",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    fontSize: "var(--size-micro)",
                    fontWeight: 500,
                  }}
                >
                  Trend (14d)
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr
                  key={s.switch_name}
                  style={{ borderBottom: "1px solid var(--rule)" }}
                >
                  <td
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    <Link
                      href={`/dashboard/switches/${encodeURIComponent(s.switch_name)}`}
                      style={{
                        color: "var(--ink)",
                        textDecoration: "underline",
                        textDecorationColor: "var(--accent)",
                        textUnderlineOffset: "3px",
                      }}
                    >
                      {s.switch_name}
                    </Link>
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                    <PhaseBadge phase={s.current_phase} />
                  </td>
                  <td
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      textAlign: "right",
                      fontVariantNumeric: "tabular-nums",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {s.total_verdicts.toLocaleString()}
                  </td>
                  <td
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      color: "var(--ink-soft)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--size-caption)",
                    }}
                    title={s.last_activity}
                  >
                    {formatRelative(s.last_activity)}
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                    <Sparkline data={s.sparkline} label={s.switch_name} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {pages > 1 && (
        <div
          className="mt-4"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          <span>
            Page {page + 1} of {pages} · showing {visible.length} of{" "}
            {sorted.length}
          </span>
          <span style={{ display: "flex", gap: "var(--space-2)" }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={page >= pages - 1}
              onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            >
              Next
            </button>
          </span>
        </div>
      )}
    </div>
  );
}

function SortHeader({
  label,
  active,
  indicator,
  onClick,
  align,
}: {
  label: string;
  active: boolean;
  indicator: string;
  onClick: () => void;
  align?: "right";
}) {
  return (
    <th
      scope="col"
      aria-sort={active ? "ascending" : "none"}
      style={{
        padding: 0,
        textAlign: align ?? "left",
      }}
    >
      <button
        type="button"
        onClick={onClick}
        style={{
          all: "unset",
          cursor: "pointer",
          display: "block",
          width: "100%",
          padding: "var(--space-3) var(--space-4)",
          color: active ? "var(--ink)" : "var(--ink-soft)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontSize: "var(--size-micro)",
          fontFamily: "var(--font-display)",
          fontWeight: 500,
          textAlign: align ?? "left",
        }}
      >
        {label}
        {indicator}
      </button>
    </th>
  );
}
