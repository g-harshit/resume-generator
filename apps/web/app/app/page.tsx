"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ResumeDropzone } from "@/components/resume-dropzone";
import { api, type Profile, type Upload } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { toShow } from "@/lib/notes";

const POLL_MS = 1500;

type State =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "working"; upload: Upload | null; filename: string }
  | { kind: "failed"; message: string }
  | { kind: "ready"; profile: Profile; upload: Upload | null };

function errorMessage(err: unknown) {
  return err instanceof TypeError
    ? "Can't reach the server. Check your connection and try again."
    : (err as Error).message;
}

export default function AppHome() {
  const { user } = useAuth();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [replacing, setReplacing] = useState(false);
  const alive = useRef(true);

  const showProfile = useCallback(async (latest: Upload | null = null) => {
    const profile = await api.getProfile();
    if (!profile) {
      setState({ kind: "empty" });
      return;
    }
    // Offer a newer upload that wasn't applied (the profile had already been reviewed).
    setState({ kind: "ready", profile, upload: latest && !latest.applied ? latest : null });
  }, []);

  useEffect(() => {
    // Deferred a tick so the effect body itself doesn't set state.
    const t = setTimeout(() => {
      showProfile().catch((err) => setState({ kind: "failed", message: errorMessage(err) }));
    }, 0);
    alive.current = true;
    return () => {
      clearTimeout(t);
      alive.current = false;
    };
  }, [showProfile]);

  // Poll until the parse finishes; stops if the page is left.
  async function watch(id: number, filename: string) {
    while (alive.current) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      let upload: Upload;
      try {
        upload = await api.getUpload(id);
      } catch {
        continue; // a blip while the API restarts: keep waiting
      }
      if (!alive.current) return;
      if (upload.status === "done") return showProfile(upload);
      if (upload.status === "failed") {
        return setState({ kind: "failed", message: upload.error ?? "We couldn't read that file." });
      }
      setState({ kind: "working", upload, filename });
    }
  }

  async function start(file: File) {
    setState({ kind: "working", upload: null, filename: file.name });
    try {
      const upload = await api.upload(file);
      setState({ kind: "working", upload, filename: file.name });
      await watch(upload.id, file.name);
    } catch (err) {
      setState({ kind: "failed", message: errorMessage(err) });
    }
  }

  async function replaceWith(upload: Upload) {
    setReplacing(true);
    try {
      await api.applyUpload(upload.id);
      await showProfile();
    } finally {
      setReplacing(false);
    }
  }

  const firstName = user?.name.split(/\s+/)[0];

  if (state.kind === "loading") {
    return <p role="status" className="text-muted">Loading…</p>;
  }

  if (state.kind === "ready") {
    const { profile, upload } = state;
    const d = profile.data;
    const pending = upload;
    const shown = toShow(d, profile.checks, profile.notes);
    const toCheck = shown.general.length + shown.placed.length;
    const bullets = d.experience.reduce((n, e) => n + e.bullets.length, 0);
    const skills = d.skills.reduce((n, g) => n + g.items.length, 0);

    return (
      <div className="flex max-w-3xl flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-5xl leading-tight">Hi {firstName}.</h1>
          <p className="text-muted">
            {profile.reviewed_at
              ? "Your profile is ready."
              : "We read your resume. Here's what we found."}
          </p>
        </div>

        {pending && (
          <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 sm:flex-row sm:items-center">
            <p className="flex-1 text-sm">
              We read <strong>{pending.filename}</strong>. Your profile has your own edits, so we
              haven&apos;t changed it.
            </p>
            <button
              type="button"
              disabled={replacing}
              onClick={() => replaceWith(pending)}
              className="h-11 rounded-[10px] border border-line-strong bg-surface px-4 text-sm hover:bg-sunken disabled:opacity-60"
            >
              {replacing ? "Replacing…" : "Replace my profile with it"}
            </button>
          </div>
        )}

        <section aria-label="What we read" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
          <div className="flex flex-col">
            <span className="text-xl font-semibold">{d.basics.name || "Name not found"}</span>
            <span className="text-muted">
              {[d.basics.headline, d.basics.email, d.basics.location].filter(Boolean).join(" · ")}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Roles", d.experience.length],
              ["Bullets", bullets],
              ["Skills", skills],
              ["Education", d.education.length],
            ].map(([label, n]) => (
              <div key={label} className="rounded-lg bg-ground px-3 py-2.5">
                <dt className="text-sm text-muted">{label}</dt>
                <dd className="text-2xl font-semibold">{n}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="flex flex-wrap items-center gap-4">
          <Link
            href="/app/profile"
            className="inline-flex h-12 items-center rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover hover:text-white"
          >
            {profile.reviewed_at ? "Edit your profile" : "Review your profile"}
          </Link>
          {toCheck > 0 && (
            <span className="rounded-full bg-warn-soft px-3 py-1.5 text-sm font-medium text-warn-ink">
              {toCheck === 1 ? "1 thing to check" : `${toCheck} things to check`}
            </span>
          )}
        </div>

        <details className="group rounded-xl border border-line bg-surface p-5">
          <summary className="cursor-pointer text-sm font-medium">Start over with a different file</summary>
          <div className="mt-4">
            <ResumeDropzone onFile={start} />
          </div>
        </details>
      </div>
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-7">
      <div className="flex flex-col gap-2.5">
        <h1 className="font-display text-5xl leading-tight">Start with the resume you already have.</h1>
        <p className="text-[17px] leading-relaxed text-muted">
          We read it into a profile you own. Every tailored resume is built from that profile,
          so you fix a detail once, not in ten files.
        </p>
      </div>

      {state.kind === "working" ? (
        <div role="status" className="flex items-center gap-3.5 rounded-xl border border-line bg-surface px-4.5 py-4">
          <span className="flex h-12 w-10 shrink-0 items-center justify-center rounded-md bg-sunken text-[11px] font-semibold text-muted">
            {state.filename.split(".").pop()?.toUpperCase()}
          </span>
          <div className="flex flex-1 flex-col gap-2">
            <div className="flex flex-wrap justify-between gap-2 text-[15px]">
              <span className="font-medium">{state.filename}</span>
              <span className="text-muted">
                {state.upload?.status === "running" ? "Reading your resume…" : "Uploading…"}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
              <div className="h-1.5 w-1/3 animate-[indeterminate_1.4s_ease-in-out_infinite] rounded-full bg-accent" />
            </div>
            <span className="text-sm text-muted">This can take up to a minute.</span>
          </div>
        </div>
      ) : (
        <>
          {state.kind === "failed" && (
            <p role="alert" className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
              {state.message}
            </p>
          )}
          <ResumeDropzone onFile={start} />
        </>
      )}

      <div className="grid gap-5 border-t border-line pt-5 sm:grid-cols-3">
        {[
          ["You check it first", "Nothing is used until you've reviewed what we read."],
          ["Only your facts", "Tailoring rewords and reorders. It never adds a skill you didn't list."],
          ["Your data stays yours", "Your file is only used to build your profile."],
        ].map(([title, body]) => (
          <div key={title} className="flex flex-col gap-1">
            <span className="text-sm font-semibold">{title}</span>
            <span className="text-[13px] leading-normal text-muted">{body}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
