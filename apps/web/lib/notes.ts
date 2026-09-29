import type { ResumeData } from "@rg/schema";
import type { Note } from "@/lib/api";

/** Where a note or check points, in words: "Experience · Cartwheel". */
export function notePlace(note: Note, data: ResumeData): string {
  if (note.target === "basics") return "Contact details";
  if (note.target === "summary") return "Summary";
  for (const e of data.experience) {
    if (e.id === note.target || e.bullets.some((b) => b.id === note.target)) {
      return `Experience · ${e.company || e.title || "untitled role"}`;
    }
  }
  for (const e of data.education) {
    if (e.id === note.target) return `Education · ${e.institution || e.degree || "untitled"}`;
  }
  for (const p of data.projects) {
    if (p.id === note.target || p.bullets.some((b) => b.id === note.target)) {
      return `Projects · ${p.name || "untitled project"}`;
    }
  }
  for (const c of data.certifications) {
    if (c.id === note.target) return `Certifications · ${c.name}`;
  }
  return "Your resume";
}

const DATE_FIELDS = new Set(["start", "end", "date"]);

/** The current value of `field` on the entry `target` points at. */
function valueOf(data: ResumeData, target: string, field: string): unknown {
  if (target === "basics") return (data.basics as unknown as Record<string, unknown>)[field];
  const entry = [...data.experience, ...data.education, ...data.projects, ...data.certifications].find(
    (e) => e.id === target,
  ) as Record<string, unknown> | undefined;
  if (entry && field === "end" && entry.current) return true; // a current role needs no end
  return entry?.[field];
}

/** A parse note about a date is settled once that date has a value. Other parse
 *  notes (a line we couldn't find in the file) stand until the profile is confirmed. */
export function noteStillApplies(note: Note, data: ResumeData): boolean {
  if (!note.field || !DATE_FIELDS.has(note.field)) return true;
  return !valueOf(data, note.target, note.field);
}

/** Checks come back with each save, so for a moment they describe the last saved
 *  data. Every field check is "this is missing": once the field has a value here,
 *  it's already answered — don't flash "add an end date" at someone who just did. */
function checkStillApplies(check: Note, data: ResumeData): boolean {
  return !check.field || !valueOf(data, check.target, check.field);
}

/**
 * What to show the user, from the live checks and the parse notes:
 * - `general`: notes not about any entry (the model couldn't place something)
 * - `placed`: notes and checks about an entry that still exists. Where a parse note
 *   and a check are about the same field, only the note is kept: "couldn't read
 *   '21'" says more than "add an end date".
 */
export function toShow(data: ResumeData, checks: Note[], notes: Note[]) {
  const live = notes.filter((n) => noteStillApplies(n, data));
  const ids = new Set([
    "basics",
    "summary",
    ...data.experience.flatMap((e) => [e.id, ...e.bullets.map((b) => b.id)]),
    ...data.education.map((e) => e.id),
    ...data.projects.flatMap((p) => [p.id, ...p.bullets.map((b) => b.id)]),
    ...data.certifications.map((c) => c.id),
  ]);
  const placedNotes = live.filter((n) => ids.has(n.target));
  const covered = new Set(placedNotes.map((n) => `${n.target}.${n.field}`));
  return {
    general: live.filter((n) => n.target === ""),
    placed: [
      ...placedNotes,
      ...checks.filter((c) => !covered.has(`${c.target}.${c.field}`) && checkStillApplies(c, data)),
    ],
  };
}
