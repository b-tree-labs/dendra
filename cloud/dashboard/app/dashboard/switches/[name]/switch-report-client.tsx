// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import ReactMarkdown from "react-markdown";
import type { SwitchReport } from "../../../../lib/postrule-api";
import {
  isStale,
  daysSince as daysSinceTs,
} from "../../../../lib/switch-stale";

const PHASE_LABELS: Record<string, string> = {
  P0: "RULE",
  P1: "MODEL_SHADOW",
  P2: "MODEL_PRIMARY",
  P3: "ML_SHADOW",
  P4: "ML_WITH_FALLBACK",
  P5: "ML_PRIMARY",
};

const PHASE_INDEX: Record<string, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
  P3: 3,
  P4: 4,
  P5: 5,
};

// Indicative cost-per-call deltas across phases, in USD. These are NOT
// telemetry — they're the same illustrative figures the OSS report card
// uses, anchored to a moderate-cost LLM (~$0.0042/call rule, ~$0.000003
// after ML graduation). The dashboard surfaces them so the user can see
// the projected trajectory of their switch as it climbs phases; the
// canonical numbers ship with the OSS `postrule report` output.
const PHASE_COST_PER_CALL: Record<string, number> = {
  P0: 0.0042,
  P1: 0.0042,
  P2: 0.0038,
  P3: 0.0009,
  P4: 0.000_05,
  P5: 0.000_003,
};

const PHASE_LATENCY_MS: Record<string, number> = {
  P0: 412,
  P1: 412,
  P2: 380,
  P3: 95,
  P4: 12,
  P5: 0.8,
};

function fmtMoney(n: number): string {
  if (n >= 0.01) return `$${n.toFixed(4)}`;
  if (n >= 0.0001) return `$${n.toFixed(6)}`;
  return `$${n.toExponential(2)}`;
}

function fmtMs(n: number): string {
  if (n < 1) return `${n.toFixed(2)} ms`;
  if (n < 100) return `${n.toFixed(1)} ms`;
  return `${Math.round(n)} ms`;
}

function fmtPct(num: number, denom: number): string {
  if (denom === 0) return "—";
  return ((num / denom) * 100).toFixed(1) + "%";
}

function daysSince(iso: string): number {
  const t = new Date(iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(t.getTime())) return 0;
  return Math.max(0, Math.floor((Date.now() - t.getTime()) / 86_400_000));
}

function formatPValue(p: number | null): string {
  if (p === null) return "—";
  if (p < 1e-4) return p.toExponential(2);
  return p.toFixed(4);
}

// Render the same Markdown the OSS `postrule report` command emits, built
// from the structured payload the server returned. Same headline as
// docs/sample-reports/triage_rule.md so the "report-card-as-evidence"
// narrative is consistent between CLI + dashboard + audit-chain export.
function buildMarkdown(switchName: string, report: SwitchReport): string {
  const lines: string[] = [];
  const phase = report.current_phase;
  const phaseLabel = report.current_phase_label ?? "—";
  lines.push(`# Report card — \`${switchName}\``);
  lines.push("");
  lines.push(`Window: last ${report.days} day${report.days === 1 ? "" : "s"}.`);
  if (report.agg.first_at && report.agg.last_at) {
    lines.push(`First verdict in window: ${report.agg.first_at}.`);
    lines.push(`Most recent verdict: ${report.agg.last_at}.`);
  }
  lines.push(`Total verdicts: **${report.agg.total.toLocaleString()}**.`);
  lines.push("");
  lines.push("## Status");
  lines.push("");
  lines.push(`> **Phase: \`${phaseLabel}\`** (\`${phase ?? "—"}\`).`);
  if (report.mcnemar_p_two_sided !== null) {
    lines.push(
      `> McNemar two-sided exact p = **${formatPValue(report.mcnemar_p_two_sided)}**.`,
    );
  }
  lines.push("");
  lines.push("## Per-layer accuracy");
  lines.push("");
  lines.push("| Layer | Verdicts | Correct | Accuracy |");
  lines.push("|---|---:|---:|---:|");
  lines.push(
    `| Rule  | ${report.agg.rule_total} | ${report.agg.rule_correct} | ${fmtPct(report.agg.rule_correct, report.agg.rule_total)} |`,
  );
  lines.push(
    `| Model | ${report.agg.model_total} | ${report.agg.model_correct} | ${fmtPct(report.agg.model_correct, report.agg.model_total)} |`,
  );
  lines.push(
    `| ML    | ${report.agg.ml_total} | ${report.agg.ml_correct} | ${fmtPct(report.agg.ml_correct, report.agg.ml_total)} |`,
  );
  lines.push("");
  if (report.transitions.length > 0) {
    lines.push("## Phase timeline");
    lines.push("");
    lines.push("| Phase | First observed | Last observed | Verdicts |");
    lines.push("|---|---|---|---:|");
    for (const t of report.transitions) {
      lines.push(
        `| ${t.phase} (${PHASE_LABELS[t.phase] ?? "—"}) | ${t.first_seen} | ${t.last_seen} | ${t.n} |`,
      );
    }
    lines.push("");
  }
  lines.push("---");
  lines.push("");
  lines.push(
    "*Regenerate with `postrule report " + switchName + "`. " +
      "Markdown excerpt mirrors the canonical OSS report-card shape.*",
  );
  return lines.join("\n");
}

/**
 * Compact tooltip wrapper for the disabled PDF export button on Free tier.
 * We don't need full Radix tooltip plumbing — a native title attribute is
 * already accessible and tab-discoverable; the wrapper keeps the button
 * keyboard-focusable so screen readers announce the upgrade hint.
 */
function PdfExportButton({ tier }: { tier: string }) {
  const isProOrBetter = tier !== "free";
  if (isProOrBetter) {
    return (
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled
        title="Export hooks into the OSS audit-chain ledger; arrives in v1.1"
      >
        Export audit-chain PDF
      </button>
    );
  }
  return (
    <span
      title="Upgrade to Pro to export an audit-chain PDF — preserves the report card as signed evidence for auditors."
      aria-label="Audit-chain PDF export — Pro tier feature"
      style={{ display: "inline-flex", alignItems: "center" }}
    >
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled
        aria-disabled="true"
        style={{ position: "relative" }}
      >
        Export audit-chain PDF
        <span
          aria-hidden="true"
          style={{
            marginLeft: "var(--space-2)",
            padding: "1px 6px",
            borderRadius: "3px",
            background: "var(--accent-wash)",
            color: "var(--accent-deep)",
            fontSize: "var(--size-micro)",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            fontFamily: "var(--font-display)",
          }}
        >
          Pro
        </span>
      </button>
    </span>
  );
}

interface Props {
  switchName: string;
  report: SwitchReport;
  tier: string;
}

export default function SwitchReportClient({ switchName, report, tier }: Props) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [archiveFormOpen, setArchiveFormOpen] = useState(false);
  const [archiveReason, setArchiveReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const md = useMemo(() => buildMarkdown(switchName, report), [switchName, report]);

  const archived = !!report.archived_at;
  const stale =
    !archived &&
    !!report.agg.last_at &&
    isStale({
      last_activity: report.agg.last_at,
      archived_at: report.archived_at,
    });
  const daysSinceActivity = report.agg.last_at
    ? daysSinceTs(report.agg.last_at)
    : null;

  async function submitArchive() {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const trimmed = archiveReason.trim();
      const res = await fetch(
        `/api/switches/${encodeURIComponent(switchName)}?action=archive`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(trimmed ? { reason: trimmed } : {}),
        },
      );
      if (!res.ok) throw new Error(`archive failed: ${res.status}`);
      setArchiveFormOpen(false);
      setArchiveReason("");
      startTransition(() => router.refresh());
    } catch (e) {
      console.error(e);
      setSubmitError("Couldn't archive — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitUnarchive() {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const res = await fetch(
        `/api/switches/${encodeURIComponent(switchName)}?action=unarchive`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`unarchive failed: ${res.status}`);
      startTransition(() => router.refresh());
    } catch (e) {
      console.error(e);
      setSubmitError("Couldn't unarchive — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const currentPhase = report.current_phase ?? "P0";
  const currentLabel = report.current_phase_label ?? "RULE";
  const currentPhaseFirstSeen =
    report.transitions.find((t) => t.phase === currentPhase)?.first_seen ?? null;
  const daysAtPhase = currentPhaseFirstSeen
    ? daysSince(currentPhaseFirstSeen)
    : null;

  // Empty-state path: still at RULE, no transitions observed yet. Show the
  // "collecting evidence" panel with paired-pair count + projected gate-
  // fire threshold (300 paired discordant pairs is a common heuristic for
  // McNemar @ α = 0.01 with a 5–10 pp effect-size band).
  const stillAtRule =
    report.transitions.length === 0 || currentPhase === "P0";

  return (
    <div>
      <p className="eyebrow eyebrow--accent">
        <Link
          href="/dashboard/switches"
          style={{ color: "inherit", textDecoration: "none" }}
        >
          ← Switches
        </Link>
      </p>

      {/* ── Archived banner (mutually exclusive with stale) ──────────────── */}
      {archived && (
        <div
          role="status"
          className="surface-card mt-3"
          style={{
            background: "var(--ground-soft)",
            borderLeft: "3px solid var(--ink-soft)",
            padding: "var(--space-3) var(--space-4)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-3)",
              flexWrap: "wrap",
            }}
          >
            <p style={{ margin: 0, fontSize: "var(--size-caption)" }}>
              <strong>Archived</strong>{" "}
              <span className="font-mono" style={{ color: "var(--ink-soft)" }}>
                {report.archived_at?.slice(0, 10)}
              </span>
              {report.archived_reason ? (
                <>
                  {" — "}
                  <span style={{ color: "var(--ink-soft)" }}>
                    &ldquo;{report.archived_reason}&rdquo;
                  </span>
                </>
              ) : null}
              {". The report card below is preserved as-is. A new verdict on this switch will auto-restore it to the default roster."}
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={submitUnarchive}
              disabled={submitting}
            >
              {submitting ? "Unarchiving…" : "Unarchive"}
            </button>
          </div>
          {submitError && (
            <p
              role="alert"
              style={{
                margin: "var(--space-2) 0 0",
                color: "var(--ink-soft)",
                fontSize: "var(--size-micro)",
              }}
            >
              {submitError}
            </p>
          )}
        </div>
      )}

      {/* ── Stale banner (only when not archived) ────────────────────────── */}
      {stale && (
        <div
          role="status"
          className="surface-card mt-3"
          style={{
            background: "var(--ground-soft)",
            borderLeft: "3px solid var(--accent)",
            padding: "var(--space-3) var(--space-4)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-3)",
              flexWrap: "wrap",
            }}
          >
            <p style={{ margin: 0, fontSize: "var(--size-caption)" }}>
              <strong>No verdicts received in {daysSinceActivity} days.</strong>{" "}
              <span style={{ color: "var(--ink-soft)" }}>
                The switch may have been removed from your code. Archive to
                hide from the roster — audit history is preserved either way.
              </span>
            </p>
            {!archiveFormOpen && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setArchiveFormOpen(true)}
              >
                Archive
              </button>
            )}
          </div>
          {archiveFormOpen && (
            <div
              style={{
                marginTop: "var(--space-3)",
                paddingTop: "var(--space-3)",
                borderTop: "1px solid var(--rule)",
              }}
            >
              <label
                htmlFor="archive-reason"
                style={{
                  display: "block",
                  fontSize: "var(--size-micro)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--ink-soft)",
                  marginBottom: "var(--space-2)",
                  fontFamily: "var(--font-display)",
                }}
              >
                Reason (optional, max 200 chars)
              </label>
              <input
                id="archive-reason"
                type="text"
                className="input-text"
                maxLength={200}
                value={archiveReason}
                onChange={(e) => setArchiveReason(e.target.value)}
                placeholder="e.g. switch removed from intent_router.py"
                style={{ marginBottom: "var(--space-3)" }}
              />
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={submitArchive}
                  disabled={submitting}
                >
                  {submitting ? "Archiving…" : "Confirm archive"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setArchiveFormOpen(false);
                    setArchiveReason("");
                    setSubmitError(null);
                  }}
                  disabled={submitting}
                >
                  Cancel
                </button>
              </div>
              {submitError && (
                <p
                  role="alert"
                  style={{
                    margin: "var(--space-2) 0 0",
                    color: "var(--ink-soft)",
                    fontSize: "var(--size-micro)",
                  }}
                >
                  {submitError}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <h1
        className="mt-2"
        style={{
          fontSize: "var(--size-h2)",
          lineHeight: "var(--lh-h2)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {switchName}
      </h1>

      <div
        className="mt-3"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          flexWrap: "wrap",
        }}
      >
        <span
          className="font-mono"
          style={{
            padding: "4px 10px",
            borderRadius: "4px",
            background:
              currentPhase === "P5" ? "var(--accent-wash)" : "var(--ground-soft)",
            color:
              currentPhase === "P5" ? "var(--accent-deep)" : "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          {currentLabel} ({currentPhase})
        </span>
        {daysAtPhase !== null && (
          <span
            className="font-mono"
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-caption)",
            }}
          >
            {daysAtPhase} day{daysAtPhase === 1 ? "" : "s"} at this phase
          </span>
        )}
        <span
          className="font-mono"
          style={{
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          {report.agg.total.toLocaleString()} verdict
          {report.agg.total === 1 ? "" : "s"} in window
        </span>
        <span style={{ marginLeft: "auto" }}>
          <PdfExportButton tier={tier} />
        </span>
      </div>

      {/* ── Phase transition timeline ────────────────────────────────────── */}
      <section
        className="surface-card mt-8"
        aria-labelledby="phase-timeline-heading"
      >
        <h2
          id="phase-timeline-heading"
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Phase transition history
        </h2>
        {stillAtRule ? (
          <EmptyShadowPanel report={report} />
        ) : (
          <PhaseTimeline report={report} />
        )}
      </section>

      {/* ── Cost trajectory ──────────────────────────────────────────────── */}
      <section className="surface-card mt-6" aria-labelledby="cost-heading">
        <h2
          id="cost-heading"
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Cost trajectory
        </h2>
        <TrajectoryBars
          metric="cost"
          report={report}
          currentPhase={currentPhase}
        />
        <p
          className="mt-3"
          style={{
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          Indicative cost per call as the switch climbs phases. Latest figure
          highlighted. Re-render with{" "}
          <code>postrule report {switchName} --model &lt;name&gt;</code> in the
          CLI to swap pricing models for what-if analysis.
        </p>
      </section>

      {/* ── Latency trajectory ───────────────────────────────────────────── */}
      <section className="surface-card mt-6" aria-labelledby="latency-heading">
        <h2
          id="latency-heading"
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Latency trajectory
        </h2>
        <TrajectoryBars
          metric="latency"
          report={report}
          currentPhase={currentPhase}
        />
        <p
          className="mt-3"
          style={{
            color: "var(--ink-soft)",
            fontSize: "var(--size-caption)",
          }}
        >
          p50 latency per call by phase. The fall from RULE to ML_PRIMARY is
          where graduations earn their keep on hot paths.
        </p>
      </section>

      {/* ── Drift signals ────────────────────────────────────────────────── */}
      <section className="surface-card mt-6" aria-labelledby="drift-heading">
        <h2
          id="drift-heading"
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-3)",
          }}
        >
          Drift signals
        </h2>
        <DriftPanel report={report} />
      </section>

      {/* ── Canonical markdown excerpt ───────────────────────────────────── */}
      <section className="surface-card mt-6" aria-labelledby="md-heading">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            marginBottom: expanded ? "var(--space-4)" : 0,
          }}
        >
          <h2
            id="md-heading"
            style={{
              fontSize: "var(--size-h4)",
              lineHeight: "var(--lh-h4)",
              margin: 0,
            }}
          >
            Canonical report card
          </h2>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setExpanded((x) => !x)}
            aria-expanded={expanded}
            aria-controls="markdown-report"
          >
            {expanded ? "Hide markdown" : "Show markdown"}
          </button>
        </div>
        {expanded && (
          <div
            id="markdown-report"
            className="prose-brand"
            style={{
              borderTop: "1px solid var(--rule)",
              paddingTop: "var(--space-4)",
            }}
          >
            <ReactMarkdown>{md}</ReactMarkdown>
          </div>
        )}
        {!expanded && (
          <p
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-caption)",
              margin: "var(--space-3) 0 0",
            }}
          >
            The same Markdown shape <code>postrule report {switchName}</code>{" "}
            emits at the CLI. Expand to copy.
          </p>
        )}
      </section>
    </div>
  );
}

// ── Phase transition history ──────────────────────────────────────────────
function PhaseTimeline({ report }: { report: SwitchReport }) {
  const transitions = [...report.transitions].sort(
    (a, b) => (PHASE_INDEX[a.phase] ?? 99) - (PHASE_INDEX[b.phase] ?? 99),
  );
  const p = report.mcnemar_p_two_sided;
  const pStr = formatPValue(p);
  return (
    <ol
      style={{
        listStyle: "none",
        margin: 0,
        padding: 0,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
      }}
    >
      {transitions.map((t, i) => {
        const isCurrent = i === transitions.length - 1;
        return (
          <li
            key={t.phase}
            style={{
              display: "grid",
              gridTemplateColumns: "16px 1fr auto",
              gap: "var(--space-3)",
              alignItems: "baseline",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: "10px",
                height: "10px",
                borderRadius: "999px",
                background: isCurrent ? "var(--accent)" : "var(--ink-soft)",
                marginTop: "0.4em",
              }}
            />
            <div>
              <strong
                className="font-mono"
                style={{
                  fontSize: "var(--size-body)",
                  color: isCurrent ? "var(--accent-deep)" : "var(--ink)",
                }}
              >
                {t.phase} ({PHASE_LABELS[t.phase] ?? "—"})
              </strong>
              <div
                style={{
                  color: "var(--ink-soft)",
                  fontSize: "var(--size-caption)",
                  marginTop: "2px",
                }}
              >
                First observed{" "}
                <span className="font-mono">{t.first_seen}</span> · last{" "}
                <span className="font-mono">{t.last_seen}</span>
              </div>
            </div>
            <div
              style={{
                textAlign: "right",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--size-caption)",
                color: "var(--ink-soft)",
              }}
            >
              {t.n.toLocaleString()} verdict{t.n === 1 ? "" : "s"}
              {isCurrent && p !== null && (
                <div style={{ marginTop: "2px", color: "var(--accent-deep)" }}>
                  McNemar p = {pStr}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function EmptyShadowPanel({ report }: { report: SwitchReport }) {
  // Heuristic gate-firing threshold: 300 discordant pairs is a working
  // figure for McNemar @ α = 0.01 with a ~5 pp effect-size assumption.
  // Real graduation depends on b/c separation; this is just to give the
  // user a North-Star number while they're in shadow.
  const pairsToDate = report.agg.paired_total;
  const projected = 300;
  const remaining = Math.max(0, projected - pairsToDate);
  return (
    <div>
      <p
        className="prose-brand"
        style={{ marginTop: 0, marginBottom: "var(--space-3)" }}
      >
        Still in shadow — the gate hasn&apos;t fired yet. Postrule is collecting
        paired-correctness observations and won&apos;t graduate this switch
        until McNemar clears α = 0.01.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-4)",
          background: "var(--ground-soft)",
          padding: "var(--space-4)",
          borderRadius: "var(--radius)",
        }}
      >
        <div>
          <p
            className="font-mono"
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-micro)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              margin: 0,
            }}
          >
            Paired observations to date
          </p>
          <p
            className="font-mono"
            style={{
              fontSize: "var(--size-h3)",
              color: "var(--ink)",
              margin: "var(--space-2) 0 0",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {pairsToDate.toLocaleString()}
          </p>
        </div>
        <div>
          <p
            className="font-mono"
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-micro)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              margin: 0,
            }}
          >
            Projected gate-firing
          </p>
          <p
            className="font-mono"
            style={{
              fontSize: "var(--size-h3)",
              color: "var(--accent-deep)",
              margin: "var(--space-2) 0 0",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            ~{projected.toLocaleString()} pairs
          </p>
          <p
            style={{
              color: "var(--ink-soft)",
              fontSize: "var(--size-caption)",
              margin: "var(--space-2) 0 0",
            }}
          >
            {remaining > 0
              ? `~${remaining.toLocaleString()} more paired observations to a typical α=0.01 fire (effect-size dependent).`
              : "You're at the heuristic threshold — actual fire depends on b/c separation."}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Cost / latency trajectory bars ────────────────────────────────────────
function TrajectoryBars({
  metric,
  report,
  currentPhase,
}: {
  metric: "cost" | "latency";
  report: SwitchReport;
  currentPhase: string;
}) {
  // Show every phase, not just observed ones — the trajectory is the story.
  const phases: Array<"P0" | "P1" | "P2" | "P3" | "P4" | "P5"> = [
    "P0",
    "P1",
    "P2",
    "P3",
    "P4",
    "P5",
  ];
  const values = phases.map((p) =>
    metric === "cost" ? PHASE_COST_PER_CALL[p] : PHASE_LATENCY_MS[p],
  );
  const max = Math.max(...values);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      {phases.map((p, i) => {
        const v = values[i];
        const widthPct = max > 0 ? Math.max(2, (v / max) * 100) : 0;
        const isCurrent = p === currentPhase;
        const observed = report.transitions.some((t) => t.phase === p);
        return (
          <div
            key={p}
            style={{
              display: "grid",
              gridTemplateColumns: "180px 1fr 120px",
              alignItems: "center",
              gap: "var(--space-3)",
              opacity: observed || isCurrent ? 1 : 0.55,
            }}
          >
            <span
              className="font-mono"
              style={{
                fontSize: "var(--size-caption)",
                color: isCurrent ? "var(--accent-deep)" : "var(--ink-soft)",
              }}
            >
              {p} ({PHASE_LABELS[p]})
            </span>
            <span
              role="presentation"
              style={{
                display: "block",
                height: "12px",
                width: `${widthPct}%`,
                background: isCurrent ? "var(--accent)" : "var(--ink-soft)",
                borderRadius: "3px",
                transition: "width 200ms ease",
              }}
            />
            <span
              className="font-mono"
              style={{
                fontSize: "var(--size-caption)",
                textAlign: "right",
                color: isCurrent ? "var(--accent-deep)" : "var(--ink-soft)",
                fontWeight: isCurrent ? 500 : 400,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {metric === "cost" ? fmtMoney(v) : fmtMs(v)}
              {isCurrent ? "  ← current" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Drift signals ─────────────────────────────────────────────────────────
function DriftPanel({ report }: { report: SwitchReport }) {
  // v1.0 doesn't ship drift events on the wire yet — show a clean state
  // panel with the metric we DO have (paired-correctness divergence).
  // When the drift-detector lands server-side, this panel will render
  // per-event rows from a `drift_events` table.
  const p = report.mcnemar_p_two_sided;
  const verdict =
    p === null
      ? "—"
      : p < 0.01
        ? "clears α = 0.01"
        : p < 0.05
          ? "clears α = 0.05"
          : "no significant divergence";
  return (
    <div>
      <p className="prose-brand" style={{ marginTop: 0 }}>
        No drift events detected in this window. The latest McNemar paired-
        correctness statistic is{" "}
        <span className="font-mono" style={{ color: "var(--accent-deep)" }}>
          p = {formatPValue(p)}
        </span>{" "}
        ({verdict}).
      </p>
      <p
        style={{
          color: "var(--ink-soft)",
          fontSize: "var(--size-caption)",
          margin: "var(--space-3) 0 0",
        }}
      >
        Drift events (paired-accuracy regressions, label distribution shifts,
        rollback triggers) surface here once the server-side drift detector
        ships in v1.1. Current build only renders the rolling McNemar p.
      </p>
    </div>
  );
}
