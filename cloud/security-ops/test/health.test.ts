// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Tiny /health probe test. The security-ops Worker is mostly invoked
// via the email + scheduled handlers; /health exists so smoke tests
// + Better Stack heartbeats can verify it deployed cleanly.

import { describe, it, expect } from 'vitest';
import { SELF } from 'cloudflare:test';

describe('GET /health', () => {
  it('returns 200 with service identity', async () => {
    const res = await SELF.fetch('https://security-ops.test/health');
    expect(res.status).toBe(200);
    const body = await res.json<{ status: string; service: string; environment: string }>();
    expect(body.status).toBe('ok');
    expect(body.service).toBe('postrule-security-ops');
    expect(body.environment).toBe('test');
  });

  it('returns 404 for unknown paths', async () => {
    const res = await SELF.fetch('https://security-ops.test/nope');
    expect(res.status).toBe(404);
  });
});
