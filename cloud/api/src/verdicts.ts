// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/verdicts handler — record a paired-correctness outcome.
//
// Contract:
//   POST /v1/verdicts
//   Authorization: Bearer dndr_live_…
//   Content-Type: application/json
//   {
//     "switch_name": "intent_classifier",     // required, ≤64 chars
//     "phase": "P3",                           // optional, P0–P5
//     "rule_correct": true,                    // optional bool
//     "model_correct": false,                  // optional bool
//     "ml_correct": true,                      // optional bool
//     "ground_truth": "book_flight",           // optional, ≤512 chars
//     "request_id": "req_abc123",              // optional, ≤128 chars; idempotency
//     "metadata": { "user_segment": "…" }      // optional, ≤4 KB JSON
//   }
//
// Returns:
//   201 Created  { "id": 42, "accepted_at": "..." }
//   200 OK       { "id": <existing>, "accepted_at": "...", "duplicate": true }   on idempotent retry
//   400          { "error": "<reason>" }                                          on validation failure

import type { Context } from 'hono';
import type { ApiEnv, AuthContext } from './auth';

const SWITCH_NAME_RE = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
const PHASES = new Set(['P0', 'P1', 'P2', 'P3', 'P4', 'P5']);
const MAX_GROUND_TRUTH = 512;
const MAX_REQUEST_ID = 128;
const MAX_METADATA_BYTES = 4096;

interface VerdictBody {
  switch_name?: unknown;
  phase?: unknown;
  rule_correct?: unknown;
  model_correct?: unknown;
  ml_correct?: unknown;
  ground_truth?: unknown;
  request_id?: unknown;
  metadata?: unknown;
}

interface ParsedVerdict {
  switch_name: string;
  phase: string | null;
  rule_correct: number | null;
  model_correct: number | null;
  ml_correct: number | null;
  ground_truth: string | null;
  request_id: string | null;
  metadata_json: string | null;
}

function validate(body: VerdictBody): { ok: true; v: ParsedVerdict } | { ok: false; error: string } {
  if (typeof body.switch_name !== 'string' || !SWITCH_NAME_RE.test(body.switch_name)) {
    return { ok: false, error: 'switch_name must match [A-Za-z][A-Za-z0-9_.-]{0,63}' };
  }

  let phase: string | null = null;
  if (body.phase !== undefined && body.phase !== null) {
    if (typeof body.phase !== 'string' || !PHASES.has(body.phase)) {
      return { ok: false, error: 'phase must be one of P0..P5' };
    }
    phase = body.phase;
  }

  function asBool(v: unknown, name: string): { ok: true; n: number | null } | { ok: false; error: string } {
    if (v === undefined || v === null) return { ok: true, n: null };
    if (typeof v !== 'boolean') return { ok: false, error: `${name} must be boolean if present` };
    return { ok: true, n: v ? 1 : 0 };
  }

  const rc = asBool(body.rule_correct, 'rule_correct');
  if (!rc.ok) return rc;
  const mc = asBool(body.model_correct, 'model_correct');
  if (!mc.ok) return mc;
  const hc = asBool(body.ml_correct, 'ml_correct');
  if (!hc.ok) return hc;

  let ground_truth: string | null = null;
  if (body.ground_truth !== undefined && body.ground_truth !== null) {
    if (typeof body.ground_truth !== 'string') {
      return { ok: false, error: 'ground_truth must be string if present' };
    }
    if (body.ground_truth.length > MAX_GROUND_TRUTH) {
      return { ok: false, error: `ground_truth exceeds ${MAX_GROUND_TRUTH} chars` };
    }
    ground_truth = body.ground_truth;
  }

  let request_id: string | null = null;
  if (body.request_id !== undefined && body.request_id !== null) {
    if (typeof body.request_id !== 'string') {
      return { ok: false, error: 'request_id must be string if present' };
    }
    if (body.request_id.length === 0 || body.request_id.length > MAX_REQUEST_ID) {
      return { ok: false, error: `request_id length must be 1..${MAX_REQUEST_ID}` };
    }
    request_id = body.request_id;
  }

  let metadata_json: string | null = null;
  if (body.metadata !== undefined && body.metadata !== null) {
    if (typeof body.metadata !== 'object' || Array.isArray(body.metadata)) {
      return { ok: false, error: 'metadata must be a JSON object if present' };
    }
    const serialized = JSON.stringify(body.metadata);
    if (serialized.length > MAX_METADATA_BYTES) {
      return { ok: false, error: `metadata exceeds ${MAX_METADATA_BYTES} bytes serialized` };
    }
    metadata_json = serialized;
  }

  return {
    ok: true,
    v: {
      switch_name: body.switch_name,
      phase,
      rule_correct: rc.n,
      model_correct: mc.n,
      ml_correct: hc.n,
      ground_truth,
      request_id,
      metadata_json,
    },
  };
}

export async function recordVerdictHandler(c: Context<{ Bindings: ApiEnv }>) {
  const auth = c.get('auth') as AuthContext | undefined;
  if (!auth) {
    // usageMiddleware should have established auth, but be defensive.
    return c.json({ error: 'unauthorized' }, 401);
  }

  const body = (await c.req.json().catch(() => null)) as VerdictBody | null;
  if (!body || typeof body !== 'object') {
    return c.json({ error: 'invalid_json' }, 400);
  }

  const parsed = validate(body);
  if (!parsed.ok) {
    return c.json({ error: parsed.error }, 400);
  }
  const v = parsed.v;

  // Idempotency: if request_id already exists for this key, return the
  // original row's id rather than insert a duplicate.
  if (v.request_id) {
    const existing = await c.env.DB.prepare(
      `SELECT id, created_at FROM verdicts
        WHERE api_key_id = ? AND request_id = ? LIMIT 1`,
    )
      .bind(auth.api_key_id, v.request_id)
      .first<{ id: number; created_at: string }>();
    if (existing) {
      return c.json({ id: existing.id, accepted_at: existing.created_at, duplicate: true });
    }
  }

  const result = await c.env.DB.prepare(
    `INSERT INTO verdicts
       (api_key_id, switch_name, phase, rule_correct, model_correct, ml_correct,
        ground_truth, request_id, metadata_json)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
     RETURNING id, created_at`,
  )
    .bind(
      auth.api_key_id,
      v.switch_name,
      v.phase,
      v.rule_correct,
      v.model_correct,
      v.ml_correct,
      v.ground_truth,
      v.request_id,
      v.metadata_json,
    )
    .first<{ id: number; created_at: string }>();

  if (!result) {
    return c.json({ error: 'insert_failed' }, 500);
  }

  // Auto-unarchive on revival. If this (user, switch) was archived (the
  // customer commented out the @ml_switch and clicked archive on the
  // dashboard), a fresh verdict means the function is alive again —
  // remove the archive row so the switch resurfaces in the default
  // roster view. Single indexed DELETE; no-op when the row is absent.
  //
  // This does NOT affect verdict counting / tier-cap enforcement —
  // usageMiddleware has already incremented the counter by this point.
  await c.env.DB.prepare(
    `DELETE FROM switch_archives
      WHERE user_id = ? AND switch_name = ?`,
  )
    .bind(auth.user_id, v.switch_name)
    .run();

  return c.json({ id: result.id, accepted_at: result.created_at }, 201);
}
