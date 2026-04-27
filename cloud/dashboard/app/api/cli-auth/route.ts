import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/cli-auth
 *
 * Receives a one-time code from the CLI device flow and returns
 * an API key plus the signed-in user's email.
 *
 * v1 stub: returns a deterministic mock token so the CLI loop can
 * be smoke-tested without a live Clerk session.
 *
 * TODO: tie to Clerk session via auth() and Supabase api_keys table.
 */
export async function POST(req: NextRequest) {
  let body: { code?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const code = body.code;
  if (!code || typeof code !== "string") {
    return NextResponse.json({ error: "missing_code" }, { status: 400 });
  }

  // TODO(real): look up the cli_sessions row by code, ensure it was
  // approved by an authenticated Clerk session, mint an API key,
  // store it in Supabase, return it once.
  return NextResponse.json({
    api_key: `dndra_${code.slice(0, 16)}`,  // pragma: allowlist secret
    email: "user@example.com",
  });
}
