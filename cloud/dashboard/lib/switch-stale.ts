// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Stale-switch detection helpers. Presentation-only — no data changes.
//
// A switch is "stale" when last_activity is older than STALE_AFTER_DAYS
// AND the switch is not archived. The UX is two-pronged:
//   * /dashboard/switches roster: small dimmed "Stale" chip next to the
//     switch name; no re-sort (default sort by recent activity already
//     buries stale rows).
//   * /dashboard/switches/<name>: informational banner above the header
//     prompting the customer to archive if the switch is truly dormant.
//
// Threshold tunable here. 30 days matches the "we paused" timescale a
// customer typically thinks in; shorter would create banner noise on
// genuinely-low-volume switches.

export const STALE_AFTER_DAYS = 30;

/** Days elapsed since the given ISO/D1 timestamp, floored to whole days. */
export function daysSince(iso: string, now: Date = new Date()): number {
  // D1's datetime() output is "YYYY-MM-DD HH:MM:SS" UTC. Normalize to a
  // parseable ISO string before constructing the Date.
  const normalized = iso.includes("T")
    ? iso
    : iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z");
  const then = new Date(normalized);
  if (Number.isNaN(then.getTime())) return 0;
  return Math.max(0, Math.floor((now.getTime() - then.getTime()) / 86_400_000));
}

/**
 * Stale iff last_activity > STALE_AFTER_DAYS days ago AND not archived.
 *
 * Archived switches are NOT stale — once the customer has explicitly
 * archived a switch, the dormancy hint becomes redundant; we surface the
 * archive banner instead.
 */
export function isStale(args: {
  last_activity: string;
  archived_at: string | null;
  now?: Date;
}): boolean {
  if (args.archived_at) return false;
  return daysSince(args.last_activity, args.now ?? new Date()) > STALE_AFTER_DAYS;
}
