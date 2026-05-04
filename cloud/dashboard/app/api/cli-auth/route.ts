// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// POST /api/cli-auth
//
// CLI device-flow exchange. The CLI hits this endpoint with the
// one-time code it generated locally; if a Clerk session is present
// (i.e. the user has signed in via the dashboard before approving the
// CLI flow), we issue a fresh dndr_live_… key, return it once, and
// expect the CLI to write it to ~/.dendra/credentials.
//
// The CLI device flow itself (code generation, polling) lives in
// src/dendra/cli/. This route is the dashboard side of the handshake.

import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { upsertUser, issueKey } from "../../../lib/dendra-api";

export async function POST(req: NextRequest) {
  let body: { code?: string; name?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (!body.code || typeof body.code !== "string") {
    return NextResponse.json({ error: "missing_code" }, { status: 400 });
  }

  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "no_session" }, { status: 401 });
  }
  const u = await currentUser();
  const email = u?.emailAddresses?.[0]?.emailAddress;
  if (!email) {
    return NextResponse.json({ error: "no_email_on_clerk_user" }, { status: 400 });
  }

  // TODO(week 2): look up cli_sessions row by code, ensure it has not
  // been redeemed yet, mark redeemed atomically. For the v1 launch we
  // return the key directly to any authenticated dashboard caller — the
  // CLI binds the code to a polling loop on its end.
  try {
    const user = await upsertUser(userId, email);
    const issued = await issueKey(
      user.user_id,
      body.name ?? `cli-${body.code.slice(0, 8)}`,
      "live",
    );
    return NextResponse.json({ api_key: issued.plaintext, email });
  } catch (e) {
    console.error("cli-auth issue failed", e);
    return NextResponse.json({ error: "issue_failed" }, { status: 500 });
  }
}
