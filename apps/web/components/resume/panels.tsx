"use client";

import type { ResumeData } from "@rg/schema";
import Link from "next/link";
import { useState } from "react";
import { api, type ResumeFull, type TermMatch } from "@/lib/api";

const panel = "flex flex-col gap-3 rounded-xl border border-line bg-surface p-4";

export type SkillAdded = {
  skill: string;
  entryId: string | null;
  bullet: { id: string; text: string } | null;
  profile: ResumeData;
};

/** "I have this": where the person used a skill, in their own words. Nothing inferred. */
function IHaveThis({
  term,
  profile,
  onAdded,
}: {
  term: string;
  profile: ResumeData;
  onAdded: (added: SkillAdded) => void;
}) {
  const [open, setOpen] = useState(false);
  const [where, setWhere] = useState("");
  const [line, setLine] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const places = [
    ...profile.experience.map((e) => ({ id: e.id, label: [e.title, e.company].filter(Boolean).join(" at ") })),
    ...profile.projects.map((p) => ({ id: p.id, label: `Project: ${p.name}` })),
  ];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.addSkill(term, where || undefined, where ? line : undefined);
      onAdded({ skill: term, entryId: where || null, bullet: res.bullet, profile: res.profile.data });
      setOpen(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="h-8 rounded-lg border border-warn bg-surface px-2.5 text-[13px] text-warn-ink hover:bg-warn-soft"
      >
        I have this
      </button>
    );
  }
  return (
    <form method="post" onSubmit={submit} className="flex w-full flex-col gap-2 rounded-lg bg-surface p-3 text-ink">
      <label className="flex flex-col gap-1 text-[13px]">
        Where did you use {term}?
        <select
          value={where}
          onChange={(e) => setWhere(e.target.value)}
          className="h-10 rounded-lg border border-line-strong bg-surface px-2 text-sm"
        >
          <option value="">Just list it as a skill</option>
          {places.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {where && (
        <label className="flex flex-col gap-1 text-[13px]">
          In your own words, what did you do with it there?
          <textarea
            value={line}
            onChange={(e) => setLine(e.target.value)}
            rows={2}
            required
            minLength={10}
            className="rounded-lg border border-line-strong p-2 text-sm"
          />
        </label>
      )}
      {error && <p role="alert" className="text-[13px] text-warn-ink">{error}</p>}
      <p className="text-xs text-muted">Saved to your profile too, so every future resume knows it.</p>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || (!!where && line.trim().length < 10)}
          className="h-9 rounded-lg bg-accent px-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="h-9 rounded-lg px-3 text-sm text-muted hover:bg-sunken">
          Cancel
        </button>
      </div>
    </form>
  );
}

export function MatchPanel({
  match,
  profile,
  onSkillAdded,
  bridge,
}: {
  match: NonNullable<ResumeFull["match"]>;
  profile: ResumeData | null;
  onSkillAdded: (added: SkillAdded) => void;
  /** Name the job's skills in the lines that already prove them. `added`: the last run's result. */
  bridge?: { busy: boolean; disabled: boolean; run: () => void; added: string[] | null };
}) {
  // A posting with no skills listed (a company overview) is matched on the words it uses.
  const skillless = match.must_have.length + match.nice_to_have.length === 0;
  const missing = skillless
    ? match.keywords.filter((m) => !m.covered).map((m) => ({ ...m, kind: "keyword" }))
    : [
        ...match.must_have.filter((m) => !m.covered).map((m) => ({ ...m, kind: "must have" })),
        ...match.nice_to_have.filter((m) => !m.covered).map((m) => ({ ...m, kind: "nice to have" })),
      ];
  const covered: TermMatch[] = (skillless ? match.keywords : [...match.must_have, ...match.nice_to_have]).filter(
    (m) => m.covered,
  );
  const pct = match.total ? (100 * match.covered) / match.total : 0;

  const others = skillless ? [] : match.keywords;

  return (
    <section aria-label="Job match" className={panel}>
      {match.total === 0 ? (
        <div className="flex flex-col gap-1.5 rounded-lg bg-warn-soft p-3 text-warn-ink">
          <span className="text-sm font-semibold">Nothing to match in this job</span>
          <span className="text-[13px] leading-normal">
            What was pasted has no skills or keywords to match — it reads like a company overview rather than
            one role&apos;s requirements. For a keyword match,{" "}
            <Link href="/app/new" className="font-medium text-warn-ink underline">
              start a new resume
            </Link>{" "}
            from the role&apos;s job description — its responsibilities and requirements.
          </span>
        </div>
      ) : (
      <div className="flex items-center gap-3">
        <div
          aria-hidden="true"
          className="flex size-16 shrink-0 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(var(--color-accent) 0 ${pct}%, var(--color-sunken) ${pct}% 100%)` }}
        >
          <span className="flex size-12 items-center justify-center rounded-full bg-surface text-base font-semibold">
            {match.covered}/{match.total}
          </span>
        </div>
        <div className="flex flex-col">
          <h2 className="text-[15px] font-semibold">Job keywords covered</h2>
          <span className="text-[13px] leading-snug text-muted">
            {match.covered} of the job&apos;s {match.total} {skillless ? "keywords" : "skills"} appear in this
            resume&apos;s text.
            {skillless && " The posting lists no required skills, so these are the words it uses."}
          </span>
        </div>
      </div>
      )}

      {bridge && (
        <div className="flex flex-col gap-1.5 rounded-lg bg-sunken p-3">
          <span className="text-[13px] leading-snug">
            Some skills may already be shown by what a line describes: Django is Python, ECS is AWS. Name them in
            those lines, and only where your words prove it.
          </span>
          <button
            type="button"
            onClick={bridge.run}
            disabled={bridge.disabled}
            className="h-9 self-start rounded-lg border border-line bg-surface px-3 text-sm font-medium hover:bg-sunken disabled:opacity-60"
          >
            {bridge.busy ? "Reading your lines…" : "Name skills my lines prove"}
          </button>
          {bridge.added && (
            <span role="status" className="text-[13px] leading-snug text-muted">
              {bridge.added.length
                ? `Added ${bridge.added.join(", ")}. Each changed line is marked, with Use original.`
                : "None of your lines prove the missing skills. If you have them, add the fact to your profile (\"…Kafka queues at 20k events/s\") and re-tailor."}
            </span>
          )}
        </div>
      )}

      {missing.length > 0 && profile && (
        <div className="flex flex-col gap-2 rounded-lg bg-warn-soft p-3 text-warn-ink">
          <span className="text-sm font-semibold">Not in this resume yet</span>
          <ul className="flex flex-col gap-2">
            {missing.map((m) => (
              <li key={m.term} className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm">
                  <span className="font-semibold">{m.term}</span> · {m.kind}
                </span>
                <IHaveThis term={m.term} profile={profile} onAdded={onSkillAdded} />
              </li>
            ))}
          </ul>
          <span className="text-xs leading-normal">
            Add one to a line with &ldquo;+ Add job keywords&rdquo;, or to your profile with &ldquo;I have this&rdquo;.
            If you don&apos;t have one of these, leave it.
          </span>
        </div>
      )}

      {others.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">Other words the job uses</span>
          <ul className="flex flex-wrap gap-1.5">
            {others.map((m) => (
              <li
                key={m.term}
                title={m.covered ? "In this resume" : "Not in this resume"}
                className={`rounded-full px-2.5 py-0.5 text-[13px] ${
                  m.covered ? "bg-accent-soft text-accent-ink" : "border border-dashed border-line-strong text-muted"
                }`}
              >
                {m.covered ? "✓ " : ""}
                {m.term}
              </li>
            ))}
          </ul>
          <span className="text-xs text-muted">Add any that fit a line with &ldquo;+ Add job keywords&rdquo;.</span>
        </div>
      )}

      {covered.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">Covered</span>
          <ul className="flex flex-wrap gap-1.5">
            {covered.map((m) => (
              <li key={m.term} className="rounded-full bg-accent-soft px-2.5 py-0.5 text-[13px] text-accent-ink">
                {m.term}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** What an applicant tracking system needs, for this resume as it stands. */
export function AtsChecks({ data, pages }: { data: ResumeData; pages: number | null }) {
  const checks: { ok: boolean | null; text: string }[] = [
    { ok: true, text: "One column, real text, standard headings" },
    {
      ok: !!data.basics.email && !!data.basics.phone,
      text: data.basics.email && data.basics.phone ? "Email and phone in the body" : "Add an email and phone to your profile",
    },
    {
      ok: data.experience.every((e) => e.start && (e.end || e.current)),
      text: data.experience.every((e) => e.start && (e.end || e.current)) ? "Every role has dates" : "A role is missing dates (fix it in your profile)",
    },
    {
      ok: data.experience.every((e) => e.bullets.length > 0),
      text: data.experience.every((e) => e.bullets.length > 0) ? "Every role has at least one line" : "A role has no lines ticked",
    },
    {
      ok: pages === null ? null : pages <= 2,
      text: pages === null ? "Counting pages…" : pages === 1 ? "Fits on one page" : `${pages} pages${pages > 2 ? " — consider leaving some lines out" : ""}`,
    },
  ];
  return (
    <section aria-label="ATS checks" className={panel}>
      <h2 className="text-[15px] font-semibold">ATS checks</h2>
      <ul className="flex flex-col gap-1.5 text-[13px]">
        {checks.map((c) => (
          <li key={c.text} className={`flex items-start gap-2 ${c.ok === false ? "text-warn-ink" : ""}`}>
            <span aria-hidden="true" className="w-4 shrink-0 font-semibold">
              {c.ok === null ? "·" : c.ok ? "✓" : "!"}
            </span>
            <span>
              {c.text}
              <span className="sr-only">{c.ok === false ? " (needs attention)" : ""}</span>
            </span>
          </li>
        ))}
      </ul>
      {data.experience.some((e) => !e.start) && (
        <Link href="/app/profile" className="text-[13px]">
          Open your profile
        </Link>
      )}
    </section>
  );
}
