import type { ResumeData } from "@rg/schema";
import type { ParseWarning } from "@/lib/api";

const SECTION: Record<string, string> = {
  basics: "Contact details",
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  skills: "Skills",
  projects: "Projects",
  certifications: "Certifications",
};

/** "experience.1.end" → "Experience · Cartwheel": where a warning points, in words. */
export function warningPlace(w: ParseWarning, data: ResumeData | null): string {
  const [section, index] = w.path.split(".");
  const label = SECTION[section] ?? "Your resume";
  const i = Number(index);
  if (!data || !Number.isInteger(i)) return label;
  const entry =
    section === "experience"
      ? data.experience[i]?.company || data.experience[i]?.title
      : section === "education"
        ? data.education[i]?.institution
        : section === "projects"
          ? data.projects[i]?.name
          : section === "certifications"
            ? data.certifications[i]?.name
            : undefined;
  return entry ? `${label} · ${entry}` : label;
}
