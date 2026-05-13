// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Daily-at-09:00-UTC cron handler. Two responsibilities:
//
//   1. Compose a digest of all untriaged reports whose age in business
//      days is >= 4 (i.e. day 5 and onward, which is the published
//      5-business-day triage SLA window edge). One consolidated email,
//      not one per overdue row, so the operator gets a single list.
//
//   2. For urgent reports that have been open >24 hours of wall-clock
//      time and are still untriaged: a separate immediate-escalation
//      email per row. Wall-clock not business-day here — "urgent"
//      doesn't get weekend grace.
//
// "All clear" (zero overdue, zero urgent-stale) is silent. The cron
// runs every day; we don't want to train the operator to ignore the
// 09:00 email.

import type { Env } from './env';
import { listOpenReports, type SecurityReportRow } from './reports';
import { sendOpsAlert } from './mailer';

/**
 * Count Mon-Fri days strictly between two instants. Weekends are
 * skipped; holidays are ignored (solo founder, no calendar to wire
 * up). Returns 0 if `later <= earlier`.
 *
 * Semantics: "Submitted Mon 09:00 UTC, now Tue 09:00 UTC" → 1
 * business day. "Submitted Fri 09:00 UTC, now Mon 09:00 UTC" → 1
 * business day (Sat/Sun skipped). The function iterates day-by-day
 * which is plenty fast for the report volumes in scope (handfuls of
 * rows per check, at most ~260 iterations per row over a year).
 */
export function businessDaysBetween(earlier: Date, later: Date): number {
  const start = earlier.getTime();
  const end = later.getTime();
  if (end <= start) return 0;
  // Round both to UTC-midnight day boundaries, then count Mon-Fri
  // days strictly after start and up to (and including) end.
  const startDay = utcDayIndex(earlier);
  const endDay = utcDayIndex(later);
  let count = 0;
  for (let d = startDay + 1; d <= endDay; d++) {
    // 0 = Sunday, 6 = Saturday in JS getUTCDay.
    const dow = utcDowFromDayIndex(d);
    if (dow !== 0 && dow !== 6) count++;
  }
  return count;
}

/** Days since the Unix epoch in UTC. */
function utcDayIndex(d: Date): number {
  return Math.floor(d.getTime() / 86_400_000);
}

/** Day-of-week (0=Sun..6=Sat) for a UTC day index. 1970-01-01 was a Thursday (4). */
function utcDowFromDayIndex(dayIndex: number): number {
  return ((dayIndex % 7) + 4 + 7) % 7;
}

/** Wall-clock hours between two instants. Negative clamped to 0. */
export function hoursBetween(earlier: Date, later: Date): number {
  const ms = later.getTime() - earlier.getTime();
  if (ms <= 0) return 0;
  return ms / 3_600_000;
}

/** Threshold: >= 4 business days open triggers the overdue digest. */
const OVERDUE_BUSINESS_DAYS = 4;
/** Threshold: urgent + >24h wall-clock open triggers separate escalation. */
const URGENT_STALE_HOURS = 24;

interface CronOutcome {
  overdue: SecurityReportRow[];
  urgentStale: SecurityReportRow[];
}

/**
 * Pure logic — read open reports, partition into the two alert
 * buckets, return them. Separated from sendOverdueDigest /
 * sendUrgentEscalations so a future "preview the cron output"
 * admin endpoint can call this without sending.
 */
export async function computeCronOutcome(
  env: Env,
  now: Date = new Date(),
): Promise<CronOutcome> {
  const open = await listOpenReports(env);
  const overdue: SecurityReportRow[] = [];
  const urgentStale: SecurityReportRow[] = [];
  for (const row of open) {
    const received = new Date(row.received_at);
    if (Number.isNaN(received.getTime())) {
      // Bad data — log and skip rather than crashing the cron.
      console.error(
        JSON.stringify({
          level: 'error',
          msg: 'security_report_bad_received_at',
          reference: row.reference,
          received_at: row.received_at,
          env: env.ENVIRONMENT,
        }),
      );
      continue;
    }
    if (businessDaysBetween(received, now) >= OVERDUE_BUSINESS_DAYS) {
      overdue.push(row);
    }
    if (row.urgent === 1 && hoursBetween(received, now) >= URGENT_STALE_HOURS) {
      urgentStale.push(row);
    }
  }
  return { overdue, urgentStale };
}

/** Compose the overdue-digest email body. */
export function buildOverdueDigest(
  rows: SecurityReportRow[],
  now: Date,
): { subject: string; text: string } {
  const subject =
    '⚠ Security report triage overdue (' +
    rows.length +
    ' report' +
    (rows.length === 1 ? '' : 's') +
    ' >' +
    OVERDUE_BUSINESS_DAYS +
    ' business days)';
  const lines: string[] = [
    'The following security reports have been open for more than',
    OVERDUE_BUSINESS_DAYS + ' business days without being marked triaged.',
    'The published SLA is "human triage within five business days" —',
    'these are at or past that threshold.',
    '',
  ];
  for (const row of rows) {
    const received = new Date(row.received_at);
    const age = businessDaysBetween(received, now);
    lines.push('• ' + row.reference + (row.urgent === 1 ? ' [URGENT]' : ''));
    lines.push('    sender:    ' + row.sender);
    lines.push('    subject:   ' + (row.subject ?? '<no subject>'));
    lines.push('    received:  ' + row.received_at);
    lines.push('    open for:  ' + age + ' business day' + (age === 1 ? '' : 's'));
    lines.push('');
  }
  lines.push(
    'Mark a report triaged by stamping triaged_at, e.g.:',
    '',
    "  wrangler d1 execute dendra-events --env production \\",
    '    --command \"UPDATE security_reports SET triaged_at = datetime(\\\'now\\\') WHERE reference = \\\'SR-YYYY-NNNN\\\'\"',
    '',
    '— dendra-security-ops',
  );
  return { subject, text: lines.join('\n') };
}

/** Compose the urgent-stale escalation email for a single row. */
export function buildUrgentEscalation(
  row: SecurityReportRow,
  now: Date,
): { subject: string; text: string } {
  const received = new Date(row.received_at);
  const hours = Math.floor(hoursBetween(received, now));
  return {
    subject: '[URGENT-STALE] ' + row.reference + ' still untriaged after ' + hours + 'h',
    text: [
      'An URGENT-marked security report has been open more than 24 hours',
      'without being marked triaged.',
      '',
      'Reference: ' + row.reference,
      'Sender:    ' + row.sender,
      'Subject:   ' + (row.subject ?? '<no subject>'),
      'Received:  ' + row.received_at,
      'Open for:  ' + hours + ' hours',
      '',
      'This is the second alert for this report — the first went out',
      'at receipt via the email handler. Triage now or de-classify by',
      'marking triaged.',
      '',
      '— dendra-security-ops',
    ].join('\n'),
  };
}

/**
 * Scheduled-event entry point. Called from the Worker's `scheduled`
 * export with the cron event + env. Pure orchestrator: queries,
 * partitions, sends.
 */
export async function runScheduled(env: Env, now: Date = new Date()): Promise<void> {
  const outcome = await computeCronOutcome(env, now);

  if (outcome.overdue.length === 0 && outcome.urgentStale.length === 0) {
    // Silent success — matches the spec "no all-clear email".
    console.log(
      JSON.stringify({
        level: 'info',
        msg: 'security_cron_silent',
        env: env.ENVIRONMENT,
        at: now.toISOString(),
      }),
    );
    return;
  }

  if (outcome.overdue.length > 0) {
    const digest = buildOverdueDigest(outcome.overdue, now);
    try {
      await sendOpsAlert(env, digest);
    } catch (err) {
      console.error(
        JSON.stringify({
          level: 'error',
          msg: 'security_cron_digest_failed',
          error: err instanceof Error ? err.message : String(err),
          env: env.ENVIRONMENT,
        }),
      );
    }
  }

  // Fan out urgent escalations in parallel — independent sends, and a
  // slow MailChannels response shouldn't stretch the cron's total
  // runtime linearly when there are multiple stale-urgent reports.
  await Promise.all(
    outcome.urgentStale.map(async (row) => {
      try {
        await sendOpsAlert(env, buildUrgentEscalation(row, now));
      } catch (err) {
        console.error(
          JSON.stringify({
            level: 'error',
            msg: 'security_cron_urgent_escalation_failed',
            reference: row.reference,
            error: err instanceof Error ? err.message : String(err),
            env: env.ENVIRONMENT,
          }),
        );
      }
    }),
  );
}
