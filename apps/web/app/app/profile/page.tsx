"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { type IssuesFor, ProfileAiProvider, ProfileEditor } from "@/components/profile/profile-editor";
import { api, type Profile } from "@/lib/api";
import { notePlace, toShow } from "@/lib/notes";
import { type SaveState, useProfileEditor } from "@/lib/use-profile-editor";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null | "loading">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getProfile()
      .then((p) => {
        if (cancelled) return;
        if (p === null) router.replace("/app"); // nothing to review before an upload
        else setProfile(p);
      })
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) return <p role="alert" className="text-warn-ink">{error}</p>;
  if (profile === "loading" || profile === null) return <p role="status" className="text-muted">Loading…</p>;
  return <Review initial={profile} />;
}

function SaveStatus({ save }: { save: SaveState }) {
  const text = {
    saved: "All changes saved",
    unsaved: "Unsaved changes…",
    saving: "Saving…",
    error: save.kind === "error" ? `Couldn't save: ${save.message}` : "",
    conflict: "",
  }[save.kind];
  return (
    <span role="status" className={`text-sm ${save.kind === "error" ? "text-warn-ink" : "text-muted"}`}>
      {text}
    </span>
  );
}

function Original({ profile }: { profile: Profile }) {
  const [url, setUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const id = profile.source_document_id;
  const isPdf = profile.source_mime === "application/pdf";

  useEffect(() => {
    if (id === null) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    if (isPdf) {
      api.getUploadFile(id).then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      });
    } else {
      api.getUploadText(id).then((r) => !cancelled && setText(r.text));
    }
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, isPdf]);

  if (id === null) return null;
  return (
    <section aria-label="Your original file" className="flex flex-col gap-2.5 lg:sticky lg:top-6 lg:h-[calc(100vh-8rem)]">
      <h2 className="text-[13px] font-semibold tracking-wider text-muted uppercase">Your original</h2>
      {isPdf ? (
        url ? (
          <iframe src={url} title="Your original resume" className="h-[70vh] w-full flex-1 rounded-lg border border-line bg-surface lg:h-auto" />
        ) : (
          <div className="flex-1 rounded-lg border border-line bg-surface" />
        )
      ) : (
        <>
          <p className="text-[13px] text-muted">Word files can&apos;t be shown here, so this is the text we read from it.</p>
          <pre className="max-h-[70vh] flex-1 overflow-auto rounded-lg border border-line bg-surface p-5 font-sans text-sm leading-relaxed whitespace-pre-wrap lg:max-h-none">
            {text ?? ""}
          </pre>
        </>
      )}
    </section>
  );
}

function Review({ initial }: { initial: Profile }) {
  const router = useRouter();
  const { data, setData, checks, notes, reviewedAt, save, flush, confirm } = useProfileEditor(initial);
  const ai = useMemo(() => ({ flush }), [flush]);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const { general, placed: all } = toShow(data, checks, notes);
  const blocking = checks.filter((c) => c.blocking);

  const issues: IssuesFor = (target, field) =>
    all
      .filter((i) => i.target === target && (field === undefined || i.field === field))
      .map((i) => i.message);

  async function onConfirm() {
    setConfirming(true);
    setConfirmError(null);
    try {
      if (await confirm()) router.push("/app");
    } catch (err) {
      setConfirmError((err as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  const count = all.length + general.length;

  return (
    <div className="flex flex-col gap-6 pb-28">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-4xl sm:text-5xl">{reviewedAt ? "Your profile" : "Is this right?"}</h1>
          <p className="max-w-2xl text-[15px] text-muted">
            {reviewedAt
              ? "Everything true about you. Every resume you make is built from this."
              : "Here's what we read from your file. Fix anything we got wrong — every resume you make is built from this."}
          </p>
        </div>
        {count > 0 && (
          <span className="rounded-full bg-warn-soft px-3 py-1.5 text-sm font-medium text-warn-ink">
            {count === 1 ? "1 thing to check" : `${count} things to check`}
          </span>
        )}
      </div>

      {save.kind === "conflict" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn-ink">
          <span className="flex-1">
            Your profile was changed somewhere else (another tab?). Your latest edits here weren&apos;t saved.
          </span>
          <button type="button" onClick={() => window.location.reload()} className="h-10 rounded-lg border border-warn bg-surface px-3">
            Reload the latest
          </button>
        </div>
      )}

      <div
        className={
          initial.source_document_id === null
            ? "flex max-w-3xl flex-col" // built from scratch: no original to show beside it
            : "grid gap-7 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]"
        }
      >
        <Original profile={initial} />
        <div className="flex min-w-0 flex-col gap-4">
          {general.length > 0 && (
            <section aria-label="Notes from reading your file" className="flex flex-col gap-2 rounded-xl bg-warn-soft p-4 text-sm text-warn-ink">
              <h2 className="font-semibold">From reading your file</h2>
              <ul className="flex flex-col gap-1">
                {general.map((n) => (
                  <li key={n.message}>{n.message}</li>
                ))}
              </ul>
            </section>
          )}
          <ProfileAiProvider value={ai}>
            <ProfileEditor data={data} setData={setData} issues={issues} />
          </ProfileAiProvider>
        </div>
      </div>

      <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-surface md:left-58">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 md:px-11">
          <div className="flex flex-col">
            <SaveStatus save={save} />
            {(confirmError || blocking[0]) && !reviewedAt && (
              <span className="text-sm text-warn-ink">
                {confirmError ?? `Before confirming: ${notePlace(blocking[0]!, data)} — ${blocking[0]!.message}`}
              </span>
            )}
          </div>
          {reviewedAt ? (
            <button type="button" onClick={() => router.push("/app")} className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover">
              Done
            </button>
          ) : (
            <button
              type="button"
              disabled={confirming || blocking.length > 0 || save.kind === "conflict"}
              onClick={onConfirm}
              className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {confirming ? "Saving…" : "Looks right — save my profile"}
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
