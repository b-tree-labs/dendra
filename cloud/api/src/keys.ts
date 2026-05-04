// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// API key generation + verification.
//
// Format:  dndr_live_<32 base62 chars>   ← 32 chars × log2(62) ≈ 190 bits
//          dndr_test_<32 base62 chars>   ← sandbox, same shape
//
// Hashing: HMAC-SHA-256(pepper, full_key). NOT argon2id.
//
// Reasoning: argon2id is the right choice for low-entropy secrets
// (passwords) where attackers can grind candidates. API keys here are
// 190-bit random strings; pre-image attacks on SHA-256 require ≥2^128
// work. The pepper (server-side secret) defends against database leaks.
// HMAC-SHA-256 runs in <0.1ms on Workers; argon2id with the spec'd
// m=64MB doesn't fit the Workers per-request CPU budget at any tier.
// Spec deviation acknowledged in saas-launch-tech-spec, line 125–145.

const BASE62 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
const KEY_LEN = 32;

export type KeyEnvironment = 'live' | 'test';

export interface IssuedKey {
  /** Plaintext, returned to user ONCE at issuance. */
  plaintext: string;
  /** First 8 chars after the prefix — for dashboard display. */
  prefix: string;
  /** Last 4 chars — for dashboard display. */
  suffix: string;
  /** HMAC-SHA-256(pepper, plaintext) hex-encoded; what we store in D1. */
  hash: string;
}

/**
 * Generate a new API key. Crypto-grade randomness from
 * crypto.getRandomValues (Workers and Node both expose it).
 */
export async function generateKey(
  pepper: string,
  env: KeyEnvironment = 'live',
): Promise<IssuedKey> {
  const bytes = new Uint8Array(KEY_LEN);
  crypto.getRandomValues(bytes);
  const random = Array.from(bytes, (b) => BASE62[b % 62]).join('');
  const plaintext = `dndr_${env}_${random}`;
  const hash = await hashKey(plaintext, pepper);
  return {
    plaintext,
    prefix: random.slice(0, 8),
    suffix: random.slice(-4),
    hash,
  };
}

/**
 * Compute HMAC-SHA-256(pepper, key) → hex. Used for both issuance and
 * lookup. Deterministic so D1 lookup-by-hash works.
 */
export async function hashKey(plaintext: string, pepper: string): Promise<string> {
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    enc.encode(pepper),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', cryptoKey, enc.encode(plaintext));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Parse a Bearer token for shape validity. Returns the plaintext if
 * shape-valid, or null if malformed. Does NOT verify against the DB.
 */
export function parseBearer(authHeader: string | null): string | null {
  if (!authHeader) return null;
  const m = /^Bearer\s+(dndr_(live|test)_[A-Za-z0-9]{32})$/.exec(authHeader.trim());
  return m?.[1] ?? null;
}
