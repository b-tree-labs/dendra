// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// /dashboard/switches — list every switch the authed user has emitted a
// verdict for. Sortable, paginated, with 14-day sparklines per row.

import { auth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { upsertUser, listSwitches } from "../../../lib/dendra-api";
import SwitchesClient from "./switches-client";

export const runtime = "edge";

export default async function SwitchesListPage() {
  const { userId } = await auth();
  if (!userId) redirect("/");

  const u = await currentUser();
  const email = u?.emailAddresses?.[0]?.emailAddress;
  if (!email) redirect("/");

  const user = await upsertUser(userId, email);
  const data = await listSwitches(user.user_id);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <p className="eyebrow eyebrow--accent">Account</p>
      <h1
        className="mt-2"
        style={{
          fontSize: "var(--size-h2)",
          lineHeight: "var(--lh-h2)",
        }}
      >
        Switches
      </h1>
      <p className="prose-brand mt-3">
        Every site you&apos;ve wrapped with <code>@ml_switch</code> appears
        below once it records a verdict. Click a switch to open its report
        card — phase timeline, paired-correctness gate, drift signals,
        cost trajectory.
      </p>
      <SwitchesClient
        switches={data.switches}
        sparklineWindowDays={data.sparkline_window_days}
        tier={user.tier}
      />
    </main>
  );
}
