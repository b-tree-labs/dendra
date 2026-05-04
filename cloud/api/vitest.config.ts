// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1

import { defineWorkersConfig } from '@cloudflare/vitest-pool-workers/config';

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        singleWorker: true,
        miniflare: {
          compatibilityDate: '2026-04-01',
          compatibilityFlags: ['nodejs_compat'],
        },
      },
    },
  },
});
