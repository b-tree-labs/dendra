// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Tests for the daily cron handler. Two alert paths:
//
//   - Overdue digest: any untriaged row with >=4 business days open.
//   - Urgent-stale escalation: urgent=1 + untriaged + >24h wall-clock.
//
// Plus the business-day arithmetic itself, since "skip Sat/Sun" is the
// kind of thing that breaks subtly at DST or month boundaries.

import { describe, it, expect, beforeAll, beforeEach, afterEach } from 'vitest';
import { env } from 'cloudflare:test';
import migration0010 from '../../collector/migrations/0010_security_reports.sql?raw';
import {
  runScheduled,
  computeCronOutcome,
  businessDaysBetween,
  hoursBetween,
} from '../src/cron-handler';
import {
  applySql,
  resetTables,
  installMailChannelsStub,
  type MailStub,
} from './_helpers';

let mailStub: MailStub;

beforeAll(async () => {
  await applySql(migration0010);
});

beforeEach(async () => {
  await resetTables();
  mailStub = installMailChannelsStub();
});

afterEach(() => {
  mailStub.restore();
});

async function insertRow(args: {
  reference: string;
  receivedAt: string;
  urgent?: boolean;
  triagedAt?: string | null;
}) {
  await env.DB.prepare(
    `INSERT INTO security_reports
       (reference, received_at, sender, subject, urgent, triaged_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      args.reference,
      args.receivedAt,
      'reporter@example.com',
      'A subject',
      args.urgent ? 1 : 0,
      args.triagedAt ?? null,
    )
    .run();
}

describe('businessDaysBetween — arithmetic', () => {
  it('returns 0 for same day', () => {
    const d = new Date('2026-05-13T09:00:00Z');
    expect(businessDaysBetween(d, d)).toBe(0);
  });

  it('returns 1 for Mon → Tue', () => {
    // 2026-05-11 was a Monday (per ISO calendar).
    expect(
      businessDaysBetween(
        new Date('2026-05-11T09:00:00Z'),
        new Date('2026-05-12T09:00:00Z'),
      ),
    ).toBe(1);
  });

  it('skips Sat + Sun: Fri → Mon is 1 business day', () => {
    // 2026-05-15 = Friday, 2026-05-18 = Monday.
    expect(
      businessDaysBetween(
        new Date('2026-05-15T09:00:00Z'),
        new Date('2026-05-18T09:00:00Z'),
      ),
    ).toBe(1);
  });

  it('Mon → next Mon is 5 business days (M-F counted, weekend skipped)', () => {
    expect(
      businessDaysBetween(
        new Date('2026-05-11T09:00:00Z'),
        new Date('2026-05-18T09:00:00Z'),
      ),
    ).toBe(5);
  });

  it('Mon → Fri same week is 4 business days', () => {
    expect(
      businessDaysBetween(
        new Date('2026-05-11T09:00:00Z'),
        new Date('2026-05-15T09:00:00Z'),
      ),
    ).toBe(4);
  });

  it('clamps to 0 when later <= earlier', () => {
    expect(
      businessDaysBetween(
        new Date('2026-05-15T09:00:00Z'),
        new Date('2026-05-13T09:00:00Z'),
      ),
    ).toBe(0);
  });
});

describe('hoursBetween', () => {
  it('returns the wall-clock hour delta', () => {
    expect(
      hoursBetween(
        new Date('2026-05-13T09:00:00Z'),
        new Date('2026-05-14T09:00:00Z'),
      ),
    ).toBe(24);
  });
});

describe('runScheduled — silent path', () => {
  it('sends nothing when there are no open reports', async () => {
    await runScheduled(env, new Date('2026-05-20T09:00:00Z'));
    expect(mailStub.records).toHaveLength(0);
  });

  it('sends nothing when all open reports are within SLA', async () => {
    // Inserted 1 business day ago — well within the 5-business-day SLA.
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-19T09:00:00Z',
    });
    await runScheduled(env, new Date('2026-05-20T09:00:00Z'));
    expect(mailStub.records).toHaveLength(0);
  });

  it('sends nothing when overdue rows have been triaged', async () => {
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-11T09:00:00Z', // Mon
      triagedAt: '2026-05-12T09:00:00Z',
    });
    // Pretend "now" is the following Monday — 5 biz days post-receipt,
    // but the row was triaged so it should not be flagged.
    await runScheduled(env, new Date('2026-05-18T09:00:00Z'));
    expect(mailStub.records).toHaveLength(0);
  });
});

describe('runScheduled — overdue digest', () => {
  it('sends a consolidated digest when one report is past 4 business days', async () => {
    // Received Mon 2026-05-11; cron runs Mon 2026-05-18 → 5 biz days.
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-11T09:00:00Z',
    });
    await runScheduled(env, new Date('2026-05-18T09:00:00Z'));
    expect(mailStub.records).toHaveLength(1);
    const alert = mailStub.records[0]!;
    expect(alert.to).toBe(env.SECURITY_FORWARD_TO);
    expect(alert.subject).toContain('Security report triage overdue');
    expect(alert.subject).toContain('1 report');
    expect(alert.text).toContain('SR-2026-0001');
    expect(alert.text).toContain('5 business days');
  });

  it('lists every overdue row in one digest, not one digest per row', async () => {
    await insertRow({ reference: 'SR-2026-0001', receivedAt: '2026-05-11T09:00:00Z' });
    await insertRow({ reference: 'SR-2026-0002', receivedAt: '2026-05-11T10:00:00Z' });
    await runScheduled(env, new Date('2026-05-18T09:00:00Z'));
    const overdueDigests = mailStub.records.filter((r) =>
      r.subject.includes('Security report triage overdue'),
    );
    expect(overdueDigests).toHaveLength(1);
    expect(overdueDigests[0]!.subject).toContain('2 reports');
    expect(overdueDigests[0]!.text).toContain('SR-2026-0001');
    expect(overdueDigests[0]!.text).toContain('SR-2026-0002');
  });
});

describe('runScheduled — urgent-stale escalation', () => {
  it('sends a per-row urgent alert when an urgent report is open >24h', async () => {
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-13T09:00:00Z',
      urgent: true,
    });
    // 36h later — well past the 24h threshold but still under 4 biz days.
    await runScheduled(env, new Date('2026-05-14T21:00:00Z'));

    const urgentAlerts = mailStub.records.filter((r) =>
      r.subject.includes('[URGENT-STALE]'),
    );
    expect(urgentAlerts).toHaveLength(1);
    expect(urgentAlerts[0]!.subject).toContain('SR-2026-0001');
    expect(urgentAlerts[0]!.text).toContain('SR-2026-0001');
    // Not yet overdue (<4 biz days) so no consolidated digest fired.
    expect(
      mailStub.records.filter((r) => r.subject.includes('Security report triage overdue')),
    ).toHaveLength(0);
  });

  it('does not double-alert an urgent row that was just received (<24h)', async () => {
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-13T09:00:00Z',
      urgent: true,
    });
    // 12h later — under the threshold.
    await runScheduled(env, new Date('2026-05-13T21:00:00Z'));
    expect(mailStub.records).toHaveLength(0);
  });

  it('sends both digest and urgent escalation when both conditions hold', async () => {
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: '2026-05-11T09:00:00Z',
      urgent: true,
    });
    await runScheduled(env, new Date('2026-05-18T09:00:00Z'));
    // One digest + one urgent escalation.
    expect(mailStub.records).toHaveLength(2);
    const subjects = mailStub.records.map((r) => r.subject);
    expect(subjects.some((s) => s.includes('Security report triage overdue'))).toBe(true);
    expect(subjects.some((s) => s.includes('[URGENT-STALE]'))).toBe(true);
  });
});

describe('computeCronOutcome — partitioning', () => {
  it('returns empty arrays when there is nothing to alert on', async () => {
    const outcome = await computeCronOutcome(env, new Date('2026-05-20T09:00:00Z'));
    expect(outcome.overdue).toEqual([]);
    expect(outcome.urgentStale).toEqual([]);
  });

  it('skips rows with unparseable received_at without crashing', async () => {
    await insertRow({
      reference: 'SR-2026-0001',
      receivedAt: 'not-a-date',
    });
    const outcome = await computeCronOutcome(env, new Date('2026-05-20T09:00:00Z'));
    expect(outcome.overdue).toEqual([]);
    expect(outcome.urgentStale).toEqual([]);
  });
});
