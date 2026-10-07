"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, type Preview, type ResumeFull, saveFile } from "@/lib/api";
import { PdfPages } from "@/components/pdf-pages";
import { Loading } from "@/components/loading";

export default function CoverLetterPage() {
  // useSearchParams (?id=) needs a Suspense boundary.
  return (
    <Suspense fallback={<Loading />}>
      <Loader />
    </Suspense>
  );
}

function errorMessage(err: unknown) {
  return err instanceof TypeError ? "Can't reach the server." : (err as Error).message;
}

function Loader() {
  const id = Number(useSearchParams().get("id"));
  const [resume, setResume] = useState<ResumeFull | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api
      .getResume(id)
      .then((r) => !cancelled && setResume(r))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!id) return <p className="text-muted">No resume chosen. <Link href="/app/resumes">See your resumes</Link>.</p>;
  if (error) return <p role="alert" className="text-warn-ink">{error}</p>;
  if (!resume) return <Loading />;
  return <Letter key={resume.cover_letter?.generated_at ?? "none"} resume={resume} onWritten={setResume} />;
}

function Letter({ resume, onWritten }: { resume: ResumeFull; onWritten: (r: ResumeFull) => void }) {
  const letter = resume.cover_letter;
  const [writing, setWriting] = useState(false);
  const [confirmRewrite, setConfirmRewrite] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // What's printed, and the copy being edited (null when not editing).
  const [saved, setSaved] = useState(letter);
  const [draft, setDraft] = useState<{ text: string; greeting: string; sign_off: string } | null>(null);
  const [saving, setSaving] = useState(false);
  // The PDF's own pages, so what's on screen is what downloads.
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewFor, setPreviewFor] = useState<string | null>(null);
  const shownKey = saved ? `${saved.greeting}|${saved.text}|${saved.sign_off}` : null;

  useEffect(() => {
    if (!saved) return;
    let cancelled = false;
    const key = `${saved.greeting}|${saved.text}|${saved.sign_off}`;
    api
      .coverLetterPreview(resume.id, resume.template)
      .then((p) => {
        if (cancelled) return;
        setPreview(p);
        setPreviewFor(key);
      })
      .catch((err) => !cancelled && setProblem(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [resume.id, resume.template, saved]);

  async function write() {
    setConfirmRewrite(false);
    setWriting(true);
    setProblem(null);
    try {
      onWritten(await api.writeCoverLetter(resume.id));
    } catch (err) {
      setProblem(errorMessage(err));
      setWriting(false);
    }
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    setProblem(null);
    try {
      const r = await api.saveCoverLetter(resume.id, draft);
      setSaved(r.cover_letter);
      setDraft(null);
    } catch (err) {
      setProblem(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function download() {
    setDownloading(true);
    try {
      saveFile(await api.coverLetterPdf(resume.id, resume.template));
    } catch (err) {
      setProblem(errorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  const field =
    "rounded-lg border border-line-strong bg-surface px-3 py-2 font-serif text-[16px] leading-relaxed focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none";
  const stale = !preview || previewFor !== shownKey;

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <div className="flex flex-col gap-1">
        <span className="text-sm text-muted">
          <Link href={`/app/resume?id=${resume.id}`}>{resume.title}</Link> / Cover letter
        </span>
        <h1 className="font-display text-4xl">Cover letter</h1>
      </div>

      {problem && (
        <p role="alert" className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
          {problem}
        </p>
      )}

      {!saved ? (
        <div className="flex flex-col items-start gap-4 rounded-xl border border-line bg-surface p-6">
          <p className="leading-relaxed text-muted">
            A letter that says what your resume can&apos;t: why this role and company, the thread
            through your work, and how you&apos;d approach the job — pointing to your experience, not
            repeating it. Every sentence is checked against your resume; anything it can&apos;t back up
            is rewritten or left out, and you&apos;ll see what and why. You can edit all of it before
            downloading.
          </p>
          <button
            type="button"
            onClick={write}
            disabled={writing}
            className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {writing ? "Writing… (15–30 s)" : "Write my cover letter"}
          </button>
        </div>
      ) : draft ? (
        <section aria-label="Edit the letter" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Greeting</span>
            <input
              value={draft.greeting}
              onChange={(e) => setDraft({ ...draft, greeting: e.target.value })}
              maxLength={200}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Letter <span className="font-normal text-muted">— separate paragraphs with a blank line</span>
            </span>
            <textarea
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
              rows={16}
              className={`field-sizing-content min-h-72 ${field}`}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Sign-off</span>
            <textarea
              value={draft.sign_off}
              onChange={(e) => setDraft({ ...draft, sign_off: e.target.value })}
              rows={2}
              maxLength={300}
              className={field}
            />
          </label>
          <p className="text-xs text-muted">
            Your name, contact details and today&apos;s date are added at the top, as on your resume.
          </p>
          <div className="flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={save}
              disabled={saving || !draft.text.trim()}
              className="h-11 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              disabled={saving}
              className="h-11 rounded-[10px] px-4 text-sm text-muted hover:bg-sunken"
            >
              Cancel
            </button>
          </div>
        </section>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={() => setDraft({ text: saved.text, greeting: saved.greeting, sign_off: saved.sign_off })}
              disabled={writing}
              className="h-11 rounded-[10px] border border-line-strong bg-surface px-4 text-sm font-medium hover:bg-sunken disabled:opacity-50"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={() => setConfirmRewrite(true)}
              disabled={writing}
              className="h-11 rounded-[10px] border border-line-strong bg-surface px-4 text-sm hover:bg-sunken disabled:opacity-50"
            >
              {writing ? "Writing… (15–30 s)" : "Rewrite"}
            </button>
            <button
              type="button"
              onClick={download}
              disabled={downloading || writing || stale}
              className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {downloading ? "Making PDF…" : "Download PDF"}
            </button>
          </div>
          {confirmRewrite && (
            <div
              role="alertdialog"
              aria-label="Rewrite the letter?"
              className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm"
            >
              <span className="flex-1">Rewriting replaces this letter, including your edits.</span>
              <button type="button" onClick={write} className="h-10 rounded-lg bg-accent px-3 font-medium text-white">
                Rewrite
              </button>
              <button
                type="button"
                onClick={() => setConfirmRewrite(false)}
                className="h-10 rounded-lg px-3 text-muted hover:bg-sunken"
              >
                Cancel
              </button>
            </div>
          )}
          <section aria-label="The letter, as it downloads" className="flex flex-col gap-2">
            <span className="text-sm text-muted">
              {preview ? `${preview.pages} page${preview.pages > 1 ? "s" : ""} · exactly what downloads` : "Laying out…"}
            </span>
            <div className="relative" aria-busy={stale}>
              <div className={stale ? "opacity-60 blur-[3px]" : ""}>
                {preview ? (
                  <PdfPages images={preview.images} links={preview.links} title={`${resume.title} cover letter`} />
                ) : (
                  <div className="aspect-[210/297] rounded-lg border border-line bg-surface" />
                )}
              </div>
              {stale && (
                <div className="absolute inset-0 flex justify-center">
                  <div
                    role="status"
                    className="sticky top-1/3 mt-24 flex h-fit items-center gap-2.5 rounded-full border border-line bg-surface px-4 py-2 text-sm shadow-md"
                  >
                    <span
                      aria-hidden="true"
                      className="size-4 animate-spin rounded-full border-2 border-accent border-t-transparent"
                    />
                    Updating the preview…
                  </div>
                </div>
              )}
            </div>
          </section>
          {saved.removed.length > 0 && (
            <section aria-label="Left out" className="flex flex-col gap-2 rounded-xl bg-warn-soft p-4 text-warn-ink">
              <h2 className="text-sm font-semibold">Left out ({saved.removed.length})</h2>
              <ul className="flex flex-col gap-2 text-[13px] leading-normal">
                {saved.removed.map((r) => (
                  <li key={r.text}>
                    <span className="italic">&ldquo;{r.text}&rdquo;</span> — {r.reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
