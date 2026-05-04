// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Server-side client for the Dendra api Worker's /admin endpoints.
// Used by the dashboard's Clerk-authenticated route handlers; never
// runs on the client (the service token must stay on the server).

const API_BASE = process.env.DENDRA_API_BASE_URL ?? 'https://staging-api.dendra.run';
const SERVICE_TOKEN = process.env.DENDRA_API_SERVICE_TOKEN;

function assertServerOnly() {
  if (typeof window !== 'undefined') {
    throw new Error('dendra-api lib is server-only — service token must not leak to the client');
  }
  if (!SERVICE_TOKEN) {
    throw new Error('DENDRA_API_SERVICE_TOKEN env var is not set');
  }
}

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  assertServerOnly();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Dashboard-Token': SERVICE_TOKEN!,
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`dendra-api ${path} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface DendraUser {
  user_id: number;
  tier: 'free' | 'pro' | 'scale' | 'business';
  account_hash: string;
}

export interface ApiKeyMeta {
  id: number;
  key_prefix: string;
  key_suffix: string;
  name: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface IssuedKey {
  id: number;
  plaintext: string;
  prefix: string;
  suffix: string;
  name: string | null;
  environment: 'live' | 'test';
  created_at: string;
}

/** Idempotent — call on every authenticated request. Returns the user's row id. */
export async function upsertUser(clerkUserId: string, email: string): Promise<DendraUser> {
  return adminFetch<DendraUser>('/admin/users', {
    method: 'POST',
    body: JSON.stringify({ clerk_user_id: clerkUserId, email }),
  });
}

export async function listKeys(userId: number): Promise<ApiKeyMeta[]> {
  const r = await adminFetch<{ keys: ApiKeyMeta[] }>(`/admin/keys?user_id=${userId}`);
  return r.keys;
}

export async function issueKey(
  userId: number,
  name: string | null = null,
  environment: 'live' | 'test' = 'live',
): Promise<IssuedKey> {
  return adminFetch<IssuedKey>('/admin/keys', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, name, environment }),
  });
}

export async function revokeKey(userId: number, keyId: number): Promise<void> {
  await adminFetch(`/admin/keys/${keyId}`, {
    method: 'DELETE',
    body: JSON.stringify({ user_id: userId }),
  });
}
