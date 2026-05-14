// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /v1/registry/contribute, /v1/team-corpus, /v1/team-corpus/:id handlers.
//
// Backs the Python `postrule.cloud.registry` and `postrule.cloud.team_corpus`
// modules. All routes are Bearer-authenticated via the standard auth
// middleware mounted in index.ts.
//
// Storage: D1 tables `team_corpora` and `registry_contributions`
// (migration 0005_cloud_features.sql).

import type { Context } from 'hono';
import type { ApiEnv } from './auth';
import { requireAuth } from './auth';

const TEAM_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const MAX_TEAM_PAYLOAD_BYTES = 16 * 1024;
const MAX_REGISTRY_PAYLOAD_BYTES = 32 * 1024;

// Conservative identifier-key set; mirrors `postrule.cloud.registry._IDENTIFYING_KEYS`.
// Server-side check rejects any contribution where these keys appear at
// any nesting level — defense in depth against a buggy or malicious client.
const IDENTIFYING_KEYS = new Set([
  'author',
  'email',
  'user',
  'username',
  'owner',
  'repo_url',
  'remote_url',
  'absolute_path',
  'abs_path',
  'host',
  'hostname',
  'machine_id',
]);

function containsIdentifyingKey(obj: unknown): boolean {
  if (Array.isArray(obj)) return obj.some(containsIdentifyingKey);
  if (obj && typeof obj === 'object') {
    for (const k of Object.keys(obj)) {
      if (IDENTIFYING_KEYS.has(k)) return true;
      if (containsIdentifyingKey((obj as Record<string, unknown>)[k])) return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// POST /v1/team-corpus
//
// Body: { team_id: "acme-eng", corpus: { ...arbitrary JSON... } }
// Returns: { share_url: "https://api.postrule.ai/v1/team-corpus/acme-eng" }
// ---------------------------------------------------------------------------
export async function shareCorpusHandler(c: Context<{ Bindings: ApiEnv }>) {
  const userId = requireAuth(c).user_id;

  let body: { team_id?: unknown; corpus?: unknown };
  try {
    body = (await c.req.json()) as typeof body;
  } catch {
    return c.json({ error: 'invalid_json' }, 400);
  }

  if (typeof body.team_id !== 'string' || !TEAM_ID_RE.test(body.team_id)) {
    return c.json({ error: 'team_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}' }, 400);
  }
  if (!body.corpus || typeof body.corpus !== 'object') {
    return c.json({ error: 'corpus must be a JSON object' }, 400);
  }

  const payload = JSON.stringify(body.corpus);
  if (new TextEncoder().encode(payload).byteLength > MAX_TEAM_PAYLOAD_BYTES) {
    return c.json({ error: 'corpus exceeds 16 KB' }, 400);
  }

  await c.env.DB.prepare(
    'INSERT INTO team_corpora (user_id, team_id, payload_json) VALUES (?, ?, ?)',
  )
    .bind(userId, body.team_id, payload)
    .run();

  const origin = new URL(c.req.url).origin;
  return c.json({ share_url: `${origin}/v1/team-corpus/${body.team_id}` }, 201);
}

// ---------------------------------------------------------------------------
// GET /v1/team-corpus/:id
//
// Returns: the most recent corpus uploaded for this team_id, as raw JSON.
// 404 if no corpus has been shared under that team_id yet.
// ---------------------------------------------------------------------------
export async function fetchCorpusHandler(c: Context<{ Bindings: ApiEnv }>) {
  const teamId = c.req.param('id');
  if (!teamId || !TEAM_ID_RE.test(teamId)) {
    return c.json({ error: 'team_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}' }, 400);
  }

  const row = await c.env.DB.prepare(
    'SELECT payload_json FROM team_corpora WHERE team_id = ? ORDER BY id DESC LIMIT 1',
  )
    .bind(teamId)
    .first<{ payload_json: string }>();

  if (!row) {
    return c.json({ error: 'not_found' }, 404);
  }

  try {
    return c.json(JSON.parse(row.payload_json));
  } catch {
    // Should never happen — we JSON-stringified the value at insert time.
    return c.json({ error: 'corrupt_payload' }, 500);
  }
}

// ---------------------------------------------------------------------------
// POST /v1/registry/contribute
//
// Body: anonymized corpus dict. Server validates that no identifying
// keys (author/email/host/etc.) are present at any nesting level —
// defense in depth on top of the client-side `anonymize` pass.
// Returns: { id: <row id>, accepted_at: "..." }
// ---------------------------------------------------------------------------
export async function contributeHandler(c: Context<{ Bindings: ApiEnv }>) {
  const userId = requireAuth(c).user_id;

  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'invalid_json' }, 400);
  }

  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return c.json({ error: 'corpus must be a JSON object' }, 400);
  }

  if (containsIdentifyingKey(body)) {
    return c.json(
      {
        error: 'corpus contains identifying keys; run postrule.cloud.registry.anonymize first',
      },
      400,
    );
  }

  const payload = JSON.stringify(body);
  if (new TextEncoder().encode(payload).byteLength > MAX_REGISTRY_PAYLOAD_BYTES) {
    return c.json({ error: 'corpus exceeds 32 KB' }, 400);
  }

  const result = await c.env.DB.prepare(
    'INSERT INTO registry_contributions (user_id, payload_json) VALUES (?, ?) RETURNING id, created_at',
  )
    .bind(userId, payload)
    .first<{ id: number; created_at: string }>();

  return c.json(
    {
      id: result?.id,
      accepted_at: result?.created_at,
    },
    201,
  );
}
