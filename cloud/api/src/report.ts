// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// GET /v1/switches/:name/report — render a report card for a switch.
//
// Aggregates verdicts in a rolling window (default 30 days, max 365) and
// computes:
//   * per-layer accuracy (rule / model / ml)
//   * paired-correctness counts (b = rule wins / ml loses, c = ml wins /
//     rule loses) and the McNemar two-sided exact-binomial p-value
//   * phase distribution + transition timeline
//   * recent activity timestamps
//
// Response: Markdown by default; `?format=json` returns the structured
// payload the dashboard renders into a richer report card.
//
// Data isolation: scoping is by user_id (not api_key_id), so a customer
// with both a live and a test key sees their unified roster. Querying
// for a switch the authed user has never reported a verdict for returns
// 404 — never 200-empty — so cross-account probing can't enumerate names.

import type { Context } from 'hono';
import type { ApiEnv, AuthContext } from './auth';

const SWITCH_NAME_RE = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;

interface AggRow {
  total: number;
  rule_total: number;
  rule_correct: number;
  model_total: number;
  model_correct: number;
  ml_total: number;
  ml_correct: number;
  // McNemar discordant pairs (where both rule_correct AND ml_correct
  // are non-null, so pair is well-formed)
  paired_total: number;
  b: number;
  c: number;
  first_at: string | null;
  last_at: string | null;
}

interface PhaseRow {
  phase: string | null;
  n: number;
}

interface TransitionRow {
  phase: string;
  first_seen: string;
  last_seen: string;
  n: number;
}

/**
 * Two-sided McNemar exact-binomial p-value.
 *
 * Under H0 the discordant pairs split 50/50; we observed (b, c) so the
 * test statistic is min(b,c). P = 2 * P(X ≤ min(b,c)) under
 * Binomial(b+c, 0.5), capped at 1.
 *
 * For small b+c (which is the operating regime — most switches won't
 * have millions of discordant pairs), this is exact and stable.
 */
export function mcnemarPValue(b: number, c: number): number | null {
  const n = b + c;
  if (n === 0) return null;
  const k = Math.min(b, c);

  // Sum of Binomial(n, 0.5) PMF for i=0..k.
  // Use log-space to avoid overflow on large n.
  let logSum = -Infinity;
  let logCoef = 0; // log(C(n, 0)) = 0
  for (let i = 0; i <= k; i++) {
    if (i > 0) {
      logCoef += Math.log(n - i + 1) - Math.log(i);
    }
    const logTerm = logCoef + n * Math.log(0.5);
    // Stable log-sum-exp.
    if (logTerm > logSum) {
      logSum = logTerm + Math.log1p(Math.exp(logSum - logTerm));
    } else {
      logSum = logSum + Math.log1p(Math.exp(logTerm - logSum));
    }
  }
  const pOneSided = Math.exp(logSum);
  return Math.min(1, 2 * pOneSided);
}

function pct(num: number, denom: number): string {
  if (denom === 0) return '—';
  return ((num / denom) * 100).toFixed(1) + '%';
}

function renderMarkdown(args: {
  switch_name: string;
  days: number;
  agg: AggRow;
  phases: PhaseRow[];
  transitions: TransitionRow[];
}): string {
  const { switch_name, days, agg, phases, transitions } = args;
  const ruleAcc = agg.rule_total > 0 ? agg.rule_correct / agg.rule_total : null;
  const mlAcc = agg.ml_total > 0 ? agg.ml_correct / agg.ml_total : null;
  const p = mcnemarPValue(agg.b, agg.c);

  const lines: string[] = [];
  lines.push(`# Report card — \`${switch_name}\``);
  lines.push('');
  lines.push(`Window: last ${days} day${days === 1 ? '' : 's'}.`);
  if (agg.first_at && agg.last_at) {
    lines.push(`First verdict in window: ${agg.first_at}.`);
    lines.push(`Most recent verdict: ${agg.last_at}.`);
  }
  lines.push(`Total verdicts: **${agg.total.toLocaleString()}**.`);
  lines.push('');

  lines.push('## Per-layer accuracy');
  lines.push('');
  lines.push('| Layer | Verdicts | Correct | Accuracy |');
  lines.push('|---|---:|---:|---:|');
  lines.push(`| Rule  | ${agg.rule_total} | ${agg.rule_correct} | ${pct(agg.rule_correct, agg.rule_total)} |`);
  lines.push(`| Model | ${agg.model_total} | ${agg.model_correct} | ${pct(agg.model_correct, agg.model_total)} |`);
  lines.push(`| ML    | ${agg.ml_total} | ${agg.ml_correct} | ${pct(agg.ml_correct, agg.ml_total)} |`);
  lines.push('');

  if (agg.paired_total > 0) {
    lines.push('## Rule vs ML — paired McNemar gate');
    lines.push('');
    lines.push(`Paired correctness pairs (both layers ran): **${agg.paired_total.toLocaleString()}**.`);
    lines.push('');
    lines.push('| | Rule wins | Rule loses |');
    lines.push('|---|---:|---:|');
    lines.push(`| Discordant pairs | ${agg.b} (b) | ${agg.c} (c) |`);
    lines.push('');
    if (p !== null) {
      const verdict =
        p < 0.01 ? '**clears α = 0.01**' : p < 0.05 ? 'clears α = 0.05 (not 0.01)' : 'does not clear α = 0.05';
      lines.push(`McNemar two-sided exact p = **${p.toExponential(2)}** — ${verdict}.`);
      const ruleAdvantage = (ruleAcc ?? 0) - (mlAcc ?? 0);
      if (ruleAdvantage > 0) {
        lines.push(`Rule is currently +${(ruleAdvantage * 100).toFixed(2)} pp ahead of ML.`);
      } else if (ruleAdvantage < 0) {
        lines.push(`ML is currently +${(-ruleAdvantage * 100).toFixed(2)} pp ahead of Rule.`);
      } else {
        lines.push('Rule and ML are tied.');
      }
    }
    lines.push('');
  }

  if (phases.length > 0) {
    lines.push('## Phase distribution');
    lines.push('');
    lines.push('| Phase | Verdicts | Share |');
    lines.push('|---|---:|---:|');
    for (const r of phases) {
      lines.push(`| ${r.phase ?? '_(unspecified)_'} | ${r.n} | ${pct(r.n, agg.total)} |`);
    }
    lines.push('');
  }

  if (transitions.length > 1) {
    lines.push('## Phase timeline');
    lines.push('');
    lines.push('| Phase | First observed | Last observed | Verdicts |');
    lines.push('|---|---|---|---:|');
    for (const t of transitions) {
      lines.push(`| ${t.phase} | ${t.first_seen} | ${t.last_seen} | ${t.n} |`);
    }
    lines.push('');
  }

  lines.push('---');
  lines.push('');
  lines.push('Generated by Dendra Insights. Source: paired-correctness verdicts posted via POST /v1/verdicts.');
  return lines.join('\n');
}

/**
 * Phase label (RULE / MODEL_SHADOW / …) for a P0..P5 letter. Keeps the
 * SDK-side enum stable while the wire format stays compact.
 */
const PHASE_LABELS: Record<string, string> = {
  P0: 'RULE',
  P1: 'MODEL_SHADOW',
  P2: 'MODEL_PRIMARY',
  P3: 'ML_SHADOW',
  P4: 'ML_WITH_FALLBACK',
  P5: 'ML_PRIMARY',
};

export function phaseLabel(phase: string | null): string | null {
  if (!phase) return null;
  return PHASE_LABELS[phase] ?? phase;
}

/**
 * Shared computation. Used by the Bearer `/v1` route AND the
 * service-token `/admin/switches/:name/report` route the dashboard calls
 * server-side. Returns null when no verdicts exist for the given user_id
 * and switch_name — callers MUST treat null as 404 to preserve isolation.
 */
export async function computeReport(
  db: D1Database,
  user_id: number,
  switch_name: string,
  days: number,
): Promise<{
  agg: AggRow;
  phases: PhaseRow[];
  transitions: TransitionRow[];
  mcnemar_p_two_sided: number | null;
} | null> {
  // First confirm ownership — zero rows ⇒ 404 (NOT 200-empty). The
  // ownership check uses the same JOIN as the aggregation, so the
  // partial-index path is hot.
  const own = await db
    .prepare(
      `SELECT 1 AS hit
         FROM verdicts v
         JOIN api_keys k ON k.id = v.api_key_id
        WHERE k.user_id = ?
          AND v.switch_name = ?
        LIMIT 1`,
    )
    .bind(user_id, switch_name)
    .first<{ hit: number }>();
  if (!own) return null;

  const agg = await db
    .prepare(
      `SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN v.rule_correct  IS NOT NULL THEN 1 ELSE 0 END) AS rule_total,
          SUM(CASE WHEN v.rule_correct  = 1 THEN 1 ELSE 0 END)         AS rule_correct,
          SUM(CASE WHEN v.model_correct IS NOT NULL THEN 1 ELSE 0 END) AS model_total,
          SUM(CASE WHEN v.model_correct = 1 THEN 1 ELSE 0 END)         AS model_correct,
          SUM(CASE WHEN v.ml_correct    IS NOT NULL THEN 1 ELSE 0 END) AS ml_total,
          SUM(CASE WHEN v.ml_correct    = 1 THEN 1 ELSE 0 END)         AS ml_correct,
          SUM(CASE WHEN v.rule_correct IS NOT NULL AND v.ml_correct IS NOT NULL THEN 1 ELSE 0 END) AS paired_total,
          SUM(CASE WHEN v.rule_correct = 1 AND v.ml_correct = 0 THEN 1 ELSE 0 END) AS b,
          SUM(CASE WHEN v.rule_correct = 0 AND v.ml_correct = 1 THEN 1 ELSE 0 END) AS c,
          MIN(v.created_at) AS first_at,
          MAX(v.created_at) AS last_at
         FROM verdicts v
         JOIN api_keys k ON k.id = v.api_key_id
        WHERE k.user_id = ?
          AND v.switch_name = ?
          AND v.created_at >= datetime('now', ?)`,
    )
    .bind(user_id, switch_name, `-${days} days`)
    .first<AggRow>();

  if (!agg) {
    throw new Error('aggregation_failed');
  }

  const safeAgg: AggRow = {
    total: agg.total ?? 0,
    rule_total: agg.rule_total ?? 0,
    rule_correct: agg.rule_correct ?? 0,
    model_total: agg.model_total ?? 0,
    model_correct: agg.model_correct ?? 0,
    ml_total: agg.ml_total ?? 0,
    ml_correct: agg.ml_correct ?? 0,
    paired_total: agg.paired_total ?? 0,
    b: agg.b ?? 0,
    c: agg.c ?? 0,
    first_at: agg.first_at,
    last_at: agg.last_at,
  };

  const phases = (
    await db
      .prepare(
        `SELECT v.phase AS phase, COUNT(*) AS n
           FROM verdicts v
           JOIN api_keys k ON k.id = v.api_key_id
          WHERE k.user_id = ?
            AND v.switch_name = ?
            AND v.created_at >= datetime('now', ?)
          GROUP BY v.phase
          ORDER BY v.phase`,
      )
      .bind(user_id, switch_name, `-${days} days`)
      .all<PhaseRow>()
  ).results ?? [];

  // Phase transition timeline — first/last timestamp the phase was
  // observed across the FULL history (window-independent, since
  // transitions are rare and the user expects to see the lifecycle).
  const transitions = (
    await db
      .prepare(
        `SELECT v.phase AS phase,
                MIN(v.created_at) AS first_seen,
                MAX(v.created_at) AS last_seen,
                COUNT(*) AS n
           FROM verdicts v
           JOIN api_keys k ON k.id = v.api_key_id
          WHERE k.user_id = ?
            AND v.switch_name = ?
            AND v.phase IS NOT NULL
          GROUP BY v.phase
          ORDER BY first_seen ASC`,
      )
      .bind(user_id, switch_name)
      .all<TransitionRow>()
  ).results ?? [];

  return {
    agg: safeAgg,
    phases,
    transitions,
    mcnemar_p_two_sided: mcnemarPValue(safeAgg.b, safeAgg.c),
  };
}

export async function renderReportHandler(c: Context<{ Bindings: ApiEnv }>) {
  const auth = c.get('auth') as AuthContext;
  const switch_name = c.req.param('name') ?? '';
  if (!SWITCH_NAME_RE.test(switch_name)) {
    return c.json({ error: 'invalid_switch_name' }, 400);
  }
  const daysParam = Number(c.req.query('days') ?? '30');
  const days = Number.isFinite(daysParam) && daysParam > 0
    ? Math.min(Math.floor(daysParam), 365)
    : 30;
  const format = c.req.query('format') === 'json' ? 'json' : 'md';

  const report = await computeReport(c.env.DB, auth.user_id, switch_name, days);
  if (!report) {
    // 404 — never 200-empty. Preserves data isolation: an attacker can't
    // probe switch names by watching response shapes.
    return c.json({ error: 'switch_not_found' }, 404);
  }

  if (format === 'json') {
    const currentPhase = report.transitions.length
      ? report.transitions[report.transitions.length - 1].phase
      : null;
    return c.json({
      switch_name,
      days,
      agg: report.agg,
      phases: report.phases,
      transitions: report.transitions,
      current_phase: currentPhase,
      current_phase_label: phaseLabel(currentPhase),
      mcnemar_p_two_sided: report.mcnemar_p_two_sided,
    });
  }

  const md = renderMarkdown({
    switch_name,
    days,
    agg: report.agg,
    phases: report.phases,
    transitions: report.transitions,
  });
  return new Response(md, {
    status: 200,
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
}
