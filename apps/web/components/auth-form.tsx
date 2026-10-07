"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { GoogleButton } from "@/components/google-button";
import { useAuth } from "@/lib/auth-context";
import { APP_NAME, GOOGLE_CLIENT_ID } from "@/lib/config";
import { LogoMark } from "@/components/logo-mark";

type Mode = "login" | "register";

const COPY: Record<Mode, { title: string; lead: string; submit: string; busy: string }> = {
  login: {
    title: "Welcome back.",
    lead: "Sign in to your profile and resumes.",
    submit: "Sign in",
    busy: "Signing in…",
  },
  register: {
    title: "Create your account.",
    lead: "Next you'll upload the resume you use today. We'll turn it into a profile you own.",
    submit: "Create account",
    busy: "Creating account…",
  },
};

/** Only same-site paths, so `?next=` can't send someone to another site after login. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/app";
}

const inputClass =
  "h-11 rounded-lg border border-line-strong bg-surface px-3 text-base text-ink " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

export function AuthForm({ mode }: { mode: Mode }) {
  const { user, loading, login, register, loginWithGoogle } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const copy = COPY[mode];

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, next, router]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, String(form.get("name")));
      // The effect above redirects once `user` is set.
    } catch (err) {
      setError(
        err instanceof TypeError
          ? "Can't reach the server. Check your connection and try again."
          : (err as Error).message,
      );
      setSubmitting(false);
    }
  }

  async function onGoogle(credential: string) {
    setError(null);
    setSubmitting(true);
    try {
      await loginWithGoogle(credential);
    } catch (err) {
      setError(
        err instanceof TypeError
          ? "Can't reach the server. Check your connection and try again."
          : (err as Error).message,
      );
      setSubmitting(false);
    }
  }

  const otherHref = `${mode === "login" ? "/register" : "/login"}${
    next !== "/app" ? `?next=${encodeURIComponent(next)}` : ""
  }`;

  return (
    <main className="flex flex-1 flex-col">
      <header className="flex h-18 items-center border-b border-line px-4 sm:px-10">
        <Link href="/" className="flex items-center gap-2.5 font-display text-3xl text-ink hover:text-ink">
          <LogoMark size={30} />
          {APP_NAME}
        </Link>
      </header>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col gap-8 px-4 py-14">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-5xl leading-tight">{copy.title}</h1>
          <p className="text-base leading-relaxed text-muted">{copy.lead}</p>
        </div>

        {GOOGLE_CLIENT_ID && (
          <div className="flex flex-col gap-5">
            <GoogleButton text={mode === "login" ? "signin_with" : "signup_with"} onCredential={onGoogle} />
            <div className="flex items-center gap-3 text-sm text-muted">
              <span className="h-px flex-1 bg-line" />
              or with email
              <span className="h-px flex-1 bg-line" />
            </div>
          </div>
        )}

        {/* method="post": if someone submits before the page's JavaScript has loaded,
            the browser falls back to a native submit, and a GET would put the password
            in the URL (history, server logs). A POST keeps it out. */}
        <form method="post" onSubmit={onSubmit} className="flex flex-col gap-4">
          {mode === "register" && (
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Your name
              <input name="name" required maxLength={120} autoComplete="name" className={inputClass} />
            </label>
          )}
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Email
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Password
            <input
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              maxLength={128}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              aria-describedby={mode === "register" ? "password-hint" : undefined}
              className={inputClass}
            />
            {mode === "register" && (
              <span id="password-hint" className="text-sm font-normal text-muted">
                At least 8 characters.
              </span>
            )}
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-sm text-warn-ink">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 h-12 rounded-[10px] bg-accent text-base font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-60"
          >
            {submitting ? copy.busy : copy.submit}
          </button>
        </form>

        <div className="flex flex-col gap-2 text-sm text-muted">
          <p>
            {mode === "login" ? "New here? " : "Already have an account? "}
            <Link href={otherHref}>{mode === "login" ? "Create an account" : "Sign in"}</Link>
          </p>
          {mode === "login" && (
            <p>
              <Link href="/forgot-password">Forgot your password?</Link>
            </p>
          )}
          {mode === "register" && (
            <p>
              By creating an account you agree to the <Link href="/terms">terms</Link> and{" "}
              <Link href="/privacy">privacy policy</Link>.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
