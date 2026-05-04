// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { describe, it, expect, beforeAll } from 'vitest';
import { env, SELF } from 'cloudflare:test';
import migration0001 from '../../collector/migrations/0001_initial.sql?raw';
import migration0002 from '../../collector/migrations/0002_leads.sql?raw';
import migration0003 from '../../collector/migrations/0003_saas.sql?raw';
import migration0004 from '../../collector/migrations/0004_verdicts.sql?raw';
import { generateKeypair, signLicense, verifyLicense } from '../src/license';

const SERVICE_TOKEN = 'test-service-token-for-dashboard';
const BASE = 'https://api.test';

const adminHeaders = {
  'Content-Type': 'application/json',
  'X-Dashboard-Token': SERVICE_TOKEN,
};

async function applySql(sql: string) {
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

beforeAll(async () => {
  await applySql(migration0001);
  await applySql(migration0002);
  await applySql(migration0003);
  await applySql(migration0004);
});

describe('license signing primitives', () => {
  it('generateKeypair returns 32-byte hex strings', async () => {
    const { privateKeyHex, publicKeyHex } = await generateKeypair();
    expect(privateKeyHex).toMatch(/^[0-9a-f]{64}$/);
    expect(publicKeyHex).toMatch(/^[0-9a-f]{64}$/);
    expect(privateKeyHex).not.toBe(publicKeyHex);
  });

  it('signLicense + verifyLicense round-trip', async () => {
    const { privateKeyHex, publicKeyHex } = await generateKeypair();
    const { token, claims } = await signLicense({
      privateKeyHex,
      user_id: 42,
      tier: 'business',
      account_hash: 'abc123',
      ttlSeconds: 3600,
      max_seats: 10,
    });
    expect(token.split('.').length).toBe(3);

    const verified = await verifyLicense(token, publicKeyHex);
    expect(verified.sub).toBe('42');
    expect(verified.tier).toBe('business');
    expect(verified.account_hash).toBe('abc123');
    expect(verified.max_seats).toBe(10);
    expect(verified.license_id).toBe(claims.license_id);
  });

  it('verifyLicense rejects a tampered payload', async () => {
    const { privateKeyHex, publicKeyHex } = await generateKeypair();
    const { token } = await signLicense({
      privateKeyHex,
      user_id: 1,
      tier: 'business',
      account_hash: 'h',
      ttlSeconds: 3600,
    });
    const parts = token.split('.');
    const tampered = `${parts[0]}.${'X' + parts[1]!.slice(1)}.${parts[2]}`;
    await expect(verifyLicense(tampered, publicKeyHex)).rejects.toThrow(/invalid_signature/);
  });

  it('verifyLicense rejects a wrong public key', async () => {
    const a = await generateKeypair();
    const b = await generateKeypair();
    const { token } = await signLicense({
      privateKeyHex: a.privateKeyHex,
      user_id: 1,
      tier: 'business',
      account_hash: 'h',
      ttlSeconds: 3600,
    });
    await expect(verifyLicense(token, b.publicKeyHex)).rejects.toThrow(/invalid_signature/);
  });

  it('verifyLicense rejects an expired token', async () => {
    const { privateKeyHex, publicKeyHex } = await generateKeypair();
    // ttl negative → exp is in the past.
    const { token } = await signLicense({
      privateKeyHex,
      user_id: 1,
      tier: 'business',
      account_hash: 'h',
      ttlSeconds: -10,
    });
    await expect(verifyLicense(token, publicKeyHex)).rejects.toThrow(/expired/);
  });
});

describe('POST /admin/licenses/issue', () => {
  let userId: number;

  beforeAll(async () => {
    const u = await SELF.fetch(`${BASE}/admin/users`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ clerk_user_id: 'lic_user', email: 'lic@example.com' }),
    });
    userId = (await u.json<{ user_id: number }>()).user_id;
    await env.DB.prepare(`UPDATE users SET current_tier='business' WHERE id=?`)
      .bind(userId)
      .run();
  });

  it('issues a token for a known user', async () => {
    const res = await SELF.fetch(`${BASE}/admin/licenses/issue`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: userId, ttl_days: 90, max_seats: 5 }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{
      token: string;
      claims: { tier: string; sub: string; max_seats: number | null };
    }>();
    expect(body.token.split('.').length).toBe(3);
    expect(body.claims.tier).toBe('business');
    expect(body.claims.sub).toBe(String(userId));
    expect(body.claims.max_seats).toBe(5);
  });

  it('rejects unknown user', async () => {
    const res = await SELF.fetch(`${BASE}/admin/licenses/issue`, {
      method: 'POST',
      headers: adminHeaders,
      body: JSON.stringify({ user_id: 99999 }),
    });
    expect(res.status).toBe(404);
  });

  it('rejects without service token', async () => {
    const res = await SELF.fetch(`${BASE}/admin/licenses/issue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });
    expect(res.status).toBe(401);
  });
});
