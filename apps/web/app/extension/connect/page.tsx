"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { APP_NAME, EXTENSION_IDS } from "@/lib/config";

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

/** Send the login to one extension ID; true if that extension took it. */
function sendTo(runtime: ChromeRuntime, id: string, token: string): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      runtime.sendMessage(id, { type: "connect", token }, (response) => {
        resolve(!runtime.lastError && Boolean((response as { ok?: boolean } | undefined)?.ok));
      });
    } catch {
      resolve(false);
    }
  });
}

/** Hand the website's login to the Chrome extension (the Store's, or an unpacked one),
 *  then say so. */
async function send(token: string): Promise<State> {
  const runtime = window.chrome?.runtime;
  if (!runtime?.sendMessage) return "no-extension";
  const results = await Promise.all(EXTENSION_IDS.map((id) => sendTo(runtime, id, token)));
  return results.some(Boolean) ? "connected" : "no-extension";
}

export default function ConnectExtension() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [state, setState] = useState<State>("sending");

  // Hand over the login this browser already holds, straight away: no need to wait for
  // the API to confirm it (on the free plan it may be asleep, and waking takes up to a
  // minute). A token that turns out to be stale just signs the extension out again.
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    void send(token).then((s) => !cancelled && setState(s));
    return () => {
      cancelled = true;
    };
  }, []);

  // Not signed in on the website: sign in first, then come back here.
  useEffect(() => {
    if (!loading && !user && !getToken()) {
      router.replace(`/login?next=${encodeURIComponent("/extension/connect")}`);
    }
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
