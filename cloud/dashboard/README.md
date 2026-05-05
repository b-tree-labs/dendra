# Dendra dashboard (`app.dendra.run`)

Next.js 15 app that handles sign-in (Clerk), API-key issuance, and the
CLI device-flow exchange. Pairs with the `dendra` Python CLI in the
parent repo. Deployed to Cloudflare Pages via the `@cloudflare/next-on-pages`
adapter (see `wrangler.toml`).

## Local development

```sh
cd cloud/dashboard
cp .env.example .env.local
# edit .env.local with Clerk + Supabase keys
npm install
npm run dev
```

Open http://localhost:3000 . The CLI's `dendra login` command, when
pointed at a local dashboard with `DENDRA_CLOUD_API_BASE=http://localhost:3000/api`,
will hit the `app/api/cli-auth/route.ts` endpoint.

## Clerk setup

1. Create a free Clerk app at https://clerk.com
2. Copy the publishable + secret keys into `.env.local`
3. (Optional) configure social providers in the Clerk dashboard

## Supabase setup

The v1 dashboard ships without a live database. When wiring it up:

```sql
create table cli_sessions (
  code         text primary key,
  user_id      text,
  approved_at  timestamptz,
  ip           text,
  created_at   timestamptz not null default now()
);

create table api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     text not null,
  prefix      text not null,
  hash        text not null,
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz
);
```

Set `DATABASE_URL` in `.env.local` to your Supabase connection string.

## Deploy to Vercel

```sh
vercel --prod
```

Set the same `.env.example` variables in the Cloudflare Pages project
settings (or via `wrangler pages secret put` for the secrets). Point
`app.dendra.run` at the Pages project as a custom domain.

## Architecture notes

- `app/page.tsx` — landing CTA (sign in / sign up).
- `app/dashboard/page.tsx` — logged-in view with API key generation.
- `app/api/cli-auth/route.ts` — POST endpoint the CLI polls during
  `dendra login`. v1 returns a stub token; production reads/writes
  the `cli_sessions` table.
- `middleware.ts` — Clerk session middleware, matches all routes
  except static files.

OSS classification works without this dashboard. Cloud features
(`dendra.cloud.sync`, `dendra.cloud.team_corpus`, `dendra.cloud.registry`)
require an account.
