"use client";

import type { ResumeData } from "@rg/schema";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PagePreview } from "@/components/page-preview";
import {
  api,
  type LineHistory,
  type Preview,
  type ResumeFull,
  saveFile,
  type TemplateInfo,
  type TermMatch,
} from "@/lib/api";

export default function ResumePage() {
  // useSearchParams (?id=) needs a Suspense boundary.
  return (
    <Suspense fallback={<p role="status" className="text-muted">Loading…</p>}>
      <ResumeView />
    </Suspense>
  );
}

function ResumeView() {
  const id = Number(useSearchParams().get("id"));
  const [resume, setResume] = useState<ResumeFull | null>(null);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [template, setTemplate] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    Promise.all([api.getResume(id), api.listTemplates()])
      .then(([r, t]) => {
        if (cancelled) return;
        setResume(r);
        setTemplates(t);
        setTemplate(r.template);
      })
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id || !template) return;
    let cancelled = false;
    api
      .previewResume(id, template)
      .then((p) => !cancelled && setPreview(p))
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, [id, template]);

  if (!id) return <p className="text-muted">No resume chosen. <Link href="/app/resumes">See your resumes</Link>.</p>;
  if (error) return <p role="alert" className="text-warn-ink">{error}</p>;
  if (!resume || !template) return <p role="status" className="text-muted">Loading…</p>;

  async function download() {
    setDownloading(true);
    try {
      saveFile(await api.resumePdf(id, template!));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted">
            <Link href="/app/resumes">My resumes</Link> /
          </span>
          <h1 className="font-display text-3xl sm:text-4xl">{resume.title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="flex items-center gap-2 text-sm text-muted">
            Template
            <select
              value={template}
              onChange={(e) => {
                setPreview(null);
                setTemplate(e.target.value);
              }}
              className="h-11 rounded-lg border border-line-strong bg-surface px-2.5 text-sm text-ink"
            >
              {templates.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={download}
            disabled={downloading}
            className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {downloading ? "Making PDF…" : "Download PDF"}
          </button>
        </div>
      </div>

      <div className="grid gap-7 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <section aria-label="Preview" className="flex flex-col gap-2">
          <span className="text-sm text-muted">
            {preview ? `${preview.pages} page${preview.pages > 1 ? "s" : ""} · A4` : "Laying out…"}
          </span>
          <div className="overflow-hidden rounded-lg border border-line">
            {preview ? (
              <PagePreview html={preview.html} title={`${resume.title}, preview`} bare />
            ) : (
              <div className="aspect-[794/1123] bg-surface" />
            )}
          </div>
        </section>

        <div className="flex min-w-0 flex-col gap-4">
          {resume.match && <MatchPanel match={resume.match} />}
          <Changes content={resume.content} provenance={resume.provenance} />
        </div>
      </div>
    </div>
  );
}

function MatchPanel({ match }: { match: NonNullable<ResumeFull["match"]> }) {
  const missing = [...match.must_have, ...match.nice_to_have].filter((m) => !m.covered);
  return (
    <section aria-label="Job match" className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold">Job keywords in this resume</h2>
        <span className="text-xl font-semibold">
          {match.covered}/{match.total}
        </span>
      </div>
      {missing.length > 0 && (
        <div className="flex flex-col gap-2 rounded-lg bg-warn-soft p-3 text-warn-ink">
          <span className="text-sm font-semibold">Not in your profile</span>
          <ul className="flex flex-wrap gap-1.5">
            {missing.map((m: TermMatch) => (
              <li key={m.term} className="rounded-full border border-dashed border-warn bg-surface px-2.5 py-0.5 text-[13px]">
                {m.term}
              </li>
            ))}
          </ul>
          <span className="text-[13px] leading-normal">
            We only use what&apos;s in your profile. If you have these,{" "}
            <Link href="/app/profile">add them there</Link> and tailor again.
          </span>
        </div>
      )}
    </section>
  );
}

function Changes({ content, provenance }: { content: ResumeData; provenance: Record<string, LineHistory> }) {
  const lines = new Map<string, string>([
    ["summary", content.summary],
    ...[...content.experience, ...content.projects].flatMap((e) =>
      e.bullets.map((b) => [b.id, b.text] as [string, string]),
    ),
  ]);
  const entries = Object.entries(provenance);
  const reworded = entries.filter(([, p]) => p.status === "reworded");
  const reverted = entries.filter(([, p]) => p.status === "reverted");

  return (
    <section aria-label="What we changed" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-col gap-1">
        <h2 className="font-semibold">What we changed</h2>
        <p className="text-[13px] leading-normal text-muted">
          Every reworded line was checked against your original: no new numbers, tools or claims.
        </p>
      </div>

      {reworded.length === 0 && reverted.length === 0 && (
        <p className="text-sm text-muted">Nothing was reworded: your lines are as you wrote them, chosen and ordered for this job.</p>
      )}

      {reworded.length > 0 && (
        <ul className="flex flex-col gap-3">
          {reworded.map(([id, p]) => (
            <li key={id} className="flex flex-col gap-1 rounded-lg bg-accent-soft/60 p-3 text-sm">
              {id === "summary" && <span className="text-xs font-semibold tracking-wide text-accent-ink uppercase">Summary</span>}
              <span>{lines.get(id)}</span>
              <details className="text-[13px] text-muted">
                <summary className="cursor-pointer">{id === "summary" ? "Your previous summary" : "Your original"}</summary>
                <p className="mt-1">{p.original || "(none)"}</p>
              </details>
            </li>
          ))}
        </ul>
      )}

      {reverted.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Kept in your words ({reverted.length})</h3>
          <ul className="flex flex-col gap-2">
            {reverted.map(([id, p]) => (
              <li key={id} className="text-[13px] leading-normal">
                <details>
                  <summary className="cursor-pointer">
                    {id === "summary" ? "Summary" : (lines.get(id) ?? p.original)}
                  </summary>
                  <p className="mt-1 text-muted">
                    The rewording {p.reason}:
                    <span className="mt-0.5 block italic">“{p.attempted}”</span>
                  </p>
                </details>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
