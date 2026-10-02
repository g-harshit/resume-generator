"use client";

import type {
  Bullet,
  Certification,
  Education,
  Experience,
  Link,
  Project,
  ResumeData,
  SkillGroup,
} from "@rg/schema";
import { createContext, useContext, useState } from "react";
import { SummaryAi } from "@/components/summary-ai";
import { api, type DraftedLines } from "@/lib/api";
import { newId } from "@/lib/ids";
import {
  AddButton,
  DateField,
  Issues,
  ItemControls,
  inputClass,
  move,
  removeAt,
  replaceAt,
  TextArea,
  TextField,
} from "./fields";

/** Messages for an entry (by id) and optionally one of its fields. */
export type IssuesFor = (target: string, field?: string | null) => string[];

export type Props = {
  data: ResumeData;
  setData: (update: (d: ResumeData) => ResumeData) => void;
  issues: IssuesFor;
};

/**
 * AI writing help in the profile editor. Present when the editor can save first: the
 * server writes from the saved profile. Without it, the editor is plain fields.
 */
const AiContext = createContext<{ flush: () => Promise<boolean> } | null>(null);
export const ProfileAiProvider = AiContext.Provider;

function problemText(err: unknown) {
  return err instanceof TypeError ? "Can't reach the server." : (err as Error).message;
}

/**
 * "Help me write these": the person describes a project or job in their own words,
 * and gets resume lines to add — only from what they wrote.
 */
function NotesToLines({
  kind,
  context,
  onAdd,
  open: startOpen,
}: {
  kind: "project" | "experience";
  context: string;
  onAdd: (lines: string[]) => void;
  open: boolean;
}) {
  const ai = useContext(AiContext);
  const [open, setOpen] = useState(startOpen);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DraftedLines | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  if (!ai) return null;

  async function write() {
    setBusy(true);
    setProblem(null);
    try {
      await ai!.flush();
      setResult(await api.writeProfileLines(kind, context, notes));
    } catch (err) {
      setProblem(problemText(err));
    } finally {
      setBusy(false);
    }
  }

  function add(lines: string[]) {
    onAdd(lines);
    setResult((r) => (r ? { ...r, lines: r.lines.filter((l) => !lines.includes(l)) } : r));
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="self-start text-[13px] text-accent underline-offset-2 hover:underline">
        ✦ Help me write these lines
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-2.5 rounded-lg bg-accent-soft/50 p-3">
      <TextArea
        label={kind === "project" ? "Tell us about this project in your own words" : "Tell us what you did here, in your own words"}
        rows={3}
        value={notes}
        onChange={setNotes}
        placeholder={
          kind === "project"
            ? "e.g. made a website for our college fest with react and firebase. i did the login and the events page. around 800 students signed up"
            : "e.g. fixed bugs in the android app, wrote tests in kotlin, built a settings screen that shipped to users"
        }
      />
      <p className="text-xs leading-normal text-muted">
        What you built, what you did, the tools you used, and anything that came of it (numbers
        if you have them). We only use what you write here — nothing is made up.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={write}
          disabled={busy || notes.trim().length < 15}
          className="h-9 rounded-lg bg-accent px-3 text-[13px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? "Writing…" : result ? "Write again" : "Write lines"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-[13px] text-muted hover:text-ink">
          Close
        </button>
      </div>
      {problem && <p role="alert" className="text-[13px] text-warn-ink">{problem}</p>}
      {result && result.lines.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <ul className="flex flex-col gap-1.5">
            {result.lines.map((line) => (
              <li key={line} className="flex items-start gap-2 rounded-md bg-surface p-2 text-sm">
                <span className="flex-1">{line}</span>
                <button type="button" onClick={() => add([line])} className="shrink-0 text-[13px] text-accent hover:underline">
                  Add
                </button>
              </li>
            ))}
          </ul>
          {result.lines.length > 1 && (
            <button type="button" onClick={() => add(result.lines)} className="self-start text-[13px] font-medium text-accent hover:underline">
              Add all
            </button>
          )}
        </div>
      )}
      {result && result.left_out.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer">
            {result.left_out.length === 1 ? "1 line was left out" : `${result.left_out.length} lines were left out`} for
            saying more than you wrote
          </summary>
          <ul className="mt-1 flex flex-col gap-1">
            {result.left_out.map((x) => (
              <li key={x.text}>
                “{x.text}” — {x.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
      <h2 className="text-base font-semibold">
        {title}
        {count !== undefined && <span className="font-normal text-muted"> · {count}</span>}
      </h2>
      {children}
    </section>
  );
}

function Entry({
  heading,
  controls,
  issues,
  children,
}: {
  heading: string;
  controls: React.ReactNode;
  issues: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-t border-sunken pt-4 first-of-type:border-t-0 first-of-type:pt-0">
      <div className="flex items-center justify-between gap-2">
        <h3 className="truncate text-[15px] font-medium">{heading}</h3>
        {controls}
      </div>
      <Issues messages={issues} />
      {children}
    </div>
  );
}

// --- bullets ----------------------------------------------------------------------

function Bullets({
  bullets,
  onChange,
  issues,
  draft,
}: {
  bullets: Bullet[];
  onChange: (b: Bullet[]) => void;
  issues: IssuesFor;
  /** Offer AI help writing lines for this entry. */
  draft?: { kind: "project" | "experience"; context: string };
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[13px] text-muted">What you did</span>
      {bullets.map((b, i) => (
        <div key={b.id} className="flex items-start gap-1">
          <span aria-hidden="true" className="mt-2.5 text-muted">•</span>
          <TextArea
            label={`Line ${i + 1}`}
            hideLabel
            rows={1}
            value={b.text}
            onChange={(text) => onChange(replaceAt(bullets, i, { ...b, text }))}
            issues={issues(b.id)}
          />
          <ItemControls
            what={`line ${i + 1}`}
            index={i}
            count={bullets.length}
            onMove={(from, to) => onChange(move(bullets, from, to))}
            onRemove={() => onChange(removeAt(bullets, i))}
          />
        </div>
      ))}
      <AddButton onClick={() => onChange([...bullets, { id: newId("b"), text: "" }])}>Add a line</AddButton>
      {draft && (
        <NotesToLines
          {...draft}
          // Open already when there's nothing written yet: that's when help is wanted.
          open={!bullets.some((b) => b.text.trim())}
          onAdd={(lines) =>
            onChange([...bullets.filter((b) => b.text.trim()), ...lines.map((text) => ({ id: newId("b"), text }))])
          }
        />
      )}
    </div>
  );
}

// --- sections -----------------------------------------------------------------------

export function BasicsSection({ data, setData, issues }: Props) {
  const b = data.basics;
  const set = (patch: Partial<typeof b>) => setData((d) => ({ ...d, basics: { ...d.basics, ...patch } }));
  const setLinks = (links: Link[]) => set({ links });
  return (
    <Section title="Contact details">
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Full name" value={b.name} onChange={(name) => set({ name })} issues={issues("basics", "name")} autoComplete="name" />
        <TextField label="Job title" value={b.headline} onChange={(headline) => set({ headline })} placeholder="e.g. Backend Engineer" />
        <TextField label="Email" type="email" value={b.email} onChange={(email) => set({ email })} issues={issues("basics", "email")} autoComplete="email" />
        <TextField label="Phone" type="tel" value={b.phone} onChange={(phone) => set({ phone })} issues={issues("basics", "phone")} autoComplete="tel" />
        <TextField label="Location" value={b.location} onChange={(location) => set({ location })} placeholder="City, Country" />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] text-muted">Links</span>
        {b.links.map((link, i) => (
          <div key={link.id} className="flex items-end gap-2">
            <TextField className="w-32 shrink-0" label="Label" value={link.label} placeholder="LinkedIn" onChange={(label) => setLinks(replaceAt(b.links, i, { ...link, label }))} />
            <TextField className="flex-1" label="URL" value={link.url} onChange={(url) => setLinks(replaceAt(b.links, i, { ...link, url }))} />
            <ItemControls what={`link ${link.label || i + 1}`} index={i} count={b.links.length} onMove={(f, t) => setLinks(move(b.links, f, t))} onRemove={() => setLinks(removeAt(b.links, i))} />
          </div>
        ))}
        <AddButton onClick={() => setLinks([...b.links, { id: newId("lnk"), label: "", url: "" }])}>Add a link</AddButton>
      </div>
    </Section>
  );
}

export function SummarySection({ data, setData, issues }: Props) {
  const ai = useContext(AiContext);
  const [busy, setBusy] = useState(false);
  const [before, setBefore] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function write(length: Parameters<typeof api.writeProfileSummary>[0]) {
    setBusy(true);
    setProblem(null);
    try {
      if (!(await ai!.flush())) return;
      const { text } = await api.writeProfileSummary(length);
      setBefore(data.summary);
      setData((d) => ({ ...d, summary: text }));
    } catch (err) {
      setProblem(problemText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Summary">
      <TextArea
        label="A few lines about you (optional)"
        rows={3}
        value={data.summary}
        onChange={(summary) => setData((d) => ({ ...d, summary }))}
        issues={issues("summary")}
      />
      {ai && (
        <SummaryAi
          has={data.summary.trim() !== ""}
          busy={busy}
          disabled={busy}
          write={write}
          undo={
            before !== null && !busy
              ? () => {
                  setData((d) => ({ ...d, summary: before }));
                  setBefore(null);
                }
              : null
          }
          note="Written only from what's in your profile."
        />
      )}
      {problem && <p role="alert" className="text-[13px] text-warn-ink">{problem}</p>}
    </Section>
  );
}

export function ExperienceSection({ data, setData, issues }: Props) {
  const list = data.experience;
  const setList = (experience: Experience[]) => setData((d) => ({ ...d, experience }));
  const set = (i: number, patch: Partial<Experience>) => setList(replaceAt(list, i, { ...list[i]!, ...patch }));
  return (
    <Section title="Experience" count={list.length}>
      {list.map((e, i) => (
        <Entry
          key={e.id}
          heading={[e.title, e.company].filter(Boolean).join(", ") || "New role"}
          issues={issues(e.id, null)}
          controls={<ItemControls what={e.company || "role"} index={i} count={list.length} onMove={(f, t) => setList(move(list, f, t))} onRemove={() => setList(removeAt(list, i))} />}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Job title" value={e.title} onChange={(title) => set(i, { title })} issues={issues(e.id, "title")} />
            <TextField label="Company" value={e.company} onChange={(company) => set(i, { company })} />
            <TextField label="Location" value={e.location} onChange={(location) => set(i, { location })} />
          </div>
          <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
            <DateField label="Start" value={e.start} onChange={(start) => set(i, { start })} issues={issues(e.id, "start")} />
            <DateField label="End" value={e.end} disabled={e.current} onChange={(end) => set(i, { end })} issues={e.current ? [] : issues(e.id, "end")} />
            <label className="mt-7 flex h-10 items-center gap-2 text-sm">
              <input type="checkbox" checked={e.current} onChange={(ev) => set(i, { current: ev.target.checked, end: ev.target.checked ? null : e.end })} className="size-4 accent-accent" />
              I work here now
            </label>
          </div>
          <Bullets
            bullets={e.bullets}
            onChange={(bullets) => set(i, { bullets })}
            issues={issues}
            draft={{ kind: "experience", context: [e.title, e.company].filter(Boolean).join(" at ") }}
          />
        </Entry>
      ))}
      <AddButton
        onClick={() =>
          setList([...list, { id: newId("exp"), company: "", title: "", location: "", start: null, end: null, current: false, bullets: [] }])
        }
      >
        Add a role
      </AddButton>
    </Section>
  );
}

export function EducationSection({ data, setData, issues }: Props) {
  const list = data.education;
  const setList = (education: Education[]) => setData((d) => ({ ...d, education }));
  const set = (i: number, patch: Partial<Education>) => setList(replaceAt(list, i, { ...list[i]!, ...patch }));
  return (
    <Section title="Education" count={list.length}>
      {list.map((e, i) => (
        <Entry
          key={e.id}
          heading={e.institution || e.degree || "New entry"}
          issues={issues(e.id, null)}
          controls={<ItemControls what={e.institution || "entry"} index={i} count={list.length} onMove={(f, t) => setList(move(list, f, t))} onRemove={() => setList(removeAt(list, i))} />}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="School or university" value={e.institution} onChange={(institution) => set(i, { institution })} issues={issues(e.id, "institution")} />
            <TextField label="Degree" value={e.degree} onChange={(degree) => set(i, { degree })} placeholder="e.g. B.Tech" />
            <TextField label="Field of study" value={e.field} onChange={(field) => set(i, { field })} />
            <TextField label="Location" value={e.location} onChange={(location) => set(i, { location })} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <DateField label="Start" value={e.start} onChange={(start) => set(i, { start })} issues={issues(e.id, "start")} />
            <DateField label="End" value={e.end} onChange={(end) => set(i, { end })} issues={issues(e.id, "end")} />
          </div>
          <TextArea label="Details (grade, honours — optional)" rows={1} value={e.details} onChange={(details) => set(i, { details })} />
        </Entry>
      ))}
      <AddButton
        onClick={() =>
          setList([...list, { id: newId("edu"), institution: "", degree: "", field: "", location: "", start: null, end: null, details: "" }])
        }
      >
        Add education
      </AddButton>
    </Section>
  );
}

/** Type a skill and press Enter or comma; pasting "Go, SQL, Kafka" adds all three. */
function SkillItems({ group, onChange }: { group: SkillGroup; onChange: (items: string[]) => void }) {
  const [draft, setDraft] = useState("");
  function add(text: string) {
    const known = new Set(group.items.map((s) => s.toLowerCase()));
    const fresh = text
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && !known.has(s.toLowerCase()) && known.add(s.toLowerCase()));
    if (fresh.length) onChange([...group.items, ...fresh]);
    setDraft("");
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {group.items.map((item, i) => (
        <span key={item} className="inline-flex items-center gap-1 rounded-full bg-sunken py-1 pr-1 pl-3 text-sm">
          {item}
          <button type="button" aria-label={`Remove ${item}`} onClick={() => onChange(removeAt(group.items, i))} className="flex size-6 items-center justify-center rounded-full text-muted hover:bg-line hover:text-ink">
            ×
          </button>
        </span>
      ))}
      <input
        aria-label={`Add a skill${group.group ? ` to ${group.group}` : ""}`}
        placeholder="Add a skill…"
        value={draft}
        onChange={(e) => {
          if (e.target.value.includes(",")) add(e.target.value);
          else setDraft(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(draft);
          } else if (e.key === "Backspace" && !draft && group.items.length) {
            onChange(group.items.slice(0, -1));
          }
        }}
        onBlur={() => draft && add(draft)}
        className={`h-9 min-w-32 flex-1 ${inputClass}`}
      />
    </div>
  );
}

export function SkillsSection({ data, setData }: Props) {
  const list = data.skills;
  const setList = (skills: SkillGroup[]) => setData((d) => ({ ...d, skills }));
  const set = (i: number, patch: Partial<SkillGroup>) => setList(replaceAt(list, i, { ...list[i]!, ...patch }));
  const total = list.reduce((n, g) => n + g.items.length, 0);
  return (
    <Section title="Skills" count={total}>
      {list.map((g, i) => (
        <div key={g.id} className="flex flex-col gap-2 border-t border-sunken pt-4 first-of-type:border-t-0 first-of-type:pt-0">
          <div className="flex items-end gap-2">
            <TextField className="flex-1" label="Group name (optional)" placeholder="e.g. Languages" value={g.group} onChange={(group) => set(i, { group })} />
            <ItemControls what={g.group || "skill group"} index={i} count={list.length} onMove={(f, t) => setList(move(list, f, t))} onRemove={() => setList(removeAt(list, i))} />
          </div>
          <SkillItems group={g} onChange={(items) => set(i, { items })} />
        </div>
      ))}
      <AddButton onClick={() => setList([...list, { id: newId("sk"), group: "", items: [] }])}>Add a skill group</AddButton>
    </Section>
  );
}

export function ProjectsSection({ data, setData, issues }: Props) {
  const list = data.projects;
  const setList = (projects: Project[]) => setData((d) => ({ ...d, projects }));
  const set = (i: number, patch: Partial<Project>) => setList(replaceAt(list, i, { ...list[i]!, ...patch }));
  return (
    <Section title="Projects" count={list.length}>
      {list.map((p, i) => (
        <Entry
          key={p.id}
          heading={p.name || "New project"}
          issues={issues(p.id, null)}
          controls={<ItemControls what={p.name || "project"} index={i} count={list.length} onMove={(f, t) => setList(move(list, f, t))} onRemove={() => setList(removeAt(list, i))} />}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Name" value={p.name} onChange={(name) => set(i, { name })} issues={issues(p.id, "name")} />
            <TextField label="Link (optional)" value={p.url} onChange={(url) => set(i, { url })} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <DateField label="Start" value={p.start} onChange={(start) => set(i, { start })} issues={issues(p.id, "start")} />
            <DateField label="End" value={p.end} onChange={(end) => set(i, { end })} issues={issues(p.id, "end")} />
          </div>
          <Bullets
            bullets={p.bullets}
            onChange={(bullets) => set(i, { bullets })}
            issues={issues}
            draft={{ kind: "project", context: `Project: ${p.name}` }}
          />
        </Entry>
      ))}
      <AddButton onClick={() => setList([...list, { id: newId("prj"), name: "", url: "", start: null, end: null, bullets: [] }])}>
        Add a project
      </AddButton>
    </Section>
  );
}

export function CertificationsSection({ data, setData, issues }: Props) {
  const list = data.certifications;
  const setList = (certifications: Certification[]) => setData((d) => ({ ...d, certifications }));
  const set = (i: number, patch: Partial<Certification>) => setList(replaceAt(list, i, { ...list[i]!, ...patch }));
  return (
    <Section title="Certifications" count={list.length}>
      {list.map((c, i) => (
        <Entry
          key={c.id}
          heading={c.name || "New certification"}
          issues={issues(c.id, null)}
          controls={<ItemControls what={c.name || "certification"} index={i} count={list.length} onMove={(f, t) => setList(move(list, f, t))} onRemove={() => setList(removeAt(list, i))} />}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Name" value={c.name} onChange={(name) => set(i, { name })} />
            <TextField label="Issued by" value={c.issuer} onChange={(issuer) => set(i, { issuer })} />
          </div>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
            <DateField label="Date" value={c.date} onChange={(date) => set(i, { date })} issues={issues(c.id, "date")} />
            <TextField
              className="min-w-56 flex-1"
              label="Credential link (optional)"
              placeholder="e.g. credly.com/badges/…"
              value={c.url}
              onChange={(url) => set(i, { url })}
            />
          </div>
        </Entry>
      ))}
      <AddButton onClick={() => setList([...list, { id: newId("cert"), name: "", issuer: "", date: null, url: "" }])}>
        Add a certification
      </AddButton>
    </Section>
  );
}

export function ProfileEditor(props: Props) {
  return (
    <div className="flex flex-col gap-4">
      <BasicsSection {...props} />
      <SummarySection {...props} />
      <ExperienceSection {...props} />
      <EducationSection {...props} />
      <SkillsSection {...props} />
      <ProjectsSection {...props} />
      <CertificationsSection {...props} />
    </div>
  );
}
