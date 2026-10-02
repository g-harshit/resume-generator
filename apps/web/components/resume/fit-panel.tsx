"use client";

import type { ResumeData } from "@rg/schema";
import { useState } from "react";
import type { Layout, Section } from "@/lib/api";

const SECTION_LABEL: Record<Section, string> = {
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  skills: "Skills",
  projects: "Projects",
  certifications: "Certifications",
};

const panel = "flex flex-col gap-3 rounded-xl border border-line bg-surface p-4";
const button =
  "h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm hover:bg-sunken disabled:opacity-50";

export type FitActions = {
  setLayout: (update: (l: Layout) => Layout) => void;
  fit: (pages: number) => Promise<void>;
  condense: (entryId: string, bullets: number) => Promise<void>;
};

/** Ask for a page goal when the resume runs long, then offer ways to meet it. */
export function FitPanel({
  data,
  layout,
  pages,
  busy,
  report,
  onUndo,
  actions,
}: {
  data: ResumeData;
  layout: Layout;
  pages: number | null;
  /** What's running: "fit", or an entry id being shortened. */
  busy: string | null;
  report: { steps: string[]; notes: string[]; pagesBefore: number; pagesAfter: number } | null;
  onUndo: (() => void) | null;
  actions: FitActions;
}) {
  const [lines, setLines] = useState<Record<string, number>>({});
  if (pages === null) return null;
  const goal = layout.pages;

  // Short enough and never asked: nothing to say.
  if (goal === null && pages <= 1 && !report) return null;

  const present = (Object.keys(SECTION_LABEL) as Section[]).filter((s) =>
    s === "summary" ? true : (data[s] as unknown[]).length > 0,
  );
  const entries = [
    ...data.experience.map((e) => ({ id: e.id, label: e.company || e.title, count: e.bullets.length })),
    ...data.projects.map((p) => ({ id: p.id, label: p.name, count: p.bullets.length })),
  ].filter((e) => e.count > 1);

  return (
    <section aria-label="Length" className={panel}>
      {goal === null ? (
        <>
          <h2 className="text-[15px] font-semibold">This resume is {pages} pages</h2>
          <p className="text-[13px] leading-normal text-muted">How many pages do you want it to be?</p>
          <div className="flex flex-wrap gap-2">
            {[1, 2].filter((n) => n < pages).map((n) => (
              <button key={n} type="button" className={button} onClick={() => actions.setLayout((l) => ({ ...l, pages: n }))}>
                {n} page{n > 1 ? "s" : ""}
              </button>
            ))}
            <button type="button" className={button} onClick={() => actions.setLayout((l) => ({ ...l, pages }))}>
              Keep {pages} pages
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-[15px] font-semibold">
              {pages <= goal ? `Fits on ${goal} page${goal > 1 ? "s" : ""} ✓` : `${pages} pages — goal ${goal}`}
            </h2>
            <label className="flex items-center gap-1.5 text-[13px] text-muted">
              Goal
              <select
                value={goal}
                onChange={(e) => actions.setLayout((l) => ({ ...l, pages: Number(e.target.value) }))}
                className="h-8 rounded-md border border-line-strong bg-surface px-1.5 text-[13px] text-ink"
              >
                {[1, 2, 3].map((n) => (
                  <option key={n} value={n}>
                    {n} page{n > 1 ? "s" : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {report && (
            <div className="flex flex-col gap-1.5 rounded-lg bg-accent-soft/60 p-3 text-[13px] leading-normal">
              <span className="font-semibold">
                {report.pagesBefore} → {report.pagesAfter} page{report.pagesAfter > 1 ? "s" : ""}
              </span>
              <ul className="flex flex-col gap-1">
                {[...report.steps, ...report.notes].map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              {onUndo && (
                <button type="button" onClick={onUndo} className="self-start text-accent underline-offset-2 hover:underline">
                  Undo
                </button>
              )}
            </div>
          )}

          {pages > goal && (
            <button
              type="button"
              onClick={() => actions.fit(goal)}
              disabled={busy !== null}
              className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {busy === "fit" ? "Fitting… (20–60 s)" : `Fit to ${goal} page${goal > 1 ? "s" : ""} for me`}
            </button>
          )}
          {pages > goal && (
            <p className="text-xs leading-normal text-muted">
              Narrows the margins first; then keeps the most lines for your latest role and
              condenses older ones. Nothing new is added — and you can undo it.
            </p>
          )}

          <fieldset className="flex flex-col gap-1.5 border-t border-sunken pt-3">
            <legend className="mb-1 text-[13px] font-semibold">Margins</legend>
            <div className="flex gap-4 text-sm">
              {(["normal", "narrow"] as const).map((m) => (
                <label key={m} className="flex items-center gap-1.5 capitalize">
                  <input
                    type="radio"
                    name="margins"
                    checked={layout.margins === m}
                    onChange={() => actions.setLayout((l) => ({ ...l, margins: m }))}
                    className="accent-accent"
                  />
                  {m}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-1.5 border-t border-sunken pt-3">
            <legend className="mb-1 text-[13px] font-semibold">Sections to include</legend>
            <div className="grid grid-cols-2 gap-1.5 text-sm">
              {present.map((s) => (
                <label key={s} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={!layout.hidden.includes(s)}
                    onChange={(e) =>
                      actions.setLayout((l) => ({
                        ...l,
                        hidden: e.target.checked ? l.hidden.filter((h) => h !== s) : [...l.hidden, s],
                      }))
                    }
                    className="size-4 accent-accent"
                  />
                  {SECTION_LABEL[s]}
                </label>
              ))}
            </div>
          </fieldset>

          {entries.length > 0 && (
            <div className="flex flex-col gap-2 border-t border-sunken pt-3">
              <span className="text-[13px] font-semibold">Shorten a role</span>
              <ul className="flex flex-col gap-2">
                {entries.map((e) => {
                  const n = Math.min(lines[e.id] ?? Math.max(1, e.count - 1), e.count - 1);
                  return (
                    <li key={e.id} className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="min-w-0 flex-1 truncate" title={e.label}>
                        {e.label} <span className="text-muted">· {e.count} lines</span>
                      </span>
                      <select
                        aria-label={`Lines for ${e.label}`}
                        value={n}
                        onChange={(ev) => setLines((x) => ({ ...x, [e.id]: Number(ev.target.value) }))}
                        className="h-9 rounded-md border border-line-strong bg-surface px-1.5 text-[13px]"
                      >
                        {Array.from({ length: e.count - 1 }, (_, i) => i + 1).map((k) => (
                          <option key={k} value={k}>
                            {k} line{k > 1 ? "s" : ""}
                          </option>
                        ))}
                      </select>
                      <button type="button" disabled={busy !== null} onClick={() => actions.condense(e.id, n)} className="h-9 rounded-md border border-line-strong px-2.5 text-[13px] hover:bg-sunken disabled:opacity-50">
                        {busy === e.id ? "Shortening…" : "Shorten"}
                      </button>
                    </li>
                  );
                })}
              </ul>
              <p className="text-xs leading-normal text-muted">
                Merges that role&apos;s lines into fewer, from your own words only.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
