"use client";

import { useState } from "react";
import type { Bullet, Project, ResumeData } from "@rg/schema";
import { SummaryAi } from "@/components/summary-ai";
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
  keywordAi?: KeywordAi;
};

/** Rewrite one line with keywords the person picks from the job's missing ones. */
export type KeywordAi = {
  /** The job's terms that no line names yet. */
  gaps: string[];
  /** The line being rewritten, if any. */
  busyLine: string | null;
  disabled: boolean;
  rewrite: (lineId: string, keywords: string[], again: boolean) => void;
};

const ORIGIN_LABEL: Record<LineHistory["status"], string> = {
  kept: "Edited",
  reworded: "Reworded for this job",
  reverted: "Edited",
  condensed: "Merged from your lines",
  written: "Written from your resume",
  bridged: "Named a skill this job wants",
  keywords: "Rewritten with your keywords",
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
  onRewriteAgain,
}: {
  text: string;
  history: LineHistory | undefined;
  onUseOriginal: () => void;
  onRewriteAgain?: () => void;
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
        {history.status === "bridged" && history.skills?.length
          ? `Added ${history.skills.map((s) => `${s.skill} (your line says “${s.evidence}”)`).join(", ")}`
          : history.status === "keywords" && history.keywords?.length
            ? `Added your keywords: ${history.keywords.join(", ")}`
            : ORIGIN_LABEL[history.status]}
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
      {history.status === "keywords" && onRewriteAgain && (
        <button type="button" onClick={onRewriteAgain} className="text-accent underline-offset-2 hover:underline">
          Rewrite again
        </button>
      )}
    </div>
  );
}

/** "Add keywords" under a line: pick from the job's missing terms (or type one), rewrite. */
function LineKeywords({ line, ai }: { line: Bullet; ai: KeywordAi }) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [other, setOther] = useState("");
  const lower = line.text.toLowerCase();
  const offered = [...ai.gaps.filter((g) => !lower.includes(g.toLowerCase())), ...picked.filter((p) => !ai.gaps.includes(p))];
  const busy = ai.busyLine === line.id;

  if (busy) return <span className="text-xs text-muted" role="status">Rewriting this line…</span>;
  if (!open)
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={ai.disabled}
        className="self-start text-xs text-accent underline-offset-2 hover:underline disabled:opacity-60"
      >
        + Add job keywords
      </button>
    );

  function toggle(k: string) {
    setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : p.length < 8 ? [...p, k] : p));
  }
  function addOther() {
    const k = other.trim();
    if (k && !picked.includes(k)) setPicked((p) => (p.length < 8 ? [...p, k] : p));
    setOther("");
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-sunken/60 p-2.5">
      <span className="text-xs leading-snug text-muted">
        Pick the keywords this work really involved. AI rewrites the line to include them, and adds nothing else.
      </span>
      {offered.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Job keywords not in your lines">
          {offered.map((k) => {
            const on = picked.includes(k);
            return (
              <li key={k}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(k)}
                  className={`rounded-full border px-2.5 py-0.5 text-[13px] ${
                    on ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:bg-sunken"
                  }`}
                >
                  {on ? "✓ " : "+ "}
                  {k}
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <span className="text-xs text-muted">Every job keyword is already in your lines. You can type one below.</span>
      )}
      <div className="flex gap-1.5">
        <input
          value={other}
          onChange={(e) => setOther(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addOther();
            }
          }}
          maxLength={60}
          placeholder="Another keyword"
          aria-label="Another keyword"
          className="h-8 min-w-0 flex-1 rounded-md border border-line bg-surface px-2 text-[13px]"
        />
        <button type="button" onClick={addOther} className="h-8 rounded-md border border-line bg-surface px-2 text-[13px] hover:bg-sunken">
          Add
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!picked.length || ai.disabled}
          onClick={() => {
            ai.rewrite(line.id, picked, false);
            setOpen(false);
          }}
          className="h-8 rounded-md bg-accent px-3 text-[13px] font-medium text-white disabled:opacity-50"
        >
          {picked.length ? `Rewrite with ${picked.length} keyword${picked.length > 1 ? "s" : ""}` : "Pick keywords"}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setPicked([]);
          }}
          className="h-8 rounded-md px-2 text-[13px] text-muted hover:bg-sunken"
        >
          Cancel
        </button>
      </div>
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
  keywordAi,
}: {
  label: string;
  included: Bullet[];
  available: Bullet[];
  provenance: Record<string, LineHistory>;
  onChange: (bullets: Bullet[]) => void;
  keywordAi?: KeywordAi;
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
          <div className="flex flex-col gap-1.5 pl-6">
            <LineOrigin
              text={b.text}
              history={provenance[b.id]}
              onUseOriginal={() => onChange(replaceAt(included, i, { ...b, text: provenance[b.id]!.original }))}
              onRewriteAgain={
                keywordAi && !keywordAi.disabled && provenance[b.id]?.keywords?.length
                  ? () => keywordAi.rewrite(b.id, provenance[b.id]!.keywords!, true)
                  : undefined
              }
            />
            {keywordAi && <LineKeywords line={b} ai={keywordAi} />}
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

export function ResumeContentEditor({ data, setData, profile, provenance, summaryAi, keywordAi }: Props) {
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
            keywordAi={keywordAi}
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
                keywordAi={keywordAi}
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
