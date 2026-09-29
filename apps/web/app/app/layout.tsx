"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { APP_NAME } from "@/lib/config";

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

/** Everything under /app needs a signed-in user; anyone else goes to /login. */
export default function SignedInLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, pathname, router]);

  if (!user) {
    return (
      <p role="status" className="m-auto text-muted">
        Loading…
      </p>
    );
  }

  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <nav
        aria-label="Main"
        className="flex shrink-0 items-center justify-between gap-1 border-b border-line bg-sunken px-4 py-3 md:w-58 md:flex-col md:items-stretch md:justify-start md:border-r md:border-b-0 md:px-3.5 md:py-6"
      >
        <Link href="/app" className="font-display text-3xl text-ink hover:text-ink md:px-3 md:pb-6">
          {APP_NAME}
        </Link>
        <div className="flex items-center gap-3 md:mt-auto md:flex-col md:items-stretch">
          <div className="flex items-center gap-2.5 md:px-2">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-white"
            >
              {initials(user.name)}
            </span>
            <span className="hidden text-sm md:inline">{user.name}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="h-11 rounded-lg px-3 text-left text-sm text-muted hover:bg-surface hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </nav>
      <main className="flex-1 px-4 py-9 md:px-11">{children}</main>
    </div>
  );
}
