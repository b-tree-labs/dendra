// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Privacy policy page. Linked from the dashboard footer + Stripe Checkout
// footer (Stripe requires legal links to be reachable from the checkout
// flow when collecting card details).
//
// This is the v1.0 launch boilerplate, drafted for B-Tree Labs based on
// what we actually do today; it is NOT legal advice and should be
// reviewed by counsel before any meaningful expansion of data
// collection. Update the "Last updated" stamp on every revision.

export const runtime = "edge";

export const metadata = {
  title: "Privacy Policy — Dendra",
  description: "How B-Tree Labs handles your data when you use Dendra.",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold">Privacy Policy</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Last updated: 2026-05-06
      </p>

      <div className="prose prose-neutral mt-8 max-w-none text-base text-neutral-800">
        <h2 className="mt-10 text-xl font-semibold">Who we are</h2>
        <p>
          Dendra is a product of <strong>B-Tree Labs</strong>, a DBA of
          B-Tree Ventures, LLC, registered in Texas, USA. Throughout this
          policy, &ldquo;we&rdquo; / &ldquo;our&rdquo; refers to B-Tree
          Labs.
        </p>

        <h2 className="mt-10 text-xl font-semibold">What we collect</h2>
        <ul className="list-disc pl-6">
          <li>
            <strong>Account email</strong> — collected at sign-in via
            our identity provider (Clerk). Used to identify your account
            and send transactional email (receipts, security alerts).
          </li>
          <li>
            <strong>Payment details</strong> — handled exclusively by
            Stripe. We never see or store card numbers; Stripe returns a
            customer ID we associate with your account.
          </li>
          <li>
            <strong>API usage metadata</strong> — call counts, timestamps,
            and tier-relevant aggregates (verdicts/month, switches
            registered). Never the contents of your classifications.
          </li>
          <li>
            <strong>Operational logs</strong> — request paths, response
            codes, and error traces, retained 7 days for debugging.
            IPs are redacted after 24 hours.
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold">What we do NOT collect</h2>
        <ul className="list-disc pl-6">
          <li>
            The text, payloads, or labels you classify. Verdict events
            you opt to send to <code>/v1/verdicts</code> contain only a
            paired-correctness boolean and the timestamp; the input text
            stays on your servers.
          </li>
          <li>
            Cookies for tracking or advertising. We use a single
            session cookie (set by Clerk) and a Stripe checkout cookie
            during paid-tier upgrade flows.
          </li>
          <li>
            Third-party analytics (no Google Analytics, no Segment, no
            tracking pixels).
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold">Where data lives</h2>
        <p>
          Account + billing state lives in Cloudflare D1 (SQLite,
          replicated within Cloudflare&apos;s WNAM region). Operational
          logs live in Cloudflare Workers Observability. Card details
          live with Stripe. We do not transfer your data outside these
          providers.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Retention</h2>
        <ul className="list-disc pl-6">
          <li>Account data — until you delete your account.</li>
          <li>Operational logs — 7 days.</li>
          <li>
            Billing records — 7 years (US federal tax-record retention).
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold">Your rights</h2>
        <p>
          You can request a copy of your data, or delete your account
          and all associated records, by emailing{" "}
          <a href="mailto:privacy@dendra.run" className="underline">
            privacy@dendra.run
          </a>
          . We respond within 30 days. Residents of the EU/UK have GDPR
          rights of access, rectification, erasure, restriction,
          portability, and objection; California residents have CCPA
          rights of access, deletion, and opt-out of sale (we do not
          sell your data).
        </p>

        <h2 className="mt-10 text-xl font-semibold">Changes to this policy</h2>
        <p>
          We&apos;ll post material changes here and bump the
          &ldquo;Last updated&rdquo; date. If you have an active account
          when a change is made, we&apos;ll email you within 7 days of
          publishing it.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Contact</h2>
        <p>
          Questions:{" "}
          <a href="mailto:privacy@dendra.run" className="underline">
            privacy@dendra.run
          </a>
          . Mailing address available on request.
        </p>
      </div>
    </main>
  );
}
