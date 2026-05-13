// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// security_reports table access — reference allocation, row insert,
// timestamp updates, "what's overdue" query. Kept thin: no business
// rules in here, just SQL. The handlers in email-handler.ts and
// cron-handler.ts call into this module.

import type { Env } from './env';

export interface SecurityReportRow {
  id: number;
  reference: string;
  received_at: string;
  sender: string;
  subject: string | null;
  urgent: number;
  acked_at: string | null;
  triaged_at: string | null;
  resolved_at: string | null;
  notes: string | null;
}

/**
 * Allocate the next reference for `year`. Format: SR-YYYY-NNNN where
 * NNNN restarts at 0001 every January 1. Counted by scanning the
 * current-year rows; UNIQUE on `reference` is the race backstop.
 *
 * D1 doesn't have a real transactional read-modify-write primitive
 * for a single connection-bound counter, so the "count + 1" race is
 * resolvable only by the UNIQUE constraint — on collision, the caller
 * retries with the now-bumped count. In practice the inbound rate is
 * ~one email/day; the race is theoretical.
 */
export async function allocateReference(env: Env, year: number): Promise<string> {
  // strftime('%Y', ...) gives the row's received_at year as text.
  // Comparing as text is fine since YYYY sorts lexicographically.
  const yearStr = String(year);
  const row = await env.DB.prepare(
    `SELECT COUNT(*) AS n FROM security_reports
       WHERE strftime('%Y', received_at) = ?`,
  )
    .bind(yearStr)
    .first<{ n: number }>();
  const next = (row?.n ?? 0) + 1;
  return `SR-${yearStr}-${String(next).padStart(4, '0')}`;
}

/** Insert a freshly-received report. Returns the row id. */
export async function insertReport(
  env: Env,
  args: {
    reference: string;
    receivedAt: string;
    sender: string;
    subject: string | null;
    urgent: boolean;
  },
): Promise<number> {
  const res = await env.DB.prepare(
    `INSERT INTO security_reports
       (reference, received_at, sender, subject, urgent)
     VALUES (?, ?, ?, ?, ?)`,
  )
    .bind(
      args.reference,
      args.receivedAt,
      args.sender,
      args.subject,
      args.urgent ? 1 : 0,
    )
    .run();
  // D1's last_row_id is exposed on meta.
  return res.meta.last_row_id as number;
}

/** Stamp `acked_at` after the auto-reply is dispatched. */
export async function markAcked(env: Env, id: number, ackedAt: string): Promise<void> {
  await env.DB.prepare(`UPDATE security_reports SET acked_at = ? WHERE id = ?`)
    .bind(ackedAt, id)
    .run();
}

/** Every row that has not yet been marked triaged. */
export async function listOpenReports(env: Env): Promise<SecurityReportRow[]> {
  const res = await env.DB.prepare(
    `SELECT id, reference, received_at, sender, subject, urgent,
            acked_at, triaged_at, resolved_at, notes
       FROM security_reports
      WHERE triaged_at IS NULL
      ORDER BY received_at ASC`,
  ).all<SecurityReportRow>();
  return res.results ?? [];
}
