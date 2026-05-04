import Link from "next/link";
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";

export const runtime = "edge";

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold">Dendra</h1>
      <p className="mt-3 text-base text-neutral-700">
        Point any system in the best direction, then keep repointing.
        Free account unlocks shared switch configurations, team analyzer
        corpus, and opt-in registry contribution. OSS classification
        works without an account.
      </p>

      <div className="mt-8 flex items-center gap-3">
        <SignedOut>
          <SignInButton mode="modal">
            <button className="rounded-md bg-black px-4 py-2 text-sm text-white">
              Sign in
            </button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button className="rounded-md border border-black px-4 py-2 text-sm">
              Create free account
            </button>
          </SignUpButton>
        </SignedOut>
        <SignedIn>
          <Link
            href="/dashboard"
            className="rounded-md bg-black px-4 py-2 text-sm text-white"
          >
            Open dashboard
          </Link>
          <UserButton />
        </SignedIn>
      </div>
    </main>
  );
}
