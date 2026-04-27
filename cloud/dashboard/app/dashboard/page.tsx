import { auth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const { userId } = auth();
  if (!userId) {
    redirect("/");
  }

  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress ?? "unknown";

  // Stub data for v1. Real implementation pulls from Supabase.
  const recentCliSessions: { code: string; createdAt: string; ip: string }[] = [];

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-neutral-600">Signed in as {email}.</p>

      <section className="mt-8 rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">API key</h2>
        <p className="mt-2 text-sm text-neutral-600">
          Generate a key, then place it in <code>~/.dendra/credentials</code>{" "}
          or export it as <code>DENDRA_API_KEY</code>.
        </p>
        <button
          type="button"
          className="mt-4 rounded-md bg-black px-4 py-2 text-sm text-white"
        >
          Generate API key
        </button>
      </section>

      <section className="mt-6 rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">Recent CLI sessions</h2>
        {recentCliSessions.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-600">No sessions yet.</p>
        ) : (
          <ul className="mt-2 divide-y divide-neutral-200 text-sm">
            {recentCliSessions.map((s) => (
              <li key={s.code} className="py-2">
                <span className="font-mono">{s.code}</span> from {s.ip} at{" "}
                {s.createdAt}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
