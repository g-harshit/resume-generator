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
import { useState } from "react";
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

type Props = {
  data: ResumeData;
  setData: (update: (d: ResumeData) => ResumeData) => void;
  issues: IssuesFor;
};

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
}: {
  bullets: Bullet[];
  onChange: (b: Bullet[]) => void;
  issues: IssuesFor;
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
    </div>
  );
}

// --- sections -----------------------------------------------------------------------

function BasicsSection({ data, setData, issues }: Props) {
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

function SummarySection({ data, setData, issues }: Props) {
  return (
    <Section title="Summary">
      <TextArea
        label="A few lines about you (optional)"
        rows={3}
        value={data.summary}
        onChange={(summary) => setData((d) => ({ ...d, summary }))}
        issues={issues("summary")}
      />
    </Section>
  );
}

function ExperienceSection({ data, setData, issues }: Props) {
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
          <Bullets bullets={e.bullets} onChange={(bullets) => set(i, { bullets })} issues={issues} />
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

function EducationSection({ data, setData, issues }: Props) {
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

function SkillsSection({ data, setData }: Props) {
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

function ProjectsSection({ data, setData, issues }: Props) {
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
          <Bullets bullets={p.bullets} onChange={(bullets) => set(i, { bullets })} issues={issues} />
        </Entry>
      ))}
      <AddButton onClick={() => setList([...list, { id: newId("prj"), name: "", url: "", start: null, end: null, bullets: [] }])}>
        Add a project
      </AddButton>
    </Section>
  );
}

function CertificationsSection({ data, setData, issues }: Props) {
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
          <DateField label="Date" value={c.date} onChange={(date) => set(i, { date })} issues={issues(c.id, "date")} />
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
