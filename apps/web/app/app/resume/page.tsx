"use client";

import type { ResumeData } from "@rg/schema";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PagePreview } from "@/components/page-preview";
import { ResumeContentEditor } from "@/components/resume/content-editor";
import { AtsChecks, MatchPanel, type SkillAdded } from "@/components/resume/panels";
import { api, type Preview, type ResumeFull, saveFile, type TemplateInfo } from "@/lib/api";
import { newId } from "@/lib/ids";
import { type SaveState, useAutosave } from "@/lib/use-autosave";

export default function ResumePage() {
  // useSearchParams (?id=) needs a Suspense boundary.
  return (
    <Suspense fallback={<p role="status" className="text-muted">Loading…</p>}>
      <Loader />
    </Suspense>
  );
}

type Loaded = { resume: ResumeFull; templates: TemplateInfo[]; profile: ResumeData | null };

function Loader() {
  const id = Number(useSearchParams().get("id"));
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    Promise.all([api.getResume(id), api.listTemplates(), api.getProfile()])
      .then(([resume, templates, profile]) => {
        if (!cancelled) setLoaded({ resume, templates, profile: profile?.data ?? null });
      })
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!id) {
    return (
      <p className="text-muted">
        No resume chosen. <Link href="/app/resumes">See your resumes</Link>.
      </p>
    );
  }
  if (error) return <p role="alert" className="text-warn-ink">{error}</p>;
  if (!loaded) return <p role="status" className="text-muted">Loading…</p>;
  return <Editor key={loaded.resume.id} {...loaded} />;
}

function SaveStatus({ save }: { save: SaveState }) {
  const text = {
    saved: "All changes saved",
    unsaved: "Unsaved changes…",
    saving: "Saving…",
    error: save.kind === "error" ? `Couldn't save: ${save.message}` : "",
    conflict: "Changed somewhere else",
  }[save.kind];
  return (
    <span role="status" className={`text-sm ${save.kind === "error" || save.kind === "conflict" ? "text-warn-ink" : "text-muted"}`}>
      {text}
    </span>
  );
}

type Draft = { content: ResumeData; template: string };

function Editor({ resume, templates, profile: initialProfile }: Loaded) {
  const id = resume.id;
  const [provenance, setProvenance] = useState(resume.provenance);
  const [match, setMatch] = useState(resume.match);
  const [profile, setProfile] = useState(initialProfile);
  const [savedVersion, setSavedVersion] = useState(resume.version);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState<"pdf" | "retailor" | null>(null);
  const [confirmRetailor, setConfirmRetailor] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const { data, setData, save, flush, replace } = useAutosave<Draft, ResumeFull>({
    initial: { content: resume.content, template: resume.template },
    version: resume.version,
    save: (version, d) => api.saveResume(id, version, d.content, d.template),
    onSaved: (saved) => {
      setMatch(saved.match);
      setSavedVersion(saved.version);
    },
  });
  const setContent = (update: (c: ResumeData) => ResumeData) =>
    setData((d) => ({ ...d, content: update(d.content) }));

  // The preview is rendered on the server from what's saved, so it follows saves.
  useEffect(() => {
    let cancelled = false;
    api
      .previewResume(id, data.template)
      .then((p) => !cancelled && setPreview(p))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id, data.template, savedVersion]);

  async function download() {
    setBusy("pdf");
    try {
      if (await flush()) saveFile(await api.resumePdf(id, data.template));
    } finally {
      setBusy(null);
    }
  }

  async function retailor() {
    setConfirmRetailor(false);
    setBusy("retailor");
    setProblem(null);
    try {
      if (!(await flush())) return;
      const fresh = await api.retailorResume(id);
      replace({ content: fresh.content, template: fresh.template }, fresh.version);
      setProvenance(fresh.provenance);
      setMatch(fresh.match);
      setSavedVersion(fresh.version);
    } catch (err) {
      setProblem(err instanceof TypeError ? "Can't reach the server." : (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function skillAdded({ skill, entryId, bullet, profile: updated }: SkillAdded) {
    setProfile(updated);
    setContent((c) => {
      const has = c.skills.some((g) => g.items.some((s) => s.toLowerCase() === skill.toLowerCase()));
      const skills = has
        ? c.skills
        : c.skills.length
          ? c.skills.map((g, i) => (i === c.skills.length - 1 ? { ...g, items: [...g.items, skill] } : g))
          : [{ id: newId("sk"), group: "", items: [skill] }];
      const addLine = <E extends { id: string; bullets: { id: string; text: string }[] }>(entries: E[]) =>
        bullet && entryId ? entries.map((e) => (e.id === entryId ? { ...e, bullets: [...e.bullets, bullet] } : e)) : entries;
      return { ...c, skills, experience: addLine(c.experience), projects: addLine(c.projects) };
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm text-muted">
            <Link href="/app/resumes">My resumes</Link> / <SaveStatus save={save} />
          </span>
          <h1 className="font-display text-3xl sm:text-4xl">{resume.title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="flex items-center gap-2 text-sm text-muted">
            Template
            <select
              value={data.template}
              onChange={(e) => setData((d) => ({ ...d, template: e.target.value }))}
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
            onClick={() => setConfirmRetailor(true)}
            disabled={busy !== null || !resume.job_id}
            className="h-11 rounded-[10px] border border-line-strong bg-surface px-4 text-sm hover:bg-sunken disabled:opacity-50"
          >
            {busy === "retailor" ? "Re-tailoring… (20–40 s)" : "Re-tailor"}
          </button>
          <button
            type="button"
            onClick={download}
            disabled={busy !== null}
            className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {busy === "pdf" ? "Making PDF…" : "Download PDF"}
          </button>
        </div>
      </header>

      {confirmRetailor && (
        <div role="alertdialog" aria-label="Re-tailor this resume?" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
          <span className="flex-1">
            Re-tailoring builds this resume again from your profile as it is now. Your edits here
            are replaced (the current version stays in its history).
          </span>
          <button type="button" onClick={retailor} className="h-10 rounded-lg bg-accent px-3 font-medium text-white">
            Re-tailor
          </button>
          <button type="button" onClick={() => setConfirmRetailor(false)} className="h-10 rounded-lg px-3 text-muted hover:bg-sunken">
            Cancel
          </button>
        </div>
      )}
      {(problem || save.kind === "conflict") && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn-ink">
          <span className="flex-1">
            {save.kind === "conflict"
              ? "This resume was changed somewhere else (another tab?). Your latest edits here weren't saved."
              : problem}
          </span>
          {save.kind === "conflict" && (
            <button type="button" onClick={() => window.location.reload()} className="h-10 rounded-lg border border-warn bg-surface px-3">
              Reload the latest
            </button>
          )}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)_minmax(0,320px)]">
        <ResumeContentEditor data={data.content} setData={setContent} profile={profile} provenance={provenance} />

        <section aria-label="Preview" className="order-first flex flex-col gap-2 lg:order-none xl:sticky xl:top-6 xl:self-start">
          <span className="text-sm text-muted">
            {preview ? `${preview.pages} page${preview.pages > 1 ? "s" : ""} · A4 · updates as you save` : "Laying out…"}
          </span>
          <div className="overflow-hidden rounded-lg border border-line bg-surface">
            {preview ? (
              <PagePreview html={preview.html} title={`${resume.title}, preview`} bare />
            ) : (
              <div className="aspect-[794/1123]" />
            )}
          </div>
        </section>

        <div className="flex flex-col gap-3 lg:col-span-2 xl:col-span-1">
          {match ? (
            <MatchPanel match={match} profile={profile} onSkillAdded={skillAdded} />
          ) : (
            <p className="rounded-xl border border-line bg-surface p-4 text-sm text-muted">
              The job this resume was made for is gone, so there&apos;s nothing to match against.
            </p>
          )}
          <AtsChecks data={data.content} pages={preview?.pages ?? null} />
        </div>
      </div>
    </div>
  );
}
