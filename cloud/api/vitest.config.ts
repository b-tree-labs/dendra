// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { defineWorkersConfig } from '@cloudflare/vitest-pool-workers/config';

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        main: './src/index.ts',
        singleWorker: true,
        isolatedStorage: false,
        miniflare: {
          compatibilityDate: '2026-04-01',
          compatibilityFlags: ['nodejs_compat'],
          d1Databases: ['DB'],
          bindings: {
            ENVIRONMENT: 'test',
            API_KEY_PEPPER: 'test-pepper-32-bytes-of-pseudo-entropy-yo',
            DASHBOARD_SERVICE_TOKEN: 'test-service-token-for-dashboard',
          },
        },
      },
    },
  },
});
