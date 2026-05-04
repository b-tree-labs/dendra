// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Type augmentation for the cloudflare:test virtual env. The actual
// bindings are configured in vitest.config.ts; this file just teaches
// TypeScript what shape they have.

declare module 'cloudflare:test' {
  interface ProvidedEnv {
    DB: D1Database;
    ENVIRONMENT: string;
    API_KEY_PEPPER: string;
    DASHBOARD_SERVICE_TOKEN: string;
    STRIPE_SECRET_KEY: string;
    STRIPE_WEBHOOK_SECRET: string;
    LICENSE_SIGNING_PRIVATE_KEY: string;
  }
}

declare module '*.sql?raw' {
  const content: string;
  export default content;
}
