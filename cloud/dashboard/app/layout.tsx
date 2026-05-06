import type { Metadata } from "next";
import Link from "next/link";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dendra",
  description: "Graduated-autonomy classification primitive.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="flex min-h-screen flex-col">
          <div className="flex-1">{children}</div>
          <footer className="border-t border-neutral-200 px-6 py-8">
            <div className="mx-auto flex max-w-3xl items-center justify-between text-xs text-neutral-500">
              <span>© 2026 B-Tree Labs</span>
              <nav className="flex items-center gap-4">
                <Link href="/privacy" className="hover:text-neutral-900">
                  Privacy
                </Link>
                <Link href="/terms" className="hover:text-neutral-900">
                  Terms
                </Link>
                <a
                  href="https://github.com/b-tree-labs/dendra"
                  className="hover:text-neutral-900"
                >
                  GitHub
                </a>
              </nav>
            </div>
          </footer>
        </body>
      </html>
    </ClerkProvider>
  );
}
