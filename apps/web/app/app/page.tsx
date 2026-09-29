"use client";

import { useAuth } from "@/lib/auth-context";

export default function AppHome() {
  const { user } = useAuth();
  const firstName = user?.name.split(/\s+/)[0];

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <h1 className="font-display text-5xl leading-tight">Hi {firstName}.</h1>
      <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold">Start with the resume you already have</h2>
        <p className="text-muted">
          Uploading a draft and turning it into your profile is the next thing being built.
          You&apos;ll find it here.
        </p>
      </div>
    </div>
  );
}
