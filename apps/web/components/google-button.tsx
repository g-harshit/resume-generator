"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { GOOGLE_CLIENT_ID } from "@/lib/config";

// The bits of Google Identity Services this uses (https://accounts.google.com/gsi/client).
type Gsi = {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup" }) => void;
      renderButton: (el: HTMLElement, o: Record<string, string | number>) => void;
    };
  };
};
declare global {
  interface Window {
    google?: Gsi;
  }
}

/**
 * Google's own "Sign in with Google" button. Google gives the browser a signed ID
 * token, which the API checks (`POST /auth/google`). Shows nothing when the site has
 * no Google client ID.
 */
export function GoogleButton({
  text,
  onCredential,
}: {
  text: "signin_with" | "signup_with" | "continue_with";
  onCredential: (credential: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    callback.current = onCredential;
  });

  useEffect(() => {
    const gsi = window.google?.accounts.id;
    if (!loaded || !gsi || !box.current || !GOOGLE_CLIENT_ID) return;
    gsi.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (r) => callback.current(r.credential),
      ux_mode: "popup",
    });
    gsi.renderButton(box.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      shape: "rectangular",
      text,
      logo_alignment: "center",
      width: Math.min(400, box.current.offsetWidth || 400),
    });
  }, [loaded, text]);

  if (!GOOGLE_CLIENT_ID) return null;
  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setLoaded(true)}
      />
      {/* Google draws its button here; the height keeps the page from jumping. */}
      <div ref={box} className="flex min-h-11 w-full justify-center" />
    </>
  );
}
