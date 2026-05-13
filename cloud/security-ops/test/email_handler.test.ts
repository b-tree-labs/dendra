// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Tests for the inbound email handler. The handler is the user-facing
// edge of the SLA — every assertion here corresponds to a published
// commitment in SECURITY.md (auto-ack within seconds, reference issued,
// operator forwarded, urgent escalated).

import { describe, it, expect, beforeAll, beforeEach, afterEach } from 'vitest';
import { env } from 'cloudflare:test';
import migration0010 from '../../collector/migrations/0010_security_reports.sql?raw';
import { handleInboundEmail } from '../src/email-handler';
import {
  applySql,
  resetTables,
  makeInboundMessage,
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

describe('handleInboundEmail — happy path', () => {
  it('inserts a row, stamps acked_at, replies, and forwards', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'XSS in /dashboard/settings',
    });
    const now = new Date('2026-05-15T12:00:00.000Z');

    await handleInboundEmail(msg, env, now);

    // Row exists with the expected shape.
    const row = await env.DB.prepare(
      'SELECT reference, sender, subject, urgent, received_at, acked_at FROM security_reports',
    ).first<{
      reference: string;
      sender: string;
      subject: string;
      urgent: number;
      received_at: string;
      acked_at: string | null;
    }>();
    expect(row).not.toBeNull();
    expect(row!.reference).toBe('SR-2026-0001');
    expect(row!.sender).toBe('reporter@example.com');
    expect(row!.subject).toBe('XSS in /dashboard/settings');
    expect(row!.urgent).toBe(0);
    expect(row!.received_at).toBe('2026-05-15T12:00:00.000Z');
    expect(row!.acked_at).not.toBeNull();

    // Auto-reply went out with the reference embedded.
    expect(msg.recordedReplies).toHaveLength(1);
    expect(msg.recordedReplies[0]!.subject).toBe('Re: XSS in /dashboard/settings');
    expect(msg.recordedReplies[0]!.body).toContain('SR-2026-0001');
    expect(msg.recordedReplies[0]!.body).toContain('five business days');

    // Forward went to the configured operator inbox.
    expect(msg.recordedForwards).toHaveLength(1);
    expect(msg.recordedForwards[0]!.to).toBe(env.SECURITY_FORWARD_TO);

    // Non-urgent: no MailChannels notification fired.
    expect(mailStub.records).toHaveLength(0);
  });
});

describe('handleInboundEmail — urgent path', () => {
  it('flags urgent=1 and sends an immediate operator alert', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'URGENT: active RCE in production',
    });
    const now = new Date('2026-05-15T12:00:00.000Z');

    await handleInboundEmail(msg, env, now);

    const row = await env.DB.prepare(
      'SELECT urgent FROM security_reports',
    ).first<{ urgent: number }>();
    expect(row!.urgent).toBe(1);

    // Auto-reply still went to the reporter.
    expect(msg.recordedReplies).toHaveLength(1);
    // Forward still went out.
    expect(msg.recordedForwards).toHaveLength(1);

    // Plus an immediate operator alert via MailChannels.
    expect(mailStub.records).toHaveLength(1);
    const alert = mailStub.records[0]!;
    expect(alert.to).toBe(env.SECURITY_FORWARD_TO);
    expect(alert.subject).toContain('[URGENT]');
    expect(alert.subject).toContain('SR-2026-0001');
    expect(alert.text).toContain('reporter@example.com');
    expect(alert.text).toContain('URGENT: active RCE in production');
  });

  it('detects URGENT case-insensitively and as a word boundary', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'urgent — please read',
    });
    await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));
    const row = await env.DB.prepare('SELECT urgent FROM security_reports').first<{ urgent: number }>();
    expect(row!.urgent).toBe(1);
  });

  it('does NOT flag urgent for embedded substrings (e.g. "surgent")', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'insurgent typosquat report',
    });
    await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));
    const row = await env.DB.prepare('SELECT urgent FROM security_reports').first<{ urgent: number }>();
    expect(row!.urgent).toBe(0);
  });
});

describe('handleInboundEmail — failure isolation', () => {
  it('still forwards when the D1 insert fails', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'Looks bad',
    });
    // Sabotage D1 by dropping the table; handler should still forward.
    await env.DB.prepare('DROP TABLE security_reports').run();

    await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));

    expect(msg.recordedForwards).toHaveLength(1);
    expect(msg.recordedForwards[0]!.to).toBe(env.SECURITY_FORWARD_TO);

    // Restore the table for subsequent tests.
    await applySql(migration0010);
  });

  it('row still exists even when the auto-reply send fails', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'Bug',
    });
    msg.replyError = new Error('email send sabotaged');

    await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));

    // Row exists; acked_at is NULL because reply failed — operator
    // can ack manually.
    const row = await env.DB.prepare(
      'SELECT reference, acked_at FROM security_reports',
    ).first<{ reference: string; acked_at: string | null }>();
    expect(row).not.toBeNull();
    expect(row!.reference).toBe('SR-2026-0001');
    expect(row!.acked_at).toBeNull();

    // Forward still went out — the lifeline must not be skipped.
    expect(msg.recordedForwards).toHaveLength(1);
  });

  it('handles a forward failure without throwing', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'Bug',
    });
    msg.forwardError = new Error('routing dead');

    // Must not throw — Email Routing bounces the original on Worker
    // exception, which is exactly the failure mode we want to avoid.
    await expect(
      handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z')),
    ).resolves.toBeUndefined();

    // Row + reply still happened.
    const row = await env.DB.prepare('SELECT acked_at FROM security_reports').first<{
      acked_at: string | null;
    }>();
    expect(row!.acked_at).not.toBeNull();
    expect(msg.recordedReplies).toHaveLength(1);
  });

  it('handles a null Subject header gracefully', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: null,
    });

    await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));

    const row = await env.DB.prepare(
      'SELECT subject, urgent FROM security_reports',
    ).first<{ subject: string | null; urgent: number }>();
    expect(row!.subject).toBeNull();
    expect(row!.urgent).toBe(0);
    expect(msg.recordedReplies[0]!.subject).toBe('Re: your security report');
  });
});

describe('handleInboundEmail — reference allocation', () => {
  it('issues SR-YYYY-NNNN with year from the supplied clock', async () => {
    const msg = makeInboundMessage({
      from: 'reporter@example.com',
      subject: 'first',
    });
    // Year-end edge: pin the clock to 2027-01-01 00:00:00Z so we know
    // the year-relative counter restarted regardless of host clock.
    const now = new Date('2027-01-01T00:00:00.000Z');

    await handleInboundEmail(msg, env, now);

    const row = await env.DB.prepare('SELECT reference FROM security_reports').first<{
      reference: string;
    }>();
    expect(row!.reference).toBe('SR-2027-0001');
  });

  it('increments the counter within the same year', async () => {
    for (let i = 0; i < 3; i++) {
      const msg = makeInboundMessage({
        from: `r${i}@example.com`,
        subject: `report ${i}`,
      });
      await handleInboundEmail(msg, env, new Date('2026-05-15T12:00:00.000Z'));
    }
    const rows = await env.DB.prepare(
      'SELECT reference FROM security_reports ORDER BY id ASC',
    ).all<{ reference: string }>();
    expect(rows.results!.map((r) => r.reference)).toEqual([
      'SR-2026-0001',
      'SR-2026-0002',
      'SR-2026-0003',
    ]);
  });

  it('restarts the counter at NNNN=0001 in a new year', async () => {
    // One report in 2026...
    await handleInboundEmail(
      makeInboundMessage({ from: 'a@example.com', subject: 'a' }),
      env,
      new Date('2026-12-31T23:59:00.000Z'),
    );
    // ...then one in 2027.
    await handleInboundEmail(
      makeInboundMessage({ from: 'b@example.com', subject: 'b' }),
      env,
      new Date('2027-01-01T00:01:00.000Z'),
    );
    const rows = await env.DB.prepare(
      'SELECT reference FROM security_reports ORDER BY id ASC',
    ).all<{ reference: string }>();
    expect(rows.results!.map((r) => r.reference)).toEqual([
      'SR-2026-0001',
      'SR-2027-0001',
    ]);
  });
});
