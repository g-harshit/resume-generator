"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { authButton, authInput, AuthShell } from "@/components/auth-shell";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function ResetPasswordPage() {
  // useSearchParams (?token=) needs a Suspense boundary.
  return (
    <AuthShell>
      <Suspense>
        <ResetForm />
      </Suspense>
    </AuthShell>
  );
}

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const { adopt } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password"));
    if (password !== String(form.get("again"))) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.confirmPasswordReset(token, password);
      adopt(res.token, res.user);
      router.push("/app");
    } catch (err) {
      setError(err instanceof TypeError ? "Can't reach the server." : (err as Error).message);
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <p>
        This page needs the link from your email. <Link href="/forgot-password">Ask for a new one</Link>.
      </p>
    );
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-5xl leading-tight">Choose a new password.</h1>
        <p className="text-muted">You&apos;ll be signed out everywhere else.</p>
      </div>
      <form method="post" onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          New password
          <input name="password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" className={authInput} />
          <span className="font-normal text-muted">At least 8 characters.</span>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          The same again
          <input name="again" type="password" required minLength={8} maxLength={128} autoComplete="new-password" className={authInput} />
        </label>
        {error && (
          <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-sm text-warn-ink">
            {error}{" "}
            {error.includes("expired") && <Link href="/forgot-password">Ask for a new link</Link>}
          </p>
        )}
        <button type="submit" disabled={busy} className={authButton}>
          {busy ? "Saving…" : "Save and sign in"}
        </button>
      </form>
    </>
  );
}
