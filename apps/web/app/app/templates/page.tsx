"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PagePreview } from "@/components/page-preview";
import { api, ApiError, type Preview, type TemplateInfo } from "@/lib/api";

export default function TemplatesPage() {
  // useSearchParams (?job=, ?template=) needs a Suspense boundary.
  return (
    <Suspense fallback={<p role="status" className="text-muted">Loading…</p>}>
      <Templates />
    </Suspense>
  );
}

type Loaded = { templates: TemplateInfo[]; previews: Record<string, Preview> };

function Templates() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const job = params.get("job");
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [problem, setProblem] = useState<{ message: string; noProfile: boolean } | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const templates = await api.listTemplates();
        const previews = await Promise.all(templates.map((t) => api.previewTemplate(t.slug)));
        if (!cancelled) {
          setLoaded({
            templates,
            previews: Object.fromEntries(templates.map((t, i) => [t.slug, previews[i]!])),
          });
        }
      } catch (err) {
        if (cancelled) return;
        setProblem({
          message: err instanceof TypeError ? "Can't reach the server." : (err as Error).message,
          noProfile: err instanceof ApiError && err.status === 404,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = params.get("template") ?? loaded?.templates[0]?.slug ?? "classic";
  const current = loaded?.templates.find((t) => t.slug === selected);

  function choose(slug: string) {
    const next = new URLSearchParams(params);
    next.set("template", slug);
    router.replace(`${pathname}?${next}`, { scroll: false });
  }

  async function download() {
    setDownloading(true);
    try {
      const { blob, filename } = await api.templatePdf(selected);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 pb-28">
      <ol aria-label="Steps" className="flex flex-wrap items-center gap-2.5 text-sm text-muted">
        <li>{job ? <Link href={`/app/new?job=${job}`}>1 · Job description</Link> : "1 · Job description"}</li>
        <li aria-hidden="true">—</li>
        <li className="font-semibold text-ink">2 · Template</li>
        <li aria-hidden="true">—</li>
        <li>3 · Edit</li>
      </ol>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-4xl sm:text-5xl">Pick a look</h1>
          <p className="text-[15px] text-muted">Shown with your own details. You can switch any time.</p>
        </div>
        <span className="rounded-full bg-accent-soft px-3 py-1.5 text-sm text-accent-ink">
          Every template: one column · real text · standard headings
        </span>
      </div>

      {problem ? (
        <p role="alert" className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
          {problem.noProfile ? (
            <>
              There&apos;s nothing to show yet. <Link href="/app">Upload your resume</Link> first.
            </>
          ) : (
            problem.message
          )}
        </p>
      ) : !loaded ? (
        <p role="status" className="text-muted">
          Laying out your resume in each template…
        </p>
      ) : (
        <>
          <fieldset className="grid grid-cols-2 gap-5 lg:grid-cols-4">
            <legend className="sr-only">Template</legend>
            {loaded.templates.map((t) => {
              const preview = loaded.previews[t.slug]!;
              const isSelected = t.slug === selected;
              return (
                <label key={t.slug} className="flex cursor-pointer flex-col gap-2.5">
                  <div
                    className={`overflow-hidden rounded-[10px] shadow-sm transition-shadow ${
                      isSelected ? "outline-3 outline-offset-3 outline-accent" : "border border-line hover:shadow-md"
                    }`}
                  >
                    <PagePreview html={preview.html} title={`${t.name} template preview`} bare />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="template"
                      value={t.slug}
                      checked={isSelected}
                      onChange={() => choose(t.slug)}
                      className="size-4.5 accent-accent"
                    />
                    <span className="text-base font-semibold">{t.name}</span>
                    {preview.pages > 1 && (
                      <span className="ml-auto rounded-full bg-warn-soft px-2 py-0.5 text-xs text-warn-ink">
                        {preview.pages} pages
                      </span>
                    )}
                  </div>
                  <span className="-mt-1.5 text-[13px] text-muted">{t.description}</span>
                </label>
              );
            })}
          </fieldset>

          {current && (
            <section aria-label={`${current.name}, full size`} className="flex flex-col gap-2.5">
              <h2 className="text-[13px] font-semibold tracking-wider text-muted uppercase">
                {current.name}, full size
              </h2>
              <div className="mx-auto w-full max-w-[794px] overflow-hidden rounded-lg border border-line">
                <PagePreview html={loaded.previews[selected]!.html} title={`${current.name} template, full size`} bare />
              </div>
            </section>
          )}
        </>
      )}

      <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-surface md:left-58">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 md:px-11">
          <span className="text-sm text-muted">
            Tailoring to a job is the next thing being built. For now you can download your profile.
          </span>
          <div className="flex gap-2.5">
            <button
              type="button"
              disabled={!loaded || downloading}
              onClick={download}
              className="h-12 rounded-[10px] border border-line-strong bg-surface px-4 text-[15px] hover:bg-sunken disabled:opacity-50"
            >
              {downloading ? "Making PDF…" : "Download PDF"}
            </button>
            <button
              type="button"
              disabled
              className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white disabled:opacity-50"
            >
              Tailor my resume{current ? ` with ${current.name}` : ""}
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
