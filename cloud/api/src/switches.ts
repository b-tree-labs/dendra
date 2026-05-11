// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// GET /v1/switches — list every switch the authed account has emitted a
// verdict for, with current phase, total verdicts, last activity, and a
// 14-day-per-day verdict count for sparkline rendering.
//
// Data isolation: the authed key resolves to a single api_key_id. We
// aggregate verdicts joined to api_keys belonging to the SAME user_id so
// a user with multiple keys (e.g. live + test) sees their unified roster
// — but never another account's switches.
//
// This route is read-only and intentionally NOT mounted under the
// billable middleware: dashboard renders shouldn't consume verdict cap.

import type { Context } from 'hono';
import type { ApiEnv, AuthContext } from './auth';

const SWITCH_NAME_RE = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;

interface SwitchListRow {
  switch_name: string;
  current_phase: string | null;
  total_verdicts: number;
  last_activity: string;
  first_activity: string;
}

interface SparklineRow {
  switch_name: string;
  bucket_date: string;
  n: number;
}

export interface SwitchSummary {
  switch_name: string;
  current_phase: string | null;
  total_verdicts: number;
  last_activity: string;
  first_activity: string;
  // verdict count per day for the last 14 days, oldest first; gaps filled
  // with zero so client renderers don't have to interpolate.
  sparkline: number[];
}

/**
 * Format YYYY-MM-DD for a date offset from `now` by `daysAgo` days, in
 * UTC. We use UTC because D1's datetime('now') is UTC, and a per-day
 * bucket boundary that drifts with the user's tz would skew sparklines.
 */
function utcDateStr(daysAgo: number, now: Date = new Date()): string {
  const d = new Date(now.getTime() - daysAgo * 86400_000);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Inclusive 14-day window: today and the prior 13 days, oldest first. */
function lastNDates(n: number, now: Date = new Date()): string[] {
  const out: string[] = [];
  for (let i = n - 1; i >= 0; i--) out.push(utcDateStr(i, now));
  return out;
}

export async function listSwitchesHandler(c: Context<{ Bindings: ApiEnv }>) {
  const auth = c.get('auth') as AuthContext;

  // The authed key gets us the user_id; from there we widen to every
  // api_key the user owns. A user with revoked keys still owns the
  // verdicts those keys created — those rows surface in their roster.
  //
  // The CTE pre-computes `phase_at_latest` per (user, switch) partition
  // via a single window-function pass; the outer GROUP BY projects it
  // back out. Replaces a correlated subquery that ran once per switch
  // in the result set — for a 500-switch user, that was 500 nested
  // SELECTs and pushed `/v1/switches` toward >2s on production D1 with
  // edge RTT (see `docs/working/SCALE_REPORT-2026-05-11.md` §5.1).
  const summary = (
    await c.env.DB.prepare(
      `WITH user_verdicts AS (
         SELECT
           v.switch_name AS switch_name,
           v.phase       AS phase,
           v.created_at  AS created_at,
           FIRST_VALUE(v.phase) OVER (
             PARTITION BY v.switch_name
             ORDER BY v.created_at DESC
           ) AS phase_at_latest
         FROM verdicts v
         JOIN api_keys k ON k.id = v.api_key_id
         WHERE k.user_id = ?
       )
       SELECT
         switch_name            AS switch_name,
         COUNT(*)               AS total_verdicts,
         MIN(created_at)        AS first_activity,
         MAX(created_at)        AS last_activity,
         MAX(phase_at_latest)   AS current_phase
       FROM user_verdicts
       GROUP BY switch_name
       ORDER BY MAX(created_at) DESC`,
    )
      .bind(auth.user_id)
      .all<SwitchListRow>()
  ).results ?? [];

  // Bucket per-day counts for the last 14 days, single query.
  // strftime('%Y-%m-%d', created_at) is the UTC bucket key — datetime('now')
  // in D1 is UTC so this stays consistent with the sparkline grid.
  const sparkRows = (
    await c.env.DB.prepare(
      `SELECT v.switch_name AS switch_name,
              strftime('%Y-%m-%d', v.created_at) AS bucket_date,
              COUNT(*) AS n
         FROM verdicts v
         JOIN api_keys k ON k.id = v.api_key_id
        WHERE k.user_id = ?
          AND v.created_at >= datetime('now', '-14 days')
        GROUP BY v.switch_name, strftime('%Y-%m-%d', v.created_at)`,
    )
      .bind(auth.user_id)
      .all<SparklineRow>()
  ).results ?? [];

  const grid = lastNDates(14);
  const byName = new Map<string, Map<string, number>>();
  for (const row of sparkRows) {
    let m = byName.get(row.switch_name);
    if (!m) {
      m = new Map();
      byName.set(row.switch_name, m);
    }
    m.set(row.bucket_date, row.n);
  }

  const switches: SwitchSummary[] = summary.map((row) => {
    const buckets = byName.get(row.switch_name) ?? new Map<string, number>();
    return {
      switch_name: row.switch_name,
      current_phase: row.current_phase ?? null,
      total_verdicts: row.total_verdicts,
      last_activity: row.last_activity,
      first_activity: row.first_activity,
      sparkline: grid.map((d) => buckets.get(d) ?? 0),
    };
  });

  return c.json({ switches, sparkline_window_days: 14 });
}

// ---------------------------------------------------------------------------
// Helper used by both the bearer-auth /v1 path AND the dashboard /admin
// path: confirm a switch belongs to the given user and return the canonical
// api_key_id we use to scope verdict queries. Returns null when the switch
// is genuinely absent for that user (so callers can 404 — never 200-empty).
// ---------------------------------------------------------------------------
export async function lookupSwitchOwnership(
  db: D1Database,
  user_id: number,
  switch_name: string,
): Promise<{ found: boolean }> {
  if (!SWITCH_NAME_RE.test(switch_name)) return { found: false };
  const row = await db
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
  return { found: !!row };
}
