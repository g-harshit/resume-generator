"use client";

import Link from "next/link";
import { ApiError } from "@/lib/api";

/** "3 Oct 2026, 14:05" in the viewer's time zone; "—" for nothing. */
export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "5 min ago", "3 days ago": for last-seen columns. */
export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

export function Pill({ tone = "muted", children }: { tone?: "muted" | "good" | "warn" | "accent"; children: React.ReactNode }) {
  const tones = {
    muted: "bg-sunken text-muted",
    good: "bg-accent-soft text-accent-ink",
    warn: "bg-warn-soft text-warn-ink",
    accent: "bg-accent text-white",
  };
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export const card = "rounded-xl border border-line bg-surface";

/** What to show when the admin API refuses: a 404 means "not an admin". */
export function AdminError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <p className="text-muted">
        Not found. <Link href="/app">Back to the app</Link>.
      </p>
    );
  }
  return (
    <p role="alert" className="text-warn-ink">
      {error instanceof TypeError ? "Can't reach the server." : (error as Error).message}
    </p>
  );
}

export const ACTION_LABEL: Record<string, string> = {
  sign_out: "Signed out everywhere",
  disable: "Disabled",
  enable: "Enabled",
  delete: "Deleted account",
  export_users: "Exported users (CSV)",
};
