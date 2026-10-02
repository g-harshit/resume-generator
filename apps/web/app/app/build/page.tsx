"use client";

import type { ResumeData } from "@rg/schema";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  BasicsSection,
  CertificationsSection,
  EducationSection,
  ExperienceSection,
  type IssuesFor,
  ProfileAiProvider,
  ProjectsSection,
  type Props as SectionProps,
  SkillsSection,
  SummarySection,
} from "@/components/profile/profile-editor";
import { api, type Profile } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { newId } from "@/lib/ids";
import { notePlace } from "@/lib/notes";
import { useProfileEditor } from "@/lib/use-profile-editor";

/**
 * Building a profile from scratch, one section at a time, for someone with no resume
 * to upload. Two tracks: a student or fresher starts with education and projects
 * (work is optional); someone with work history starts with their roles.
 */

type Track = "fresher" | "experienced";
type StepId = "basics" | "education" | "projects" | "experience" | "skills" | "extras" | "summary" | "done";

type Step = { id: StepId; title: string; help: string; optional?: boolean };

const STEPS: Record<Track, Step[]> = {
  fresher: [
    { id: "basics", title: "Your contact details", help: "How recruiters reach you. A LinkedIn or GitHub link helps a lot when you're starting out." },
    {
      id: "education",
      title: "Your education",
      help: "Your degree is the first thing a recruiter reads on a fresher's resume. Add your grade (CGPA or percentage) under Details if it's good.",
    },
    {
      id: "projects",
      title: "Your projects",
      help: "Projects are your experience. College projects, hackathons, personal apps, a final-year project — anything you built. Describe each in your own words and we'll turn it into resume lines.",
    },
    {
      id: "experience",
      title: "Internships and work",
      help: "Internships, part-time jobs, freelance work. Haven't had one yet? That's fine — skip this.",
      optional: true,
    },
    { id: "skills", title: "Your skills", help: "Languages, frameworks and tools you've actually used — in a project, a course or an internship. Group them if you like (e.g. Languages, Tools)." },
    {
      id: "extras",
      title: "Certifications",
      help: "Online courses with a certificate, workshops, coding contests. Optional.",
      optional: true,
    },
    { id: "summary", title: "A short summary", help: "Two or three lines at the top of your resume. Write your own, or let us write one from what you've added.", optional: true },
    { id: "done", title: "Check and save", help: "" },
  ],
  experienced: [
    { id: "basics", title: "Your contact details", help: "How recruiters reach you." },
    {
      id: "experience",
      title: "Your work experience",
      help: "Most recent first. For each role, describe what you did in your own words and we'll turn it into resume lines.",
    },
    { id: "education", title: "Your education", help: "Degrees and diplomas. Grades are optional once you have work experience." },
    { id: "skills", title: "Your skills", help: "Languages, frameworks and tools you've used. Group them if you like (e.g. Languages, Tools)." },
    { id: "projects", title: "Projects", help: "Side projects or open-source work worth showing. Optional.", optional: true },
    { id: "extras", title: "Certifications", help: "Optional.", optional: true },
    { id: "summary", title: "A short summary", help: "Two or three lines at the top of your resume. Write your own, or let us write one from what you've added.", optional: true },
    { id: "done", title: "Check and save", help: "" },
  ],
};

const TRACK_KEY = "rg:build-track";
const STEP_KEY = "rg:build-step";

function remember(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage can be blocked; the builder just starts at the beginning next time.
  }
}
function recall(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function emptyProfile(name: string, email: string): Profile {
  return {
    data: {
      basics: { name, headline: "", email, phone: "", location: "", links: [] },
      summary: "",
      experience: [],
      education: [],
      skills: [],
      projects: [],
      certifications: [],
    },
    version: 0, // saving version 0 creates the profile
    reviewed_at: null,
    source_document_id: null,
    source_mime: null,
    updated_at: new Date().toISOString(),
    checks: [],
    notes: [],
  };
}

/** Entries added but never filled in: dropped when leaving a step. */
function withoutBlanks(d: ResumeData): ResumeData {
  const filled = (...texts: (string | null | undefined)[]) => texts.some((t) => t && t.trim());
  const lines = (bullets: { text: string }[]) => bullets.some((b) => b.text.trim());
  return {
    ...d,
    experience: d.experience.filter((e) => filled(e.title, e.company, e.location, e.start) || lines(e.bullets)),
    education: d.education.filter((e) => filled(e.institution, e.degree, e.field, e.details, e.start, e.end)),
    projects: d.projects.filter((p) => filled(p.name, p.url, p.start) || lines(p.bullets)),
    skills: d.skills.filter((g) => g.items.length || g.group.trim()),
    certifications: d.certifications.filter((c) => filled(c.name, c.issuer)),
  };
}

/** A blank entry to start a step with, so the form is there to fill in. */
function starter(id: StepId, d: ResumeData): ResumeData {
  if (id === "education" && !d.education.length) {
    return { ...d, education: [{ id: newId("edu"), institution: "", degree: "", field: "", location: "", start: null, end: null, details: "" }] };
  }
  if (id === "projects" && !d.projects.length) {
    return { ...d, projects: [{ id: newId("prj"), name: "", url: "", start: null, end: null, bullets: [] }] };
  }
  if (id === "experience" && !d.experience.length) {
    return {
      ...d,
      experience: [{ id: newId("exp"), company: "", title: "", location: "", start: null, end: null, current: false, bullets: [] }],
    };
  }
  if (id === "skills" && !d.skills.length) {
    return { ...d, skills: [{ id: newId("sk"), group: "", items: [] }] };
  }
  return d;
}

export default function BuildPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [initial, setInitial] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api
      .getProfile()
      .then((p) => {
        if (cancelled) return;
        // A confirmed profile is edited on the profile page, not built again.
        if (p?.reviewed_at) router.replace("/app/profile");
        else setInitial(p ?? emptyProfile(user.name, user.email));
      })
      .catch((err) => !cancelled && setError((err as Error).message));
    return () => {
      cancelled = true;
    };
  }, [user, router]);

  if (error) return <p role="alert" className="text-warn-ink">{error}</p>;
  if (!initial) return <p role="status" className="text-muted">Loading…</p>;
  return <Builder initial={initial} />;
}

function Builder({ initial }: { initial: Profile }) {
  const router = useRouter();
  const { data, setData, checks, save, flush, confirm } = useProfileEditor(initial);
  const [track, setTrackState] = useState<Track | null>(() => {
    const t = recall(TRACK_KEY);
    return t === "fresher" || t === "experienced" ? t : null;
  });
  const [index, setIndex] = useState(() => Number(recall(STEP_KEY)) || 0);
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const ai = useMemo(() => ({ flush }), [flush]);

  const steps = track ? STEPS[track] : [];
  const step = steps[Math.min(index, steps.length - 1)];

  function go(to: number) {
    setData((d) => {
      const next = withoutBlanks(d);
      const target = steps[to];
      return target ? starter(target.id, next) : next;
    });
    setIndex(to);
    remember(STEP_KEY, String(to));
    window.scrollTo({ top: 0 });
  }

  function chooseTrack(t: Track) {
    setTrackState(t);
    remember(TRACK_KEY, t);
    setIndex(0);
    remember(STEP_KEY, "0");
  }

  async function finish() {
    setConfirming(true);
    setProblem(null);
    try {
      setData(withoutBlanks);
      if (await confirm()) {
        remember(TRACK_KEY, null);
        remember(STEP_KEY, null);
        router.push("/app");
      }
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  if (!track || !step) {
    return (
      <div className="flex max-w-3xl flex-col gap-7">
        <div className="flex flex-col gap-2.5">
          <h1 className="font-display text-5xl leading-tight">Let&apos;s build your resume.</h1>
          <p className="text-[17px] leading-relaxed text-muted">
            One section at a time. Describe what you&apos;ve done in your own words — we&apos;ll
            help turn it into resume lines, using only what you tell us.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {(
            [
              ["fresher", "I'm a student or fresher", "Little or no work experience yet. We'll start with your education and projects."],
              ["experienced", "I have work experience", "We'll start with your jobs, then education and skills."],
            ] as const
          ).map(([t, title, body]) => (
            <button
              key={t}
              type="button"
              onClick={() => chooseTrack(t)}
              className="flex flex-col gap-1.5 rounded-xl border border-line bg-surface p-5 text-left hover:border-accent hover:bg-accent-soft/40"
            >
              <span className="text-lg font-semibold">{title}</span>
              <span className="text-sm leading-normal text-muted">{body}</span>
            </button>
          ))}
        </div>
        <p className="text-sm text-muted">
          Have a resume after all? <Link href="/app">Upload it instead</Link>.
        </p>
      </div>
    );
  }

  const issues: IssuesFor = (target, field) =>
    checks
      .filter((c) => c.target === target && (field === undefined || c.field === field))
      .map((c) => c.message);
  const props: SectionProps = { data, setData, issues };
  const blocking = checks.filter((c) => c.blocking);
  const last = index >= steps.length - 1;

  return (
    <ProfileAiProvider value={ai}>
      <div className="flex max-w-3xl flex-col gap-5 pb-28">
        <nav aria-label="Steps" className="flex flex-col gap-2">
          <span className="text-sm text-muted">
            Step {index + 1} of {steps.length} ·{" "}
            <button type="button" onClick={() => setTrackState(null)} className="underline-offset-2 hover:underline">
              {track === "fresher" ? "Student / fresher" : "Experienced"} (change)
            </button>
          </span>
          <ol className="flex gap-1">
            {steps.map((s, i) => (
              <li key={s.id} className="flex-1">
                <button
                  type="button"
                  onClick={() => go(i)}
                  aria-label={`${s.title}${i === index ? " (current step)" : ""}`}
                  aria-current={i === index ? "step" : undefined}
                  className={`block h-1.5 w-full rounded-full ${i <= index ? "bg-accent" : "bg-sunken hover:bg-line"}`}
                />
              </li>
            ))}
          </ol>
        </nav>

        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-4xl">
            {step.title}
            {step.optional && <span className="ml-2 align-middle font-sans text-sm font-normal text-muted">optional</span>}
          </h1>
          {step.help && <p className="max-w-2xl text-[15px] leading-relaxed text-muted">{step.help}</p>}
        </div>

        {step.id === "basics" && <BasicsSection {...props} />}
        {step.id === "education" && <EducationSection {...props} />}
        {step.id === "projects" && <ProjectsSection {...props} />}
        {step.id === "experience" && <ExperienceSection {...props} />}
        {step.id === "skills" && <SkillsSection {...props} />}
        {step.id === "extras" && <CertificationsSection {...props} />}
        {step.id === "summary" && <SummarySection {...props} />}
        {step.id === "done" && <Review data={withoutBlanks(data)} blocking={blocking} onFix={(i) => go(i)} steps={steps} />}

        {problem && <p role="alert" className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">{problem}</p>}
      </div>

      <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-surface md:left-58">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 md:mx-0 md:px-11">
          <span role="status" className="text-sm text-muted">
            {save.kind === "saving" ? "Saving…" : save.kind === "error" ? "Couldn't save — will retry" : save.kind === "unsaved" ? "Unsaved changes…" : "Saved as you go"}
          </span>
          <div className="flex gap-2.5">
            {index > 0 && (
              <button type="button" onClick={() => go(index - 1)} className="h-12 rounded-[10px] border border-line-strong bg-surface px-4 text-[15px] hover:bg-sunken">
                Back
              </button>
            )}
            {last ? (
              <button
                type="button"
                onClick={finish}
                disabled={confirming || blocking.length > 0}
                className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {confirming ? "Saving…" : "Save my profile"}
              </button>
            ) : (
              <button type="button" onClick={() => go(index + 1)} className="h-12 rounded-[10px] bg-accent px-5 text-[15px] font-medium text-white hover:bg-accent-hover">
                {step.optional && !hasContent(step.id, data) ? "Skip" : "Next"}
              </button>
            )}
          </div>
        </div>
      </footer>
    </ProfileAiProvider>
  );
}

function hasContent(id: StepId, d: ResumeData): boolean {
  const kept = withoutBlanks(d);
  if (id === "experience") return kept.experience.length > 0;
  if (id === "projects") return kept.projects.length > 0;
  if (id === "extras") return kept.certifications.length > 0;
  if (id === "summary") return d.summary.trim() !== "";
  return true;
}

/** What's in the profile now, and anything that has to be fixed before saving. */
function Review({
  data,
  blocking,
  onFix,
  steps,
}: {
  data: ResumeData;
  blocking: { target: string; message: string; field: string | null; blocking: boolean }[];
  onFix: (step: number) => void;
  steps: Step[];
}) {
  const stepOf = (id: StepId) => steps.findIndex((s) => s.id === id);
  const rows: [string, number, StepId][] = [
    ["Education", data.education.length, "education"],
    ["Projects", data.projects.length, "projects"],
    ["Roles", data.experience.length, "experience"],
    ["Skills", data.skills.reduce((n, g) => n + g.items.length, 0), "skills"],
    ["Certifications", data.certifications.length, "extras"],
  ];
  const lines = [...data.experience, ...data.projects].reduce((n, e) => n + e.bullets.length, 0);
  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Your profile" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
        <div className="flex flex-col">
          <span className="text-xl font-semibold">{data.basics.name || "No name yet"}</span>
          <span className="text-muted">{[data.basics.email, data.basics.phone, data.basics.location].filter(Boolean).join(" · ")}</span>
        </div>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {rows.map(([label, n, id]) => (
            <div key={label} className="flex items-center justify-between rounded-lg bg-ground px-3 py-2.5">
              <div>
                <dt className="text-sm text-muted">{label}</dt>
                <dd className="text-2xl font-semibold">{n}</dd>
              </div>
              <button type="button" onClick={() => onFix(stepOf(id))} className="text-[13px] text-accent hover:underline">
                Edit
              </button>
            </div>
          ))}
        </dl>
        {lines === 0 && (
          <p className="rounded-lg bg-warn-soft px-3 py-2 text-[13px] text-warn-ink">
            No lines about what you did yet. A resume reads much better with two or three per
            project or role — go back and use “Help me write these lines”.
          </p>
        )}
      </section>
      {blocking.length > 0 && (
        <section aria-label="Before saving" className="flex flex-col gap-2 rounded-xl bg-warn-soft p-4 text-sm text-warn-ink">
          <h2 className="font-semibold">Before saving</h2>
          <ul className="flex flex-col gap-1">
            {blocking.map((c) => (
              <li key={`${c.target}-${c.message}`}>
                {notePlace(c, data)} — {c.message}
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm text-muted">
        Saving makes this your profile. Every resume you tailor is built from it, and you can
        edit it any time.
      </p>
    </div>
  );
}
