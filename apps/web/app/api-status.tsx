"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/config";

type Status = "checking" | "ok" | "down";

// Dev-only proof that the web app can reach the API (and that CORS is right).
// Goes away when the real home page lands.
export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => setStatus(r.ok ? "ok" : "down"))
      .catch(() => setStatus("down"));
  }, []);

  const label = {
    checking: "Checking the API…",
    ok: "API and database reachable",
    down: `Can't reach the API at ${API_URL}`,
  }[status];

  const tone = {
    checking: "bg-sunken text-muted",
    ok: "bg-accent-soft text-accent-ink",
    down: "bg-warn-soft text-warn-ink",
  }[status];

  return (
    <p role="status" className={`inline-flex rounded-full px-3 py-1.5 text-sm font-medium ${tone}`}>
      {label}
    </p>
  );
}
