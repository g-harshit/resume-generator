"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

const primary =
  "inline-flex h-12 items-center rounded-[10px] bg-accent px-5 text-base font-medium text-white hover:bg-accent-hover hover:text-white";
const secondary =
  "inline-flex h-12 items-center rounded-[10px] border border-line-strong bg-surface px-5 text-base text-ink hover:text-ink";

export function HomeActions() {
  const { user, loading } = useAuth();

  // Keep the space while we find out, so the buttons don't jump in.
  if (loading) return <div className="h-12" />;

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
        Create an account
      </Link>
      <Link href="/login" className={secondary}>
        Sign in
      </Link>
    </div>
  );
}
