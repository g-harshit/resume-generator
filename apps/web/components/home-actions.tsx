"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

const primary =
  "inline-flex h-12 items-center rounded-[10px] bg-accent px-5 text-base font-medium text-white hover:bg-accent-hover hover:text-white";
const secondary =
  "inline-flex h-12 items-center rounded-[10px] border border-line-strong bg-surface px-5 text-base text-ink hover:text-ink";
const small =
  "inline-flex h-10 items-center rounded-[10px] px-3.5 text-[15px] font-medium";

/** The landing page's calls to action: signed in → the app; signed out → sign up / in. */
export function HomeActions({ compact = false }: { compact?: boolean }) {
  const { user, loading } = useAuth();

  // Keep the space while we find out, so the buttons don't jump in.
  if (loading) return <div className={compact ? "h-10" : "h-12"} />;

  if (compact) {
    return user ? (
      <Link href="/app" className={`${small} bg-accent text-white hover:bg-accent-hover hover:text-white`}>
        Go to your resumes
      </Link>
    ) : (
      <div className="flex items-center gap-1">
        <Link href="/login" className={`${small} text-ink hover:bg-sunken hover:text-ink`}>
          Sign in
        </Link>
        <Link href="/register" className={`${small} bg-accent text-white hover:bg-accent-hover hover:text-white`}>
          Get started
        </Link>
      </div>
    );
  }

  if (user) {
    return (
      <div className="flex flex-wrap gap-3">
        <Link href="/app" className={primary}>
          Go to your resumes
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-3">
      <Link href="/register" className={primary}>
        Create a free account
      </Link>
      <Link href="/login" className={secondary}>
        Sign in
      </Link>
    </div>
  );
}
