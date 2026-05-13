// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Type augmentation for the cloudflare:test virtual env, mirroring the
// bindings declared in vitest.config.mts. Same pattern as cloud/api/.
//
// The triple-slash reference pulls in the `env` / `SELF` exports from
// the @cloudflare/vitest-pool-workers package — they aren't exposed
// through `types` because the package routes its module-aware types
// at the `./types` subpath rather than the package root.

/// <reference path="../node_modules/@cloudflare/vitest-pool-workers/types/cloudflare-test.d.ts" />

// Ambient — no top-level imports/exports so these declarations are
// global. The `declare global` form requires the file to be a
// module, which would break the `declare module '*.sql?raw'`
// wildcard; ambient script files are the cleaner shape here.

declare namespace Cloudflare {
  interface Env {
    DB: D1Database;
    ENVIRONMENT: string;
    SECURITY_FORWARD_TO: string;
    SECURITY_FROM_ADDRESS: string;
  }
}

declare module '*.sql?raw' {
  const content: string;
  export default content;
}
