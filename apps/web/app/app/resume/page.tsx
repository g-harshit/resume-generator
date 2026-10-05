"use client";

import type { ResumeData } from "@rg/schema";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PdfPages } from "@/components/pdf-pages";
import { ResumeContentEditor } from "@/components/resume/content-editor";
import { HeaderEditor } from "@/components/resume/header-editor";
import { FitPanel } from "@/components/resume/fit-panel";
import { AtsChecks, MatchPanel, type SkillAdded } from "@/components/resume/panels";
import { api, type FitResult, type Layout, type Preview, type ResumeFull, saveFile, type TemplateInfo } from "@/lib/api";
import { newId } from "@/lib/ids";
import { type SaveState, useAutosave } from "@/lib/use-autosave";
import { Loading } from "@/components/loading";

export default function ResumePage() {
  // useSearchParams (?id=) needs a Suspense boundary.
  return (
    <Suspense fallback={<Loading />}>
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
  if (!loaded) return <Loading />;
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

type Draft = { content: ResumeData; template: string; layout: Layout };
type FitReport = { steps: string[]; notes: string[]; pagesBefore: number; pagesAfter: number };

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
  // AI edits to length: what's running, what it did, and what to go back to.
  const [aiBusy, setAiBusy] = useState<string | null>(null);
  const [report, setReport] = useState<FitReport | null>(null);
  const [undo, setUndo] = useState<{ draft: Draft; provenance: ResumeFull["provenance"] } | null>(null);

  const { data, setData, save, flush, replace, version: currentVersion } = useAutosave<Draft, ResumeFull>({
    initial: { content: resume.content, template: resume.template, layout: resume.layout },
    version: resume.version,
    save: (version, d) => api.saveResume(id, version, d.content, d.template, d.layout),
    onSaved: (saved) => {
      setMatch(saved.match);
      setSavedVersion(saved.version);
    },
  });
  const setContent = (update: (c: ResumeData) => ResumeData) =>
    setData((d) => ({ ...d, content: update(d.content) }));
  const setLayout = (update: (l: Layout) => Layout) => setData((d) => ({ ...d, layout: update(d.layout) }));

  function adopt(fresh: ResumeFull) {
    replace({ content: fresh.content, template: fresh.template, layout: fresh.layout }, fresh.version);
    setProvenance(fresh.provenance);
    setMatch(fresh.match);
    setSavedVersion(fresh.version);
  }

  const [bridged, setBridged] = useState<string[] | null>(null);

  async function bridgeSkills() {
    setBridged(null);
    await aiEdit("bridge", async (v) => {
      const out = await api.bridgeSkills(id, v);
      setBridged(out.added);
      return out.resume;
    });
  }

  /** Run an AI edit on the saved resume; the server returns the new version. Errors go
   * to `onError` when given (shown next to what was clicked), else the page banner. */
  async function aiEdit(
    what: string,
    run: (version: number) => Promise<ResumeFull | FitResult>,
    onError: (message: string) => void = setProblem,
  ) {
    setAiBusy(what);
    setProblem(null);
    try {
      if (!(await flush())) {
        onError("Your latest edits couldn't be saved, so the AI didn't run. Check the message above and try again.");
        return;
      }
      const before = { draft: data, provenance };
      const out = await run(currentVersion());
      if ("pages_after" in out) {
        adopt(out.resume);
        setReport({ steps: out.steps, notes: out.notes, pagesBefore: out.pages_before, pagesAfter: out.pages_after });
      } else {
        adopt(out);
      }
      setUndo(before);
    } catch (err) {
      onError(err instanceof TypeError ? "Can't reach the server." : (err as Error).message);
    } finally {
      setAiBusy(null);
    }
  }

  const [keywordError, setKeywordError] = useState<{ line: string; message: string } | null>(null);

  type Line = { id: string; text: string };
  /**
   * How a role or project can grow: its lines now, the person's own lines not in it
   * (nor merged into one of its lines), and — when merged lines are in the way — the
   * lines it would have with every merge undone.
   */
  function growth(entryId: string) {
    const entry =
      data.content.experience.find((e) => e.id === entryId) ?? data.content.projects.find((p) => p.id === entryId);
    const own: Line[] =
      profile?.experience.find((e) => e.id === entryId)?.bullets ??
      profile?.projects.find((p) => p.id === entryId)?.bullets ??
      [];
    const current = entry?.bullets ?? [];
    const used = new Set(current.flatMap((b) => [b.id, ...(provenance[b.id]?.sources ?? [])]));
    const unused = own.filter((b) => !used.has(b.id));
    const unmerged = current.filter((b) => provenance[b.id]?.status !== "condensed");
    const unmergedIds = new Set(unmerged.map((b) => b.id));
    const restored = [...unmerged, ...own.filter((b) => !unmergedIds.has(b.id))];
    return { current, unused, restored, max: Math.max(current.length + unused.length, restored.length) };
  }
  const maxLines = Object.fromEntries(
    [...data.content.experience, ...data.content.projects].map((e) => [e.id, growth(e.id).max]),
  );

  /** More lines, all the person's own: unused ones first, then by undoing merges. */
  function addLines(entryId: string, target: number) {
    const { current, unused, restored } = growth(entryId);
    const next: Line[] =
      current.length + unused.length >= target
        ? [...current, ...unused.slice(0, target - current.length)]
        : restored.slice(0, target);
    const bullets = next.map((b) => ({ id: b.id, text: b.text }));
    const set = <E extends { id: string; bullets: Line[] }>(entries: E[]) =>
      entries.map((e) => (e.id === entryId ? { ...e, bullets } : e));
    setContent((c) => ({ ...c, experience: set(c.experience), projects: set(c.projects) }));
  }

  function undoAi() {
    if (!undo) return;
    setData(() => undo.draft);
    setProvenance(undo.provenance);
    setUndo(null);
    setReport(null);
  }

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
      adopt(await api.retailorResume(id));
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
          <Link
            href={`/app/cover-letter?id=${id}`}
            className="inline-flex h-11 items-center rounded-[10px] border border-line-strong bg-surface px-4 text-sm text-ink hover:bg-sunken hover:text-ink"
          >
            Cover letter
          </Link>
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
        <div className="flex flex-col gap-3">
          <HeaderEditor
            basics={data.content.basics}
            setBasics={(update) => setContent((c) => ({ ...c, basics: update(c.basics) }))}
            hidden={data.layout.hidden_header ?? []}
            setHidden={(update) => setLayout((l) => ({ ...l, hidden_header: update(l.hidden_header ?? []) }))}
            profileLinks={profile?.basics.links ?? []}
          />
          <ResumeContentEditor
            data={data.content}
            setData={setContent}
            profile={profile}
            provenance={provenance}
            summaryAi={{
              busy: aiBusy === "summary",
              disabled: aiBusy !== null,
              write: (length) => aiEdit("summary", (v) => api.writeSummary(id, v, length)),
              undo: undo && aiBusy === null && provenance.summary?.status === "written" ? undoAi : null,
            }}
            keywordAi={
              match
                ? {
                    gaps: match.missing_in_lines ?? [],
                    byLine: match.missing_by_line ?? {},
                    busyLine: aiBusy?.startsWith("kw:") ? aiBusy.slice(3) : null,
                    disabled: aiBusy !== null,
                    error: keywordError,
                    rewrite: (lineId, keywords, again) => {
                      setKeywordError(null);
                      void aiEdit(
                        `kw:${lineId}`,
                        (v) => api.lineKeywords(id, v, lineId, keywords, again),
                        (message) => setKeywordError({ line: lineId, message }),
                      );
                    },
                  }
                : undefined
            }
          />
        </div>

        {/* Sticky on wide screens, and scrolls inside itself so every page can be reached. */}
        <section
          aria-label="Preview"
          className="order-first flex flex-col gap-2 lg:order-none xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)] xl:self-start xl:overflow-y-auto xl:pr-1"
        >
          <span className="text-sm text-muted">
            {preview ? `${preview.pages} page${preview.pages > 1 ? "s" : ""} · A4 · updates as you save` : "Laying out…"}
          </span>
          {preview ? (
            <PdfPages images={preview.images} links={preview.links} title={resume.title} />
          ) : (
            <div className="aspect-[210/297] rounded-lg border border-line bg-surface" />
          )}
        </section>

        <div className="flex flex-col gap-3 lg:col-span-2 xl:col-span-1">
          <FitPanel
            data={data.content}
            layout={data.layout}
            pages={preview?.pages ?? null}
            busy={aiBusy}
            report={report}
            onUndo={undo ? undoAi : null}
            maxLines={maxLines}
            actions={{
              setLayout,
              fit: (pages) => aiEdit("fit", (v) => api.fitToPages(id, v, pages)),
              condense: (entryId, bullets) => aiEdit(entryId, (v) => api.condenseEntry(id, v, entryId, bullets)),
              addLines,
            }}
          />
          {match ? (
            <MatchPanel
              match={match}
              profile={profile}
              onSkillAdded={skillAdded}
              bridge={{ busy: aiBusy === "bridge", disabled: aiBusy !== null, run: bridgeSkills, added: bridged }}
            />
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
