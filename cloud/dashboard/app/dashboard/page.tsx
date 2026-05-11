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
      <p className="eyebrow eyebrow--accent">Dashboard</p>
      <h1
        className="mt-2"
        style={{
          fontSize: "var(--size-h2)",
          lineHeight: "var(--lh-h2)",
        }}
      >
        Welcome back
      </h1>
      <p
        className="mt-2"
        style={{
          color: "var(--ink-soft)",
          fontSize: "var(--size-caption)",
        }}
      >
        Signed in as <span className="font-mono">{email}</span>.
      </p>

      <section className="surface-card mt-8">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-2)",
          }}
        >
          API keys
        </h2>
        <p className="prose-brand">
          Issue a key for the CLI or your hosted-API integrations. Place it
          in <code>~/.dendra/credentials</code> or export it as{" "}
          <code>DENDRA_API_KEY</code>. Or run{" "}
          <code>dendra login</code> in your terminal and we&apos;ll
          provision one automatically.
        </p>
        <Link
          href="/dashboard/keys"
          className="btn btn-primary mt-2 inline-flex"
        >
          Manage keys
        </Link>
      </section>

      <section className="surface-card mt-6">
        <h2
          style={{
            fontSize: "var(--size-h4)",
            lineHeight: "var(--lh-h4)",
            marginBottom: "var(--space-2)",
          }}
        >
          Billing
        </h2>
        <p className="prose-brand">
          Choose a plan, view invoices, or update payment details. Stripe
          handles every card detail — we never see them.
        </p>
        <Link
          href="/dashboard/billing"
          className="btn btn-secondary mt-2 inline-flex"
        >
          Open billing
        </Link>
      </section>
    </main>
  );
}
