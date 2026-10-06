"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Profile, type ResumeSummary, saveFile } from "@/lib/api";
import { toShow } from "@/lib/notes";
import { Loading } from "@/components/loading";

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function errorMessage(err: unknown) {
  return err instanceof TypeError ? "Can't reach the server." : (err as Error).message;
}

function ProfileCard({ profile }: { profile: Profile | null }) {
  if (!profile) {
    return (
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-surface px-5 py-4">
        <span className="flex-1 text-[15px]">You don&apos;t have a profile yet. Every resume is built from one.</span>
        <Link href="/app" className="text-sm">
          Upload your resume
        </Link>
      </div>
    );
  }
  const d = profile.data;
  const bullets = d.experience.reduce((n, e) => n + e.bullets.length, 0);
  const skills = d.skills.reduce((n, g) => n + g.items.length, 0);
  const shown = toShow(d, profile.checks, profile.notes);
  const issues = [...shown.general, ...shown.placed];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl border border-line bg-surface px-5 py-4">
      <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
        </svg>
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold">Your profile</span>
        <span className="text-sm text-muted">
          {plural(d.experience.length, "role")} · {plural(bullets, "line")} · {plural(skills, "skill")} ·{" "}
          {plural(d.projects.length, "project")} ·
          updated {dateFormat.format(new Date(profile.updated_at))}
          {!profile.reviewed_at && " · not confirmed yet"}
        </span>
      </div>
      {issues.length > 0 && (
        <span className="rounded-full bg-warn-soft px-3 py-1.5 text-sm text-warn-ink">
          {issues.length === 1 ? issues[0]!.message.replace(/\.$/, "") : `${issues.length} things to check`}
        </span>
      )}
      <Link
        href="/app/profile"
        className="inline-flex h-10 items-center rounded-[10px] border border-line-strong px-3.5 text-sm text-ink hover:bg-sunken hover:text-ink"
      >
        Edit profile
      </Link>
    </div>
  );
}

function Row({
  resume,
  onChanged,
  onError,
}: {
  resume: ResumeSummary;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function act(name: string, fn: () => Promise<void>) {
    setBusy(name);
    try {
      await fn();
    } catch (err) {
      onError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const action = "h-9 rounded-lg px-2.5 text-sm text-accent hover:bg-sunken disabled:opacity-50";

  return (
    <tr className="border-t border-sunken align-top">
      <td className="px-5 py-3.5">
        <Link href={`/app/resume?id=${resume.id}`} className="font-semibold text-ink hover:text-accent">
          {/* The resume's own title ("… (copy)" for a duplicate), without the company,
              which is on the line below. */}
          {resume.company ? resume.title.replace(` — ${resume.company}`, "") : resume.title}
        </Link>
        <div className="text-[13px] text-muted">{resume.company || (resume.job_id ? "" : "Job no longer available")}</div>
      </td>
      <td className="px-3 py-3.5 text-sm capitalize">{resume.template}</td>
      <td className="px-3 py-3.5 text-sm">
        {resume.total !== null ? (
          <span>
            <span className="font-semibold">{resume.covered}</span>/{resume.total}
          </span>
        ) : (
          <span className="text-muted">—</span>
        )}
      </td>
      <td className="px-3 py-3.5 text-sm text-muted capitalize">{resume.source === "extension" ? "Extension" : resume.source ? "Pasted" : "—"}</td>
      <td className="px-3 py-3.5 text-sm whitespace-nowrap text-muted">{dateFormat.format(new Date(resume.updated_at))}</td>
      <td className="px-3 py-2 text-right">
        {confirmDelete ? (
          <span className="inline-flex flex-wrap items-center justify-end gap-1 text-sm">
            Delete this resume?
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => act("delete", async () => {
                await api.deleteResume(resume.id);
                onChanged();
              })}
              className="h-9 rounded-lg bg-warn-ink px-2.5 font-medium text-white disabled:opacity-50"
            >
              {busy === "delete" ? "Deleting…" : "Delete"}
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)} className={action}>
              Keep
            </button>
          </span>
        ) : (
          <span className="inline-flex flex-wrap justify-end gap-0.5">
            <Link href={`/app/resume?id=${resume.id}`} className={`${action} inline-flex items-center`}>
              Open
            </Link>
            <button type="button" disabled={busy !== null} onClick={() => act("pdf", async () => saveFile(await api.resumePdf(resume.id, resume.template)))} className={action}>
              {busy === "pdf" ? "Making…" : "PDF"}
            </button>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => act("copy", async () => {
                const copy = await api.duplicateResume(resume.id);
                router.push(`/app/resume?id=${copy.id}`);
              })}
              className={action}
            >
              {busy === "copy" ? "Copying…" : "Duplicate"}
            </button>
            <button
              type="button"
              disabled={busy !== null || !resume.job_id}
              title="Tailor again from your profile as it is now (replaces edits to this resume)"
              onClick={() => act("retailor", async () => {
                await api.retailorResume(resume.id);
                onChanged();
              })}
              className={action}
            >
              {busy === "retailor" ? "Refreshing…" : "Refresh from profile"}
            </button>
            <button type="button" disabled={busy !== null} onClick={() => setConfirmDelete(true)} className={`${action} text-warn-ink`}>
              Delete
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listResumes(), api.getProfile()])
      .then(([r, p]) => {
        if (cancelled) return;
        setResumes(r);
        setProfile(p);
      })
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [reload]);

  return (
    <div className="flex max-w-5xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-4xl sm:text-5xl">My resumes</h1>
        <Link
          href="/app/new"
          className="inline-flex h-11 items-center rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover hover:text-white"
        >
          New resume
        </Link>
      </div>

      {resumes !== null && <ProfileCard profile={profile} />}

      {error && (
        <p role="alert" className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
          {error}
        </p>
      )}

      {resumes === null ? (
        !error && <Loading />
      ) : resumes.length === 0 ? (
        <p className="text-muted">
          No resumes yet. <Link href="/app/new">Paste a job description</Link> to make your first.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[720px] text-left">
            <thead>
              <tr className="bg-ground/60 text-[13px] text-muted">
                <th scope="col" className="px-5 py-2.5 font-medium">Job</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Template</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Keywords</th>
                <th scope="col" className="px-3 py-2.5 font-medium">From</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Updated</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {resumes.map((r) => (
                <Row key={r.id} resume={r} onChanged={() => setReload((n) => n + 1)} onError={setError} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {resumes && resumes.length > 0 && (
        <p className="text-[13px] text-muted">
          Each resume is a snapshot: editing your profile later doesn&apos;t change one you&apos;ve
          already sent. Refresh it to rebuild it from your profile as it is now.
        </p>
      )}
    </div>
  );
}
