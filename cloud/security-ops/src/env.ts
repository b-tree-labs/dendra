// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Worker environment binding shape. Mirrors the [vars] + [[d1_databases]]
// declared in wrangler.toml. Bindings absent from wrangler.toml (the
// SECURITY_FORWARD_TO secret) are typed required so the handler can
// fail fast at first use rather than silently mis-routing the mail.

export interface Env {
  /** D1 binding; same database as collector + api. */
  DB: D1Database;
  /** "staging" | "production" | "test". */
  ENVIRONMENT: string;
  /**
   * Destination for forwards of inbound reports + urgent / overdue
   * digests. Set post-deploy via:
   *   wrangler secret put SECURITY_FORWARD_TO --env production
   */
  SECURITY_FORWARD_TO: string;
  /**
   * From: address used by cron-handler outbound mail. The email-handler
   * path uses message.reply() which picks the original To: instead.
   * Defaulted in wrangler.toml [vars]; secret-overridable if needed.
   */
  SECURITY_FROM_ADDRESS: string;
}
