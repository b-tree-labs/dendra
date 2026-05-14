// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Shared scaffolding for the security-ops tests:
//
//   - applySql()             — splits a .sql migration file into
//                              statements and runs each through D1.
//   - resetTables()          — truncates security_reports between tests.
//   - makeInboundMessage()   — synthesizes a ForwardableEmailMessage-like
//                              object the email handler can consume,
//                              recording reply() / forward() calls so
//                              tests can assert on them.
//   - installMailChannelsStub() — replaces global fetch with a recorder
//                              the tests inspect (via mailRecord).

import { env } from 'cloudflare:test';
import type { InboundMessage, EmailReplyInit } from '../src/email-handler';

export async function applySql(sql: string): Promise<void> {
  const cleaned = sql
    .split('\n')
    .filter((l) => !l.trim().startsWith('--'))
    .join('\n');
  const stmts = cleaned
    .split(/;\s*(?:\n|$)/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  for (const s of stmts) {
    try {
      await env.DB.prepare(s).run();
    } catch (e) {
      if (!String(e).includes('already exists')) throw e;
    }
  }
}

export async function resetTables(): Promise<void> {
  await env.DB.prepare('DELETE FROM security_reports').run();
  // sqlite_sequence is the AUTOINCREMENT bookkeeping table; resetting
  // it isn't strictly required but keeps row ids stable across tests.
  try {
    await env.DB.prepare("DELETE FROM sqlite_sequence WHERE name = 'security_reports'").run();
  } catch {
    // sqlite_sequence is created lazily on first AUTOINCREMENT insert.
    // If no row has been inserted yet, the table doesn't exist.
  }
}

export interface RecordedReply {
  subject: string | undefined;
  contentType: string | undefined;
  body: string | undefined;
}

export interface RecordedForward {
  to: string;
}

export interface FakeMessage extends InboundMessage {
  recordedReplies: RecordedReply[];
  recordedForwards: RecordedForward[];
  /** When non-null, reply() rejects with this. */
  replyError: Error | null;
  /** When non-null, forward() rejects with this. */
  forwardError: Error | null;
}

export function makeInboundMessage(args: {
  from: string;
  to?: string;
  subject?: string | null;
}): FakeMessage {
  const headers = new Map<string, string>();
  if (args.subject !== null && args.subject !== undefined) {
    headers.set('subject', args.subject);
  }
  const recordedReplies: RecordedReply[] = [];
  const recordedForwards: RecordedForward[] = [];
  const msg: FakeMessage = {
    from: args.from,
    to: args.to ?? 'security@dendra.run',
    headers: {
      get(name: string): string | null {
        return headers.get(name.toLowerCase()) ?? null;
      },
    },
    recordedReplies,
    recordedForwards,
    replyError: null,
    forwardError: null,
    async reply(reply: EmailReplyInit): Promise<void> {
      if (msg.replyError) throw msg.replyError;
      recordedReplies.push({
        subject: reply.subject,
        contentType: reply.contentType,
        body: reply.body,
      });
    },
    async forward(to: string): Promise<void> {
      if (msg.forwardError) throw msg.forwardError;
      recordedForwards.push({ to });
    },
  };
  return msg;
}

// ---------------------------------------------------------------------------
// MailChannels fetch stub
// ---------------------------------------------------------------------------
//
// The mailer module POSTs to https://api.mailchannels.net/tx/v1/send.
// In tests we replace globalThis.fetch with a recorder so we can
// assert on the (subject, to, body) without actually firing a request.

export interface RecordedMail {
  to: string;
  from: string;
  subject: string;
  text: string;
}

export interface MailStub {
  records: RecordedMail[];
  /** When set, the next .send() call rejects. */
  failNext: boolean;
  /** Restore the original fetch. Call in afterEach. */
  restore(): void;
}

export function installMailChannelsStub(): MailStub {
  const originalFetch = globalThis.fetch;
  const stub: MailStub = {
    records: [],
    failNext: false,
    restore() {
      globalThis.fetch = originalFetch;
    },
  };
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.includes('api.mailchannels.net')) {
      if (stub.failNext) {
        stub.failNext = false;
        return new Response('upstream boom', { status: 500 });
      }
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const to = body?.personalizations?.[0]?.to?.[0]?.email ?? '';
      const from = body?.from?.email ?? '';
      const subject = body?.subject ?? '';
      const text = body?.content?.[0]?.value ?? '';
      stub.records.push({ to, from, subject, text });
      return new Response('{"ok":true}', { status: 202 });
    }
    return originalFetch(input, init);
  }) as typeof fetch;
  return stub;
}
