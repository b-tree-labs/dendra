// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { cloudflareTest } from '@cloudflare/vitest-pool-workers';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [
    cloudflareTest({
      main: './src/index.ts',
      singleWorker: true,
      isolatedStorage: false,
      miniflare: {
        compatibilityDate: '2026-04-01',
        compatibilityFlags: ['nodejs_compat'],
        d1Databases: ['DB'],
        bindings: {
          ENVIRONMENT: 'test',
          API_KEY_PEPPER: 'test-pepper-32-bytes-of-pseudo-entropy-yo', // pragma: allowlist secret
          DASHBOARD_SERVICE_TOKEN: 'test-service-token-for-dashboard', // pragma: allowlist secret
          STRIPE_SECRET_KEY: 'sk_test_dummy', // pragma: allowlist secret
          STRIPE_WEBHOOK_SECRET: 'whsec_dummy', // pragma: allowlist secret
          // Deterministic Ed25519 32-byte private key (hex) for tests.
          // Real keys are generated per-env via scripts/generate-license-key.ts.
          LICENSE_SIGNING_PRIVATE_KEY:
            '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef', // pragma: allowlist secret
          // Rate-limiter bindings (DEVICE_CODE_LIMIT / DEVICE_TOKEN_LIMIT)
          // are intentionally omitted: miniflare doesn't implement Workers
          // Rate Limiting, and the handlers fail open when the binding is
          // absent (see passesRateLimit() in device.ts).
        },
      },
    }),
  ],
});
