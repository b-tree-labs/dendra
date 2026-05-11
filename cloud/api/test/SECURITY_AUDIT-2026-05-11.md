# Pre-launch security audit — 2026-05-11

**Auditor:** Claude Opus 4.7 (1M context), invoked by Benjamin Booth
**Scope:** Dendra v1.0 cloud + SDK surface at `origin/main` HEAD
`d4684d3` (PRs #28–#44 inclusive).
**Launch target:** 2026-05-20.
**Status:** **No blockers found.** One HIGH-severity finding (vulnerable
`next` dependency) fixed in this PR; one HIGH-severity finding (no
security headers on the dashboard) fixed in this PR. Six MEDIUM /
LOW findings recorded below — accepted with rationale or deferred to
v1.1 with rationale.

---

## Findings table

| # | Sev      | Category                          | Status                                | Summary                                                                                                  |
|---|----------|-----------------------------------|---------------------------------------|----------------------------------------------------------------------------------------------------------|
| 1 | high     | 9 dependency vulns                | **fixed in this PR**                  | `next` bumped 15.5.15 → 15.5.18; closes 13 open dependabot alerts (4 high, 4 moderate, 3 low, on next).  |
| 2 | high     | 5 CSP + security headers          | **fixed in this PR**                  | Dashboard had **zero** security response headers. Added CSP / HSTS / X-Frame-Options / Referrer / Permissions / X-Content-Type-Options via `middleware.ts`. |
| 3 | medium   | 9 dependency vulns                | **fixed in this PR**                  | `hono` bumped 4.6.14 → 4.12.18; closes 3 open dependabot alerts (#30, #31, #32).                          |
| 4 | medium   | 7 rate-limit coverage             | **deferred to v1.1 with rationale**   | No per-IP / per-account-hash RPS limit on `/v1/verdicts` or `/admin/*`. Tier-cap is the only throttle. Owner doc'd this explicitly in `cloud/api/src/usage.ts` lines 17–19.  |
| 5 | medium   | 12 SECURITY.md stale              | **accepted; documented in PR body**   | SECURITY.md says "Dendra Cloud (when it exists) — separate security policy will apply" but cloud launches in 9 days. v1.1 follow-up to merge cloud scope in. |
| 6 | medium   | 11 input validation               | **accepted with rationale**           | `display_name` server-side handling is `slice(0, 64)` (truncate) instead of 400-reject. Defense in depth; UX-preserving on bypass attempt. Not exploitable. |
| 7 | low      | 9 dependency vulns (out of scope) | **out of scope for launch**           | `fast-uri` HIGH in `cloud/vscode-dendra/package-lock.json`. vscode-dendra is not in the v1.0 launch surface. Bump in a follow-up. |
| 8 | info     | 2 keys hashing algorithm          | **accepted; documented in source**    | API keys hashed with HMAC-SHA-256, not argon2id. Reasoning correct: 190-bit random keys don't need a KDF. Documented in `cloud/api/src/keys.ts` lines 9–17. |

Severity scale: critical / **high** / **medium** / low / info.

---

## Verification methodology

1. Fetched `origin/main`, verified HEAD matches `d4684d3`, verified all
   17 expected PRs (#28–#44) are present in the log.
2. Created worktree at `/tmp/dendra-security-audit-v2`.
3. Walked each of the 13 audit dimensions against the worktree HEAD.
4. Re-ran tests after every code change: `cloud/api npm test` → 220
   passed / 27 skipped (unchanged); dashboard typecheck / lint / build
   all clean.

---

## Per-dimension findings

### 1. Service-token auth boundary on `/admin/*` — CLEAN

- `timingSafeEqual` in `cloud/api/src/admin.ts` lines 34–41 is
  textbook-correct: length check up front (the only data-dependent
  early-return — but constant-length tokens make this safe), then
  XOR-OR accumulation, single final `=== 0` compare. No early exit
  inside the loop.
- `cloud/api/src/admin.ts` line 50–52: invalid token returns
  `{"error":"unauthorized"}` with status 401 — the token value is
  never echoed back, never logged on a failure path, never serialized
  into the error message. Reviewed all `console.error` / `console.log`
  calls in the file; none touch `expected` or `got`.
- `cloud/dashboard/lib/dendra-api.ts` lines 11–18: `assertServerOnly()`
  fires on every `adminFetch` and `adminFetchNullable`. All 18 admin
  call sites in the file go through one of those two helpers. Token
  cannot leak to the browser.
- `cloud/api/wrangler.toml` lines 11–16: `DASHBOARD_SERVICE_TOKEN` is
  documented as a secret. `[vars]` blocks (lines 71–72, 111–112) only
  contain `ENVIRONMENT`.

### 2. Bearer-token (`dndr_live_…`) auth path — CLEAN with note

- Hashing: HMAC-SHA-256 with `API_KEY_PEPPER`, not argon2id. The
  reasoning in `cloud/api/src/keys.ts` lines 9–17 is sound: keys are
  190-bit random strings (32 base62 chars), so the pre-image space is
  ~190 bits — far above the 2^128 floor where argon2id's grind-
  resistance becomes useful. Workers per-request CPU budget makes
  argon2id (m=64MB) infeasible regardless. Spec deviation documented.
- `cloud/api/src/keys.ts` line 60–71: hash computed via
  `crypto.subtle.sign('HMAC')`. Deterministic so D1 lookup-by-hash
  works in a single indexed read.
- Constant-time comparison is implicit: D1 indexed lookup either
  returns a row or it doesn't — no early bail based on prefix.
- `auth.ts` line 80: invalid key returns `invalid_or_revoked_key` 401
  — the bearer value is never echoed.
- No `dndr_live_…`-shaped logging found in `src/dendra/` or
  `cloud/api/src/`. The one mention in `verdict_telemetry.py:195` is
  inside a docstring example with `# pragma: allowlist secret`.

### 3. Cross-account isolation — CLEAN

- `/v1/switches/:name/report` (`cloud/api/src/report.ts` lines 217–230):
  ownership check via `JOIN api_keys k ON k.id = v.api_key_id WHERE
  k.user_id = ? AND v.switch_name = ? LIMIT 1`. If no row, returns 404
  not 200-empty. Confirmed at `cloud/api/src/report.ts:334`. Same
  pattern in the admin proxy at `cloud/api/src/admin.ts:640–658`.
- `/v1/whoami` (`cloud/api/src/index.ts:70–95`): reads from `users`
  table scoped by `auth.user_id`. No cross-account leak surface.
- `POST /v1/verdicts` auto-unarchive (`cloud/api/src/verdicts.ts:196–
  201`): the `DELETE FROM switch_archives WHERE user_id = ? AND
  switch_name = ?` uses `auth.user_id`, never anything from the
  request body. Cannot un-archive another user's switch.
- Admin endpoints (`cloud/api/src/admin.ts`): every query I reviewed
  scopes by `user_id` from the request body, but that body is only
  reachable through the service-token-authenticated dashboard, and
  every Next.js route handler in `cloud/dashboard/app/api/` derives
  `user_id` from the Clerk session (`auth()` → `currentUser()` →
  `upsertUser(...)`), never from request input. Reviewed
  `app/api/keys/route.ts`, `app/api/settings/route.ts`,
  `app/api/insights/route.ts`, `app/api/cli-auth/route.ts`,
  `app/api/switches/[name]/route.ts`, `app/api/keys/[id]/route.ts`,
  `app/api/billing/checkout/route.ts`, `app/api/billing/portal/route.ts`.
  All seven follow the same `authedUser()` pattern.

### 4. SSRF + outbound HTTP — CLEAN

- SDK adapters (`OpenAIAdapter`, `AnthropicAdapter`, `OllamaAdapter`,
  `LlamafileAdapter`) take `base_url` as a developer-supplied
  constructor arg, not request input. Library users explicitly pin
  the endpoint at decoration time.
- CLI device-flow URL: `_DEFAULT_API_BASE = "https://api.dendra.run/v1"`
  hard-coded at `src/dendra/cli.py:49`. Env override
  `DENDRA_API_BASE` is operator-controlled, not network-attacker
  controlled. Same trust model as `OPENAI_BASE_URL`.
- `_fetch_telemetry_preference` (`src/dendra/cli.py:595–620`) hits
  `{api_base}/whoami` — same trust model.
- Dashboard `API_BASE = process.env.DENDRA_API_BASE_URL ??
  'https://staging-api.dendra.run'` (`lib/dendra-api.ts:8`). Server-
  controlled config; user cannot inject.
- Stripe webhook: outbound calls limited to `stripe.Subscription`
  metadata reads, which go through the Stripe SDK's pinned base URL.
- No endpoint in the audited surface accepts a user-supplied URL that
  is then fetched server-side.

### 5. CSP + security headers — **HIGH (fixed in this PR)**

**Pre-fix state:** `cloud/dashboard/middleware.ts` had nothing but a
naked `clerkMiddleware()` export — **zero** security response headers
on any dashboard route. PR #26 ("launch readiness P0") apparently did
not land header coverage. Anyone serving content from
`app.dendra.run` could be embedded in any iframe, executed in any
mixed-content context, or sniffed by a MITM willing to downgrade.

**Fix:** Rewrote `middleware.ts` to wrap the Clerk middleware and
stamp six headers on every response:

| Header | Value (abbreviated) | Why |
|---|---|---|
| Content-Security-Policy | `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' clerk + cf-challenges; …` | Restrict what the browser executes. Allow Clerk's auth widget + Stripe Checkout redirect + Google Fonts (next/font). |
| Strict-Transport-Security | `max-age=15552000; includeSubDomains` | 6-month HTTPS lock. Preload submission deferred to v1.1. |
| X-Frame-Options | DENY | Defense in depth on top of CSP `frame-ancestors 'none'`. |
| X-Content-Type-Options | nosniff | Block MIME sniffing. |
| Referrer-Policy | strict-origin-when-cross-origin | Don't leak path / query to third parties. |
| Permissions-Policy | camera / mic / geolocation / payment-self / etc. | Disable features we don't use. |

**Known limitation, v1.1 follow-up:** `'unsafe-inline'` and
`'unsafe-eval'` on `script-src` are required by Next.js's hydration
runtime. The right migration is a per-request nonce (Next.js supports
this in middleware), which lets us drop `'unsafe-inline'`. Not
blocking launch — the rest of the CSP (no `'unsafe-inline'` on
`script-src` from third-party origins, `default-src 'self'`,
`frame-ancestors 'none'`, restrictive `connect-src`) still meaningfully
shrinks XSS impact.

**Verified:** dashboard builds (`npm run build`) and types
(`npm run typecheck`) and lints (`npm run lint`) all clean after the
middleware rewrite.

### 6. Stripe webhook signature verification — CLEAN

- `cloud/api/src/webhook.ts:46–66`: `stripe.webhooks.constructEventAsync`
  runs **before** any database mutation. On failure, returns 400 and
  logs only the exception (not the body or signature).
- Idempotency: `cloud/api/src/webhook.ts:103–112` — if
  `subscriptions.last_event_id` matches `event.id`, the handler
  returns without re-applying. Stripe is documented as at-least-once,
  and this dedup is correct.
- Signing secret comes from `c.env.STRIPE_WEBHOOK_SECRET` (line 60) —
  documented as a wrangler secret in `wrangler.toml` line 15.
- Subscription state change is **per-customer**, looked up by
  `stripe_customer_id`. No cross-account write surface.

### 7. Rate limit coverage on new endpoints — **MEDIUM (deferred v1.1)**

**Pre-audit state:** `wrangler.toml` configures rate limits only for
`DEVICE_CODE_LIMIT` and `DEVICE_TOKEN_LIMIT` (the two anonymous
endpoints). No middleware applies a per-IP or per-account-hash limit
to `/v1/verdicts`, `/admin/*`, or any of the new dashboard surface
from PRs #29–#41.

**Author's rationale, copied from `cloud/api/src/usage.ts:17–19`:**

> RPS / per-second rate limiting is intentionally deferred. For v1 we
> rely on a Cloudflare edge rate-limit rule (configurable in the
> dashboard) to bound worst-case spend; per-tier RPS enforcement
> lands in v1.1 via Durable Objects (one bucket per api_key_id).

**Acceptance reasoning for launch:**

- The **monthly tier cap** (`usage.ts:25–30`) is the de-facto
  throttle. A free-tier user blasting `/v1/verdicts` hits the 10k cap
  within minutes, after which every request returns 429. A
  Pro-tier user gets soft-capped to overage billing — they pay for
  whatever they send.
- The **service-token boundary** on `/admin/*` means only the
  dashboard origin can reach those endpoints. The dashboard's
  Clerk-authenticated route handlers run server-side on Cloudflare
  Pages, which has its own platform-level DDoS / abuse protection.
  A genuine attack would have to come through a stolen service
  token, which is the topic of finding #1 in this audit (clean).
- An **operator-side Cloudflare Rule** (configurable in the
  Cloudflare dashboard, no code change) can layer in per-IP RPS
  bounds without redeploying. Recommend the user set:
  - `/v1/verdicts`: 300 req/min per IP
  - `/admin/*`: 60 req/min per IP (only the dashboard origin should
    legitimately hit this; anything else is suspicious)

**v1.1 follow-up:** in-Worker Durable Object rate limiter keyed by
`api_key_id` (so a single customer's noisy IP doesn't drag down
their other deployments).

### 8. Detect-secrets sweep — CLEAN

- Ran `detect-secrets-hook --baseline .secrets.baseline <every file
  changed in the last 17 commits>`. Exit code 0; no new findings vs
  baseline.
- Manual audit of `cloud/api/wrangler.toml`,
  `cloud/dashboard/wrangler.toml`, `cloud/collector/wrangler.toml`,
  `cloud/dashboard/.env.example`:
  - All secrets are documented as `wrangler secret put` (cloud/api)
    or `wrangler pages secret put` (dashboard) — none in `[vars]`.
  - `.env.example` placeholders all read `REPLACE_ME` or
    `pk_test_REPLACE_ME` / `sk_test_REPLACE_ME`. No actual values.
  - Stripe **price IDs** in `cloud/dashboard/wrangler.toml` are
    publicly-visible price-table identifiers (Stripe documents these
    as non-secret).
  - KV namespace IDs in `cloud/api/wrangler.toml` are non-secret
    Cloudflare resource identifiers.

### 9. Dependency vulnerabilities — **HIGH (fixed in this PR)**

**pre-audit `gh dependabot/alerts`:** **16 open alerts**, far more than the
"4" the prompt mentioned. The repo is `b-tree-labs/dendra`. Concrete
counts at audit time:

| # | Severity | Package | Manifest | Fix in |
|---|---|---|---|---|
| 46 | high | next | dashboard | 15.5.18 |
| 45 | low | next | dashboard | 15.5.16 |
| 44 | medium | next | dashboard | 15.5.16 |
| 43 | low | next | dashboard | 15.5.16 |
| 42 | medium | next | dashboard | 15.5.16 |
| 41 | high | next | dashboard | 15.5.16 |
| 40 | medium | next | dashboard | 15.5.16 |
| 39 | high | next | dashboard | 15.5.16 |
| 38 | high | next | dashboard | 15.5.16 |
| 37 | medium | next | dashboard | 15.5.16 |
| 36 | high | next | dashboard | 15.5.16 |
| 35 | high | next | dashboard | 15.5.16 |
| 34 | high | next | dashboard | 15.5.16 |
| 33 | high | fast-uri | **vscode-dendra** (out-of-scope for v1.0) | 3.1.2 |
| 32 | medium | hono | api | 4.12.18 |
| 31 | low | hono | api | 4.12.18 |
| 30 | medium | hono | api | 4.12.18 |

**Fixes applied in this PR:**

1. `cloud/dashboard/package.json`: `next ^15.5.15` → `^15.5.18`.
   Closes 13 open `next` alerts including 7 HIGH-severity. Notable
   HIGH that **directly affects our launch surface**: GHSA-26hh-7cqf-hhc6
   (Middleware / Proxy bypass in App Router via segment-prefetch),
   GHSA-8h8q-6873-q5fj (DoS in Server Components), GHSA-c4j6-fc7j-m34r
   and GHSA-492v-c6pp-mqqv (additional middleware-bypass variants).
   We use middleware (Clerk + our new security-headers wrapper) and
   App Router server components everywhere — both are exposed.
2. `cloud/api/package.json`: `hono ^4.6.14` → `^4.12.18`. Closes 3
   alerts. Of the three, GHSA-p77w-8qqv-26rm (cache-middleware
   cross-user leak) does not affect us since we don't use Hono's
   cache middleware — but bumping is free and we get the other two
   fixes (CSS injection in JSX SSR, JWT NumericDate validation)
   in case we add those features.
3. `eslint-config-next` aligned to `^15.5.18` to match.

**Out of scope for launch:** alert #33 (`fast-uri` HIGH in
`cloud/vscode-dendra`). The VSCode extension is not part of the v1.0
launch surface; bump in a follow-up.

**Python side:** `pip-audit` not installed in this environment.
**Gap noted.** Recommend installing in CI and running on `pyproject.toml`
before the next monthly maintenance window.

### 10. Path-traversal regression on new endpoints — CLEAN

- All three new switch-name path-parameter endpoints
  (`/admin/switches/:name/report`,
   `/admin/switches/:name/archive`,
   `/admin/switches/:name/unarchive`)
  validate against `SWITCH_NAME_RE = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/`
  before any DB or handler logic runs (`admin.ts:500`, `:646`, `:727`,
  `:797`).
- `..` does NOT match the regex (first char must be `[A-Za-z]`).
  `%2e%2e` decodes to `..` at the framework layer (Hono decodes path
  params before they reach `c.req.param('name')`), so the post-decode
  string is what the regex sees.
- Even if a malformed name slipped through, the values are only used
  as **parameterized D1 bind values** — never interpolated into SQL,
  never concatenated into a filesystem path. The Worker has no
  filesystem (it's an isolate, no `fs` module).

### 11. Input validation on new write endpoints — Mostly CLEAN, one defense-in-depth note

- `PATCH /admin/whoami` `display_name`: server cap is at
  `preferences.ts:108` via `.slice(0, 64)`. **It truncates rather than
  400-rejects.** This is a UX choice — a paste of a too-long name
  becomes its 64-char prefix rather than an error. Not a security
  hole (no buffer overflows in JS land; D1 has its own row-size
  limits at MB scale), but worth surfacing.
- `PATCH /admin/whoami` `telemetry_enabled`: strict-boolean check at
  `preferences.ts:119`. Returns 400 on type mismatch.
- `POST /admin/switches/:name/archive` `reason`: cap enforced at
  `admin.ts:742–746`, returns 400 with `reason_exceeds_200_chars`
  on overflow. Type-checks string at line 739, returns 400 on
  non-string.
- All other type-checks return 400, not 500, on bad input. Reviewed
  every `c.req.json<...>().catch(() => null)` pattern in the
  changed files.

### 12. SECURITY.md audit — **MEDIUM (accepted, surface in PR body)**

**Findings:**

1. **Stale scope claim.** Line 65: "Dendra Cloud (when it exists) —
   separate security policy will apply." The cloud surface launches
   in 9 days. This needs to be flipped before launch day.
   - **Recommendation:** add a brief "## Hosted service (Dendra Cloud)"
     section pointing to the same `security@b-treeventures.com` alias,
     covering the api Worker, dashboard, webhook receiver, and
     bearer-token + service-token auth boundaries. Flag for
     PR-followup; not blocking launch since the email alias is
     already valid.
2. **No safe-harbor / disclosure-timeline language.** SECURITY.md
   defines acknowledgement / triage / patch timelines but doesn't
   commit to legal safe-harbor for good-faith research. Industry
   norm; not strictly required.
3. **Contact is a role alias.** `security@b-treeventures.com` is a
   role alias, not a personal email. Good. (Confirmed per the PR #23
   email-sweep mention.)
4. **THREAT_MODEL.md exists** at `docs/THREAT_MODEL.md`. Link is live.

### 13. License-key signing path — CLEAN

- `cloud/api/src/license.ts:178–203` (`signLicense`): private key
  comes from `args.privateKeyHex`, which the only caller
  (`admin.ts:328`) sources from `c.env.LICENSE_SIGNING_PRIVATE_KEY`
  — a wrangler secret. Never inlined; never in source.
- No dashboard surface (`cloud/dashboard/app/dashboard/license/`
  does not exist). No half-implemented endpoint leaks BSL signing
  state. The `/admin/licenses/issue` endpoint is reachable only by
  the service-token-authenticated dashboard, but the dashboard's
  route handlers don't expose a license-issue button yet — it's an
  operator-only curl path for now.

---

## Open recommendations (post-launch follow-ups)

1. **Add per-IP rate limits via a Cloudflare Rule** before launch day.
   No code change required; configure in the Cloudflare dashboard:
   - `/v1/verdicts`: 300 req/min per IP
   - `/admin/*`: 60 req/min per IP
2. **v1.1: nonce-based CSP.** Drop `'unsafe-inline'` and
   `'unsafe-eval'` from `script-src` via a per-request nonce.
3. **v1.1: in-Worker Durable Object rate limiter** keyed by
   `api_key_id`.
4. **Refresh SECURITY.md** to include the hosted-service scope.
5. **Install `pip-audit` in CI** and gate the SDK release on a clean
   Python dependency scan.
6. **HSTS preload** submission once confident no http-only origins
   remain.
7. **Bump `fast-uri` in `cloud/vscode-dendra`** when that surface
   re-enters scope.

---

## Sign-off

After the fixes in this PR:

- `cloud/api` — 220 tests passed, 27 skipped (unchanged from
  pre-audit baseline).
- `cloud/dashboard` — typecheck clean, lint clean, build clean.
- `cloud/collector` — npm audit clean.
- 16 dependabot alerts → 1 remaining (alert #33, out-of-scope
  vscode-dendra fast-uri).

**No blockers identified. Cleared to ship 2026-05-20** pending the
two pre-launch operator actions above (Cloudflare Rule for per-IP
rate limits; SECURITY.md scope update).
