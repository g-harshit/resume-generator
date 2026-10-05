"use client";

import type { ResumeData } from "@rg/schema";
import { useState } from "react";
import { type Layout, SECTIONS, type Section } from "@/lib/api";

const SECTION_LABEL: Record<Section, string> = {
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  skills: "Skills",
  projects: "Projects",
  certifications: "Certifications",
};

const panel = "flex flex-col gap-3 rounded-xl border border-line bg-surface p-4";

export type FitActions = {
  setLayout: (update: (l: Layout) => Layout) => void;
  fit: (pages: number) => Promise<void>;
  condense: (entryId: string, bullets: number) => Promise<void>;
  /** Grow a role or project to this many lines, all the person's own. */
  addLines: (entryId: string, target: number) => void;
};

// Margins: narrow matches backend/app/rendering/render.py; custom is 5–30 mm.
const NARROW_MM = 10;
const MIN_MM = 5;
const MAX_MM = 30;
const DEFAULT_CUSTOM_MM = 15;

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Typed millimetres, applied on Enter or leaving the box — not on every keystroke,
 *  so typing "12" doesn't pass through 1 (clamped to 5) on the way. */
function MarginInput({ value, onCommit }: { value: number; onCommit: (mm: number) => void }) {
  const [text, setText] = useState<string | null>(null);
  const commit = () => {
    if (text !== null && text.trim() !== "" && !Number.isNaN(Number(text))) onCommit(Number(text));
    setText(null);
  };
  return (
    <label className="flex items-center gap-1 text-sm">
      <input
        type="number"
        min={MIN_MM}
        max={MAX_MM}
        value={text ?? value}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        aria-label="Margin in millimetres"
        className="h-9 w-16 rounded-md border border-line-strong bg-surface px-2 text-right text-sm"
      />
      mm
    </label>
  );
}

/**
 * Page goal, margins, sections, and lines per role. Always there: the person may want
 * more on the page as well as less.
 */
export function FitPanel({
  data,
  layout,
  pages,
  busy,
  report,
  onUndo,
  maxLines,
  actions,
}: {
  data: ResumeData;
  layout: Layout;
  pages: number | null;
  /** What's running: "fit", or an entry id being shortened. */
  busy: string | null;
  report: { steps: string[]; notes: string[]; pagesBefore: number; pagesAfter: number } | null;
  onUndo: (() => void) | null;
  /** Per role or project: the most lines it can have from the person's own. */
  maxLines: Record<string, number>;
  actions: FitActions;
}) {
  const [lines, setLines] = useState<Record<string, number>>({});
  if (pages === null) return null;
  const goal = layout.pages;
  const over = goal !== null && pages > goal;

  const setMargin = (mm: number) =>
    actions.setLayout((l) => ({ ...l, margins: "custom", margin_mm: Math.min(MAX_MM, Math.max(MIN_MM, Math.round(mm))) }));
  const order = layout.order ?? SECTIONS;
  const present = order.filter((s) => (s === "summary" ? true : (data[s] as unknown[]).length > 0));
  // Swap a section with its neighbour among the ones on this resume.
  const moveSection = (from: number, to: number) =>
    actions.setLayout((l) => {
      const full = [...(l.order ?? SECTIONS)];
      const a = full.indexOf(present[from]!);
      const b = full.indexOf(present[to]!);
      [full[a], full[b]] = [full[b]!, full[a]!];
      return { ...l, order: full };
    });
  const entries = [
    ...data.experience.map((e) => ({ id: e.id, label: e.company || e.title, count: e.bullets.length })),
    ...data.projects.map((p) => ({ id: p.id, label: p.name, count: p.bullets.length })),
  ]
    .map((e) => ({ ...e, max: Math.max(e.count, maxLines[e.id] ?? 0) }))
    .filter((e) => e.max > 1);

  return (
    <section aria-label="Length" className={panel}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold">
          {plural(pages, "page")}
          {goal !== null && !over && <span className="font-normal text-muted"> · fits ✓</span>}
        </h2>
        <label className="flex items-center gap-1.5 text-[13px] text-muted">
          Pages wanted
          <select
            value={goal ?? ""}
            onChange={(e) => actions.setLayout((l) => ({ ...l, pages: Number(e.target.value) }))}
            className="h-9 rounded-md border border-line-strong bg-surface px-1.5 text-[13px] text-ink"
          >
            {goal === null && (
              <option value="" disabled>
                Choose…
              </option>
            )}
            {[1, 2, ...(goal === 3 ? [3] : [])].map((n) => (
              <option key={n} value={n}>
                {plural(n, "page")}
              </option>
            ))}
          </select>
        </label>
      </div>
      {goal === null && pages > 1 && (
        <p className="rounded-lg bg-warn-soft px-3 py-2 text-[13px] leading-normal text-warn-ink">
          This resume runs to {plural(pages, "page")}. How many do you want it to be?
        </p>
      )}

      {report && (
        <div className="flex flex-col gap-1.5 rounded-lg bg-accent-soft/60 p-3 text-[13px] leading-normal">
          <span className="font-semibold">
            {report.pagesBefore} → {plural(report.pagesAfter, "page")}
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

      {over && (
        <>
          <button
            type="button"
            onClick={() => actions.fit(goal)}
            disabled={busy !== null}
            className="h-11 rounded-[10px] bg-accent px-4 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {busy === "fit" ? "Fitting… (20–60 s)" : `Fit to ${plural(goal, "page")} for me`}
          </button>
          <p className="text-xs leading-normal text-muted">
            Takes out any extra spacing used to fill the page, then narrows the margins, then
            keeps the most lines for your latest role and condenses older ones. Nothing new is
            added — and you can undo it.
          </p>
        </>
      )}
      {!over && pages !== null && (
        <>
          <button
            type="button"
            onClick={() => actions.fit(goal ?? pages)}
            disabled={busy !== null}
            className="h-11 rounded-[10px] border border-accent px-4 text-[15px] font-medium text-accent hover:bg-accent-soft disabled:opacity-50"
          >
            {busy === "fit" ? "Filling… (10–30 s)" : `Fill ${pages > 1 ? `all ${pages} pages` : "the page"}`}
          </button>
          <p className="text-xs leading-normal text-muted">
            Uses the empty space: adds back your own lines left out of this resume, writes a
            longer summary, then spaces things out. Never adds a page — and you can undo it.
          </p>
        </>
      )}

      <fieldset className="flex flex-col gap-2 border-t border-sunken pt-3">
        <legend className="mb-1 text-[13px] font-semibold">Margins</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm">
          {(
            [
              ["normal", "Template's own"],
              ["narrow", `Narrow (${NARROW_MM} mm)`],
              ["custom", "Custom"],
            ] as const
          ).map(([m, label]) => (
            <label key={m} className="flex items-center gap-1.5">
              <input
                type="radio"
                name="margins"
                checked={layout.margins === m}
                onChange={() =>
                  actions.setLayout((l) => ({
                    ...l,
                    margins: m,
                    margin_mm: m === "custom" ? (l.margin_mm ?? DEFAULT_CUSTOM_MM) : l.margin_mm,
                  }))
                }
                className="accent-accent"
              />
              {label}
            </label>
          ))}
        </div>
        {layout.margins === "custom" && (
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={MIN_MM}
              max={MAX_MM}
              step={1}
              value={layout.margin_mm ?? DEFAULT_CUSTOM_MM}
              onChange={(e) => setMargin(Number(e.target.value))}
              aria-label="Margin on all four sides, in millimetres"
              className="flex-1 accent-accent"
            />
            <MarginInput value={layout.margin_mm ?? DEFAULT_CUSTOM_MM} onCommit={setMargin} />
          </div>
        )}
        {layout.margins !== "normal" && (
          <p className="text-xs text-muted">The same on all four sides.</p>
        )}
        {((layout.spacing ?? 1) > 1 || (layout.font_scale ?? 1) > 1) && (
          <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
            Stretched to fill the page:
            {(layout.font_scale ?? 1) > 1 && ` text ${Math.round(((layout.font_scale ?? 1) - 1) * 100)}% larger,`}
            {(layout.spacing ?? 1) > 1 && ` spacing ${(layout.spacing ?? 1).toFixed(1)}×.`}
            <button
              type="button"
              onClick={() => actions.setLayout((l) => ({ ...l, spacing: null, font_scale: null }))}
              className="text-accent underline-offset-2 hover:underline"
            >
              Reset
            </button>
          </p>
        )}
      </fieldset>

      <fieldset className="flex flex-col gap-1.5 border-t border-sunken pt-3">
        <legend className="mb-1 text-[13px] font-semibold">Sections, in order</legend>
        <ol className="flex flex-col gap-1 text-sm">
          {present.map((s, i) => (
            <li key={s} className="flex items-center gap-1.5">
              <label className="flex flex-1 items-center gap-1.5">
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
                <span className={layout.hidden.includes(s) ? "text-muted line-through" : ""}>{SECTION_LABEL[s]}</span>
              </label>
              <button
                type="button"
                aria-label={`Move ${SECTION_LABEL[s]} up`}
                disabled={i === 0}
                onClick={() => moveSection(i, i - 1)}
                className="flex size-8 items-center justify-center rounded-md text-muted hover:bg-sunken hover:text-ink disabled:opacity-30"
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${SECTION_LABEL[s]} down`}
                disabled={i === present.length - 1}
                onClick={() => moveSection(i, i + 1)}
                className="flex size-8 items-center justify-center rounded-md text-muted hover:bg-sunken hover:text-ink disabled:opacity-30"
              >
                ↓
              </button>
            </li>
          ))}
        </ol>
      </fieldset>

      {entries.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-sunken pt-3">
          <span className="text-[13px] font-semibold">Lines per role</span>
          <ul className="flex flex-col gap-2">
            {entries.map((e) => {
              const n = Math.min(Math.max(lines[e.id] ?? e.count, 1), e.max);
              return (
                <li key={e.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="min-w-0 flex-1 truncate" title={e.label}>
                    {e.label} <span className="text-muted">· {e.count} now</span>
                  </span>
                  <select
                    aria-label={`Lines for ${e.label}`}
                    value={n}
                    onChange={(ev) => setLines((x) => ({ ...x, [e.id]: Number(ev.target.value) }))}
                    className="h-9 rounded-md border border-line-strong bg-surface px-1.5 text-[13px]"
                  >
                    {Array.from({ length: e.max }, (_, i) => i + 1).map((k) => (
                      <option key={k} value={k}>
                        {plural(k, "line")}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={busy !== null || n === e.count}
                    onClick={() => (n < e.count ? actions.condense(e.id, n) : actions.addLines(e.id, n))}
                    className="h-9 w-[84px] rounded-md border border-line-strong px-2.5 text-[13px] hover:bg-sunken disabled:opacity-50"
                  >
                    {busy === e.id ? "Shortening…" : n < e.count ? "Shorten" : n > e.count ? "Add" : "Apply"}
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="text-xs leading-normal text-muted">
            Fewer merges that role&apos;s lines with AI, from your own words only. More adds
            back your own lines from your profile (undoing a merge if needed) — as many as it has.
          </p>
        </div>
      )}
    </section>
  );
}
