"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, type Job, type TermMatch } from "@/lib/api";

const MIN_CHARS = 200; // mirrors the API's check, so we don't send what it would refuse

export default function NewResumePage() {
  // useSearchParams (the ?job= in the URL) needs a Suspense boundary.
  return (
    <Suspense fallback={<p role="status" className="text-muted">Loading…</p>}>
      <NewResume />
    </Suspense>
  );
}

function errorMessage(err: unknown) {
  return err instanceof TypeError
    ? "Can't reach the server. Check your connection and try again."
    : (err as Error).message;
}

function NewResume() {
  const router = useRouter();
  const pathname = usePathname();
  const jobParam = useSearchParams().get("job");
  const [text, setText] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A refresh (or a link) with ?job= shows that job again, without reading it twice.
  useEffect(() => {
    const id = Number(jobParam);
    if (!id || job?.id === id) return;
    let cancelled = false;
    api
      .getJob(id)
      .then((j) => !cancelled && setJob(j))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [jobParam, job?.id]);

  async function read(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setReading(true);
    try {
      const j = await api.addJob(text);
      setJob(j);
      router.replace(`${pathname}?job=${j.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setReading(false);
    }
  }

  function startOver() {
    setJob(null);
    setText("");
    router.replace(pathname);
  }

  return (
    <div className="flex flex-col gap-6">
      <ol aria-label="Steps" className="flex flex-wrap items-center gap-2.5 text-sm text-muted">
        <li className="font-semibold text-ink">1 · Job description</li>
        <li aria-hidden="true">—</li>
        <li>2 · Template</li>
        <li aria-hidden="true">—</li>
        <li>3 · Edit</li>
      </ol>
      <h1 className="font-display text-4xl sm:text-5xl">Which job is this for?</h1>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {job ? (
          <section aria-label="The job" className="flex flex-col gap-3">
            <p className="text-[15px] text-muted">
              We read this job. The comparison on the right updates whenever your profile changes.
            </p>
            <button
              type="button"
              onClick={startOver}
              className="h-11 self-start rounded-[10px] border border-line-strong bg-surface px-4 text-sm hover:bg-sunken"
            >
              Use a different job
            </button>
          </section>
        ) : (
          <form onSubmit={read} className="flex flex-col gap-2.5">
            <label htmlFor="jd" className="text-[15px] font-semibold">
              Paste the job description
            </label>
            <textarea
              id="jd"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Copy the whole posting, including the requirements, and paste it here."
              className="min-h-[420px] resize-y rounded-xl border border-line-strong bg-surface p-4.5 text-sm leading-relaxed focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none"
            />
            {error && (
              <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-sm text-warn-ink">
                {error}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={reading || text.trim().length < MIN_CHARS}
                className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {reading ? "Reading the job…" : "Read the job"}
              </button>
              {text.trim().length > 0 && text.trim().length < MIN_CHARS && (
                <span className="text-sm text-muted">Paste the whole posting — that looks too short.</span>
              )}
            </div>
          </form>
        )}

        <WhatWeFound job={job} reading={reading} />
      </div>
    </div>
  );
}

function Chip({ m }: { m: TermMatch }) {
  const where = m.where.map((w) => (w.section === "skills" ? "your skills" : w.label)).join(", ");
  return (
    <li
      title={m.covered ? `Found in ${where}` : "Not in your profile"}
      className={`rounded-full px-2.5 py-1 text-[13px] ${
        m.covered ? "bg-accent-soft text-accent-ink" : "border border-dashed border-warn bg-warn-soft text-warn-ink"
      }`}
    >
      {m.covered ? "✓ " : ""}
      {m.term}
      <span className="sr-only">{m.covered ? ` — in your profile (${where})` : " — not in your profile"}</span>
    </li>
  );
}

function Terms({ title, terms }: { title: string; terms: TermMatch[] }) {
  if (!terms.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="flex flex-wrap gap-1.5">
        {terms.map((m) => (
          <Chip key={m.term} m={m} />
        ))}
      </ul>
    </div>
  );
}

function WhatWeFound({ job, reading }: { job: Job | null; reading: boolean }) {
  return (
    <aside aria-label="What we found" className="flex flex-col gap-4.5 self-start rounded-xl border border-line bg-surface p-5.5">
      <h2 className="text-[13px] font-semibold tracking-wider text-muted uppercase">What we found</h2>
      {!job ? (
        <p className="text-sm leading-relaxed text-muted">
          {reading
            ? "Reading the job — this takes a few seconds…"
            : "Paste a job and we'll pick out the role and what it asks for, and show which of those your profile already covers."}
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-0.5">
            <span className="text-xl font-semibold">{job.title || "Untitled role"}</span>
            <span className="text-[15px] text-muted">
              {[job.company, job.location, job.seniority].filter(Boolean).join(" · ")}
            </span>
          </div>

          {job.match ? (
            <>
              <Terms title="Must have" terms={job.match.must_have} />
              <Terms title="Nice to have" terms={job.match.nice_to_have} />
              <Terms title="Also mentioned" terms={job.match.keywords} />
              {job.match.total > 0 && (
                <div className="flex flex-col gap-2 rounded-lg bg-ground p-3.5">
                  <div className="flex justify-between text-sm font-semibold">
                    <span>Your profile covers</span>
                    <span>
                      {job.match.covered} of {job.match.total}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-line" aria-hidden="true">
                    <div
                      className="h-1.5 rounded-full bg-accent"
                      style={{ width: `${(100 * job.match.covered) / job.match.total}%` }}
                    />
                  </div>
                  {job.match.covered < job.match.total && (
                    <p className="text-[13px] leading-normal text-muted">
                      Dashed skills aren&apos;t in your profile. If you have them,{" "}
                      <Link href="/app/profile">add them to your profile</Link> — we never add a
                      skill for you.
                    </p>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted">
              <Link href="/app">Upload your resume</Link> to see how your profile matches this job.
            </p>
          )}

          <div className="flex flex-col gap-1.5">
            <button
              type="button"
              disabled
              className="h-12 rounded-[10px] bg-accent text-[15px] font-medium text-white disabled:opacity-50"
            >
              Choose a template
            </button>
            <span className="text-center text-[13px] text-muted">Templates are the next thing being built.</span>
          </div>
        </>
      )}
    </aside>
  );
}
