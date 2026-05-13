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
        // Pinned to the newest date the bundled miniflare runtime
        // supports — wrangler.toml uses 2026-05-13 for the deployed
        // Worker, but the in-process miniflare in vitest-pool-workers
        // ships its own workerd binary which lags by a few weeks.
        // Matches the cloud/api/ pattern.
        compatibilityDate: '2026-04-01',
        compatibilityFlags: ['nodejs_compat'],
        d1Databases: ['DB'],
        bindings: {
          ENVIRONMENT: 'test',
          // Deterministic forward address — assertions key off this in
          // test/email_handler.test.ts and test/cron_handler.test.ts.
          SECURITY_FORWARD_TO: 'ops@example.test',
          SECURITY_FROM_ADDRESS: 'security@b-treeventures.test',
        },
      },
    }),
  ],
});
