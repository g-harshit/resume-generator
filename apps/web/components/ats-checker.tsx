"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ResumeDropzone } from "@/components/resume-dropzone";
import { api, type AtsCheckItem, type AtsResult } from "@/lib/api";
import { rememberAtsCheck } from "@/lib/ats-claim";
import { useAuth } from "@/lib/auth-context";
import { APP_NAME } from "@/lib/config";

const ICON: Record<AtsCheckItem["status"], { mark: string; tone: string; label: string }> = {
  fail: { mark: "✕", tone: "bg-warn text-white", label: "Fix" },
  warn: { mark: "!", tone: "bg-warn-soft text-warn-ink", label: "Look at" },
  pass: { mark: "✓", tone: "bg-accent-soft text-accent-ink", label: "Passed" },
};

function CheckRow({ c }: { c: AtsCheckItem }) {
  const i = ICON[c.status];
  return (
    <li className="flex gap-3 py-3">
      <span
        aria-label={i.label}
        className={`flex size-6 shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${i.tone}`}
      >
        {i.mark}
      </span>
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">{c.title}</span>
        <span className="text-sm leading-relaxed text-muted">{c.detail}</span>
      </div>
    </li>
  );
}

function errorMessage(err: unknown) {
  return err instanceof TypeError
    ? "Can't reach the server. Check your connection and try again — the first check in a while can take up to a minute while it wakes."
    : (err as Error).message;
}

/** The free ATS checker: upload, optionally paste a job, see what an ATS reads. */
export function AtsChecker() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [jobText, setJobText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [result, setResult] = useState<AtsResult | null>(null);
  const token = params.get("r");

  // A shared or reloaded result: ?r=<token>, while it's kept (24 hours).
  useEffect(() => {
    if (!token || result?.token === token) return;
    let cancelled = false;
    api
      .getAtsCheck(token)
      .then((r) => !cancelled && setResult(r))
      .catch((err) => !cancelled && setProblem(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [token, result?.token]);

  async function run() {
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      const r = await api.atsCheck(file, jobText);
      setResult(r);
      router.replace(`${pathname}?r=${encodeURIComponent(r.token)}`, { scroll: false });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setProblem(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function keepGoing() {
    if (!result) return;
    rememberAtsCheck(result.token);
    router.push(user ? "/app" : "/register?next=/app");
  }

  function again() {
    setResult(null);
    setFile(null);
    setProblem(null);
    router.replace(pathname, { scroll: false });
  }

  if (result) {
    const { report } = result;
    const fails = report.checks.filter((c) => c.status === "fail");
    const warns = report.checks.filter((c) => c.status === "warn");
    const passes = report.checks.filter((c) => c.status === "pass");
    const kw = report.keywords;
    return (
      <div className="flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <span className="text-sm text-muted">{report.filename}</span>
          <h2 className="font-display text-4xl">
            {fails.length + warns.length === 0
              ? "An ATS reads this resume cleanly."
              : `${fails.length + warns.length} thing${fails.length + warns.length > 1 ? "s" : ""} to fix`}
          </h2>
          <p className="text-muted">
            {passes.length} of {report.checks.length} checks pass
            {fails.length > 0 && ` · ${fails.length} to fix`}
            {warns.length > 0 && ` · ${warns.length} to look at`}
            {kw && ` · ${kw.covered.length} of ${kw.covered.length + kw.missing.length} job keywords found`}
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
          <div className="flex flex-col gap-6">
            <section aria-label="Checks" className="rounded-xl border border-line bg-surface px-5 py-2">
              <ul className="divide-y divide-sunken">
                {[...fails, ...warns].map((c) => (
                  <CheckRow key={c.id} c={c} />
                ))}
              </ul>
              {passes.length > 0 && (
                <details className="border-t border-sunken py-3">
                  <summary className="cursor-pointer text-sm font-medium">Passed ({passes.length})</summary>
                  <ul className="divide-y divide-sunken">
                    {passes.map((c) => (
                      <CheckRow key={c.id} c={c} />
                    ))}
                  </ul>
                </details>
              )}
            </section>

            {kw && (
              <section aria-label="Job keywords" className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
                <h3 className="text-lg font-semibold">Keywords for {kw.job_title || "this job"}</h3>
                {kw.missing.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-warn-ink">Not in your resume ({kw.missing.length})</span>
                    <ul className="flex flex-wrap gap-1.5">
                      {kw.missing.map((t) => (
                        <li key={t} className="rounded-full border border-dashed border-warn bg-warn-soft px-2.5 py-0.5 text-[13px] text-warn-ink">
                          {t}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {kw.covered.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-accent-ink">Found ({kw.covered.length})</span>
                    <ul className="flex flex-wrap gap-1.5">
                      {kw.covered.map((t) => (
                        <li key={t} className="rounded-full bg-accent-soft px-2.5 py-0.5 text-[13px] text-accent-ink">
                          ✓ {t}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-xs text-muted">
                  Recruiters search an ATS by keywords. Only add the ones that are true of your work.
                </p>
              </section>
            )}

            <section aria-label="What an ATS reads" className="flex flex-col gap-2">
              <h3 className="text-lg font-semibold">What an ATS reads from your file</h3>
              <p className="text-sm text-muted">
                The text a simple ATS gets, in the order it reads it
                {report.file_type === "docx" ? " (Word headers, footers and text boxes left out, as many do)" : ""}.
                If lines from two columns are mixed up, or something is missing, recruiters searching
                the ATS won&apos;t find it.
              </p>
              <pre className="max-h-[480px] overflow-auto rounded-xl border border-line bg-surface p-4 font-mono text-[12px] leading-relaxed whitespace-pre-wrap">
                {report.ats_text || "(no text at all)"}
              </pre>
            </section>
          </div>

          <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
            <div className="flex flex-col gap-3 rounded-xl border border-accent bg-accent-soft p-5">
              <h3 className="text-xl font-semibold text-accent-ink">Fix these in {APP_NAME} — free</h3>
              <ul className="flex flex-col gap-1.5 text-sm text-accent-ink">
                <li>✓ Your resume becomes your profile — no retyping</li>
                <li>✓ One-column templates every ATS reads in order</li>
                {kw && kw.missing.length > 0 && <li>✓ Add the missing keywords to the lines they fit</li>}
                <li>✓ Nothing changes unless you ask</li>
              </ul>
              <button
                type="button"
                onClick={keepGoing}
                className="h-12 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover"
              >
                {user ? "Continue with this resume" : "Sign up free and fix it"}
              </button>
              <p className="text-xs leading-normal text-accent-ink/80">
                Your file is kept for 24 hours so it can come with you when you sign up, then deleted.
              </p>
            </div>
            <button type="button" onClick={again} className="self-start text-sm text-accent hover:underline">
              Check another resume
            </button>
          </aside>
        </div>
      </div>
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-5">
      <section aria-label="Check a resume" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
        {file ? (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-ground px-4 py-3">
            <span className="truncate text-sm font-medium">{file.name}</span>
            <button type="button" onClick={() => setFile(null)} className="text-sm text-accent hover:underline">
              Change
            </button>
          </div>
        ) : (
          <ResumeDropzone onFile={setFile} disabled={busy} />
        )}
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">
            Job description <span className="font-normal text-muted">(optional)</span>
          </span>
          <textarea
            value={jobText}
            onChange={(e) => setJobText(e.target.value)}
            rows={5}
            maxLength={40000}
            placeholder="Paste a job description to see which of its keywords your resume has."
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm"
          />
        </label>
        <button
          type="button"
          onClick={run}
          disabled={!file || busy}
          className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? "Checking…" : "Check my resume"}
        </button>
        {problem && (
          <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn-ink">
            {problem}
          </p>
        )}
        <p className="text-xs leading-normal text-muted">
          Free, no sign-up. PDF or Word, up to 5 MB. We keep your file for 24 hours — so it can become
          your profile if you sign up — then delete it. <Link href="/privacy">Privacy</Link>
        </p>
      </section>
    </div>
  );
}
