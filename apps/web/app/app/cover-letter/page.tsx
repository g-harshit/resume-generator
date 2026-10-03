"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, type ResumeFull, saveFile } from "@/lib/api";
import { useAutosave } from "@/lib/use-autosave";
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

  const { data: text, setData, save, flush } = useAutosave<string, ResumeFull>({
    initial: letter?.text ?? "",
    version: resume.version, // letters aren't versioned; the hook just passes it through
    save: (_version, t) => api.saveCoverLetter(resume.id, t),
  });

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

  async function download() {
    setDownloading(true);
    try {
      if (await flush()) saveFile(await api.coverLetterPdf(resume.id, resume.template));
    } catch (err) {
      setProblem(errorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  const saveText = { saved: "All changes saved", unsaved: "Unsaved changes…", saving: "Saving…", error: "Couldn't save", conflict: "" }[save.kind];

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

      {!letter ? (
        <div className="flex flex-col items-start gap-4 rounded-xl border border-line bg-surface p-6">
          <p className="leading-relaxed text-muted">
            A short letter for this job, written only from what&apos;s in this resume. Every sentence
            is checked: anything it can&apos;t back up is rewritten or left out, and you&apos;ll see
            what and why.
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
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span role="status" className="text-sm text-muted">{saveText}</span>
            <div className="flex flex-wrap gap-2.5">
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
                disabled={downloading || writing}
                className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {downloading ? "Making PDF…" : "Download PDF"}
              </button>
            </div>
          </div>
          {confirmRewrite && (
            <div role="alertdialog" aria-label="Rewrite the letter?" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
              <span className="flex-1">Rewriting replaces this letter, including your edits.</span>
              <button type="button" onClick={write} className="h-10 rounded-lg bg-accent px-3 font-medium text-white">
                Rewrite
              </button>
              <button type="button" onClick={() => setConfirmRewrite(false)} className="h-10 rounded-lg px-3 text-muted hover:bg-sunken">
                Cancel
              </button>
            </div>
          )}
          <label className="flex flex-col gap-2">
            <span className="text-sm text-muted">
              The greeting (&ldquo;Dear hiring team…&rdquo;) and your name are added in the PDF.
              Separate paragraphs with a blank line.
            </span>
            <textarea
              value={text}
              onChange={(e) => setData(() => e.target.value)}
              rows={18}
              className="field-sizing-content min-h-80 rounded-xl border border-line-strong bg-surface p-5 font-serif text-[16px] leading-relaxed focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none"
            />
          </label>
          {letter.removed.length > 0 && (
            <section aria-label="Left out" className="flex flex-col gap-2 rounded-xl bg-warn-soft p-4 text-warn-ink">
              <h2 className="text-sm font-semibold">
                Left out ({letter.removed.length}) — it claimed something your resume doesn&apos;t say
              </h2>
              <ul className="flex flex-col gap-2 text-[13px] leading-normal">
                {letter.removed.map((r) => (
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
