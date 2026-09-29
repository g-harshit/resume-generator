/* Generated from backend/app/schemas/resume.py by pnpm gen:schema. Do not edit. */

export interface ResumeData {
  basics: Basics;
  /**
   * @maxItems 30
   */
  certifications: Certification[];
  /**
   * @maxItems 15
   */
  education: Education[];
  /**
   * @maxItems 30
   */
  experience: Experience[];
  /**
   * @maxItems 20
   */
  projects: Project[];
  /**
   * @maxItems 20
   */
  skills: SkillGroup[];
  summary: string;
}
export interface Basics {
  email: string;
  headline: string;
  /**
   * @maxItems 10
   */
  links: Link[];
  location: string;
  name: string;
  phone: string;
}
export interface Link {
  id: string;
  label: string;
  url: string;
}
export interface Certification {
  date: string | null;
  id: string;
  issuer: string;
  name: string;
  url: string;
}
export interface Education {
  degree: string;
  details: string;
  end: string | null;
  field: string;
  id: string;
  institution: string;
  location: string;
  start: string | null;
}
export interface Experience {
  /**
   * @maxItems 30
   */
  bullets: Bullet[];
  company: string;
  current: boolean;
  end: string | null;
  id: string;
  location: string;
  start: string | null;
  title: string;
}
export interface Bullet {
  id: string;
  text: string;
}
export interface Project {
  /**
   * @maxItems 20
   */
  bullets: Bullet[];
  end: string | null;
  id: string;
  name: string;
  start: string | null;
  url: string;
}
export interface SkillGroup {
  group: string;
  id: string;
  /**
   * @maxItems 60
   */
  items: string[];
}
