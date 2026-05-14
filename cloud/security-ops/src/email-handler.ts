// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Inbound email handler — every message routed to
// security@postrule.ai lands here. Pipeline:
//
//   1. Parse From + Subject. Detect URGENT in the subject.
//   2. Allocate a SR-YYYY-NNNN reference and INSERT into D1.
//   3. message.reply() with the auto-ack body. Stamp acked_at.
//   4. message.forward() the original to env.SECURITY_FORWARD_TO.
//   5. If urgent: sendOpsAlert() a separate "URGENT" notification.
//
// Failure handling: under no circumstances should the forward step be
// skipped. Each numbered step is wrapped in its own try/catch; a
// failure in (2) or (3) does NOT short-circuit (4). The worst-case
// failure mode is "report received but operator never sees it" —
// the forward is the lifeline. Auto-ack failing is recoverable (op
// can ack manually); D1 insert failing is loggable.

import type { Env } from './env';
import { allocateReference, insertReport, markAcked } from './reports';
import { sendOpsAlert } from './mailer';

/** Body of the automated reply sent to the reporter. */
export function buildAutoReplyBody(reference: string): string {
  return [
    "Thanks — we've received your report. A human will triage within",
    'five business days. Reference: ' + reference + '.',
    '',
    'If this is critical (active exploit, data exfiltration in',
    'progress, etc.), reply with the word URGENT in the subject line',
    'to escalate.',
    '',
    'This is an automated acknowledgement. The next message from this',
    'address will be from a human operator.',
    '',
    '— B-Tree Labs Security',
  ].join('\n');
}

/** Subject line of the automated reply — prefixed Re: per RFC convention. */
export function buildAutoReplySubject(originalSubject: string | null): string {
  const subj = (originalSubject ?? '').trim();
  if (!subj) return 'Re: your security report';
  // Don't double-prefix; some clients already include Re:.
  if (/^re:/i.test(subj)) return subj;
  return 'Re: ' + subj;
}

export function isUrgent(subject: string | null | undefined): boolean {
  if (!subject) return false;
  return /\burgent\b/i.test(subject);
}

/**
 * Cloudflare's ForwardableEmailMessage interface is shipped via
 * @cloudflare/workers-types; we declare a structural shape here so the
 * tests can construct a fake without importing the runtime types.
 */
export interface InboundMessage {
  from: string;
  to: string;
  headers: { get(name: string): string | null };
  // raw / rawSize / setReject are present on the real type but we
  // don't use them here.
  reply(reply: EmailReplyInit): Promise<void>;
  forward(to: string, headers?: Headers): Promise<void>;
}

export interface EmailReplyInit {
  subject?: string;
  contentType?: string;
  body?: string;
}

/**
 * Handle one inbound email. Exposed as a free function so the test
 * harness can call it directly with a synthetic message; the Worker's
 * exported `email` handler is a thin shim in src/index.ts.
 */
export async function handleInboundEmail(
  message: InboundMessage,
  env: Env,
  now: Date = new Date(),
): Promise<void> {
  const subject = message.headers.get('subject');
  const sender = message.from;
  const urgent = isUrgent(subject);
  const receivedAt = now.toISOString();
  const year = now.getUTCFullYear();

  // If the D1 insert fails, we still need to forward the email —
  // losing visibility into a security report is the worst-case failure
  // mode. Track success in `reference` and continue down the pipeline
  // either way.
  let reference: string | null = null;
  let rowId: number | null = null;
  try {
    reference = await allocateReference(env, year);
    rowId = await insertReport(env, {
      reference,
      receivedAt,
      sender,
      subject,
      urgent,
    });
  } catch (err) {
    console.error(
      JSON.stringify({
        level: 'error',
        msg: 'security_report_insert_failed',
        sender,
        subject,
        error: err instanceof Error ? err.message : String(err),
        env: env.ENVIRONMENT,
      }),
    );
    // reference may have been allocated but insert failed; we'll still
    // try to ack with whatever reference we have (or a placeholder).
  }

  // If the insert failed, send the ack with a placeholder reference
  // anyway — the published SLA is 72h-ack, and silence is worse than
  // "ack with placeholder reference, we'll follow up".
  const ackReference = reference ?? 'SR-PENDING';
  try {
    await message.reply({
      subject: buildAutoReplySubject(subject),
      contentType: 'text/plain',
      body: buildAutoReplyBody(ackReference),
    });
    if (rowId !== null) {
      try {
        await markAcked(env, rowId, new Date().toISOString());
      } catch (err) {
        // Row exists but couldn't be stamped — operator can fix this
        // manually. Log and continue.
        console.error(
          JSON.stringify({
            level: 'error',
            msg: 'security_report_mark_acked_failed',
            row_id: rowId,
            error: err instanceof Error ? err.message : String(err),
            env: env.ENVIRONMENT,
          }),
        );
      }
    }
  } catch (err) {
    console.error(
      JSON.stringify({
        level: 'error',
        msg: 'security_report_auto_reply_failed',
        reference: ackReference,
        sender,
        error: err instanceof Error ? err.message : String(err),
        env: env.ENVIRONMENT,
      }),
    );
    // Continue — the forward must still go out.
  }

  // The forward is the lifeline: even if everything above failed, the
  // operator must see the raw report. Email Routing would have done
  // this anyway; routing through the Worker lets us order ack-then-
  // forward so the reporter sees the ack arrive first.
  try {
    await message.forward(env.SECURITY_FORWARD_TO);
  } catch (err) {
    console.error(
      JSON.stringify({
        level: 'error',
        msg: 'security_report_forward_failed',
        reference: ackReference,
        sender,
        error: err instanceof Error ? err.message : String(err),
        env: env.ENVIRONMENT,
      }),
    );
    // Don't rethrow — Email Routing's default behavior on Worker
    // exception is to bounce the original mail, which we explicitly
    // do NOT want. Logging plus the inserted D1 row is sufficient
    // for the operator to recover.
  }

  // Urgent escalation is a separate message from the forward — a
  // high-signal "[URGENT]" subject so a vacation-mode filter doesn't
  // bury it under the routine forward.
  if (urgent) {
    try {
      await sendOpsAlert(env, {
        subject: '[URGENT] security report received: ' + ackReference,
        text: [
          'URGENT security report received.',
          '',
          'Reference: ' + ackReference,
          'Sender:    ' + sender,
          'Subject:   ' + (subject ?? '<no subject>'),
          'Received:  ' + receivedAt,
          '',
          'The original message has been forwarded separately to',
          env.SECURITY_FORWARD_TO + '.',
          '',
          '— postrule-security-ops',
        ].join('\n'),
      });
    } catch (err) {
      console.error(
        JSON.stringify({
          level: 'error',
          msg: 'security_report_urgent_alert_failed',
          reference: ackReference,
          error: err instanceof Error ? err.message : String(err),
          env: env.ENVIRONMENT,
        }),
      );
    }
  }
}
