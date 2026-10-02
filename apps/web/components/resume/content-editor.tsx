"use client";

import type { Bullet, Project, ResumeData } from "@rg/schema";
import { useState } from "react";
import type { LineHistory, SummaryLength } from "@/lib/api";
import { newId } from "@/lib/ids";
import { ItemControls, move, removeAt, replaceAt, TextArea } from "@/components/profile/fields";

type Props = {
  data: ResumeData;
  setData: (update: (d: ResumeData) => ResumeData) => void;
  /** The profile as it is now: where lines left out of this resume come from. */
  profile: ResumeData | null;
  provenance: Record<string, LineHistory>;
  /** Write the summary with AI (from this resume's facts), and undo that. */
  summaryAi?: { busy: boolean; disabled: boolean; write: (length: SummaryLength) => void; undo: (() => void) | null };
};

const ORIGIN_LABEL: Record<LineHistory["status"], string> = {
  kept: "Edited",
  reworded: "Reworded for this job",
  reverted: "Edited",
  condensed: "Merged from your lines",
  written: "Written from your resume",
};

function Card({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {note && <span className="text-xs text-muted">{note}</span>}
      </div>
      {children}
    </section>
  );
}

/** Where this line's wording came from, and the way back to the person's own. */
function LineOrigin({
  text,
  history,
  onUseOriginal,
}: {
  text: string;
  history: LineHistory | undefined;
  onUseOriginal: () => void;
}) {
  if (!history || text === history.original) {
    return history?.status === "reverted" ? (
      <span className="text-xs text-muted" title={`The suggested rewording ${history.reason}.`}>
        Kept in your words
      </span>
    ) : null;
  }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span className="font-medium text-accent-ink">
        {ORIGIN_LABEL[history.status]}
      </span>
      {history.original && (
        <details className="text-muted">
          <summary className="cursor-pointer">See original</summary>
          <p className="mt-1 text-ink">{history.original}</p>
        </details>
      )}
      {/* A merged line's original is several lines: re-add them from the unticked list. */}
      {history.status !== "condensed" && history.original && (
        <button type="button" onClick={onUseOriginal} className="text-accent underline-offset-2 hover:underline">
          Use original
        </button>
      )}
    </div>
  );
}

/**
 * The lines of one role or project: the ones in this resume (ticked, in order,
 * editable) and the profile's others (unticked, to add back).
 */
function Lines({
  label,
  included,
  available,
  provenance,
  onChange,
}: {
  label: string;
  included: Bullet[];
  available: Bullet[];
  provenance: Record<string, LineHistory>;
  onChange: (bullets: Bullet[]) => void;
}) {
  const inResume = new Set(included.map((b) => b.id));
  const left = available.filter((b) => !inResume.has(b.id));
  return (
    <div className="flex flex-col gap-2.5">
      {included.map((b, i) => (
        <div key={b.id} className="flex flex-col gap-1">
          <div className="flex items-start gap-1.5">
            <input
              type="checkbox"
              checked
              aria-label={`Include this line in the resume`}
              onChange={() => onChange(removeAt(included, i))}
              className="mt-3 size-4 shrink-0 accent-accent"
            />
            <TextArea
              label={`${label}, line ${i + 1}`}
              hideLabel
              rows={1}
              value={b.text}
              onChange={(text) => onChange(replaceAt(included, i, { ...b, text }))}
            />
            <ItemControls
              what={`line ${i + 1}`}
              index={i}
              count={included.length}
              onMove={(from, to) => onChange(move(included, from, to))}
              onRemove={() => onChange(removeAt(included, i))}
            />
          </div>
          <div className="pl-6">
            <LineOrigin
              text={b.text}
              history={provenance[b.id]}
              onUseOriginal={() => onChange(replaceAt(included, i, { ...b, text: provenance[b.id]!.original }))}
            />
          </div>
        </div>
      ))}
      {left.map((b) => (
        <label key={b.id} className="flex items-start gap-1.5 text-[13px] leading-snug text-muted">
          <input
            type="checkbox"
            checked={false}
            onChange={() => onChange([...included, { id: b.id, text: b.text }])}
            className="mt-0.5 size-4 shrink-0 accent-accent"
          />
          <span>
            {b.text} <span className="text-xs">(left out for this job)</span>
          </span>
        </label>
      ))}
    </div>
  );
}

/** Write the summary with AI, at a length the person picks. */
function SummaryAi({
  has,
  busy,
  disabled,
  write,
  undo,
}: NonNullable<Props["summaryAi"]> & { has: boolean }) {
  const [length, setLength] = useState<SummaryLength>("same");
  // With a summary there, lengths are relative to it; without one, they're absolute.
  const choices: [SummaryLength, string][] = has
    ? [["shorter", "Shorter"], ["same", "Same length"], ["longer", "Longer"]]
    : [["shorter", "Short"], ["same", "Medium"], ["longer", "Long"]];
  return (
    <div className="flex flex-col gap-2 border-t border-sunken pt-3">
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="sr-only">Length of the {has ? "new " : ""}summary</legend>
        <span aria-hidden className="text-[13px] text-muted">Length</span>
        <div className="flex overflow-hidden rounded-lg border border-line-strong text-[13px]">
          {choices.map(([value, label]) => (
            <label
              key={value}
              className={`cursor-pointer px-2.5 py-1.5 has-[:focus-visible]:outline-2 ${
                length === value ? "bg-accent-soft font-medium text-accent-ink" : "hover:bg-sunken"
              }`}
            >
              <input
                type="radio"
                name="summary-length"
                value={value}
                checked={length === value}
                onChange={() => setLength(value)}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => write(length)}
          disabled={disabled}
          className="h-9 rounded-lg border border-line-strong px-3 text-[13px] hover:bg-sunken disabled:opacity-50"
        >
          {busy ? "Writing…" : has ? "Rewrite with AI" : "Write with AI"}
        </button>
        {undo && (
          <button type="button" onClick={undo} className="text-[13px] text-accent underline-offset-2 hover:underline">
            Undo
          </button>
        )}
        <span className="text-xs text-muted">Only from what&apos;s in this resume.</span>
      </div>
    </div>
  );
}

export function ResumeContentEditor({ data, setData, profile, provenance, summaryAi }: Props) {
  const profileRole = (id: string) => profile?.experience.find((e) => e.id === id);
  const profileProject = (id: string) => profile?.projects.find((p) => p.id === id);
  const leftOutProjects = (profile?.projects ?? []).filter((p) => !data.projects.some((x) => x.id === p.id));
  const resumeSkills = new Set(data.skills.flatMap((g) => g.items.map((s) => s.toLowerCase())));
  const moreSkills = (profile?.skills.flatMap((g) => g.items) ?? []).filter(
    (s) => !resumeSkills.has(s.toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-3">
      <Card
        title="Summary"
        note={
          provenance.summary?.status === "reworded" && data.summary !== provenance.summary.original
            ? "Written for this job"
            : undefined
        }
      >
        <TextArea
          label="Summary"
          hideLabel
          rows={3}
          value={data.summary}
          onChange={(summary) => setData((d) => ({ ...d, summary }))}
        />
        <LineOrigin
          text={data.summary}
          history={provenance.summary}
          onUseOriginal={() => setData((d) => ({ ...d, summary: provenance.summary!.original }))}
        />
        {summaryAi && <SummaryAi has={data.summary.trim() !== ""} {...summaryAi} />}
      </Card>

      {data.experience.map((e, i) => (
        <Card
          key={e.id}
          title={[e.title, e.company].filter(Boolean).join(", ") || "Role"}
          note={`${e.bullets.length} of ${profileRole(e.id)?.bullets.length ?? e.bullets.length}`}
        >
          <Lines
            label={e.company || e.title}
            included={e.bullets}
            available={profileRole(e.id)?.bullets ?? []}
            provenance={provenance}
            onChange={(bullets) =>
              setData((d) => ({ ...d, experience: replaceAt(d.experience, i, { ...d.experience[i]!, bullets }) }))
            }
          />
        </Card>
      ))}

      <Card title="Skills" note="from your profile">
        {data.skills.map((g, gi) => (
          <div key={g.id} className="flex flex-col gap-1.5">
            {g.group && <span className="text-[13px] font-medium">{g.group}</span>}
            <ul className="flex flex-wrap gap-1.5">
              {g.items.map((item, ii) => (
                <li key={item} className="inline-flex items-center gap-1 rounded-full bg-sunken py-0.5 pr-1 pl-2.5 text-[13px]">
                  {item}
                  <button
                    type="button"
                    aria-label={`Leave ${item} out of this resume`}
                    onClick={() =>
                      setData((d) => ({
                        ...d,
                        skills: replaceAt(d.skills, gi, { ...g, items: removeAt(g.items, ii) }).filter((x) => x.items.length),
                      }))
                    }
                    className="flex size-6 items-center justify-center rounded-full text-muted hover:bg-line hover:text-ink"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {moreSkills.length > 0 && (
          <div className="flex flex-col gap-1.5 border-t border-sunken pt-2.5">
            <span className="text-xs text-muted">Also in your profile — click to add</span>
            <ul className="flex flex-wrap gap-1.5">
              {moreSkills.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() =>
                      setData((d) => {
                        const skills = d.skills.length ? d.skills : [{ id: newId("sk"), group: "", items: [] }];
                        const last = skills.length - 1;
                        return { ...d, skills: replaceAt(skills, last, { ...skills[last]!, items: [...skills[last]!.items, s] }) };
                      })
                    }
                    className="rounded-full border border-dashed border-line-strong px-2.5 py-0.5 text-[13px] text-muted hover:bg-sunken hover:text-ink"
                  >
                    + {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {(data.projects.length > 0 || leftOutProjects.length > 0) && (
        <Card title="Projects">
          {data.projects.map((p, i) => (
            <div key={p.id} className="flex flex-col gap-2 border-t border-sunken pt-2.5 first-of-type:border-t-0 first-of-type:pt-0">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked
                  onChange={() => setData((d) => ({ ...d, projects: removeAt(d.projects, i) }))}
                  className="size-4 accent-accent"
                />
                {p.name}
              </label>
              <Lines
                label={p.name}
                included={p.bullets}
                available={profileProject(p.id)?.bullets ?? []}
                provenance={provenance}
                onChange={(bullets) =>
                  setData((d) => ({ ...d, projects: replaceAt(d.projects, i, { ...d.projects[i]!, bullets }) }))
                }
              />
            </div>
          ))}
          {leftOutProjects.map((p: Project) => (
            <label key={p.id} className="flex items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={false}
                onChange={() => setData((d) => ({ ...d, projects: [...d.projects, structuredClone(p)] }))}
                className="size-4 accent-accent"
              />
              {p.name} <span className="text-xs">(left out for this job)</span>
            </label>
          ))}
        </Card>
      )}

      <p className="px-1 text-xs leading-normal text-muted">
        Names, job titles, employers, dates and education come straight from your profile. To
        change them, edit your profile and re-tailor.
      </p>
    </div>
  );
}
