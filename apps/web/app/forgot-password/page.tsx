"use client";

import Link from "next/link";
import { useState } from "react";
import { authButton, authInput, AuthShell } from "@/components/auth-shell";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    setBusy(true);
    setError(null);
    try {
      setSent((await api.requestPasswordReset(email)).detail);
    } catch (err) {
      setError(err instanceof TypeError ? "Can't reach the server." : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-5xl leading-tight">Forgot your password?</h1>
        <p className="text-muted">We&apos;ll email you a link to choose a new one.</p>
      </div>
      {sent ? (
        <p role="status" className="rounded-lg bg-accent-soft px-4 py-3 text-accent-ink">
          {sent} It works for an hour.
        </p>
      ) : (
        // method="post": a submit before the page's JavaScript loads must not put the
        // email in the URL.
        <form method="post" onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Email
            <input name="email" type="email" required autoComplete="email" className={authInput} />
          </label>
          {error && (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-sm text-warn-ink">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy} className={authButton}>
            {busy ? "Sending…" : "Send the link"}
          </button>
        </form>
      )}
      <p className="text-sm text-muted">
        <Link href="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
