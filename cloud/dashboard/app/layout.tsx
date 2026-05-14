// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// Root layout for the Postrule dashboard.
//
// Brand port (2026-05-11): the page chrome (header + footer + body type)
// matches landing/index.html exactly. Brand tokens live in globals.css;
// fonts load via next/font/google so the dashboard inherits the same
// Space Grotesk / Geist Mono pairing as postrule.ai.

import type { Metadata } from "next";
import Link from "next/link";
import { Space_Grotesk, Geist_Mono } from "next/font/google";
import { ClerkProvider, SignedIn, UserButton } from "@clerk/nextjs";
import "./globals.css";

// Display face — wordmark, headings, button labels.
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
  variable: "--font-display-loaded",
});

// Mono face — code blocks, key prefixes, numeric stats.
const geistMono = Geist_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--font-mono-loaded",
});

export const metadata: Metadata = {
  title: "Postrule",
  description:
    "Software that's smarter every month than the day you shipped it.",
  icons: {
    icon: "/brand/postrule-favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        className={`${spaceGrotesk.variable} ${geistMono.variable}`}
      >
        <body className="flex min-h-screen flex-col">
          <SiteHeader />
          <div className="flex-1">{children}</div>
          <SiteFooter />
        </body>
      </html>
    </ClerkProvider>
  );
}

// ─── Header ────────────────────────────────────────────────────────────
// Mirrors landing/index.html .site-header. The <picture> source swaps
// the dark wordmark in dark mode — same pattern as README.md so the
// asset story is identical across surfaces.
function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link
          href="/"
          className="wordmark"
          aria-label="Postrule home"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className="wordmark-mark"
            src="/brand/postrule-mark.svg"
            alt=""
            aria-hidden="true"
            width="32"
            height="32"
          />
          <span>POSTRULE</span>
        </Link>
        <nav className="primary-nav" aria-label="Primary">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/dashboard/switches" className="nav-secondary">
            Switches
          </Link>
          <Link href="/dashboard/keys" className="nav-secondary">
            API keys
          </Link>
          <Link href="/dashboard/billing" className="nav-secondary">
            Billing
          </Link>
          <Link href="/dashboard/insights" className="nav-secondary">
            Insights
          </Link>
          <Link href="/dashboard/settings" className="nav-secondary">
            Settings
          </Link>
          <a
            href="https://postrule.ai"
            className="nav-secondary"
            rel="noreferrer"
          >
            postrule.ai
          </a>
          <SignedIn>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
        </nav>
      </div>
    </header>
  );
}

// ─── Footer ────────────────────────────────────────────────────────────
function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <span>© 2026 B-Tree Labs</span>
        <nav aria-label="Footer">
          <a
            href="https://github.com/b-tree-labs/postrule/tree/main/docs"
            rel="noreferrer"
          >
            Docs
          </a>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <a
            href="https://github.com/b-tree-labs/postrule"
            rel="noreferrer"
          >
            GitHub
          </a>
        </nav>
      </div>
    </footer>
  );
}
