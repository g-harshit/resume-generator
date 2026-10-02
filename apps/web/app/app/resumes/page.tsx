"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ResumeSummary } from "@/lib/api";

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });

export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listResumes()
      .then((r) => !cancelled && setResumes(r))
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-4xl sm:text-5xl">My resumes</h1>
        <Link
          href="/app/new"
          className="inline-flex h-11 items-center rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover hover:text-white"
        >
          New resume
        </Link>
      </div>

      {error ? (
        <p role="alert" className="text-warn-ink">{error}</p>
      ) : resumes === null ? (
        <p role="status" className="text-muted">Loading…</p>
      ) : resumes.length === 0 ? (
        <p className="text-muted">
          No resumes yet. <Link href="/app/new">Paste a job description</Link> to make your first.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {resumes.map((r) => (
            <li key={r.id}>
              <Link
                href={`/app/resume?id=${r.id}`}
                className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-4 text-ink hover:bg-ground hover:text-ink"
              >
                <span className="min-w-0 flex-1 font-semibold">{r.title}</span>
                <span className="text-sm text-muted capitalize">{r.template}</span>
                {r.total !== null && (
                  <span className="text-sm text-muted">
                    {r.covered}/{r.total} keywords
                  </span>
                )}
                <span className="text-sm text-muted">{dateFormat.format(new Date(r.updated_at))}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
