"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { APP_NAME, EXTENSION_ID } from "@/lib/config";

// The bit of the Chrome API a web page gets when an extension lists the page's origin
// in externally_connectable.
type ChromeRuntime = {
  sendMessage: (id: string, message: unknown, callback: (response: unknown) => void) => void;
  lastError?: { message?: string };
};
declare global {
  interface Window {
    chrome?: { runtime?: ChromeRuntime };
  }
}

type State = "sending" | "connected" | "no-extension";

/** Hand the website's login to the Chrome extension, then say so. */
function send(token: string): Promise<State> {
  const runtime = window.chrome?.runtime;
  if (!runtime?.sendMessage) return Promise.resolve("no-extension");
  return new Promise((resolve) => {
    try {
      runtime.sendMessage(EXTENSION_ID, { type: "connect", token }, (response) => {
        const ok = !runtime.lastError && (response as { ok?: boolean } | undefined)?.ok;
        resolve(ok ? "connected" : "no-extension");
      });
    } catch {
      resolve("no-extension");
    }
  });
}

export default function ConnectExtension() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [state, setState] = useState<State>("sending");

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent("/extension/connect")}`);
      return;
    }
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    void send(token).then((s) => !cancelled && setState(s));
    return () => {
      cancelled = true;
    };
  }, [loading, user, router]);

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center gap-5 px-4 py-16">
      <span className="font-display text-3xl">{APP_NAME}</span>
      {state === "connected" ? (
        <>
          <h1 className="font-display text-4xl leading-tight">The extension is signed in.</h1>
          <p className="text-[17px] leading-relaxed text-muted">
            You can close this tab. Open a job posting and click the {APP_NAME} icon in Chrome&apos;s
            toolbar.
          </p>
        </>
      ) : state === "no-extension" ? (
        <>
          <h1 className="font-display text-4xl leading-tight">We couldn&apos;t reach the extension.</h1>
          <p className="text-[17px] leading-relaxed text-muted">
            Open this page in Chrome with the {APP_NAME} extension installed and enabled, then reload
            it. Your account is fine; nothing was changed.
          </p>
          <Link href="/app">Go to your resumes instead</Link>
        </>
      ) : (
        <p role="status" className="text-muted">
          Signing the extension in…
        </p>
      )}
    </main>
  );
}
