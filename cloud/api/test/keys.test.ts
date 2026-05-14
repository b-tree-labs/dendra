// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { describe, it, expect } from 'vitest';
import { generateKey, hashKey, parseBearer } from '../src/keys';

const PEPPER = 'test-pepper-32-bytes-of-pseudo-entropy-yo';

describe('generateKey', () => {
  it('produces prul_live_-prefixed plaintext with 32 base62 chars', async () => {
    const k = await generateKey(PEPPER, 'live');
    expect(k.plaintext).toMatch(/^prul_live_[A-Za-z0-9]{32}$/);
    expect(k.prefix.length).toBe(8);
    expect(k.suffix.length).toBe(4);
  });

  it('produces prul_test_ prefix in test mode', async () => {
    const k = await generateKey(PEPPER, 'test');
    expect(k.plaintext).toMatch(/^prul_test_[A-Za-z0-9]{32}$/);
  });

  it('hash is deterministic given the same plaintext + pepper', async () => {
    const k = await generateKey(PEPPER);
    const h2 = await hashKey(k.plaintext, PEPPER);
    expect(k.hash).toBe(h2);
  });

  it('hash differs across pepper values', async () => {
    const k = await generateKey(PEPPER);
    const h2 = await hashKey(k.plaintext, 'different-pepper');
    expect(k.hash).not.toBe(h2);
  });

  it('hash is 64 hex chars (SHA-256 → 32 bytes → 64 hex)', async () => {
    const k = await generateKey(PEPPER);
    expect(k.hash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('successive calls produce different keys', async () => {
    const a = await generateKey(PEPPER);
    const b = await generateKey(PEPPER);
    expect(a.plaintext).not.toBe(b.plaintext);
    expect(a.hash).not.toBe(b.hash);
  });
});

describe('parseBearer', () => {
  it('extracts prul_live_… from a well-formed header', () => {
    const k = 'prul_live_abcdefghijklmnopqrstuvwxyz12345A'; // pragma: allowlist secret
    expect(parseBearer(`Bearer ${k}`)).toBe(k);
  });

  it('extracts prul_test_… too', () => {
    const k = 'prul_test_abcdefghijklmnopqrstuvwxyz12345A'; // pragma: allowlist secret
    expect(parseBearer(`Bearer ${k}`)).toBe(k);
  });

  it('rejects null', () => {
    expect(parseBearer(null)).toBeNull();
  });

  it('rejects no Bearer prefix', () => {
    expect(parseBearer('prul_live_abcdefghijklmnopqrstuvwxyz12345A')).toBeNull(); // pragma: allowlist secret
  });

  it('rejects wrong prefix', () => {
    expect(parseBearer('Bearer sk_live_abcdefghijklmnopqrstuvwxyz12345A')).toBeNull(); // pragma: allowlist secret
  });

  it('rejects wrong length', () => {
    expect(parseBearer('Bearer prul_live_short')).toBeNull();
  });

  it('rejects non-base62 chars', () => {
    expect(parseBearer('Bearer prul_live_+++++++++++++++++++++++++++++++A')).toBeNull();
  });

  it('tolerates extra whitespace around the header', () => {
    const k = 'prul_live_abcdefghijklmnopqrstuvwxyz12345A'; // pragma: allowlist secret
    expect(parseBearer(`  Bearer ${k}  `)).toBe(k);
  });
});
