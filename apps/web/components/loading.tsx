"use client";

import { useEffect, useState } from "react";

/**
 * "Loading…", and after a few seconds, why it's taking long: on the free hosting plan
 * the API sleeps when nobody has used it for a while, and waking it takes up to a
 * minute. Better said than leaving people to think the site is broken.
 */
export function Loading({ className = "" }: { className?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div role="status" className={`flex flex-col gap-1 text-muted ${className}`}>
      <span>Loading…</span>
      {slow && (
        <span className="text-sm">
          Waking up the server — the first visit in a while can take up to a minute.
        </span>
      )}
    </div>
  );
}
