import { auth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import Link from "next/link";

export const runtime = "edge";

export default async function DashboardPage() {
  const { userId } = await auth();
  if (!userId) {
    redirect("/");
  }

  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress ?? "unknown";

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-neutral-600">Signed in as {email}.</p>

      <section className="mt-8 rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">API keys</h2>
        <p className="mt-2 text-sm text-neutral-600">
          Issue a key for the CLI or your hosted-API integrations. Place it in{" "}
          <code className="rounded bg-neutral-100 px-1">~/.dendra/credentials</code>{" "}
          or export it as <code className="rounded bg-neutral-100 px-1">DENDRA_API_KEY</code>.
        </p>
        <Link
          href="/dashboard/keys"
          className="mt-4 inline-block rounded-md bg-black px-4 py-2 text-sm text-white"
        >
          Manage keys
        </Link>
      </section>

      <section className="mt-6 rounded-lg border border-neutral-200 p-6">
        <h2 className="text-lg font-medium">Billing</h2>
        <p className="mt-2 text-sm text-neutral-600">
          Choose a plan, view invoices, or update payment details.
        </p>
        <Link
          href="/dashboard/billing"
          className="mt-4 inline-block rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-50"
        >
          Open billing
        </Link>
      </section>
    </main>
  );
}
