import type { ResumeData } from "@rg/schema";
import { API_URL } from "@/lib/config";

export type User = {
  id: number;
  email: string;
  name: string;
  /** Shows the admin panel's link; the admin endpoints check for themselves. */
  is_admin?: boolean;
};

// --- admin panel (only admins get anything but 404) ---

export type AdminStats = {
  users: number;
  users_today: number;
  users_7d: number;
  users_30d: number;
  active_7d: number;
  google_users: number;
  password_users: number;
  disabled_users: number;
  profiles: number;
  profiles_confirmed: number;
  resumes: number;
  resumes_7d: number;
  cover_letters: number;
  jobs: number;
  jobs_from_extension: number;
  uploads: number;
  uploads_failed: number;
  signups_by_day: { day: string; count: number }[];
};

export type AdminUserRow = {
  id: number;
  email: string;
  name: string;
  sign_in: ("google" | "password")[];
  email_verified: boolean;
  created_at: string;
  last_seen_at: string | null;
  disabled: boolean;
  profile: "none" | "draft" | "confirmed";
  resumes: number;
  jobs: number;
  uploads: number;
};

export type AdminAction = {
  admin_email: string;
  action: string;
  target_email: string;
  detail: Record<string, unknown> | null;
  created_at: string;
};

export type AdminUserDetail = {
  user: AdminUserRow;
  is_admin: boolean;
  profile_updated_at: string | null;
  profile_sections: Record<string, number>;
  resumes: { id: number; title: string; template: string; has_cover_letter: boolean; created_at: string; updated_at: string }[];
  jobs: { id: number; title: string; company: string; source: string; created_at: string }[];
  uploads: { id: number; filename: string; size_bytes: number; status: string; error: string | null; created_at: string }[];
  actions: AdminAction[];
};

export type FailedUpload = {
  id: number;
  user_id: number;
  user_email: string;
  filename: string;
  error: string | null;
  created_at: string;
};
type TokenResponse = { token: string; user: User };

/** Something noticed while reading the file, pointing at an entry by id. `target`
 *  "" is a general note; "basics" / "summary" are those sections. */
export type Note = { target: string; field: string | null; message: string };
/** Something missing in the profile as it is now. Recomputed on every save. */
export type Check = Note & { blocking: boolean };

export type Upload = {
  id: number;
  filename: string;
  status: "pending" | "running" | "done" | "failed";
  error: string | null;
  notes: Note[];
  /** True when the user's profile currently holds this upload. */
  applied: boolean;
  created_at: string;
};

export type Evidence = { section: string; label: string; id: string | null };
export type TermMatch = { term: string; covered: boolean; where: Evidence[] };

export type Job = {
  id: number;
  source: "paste" | "extension";
  url: string;
  title: string;
  company: string;
  location: string;
  seniority: string;
  created_at: string;
  /** Against the profile as it is now; null before the user has a profile. */
  match: {
    must_have: TermMatch[];
    nice_to_have: TermMatch[];
    keywords: TermMatch[];
    covered: number;
    total: number;
  } | null;
};

export type TemplateInfo = { slug: string; name: string; description: string };
/** A rendered resume: its HTML, its PDF page count, and each PDF page as an image. */
export type PageLink = { x: number; y: number; w: number; h: number; url: string };
export type Preview = {
  html: string;
  pages: number;
  images: string[];
  /** Per page: where its links are, as fractions of the page, to click on the image. */
  links: PageLink[][];
};

/** What tailoring did to one line (by bullet id, or "summary"). */
export type LineHistory = {
  original: string;
  status: "kept" | "reworded" | "reverted" | "condensed" | "written" | "bridged" | "keywords";
  /** For a "condensed" line: the ids of the person's lines it was merged from. */
  sources?: string[];
  /** For a "bridged" line: the job's skills it now names, each with the person's words that prove it. */
  skills?: { skill: string; evidence: string }[];
  /** For a "keywords" line: the keywords the person chose, and the line before them. */
  keywords?: string[];
  base?: string;
  /** What the model wrote, when it wasn't allowed to stand. */
  attempted: string | null;
  reason: string | null;
};

export type ResumeSummary = {
  id: number;
  title: string;
  template: string;
  version: number;
  job_id: number | null;
  company: string;
  job_title: string;
  source: "paste" | "extension" | null;
  created_at: string;
  updated_at: string;
  covered: number | null;
  total: number | null;
};

export type CoverLetter = {
  text: string;
  /** Sentences left out because they claimed something the resume doesn't say. */
  removed: { text: string; reason: string }[];
  generated_at: string;
};

export type Section = "summary" | "experience" | "education" | "skills" | "projects" | "certifications";

/** Margins, hidden sections and the page goal: how the resume sits on the page. */
export type SummaryLength = "shorter" | "same" | "longer";

export type Layout = {
  /** "normal" is the template's own; narrow (10 mm) and custom are equal on all sides. */
  margins: "normal" | "narrow" | "custom";
  /** For "custom": millimetres on every side, 5–30. */
  margin_mm: number | null;
  /** Header items left off this resume: "headline", "location", "email", "phone", or a link id. */
  hidden_header: string[];
  hidden: Section[];
  pages: number | null;
  /** The order sections appear in; null for the usual one (SECTIONS). */
  order: Section[] | null;
};

/** The usual section order (backend/app/schemas/layout.py). */
export const SECTIONS: Section[] = ["summary", "experience", "education", "skills", "projects", "certifications"];

/** Lines written from the person's notes, and the ones dropped for saying more. */
export type DraftedLines = { lines: string[]; left_out: { text: string; reason: string }[] };

export type ResumeFull = ResumeSummary & {
  content: ResumeData;
  provenance: Record<string, LineHistory>;
  /** `missing_in_lines`: the job's terms no line names, to offer for a line. */
  match: (NonNullable<Job["match"]> & { missing_in_lines?: string[] }) | null;
  cover_letter: CoverLetter | null;
  layout: Layout;
};

/** What a fit or a shortening did, for telling the person. */
export type FitResult = {
  resume: ResumeFull;
  pages_before: number;
  pages_after: number;
  steps: string[];
  notes: string[];
};

export type Profile = {
  data: ResumeData;
  version: number;
  reviewed_at: string | null;
  source_document_id: number | null;
  /** "application/pdf" can be shown as-is; a Word file is shown as the text we read. */
  source_mime: string | null;
  updated_at: string;
  checks: Check[];
  /** Only until the profile is confirmed. */
  notes: Note[];
};

/** A response the API sent back with an error status. `status` 0 never happens here:
 *  a network failure throws the browser's own TypeError instead. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// --- token storage ---------------------------------------------------------
// localStorage can throw (private windows, blocked storage), so every access is guarded.

const TOKEN_KEY = "rg:token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Signed in for this tab only; nothing else to do.
  }
}

// --- requests --------------------------------------------------------------

function messageFrom(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ loc, msg }, ...]
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  return status >= 500 ? "Something went wrong on our side. Try again in a moment." : "Request failed";
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  // FormData sets its own multipart Content-Type (with the boundary); everything else is JSON.
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, messageFrom(res.status, body));
  }
  return res;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await send(path, init)).json() as Promise<T>;
}

/** A PDF and the file name the API chose for it. */
async function pdfDownload(path: string) {
  const res = await send(path);
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1];
  return { blob: await res.blob(), filename: name ?? "Resume.pdf" };
}

/** Hand a downloaded file to the browser as a download. */
export function saveFile({ blob, filename }: { blob: Blob; filename: string }) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  register: (email: string, password: string, name: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  admin: {
    stats: () => request<AdminStats>("/admin/stats"),
    users: (q: string, offset = 0, limit = 50) =>
      request<{ total: number; users: AdminUserRow[] }>(
        `/admin/users?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`,
      ),
    exportUsers: async (q: string) => ({
      blob: await (await send(`/admin/users.csv?q=${encodeURIComponent(q)}`)).blob(),
      filename: "users.csv",
    }),
    user: (id: number) => request<AdminUserDetail>(`/admin/users/${id}`),
    signOut: (id: number) => request<AdminUserDetail>(`/admin/users/${id}/sign-out`, { method: "POST" }),
    disable: (id: number) => request<AdminUserDetail>(`/admin/users/${id}/disable`, { method: "POST" }),
    enable: (id: number) => request<AdminUserDetail>(`/admin/users/${id}/enable`, { method: "POST" }),
    remove: async (id: number, confirmEmail: string) => {
      await send(`/admin/users/${id}`, { method: "DELETE", body: JSON.stringify({ confirm_email: confirmEmail }) });
    },
    failedUploads: () => request<FailedUpload[]>("/admin/uploads/failed"),
    log: () => request<AdminAction[]>("/admin/log"),
  },
  /** Start the API waking up, without waiting for it (nothing comes back). */
  wake: () => {
    fetch(`${API_URL}/health`, { cache: "no-store" }).catch(() => {});
  },
  /** Sign in (or up) with the ID token Google gave the browser. */
  googleSignIn: (credential: string) =>
    request<TokenResponse>("/auth/google", { method: "POST", body: JSON.stringify({ credential }) }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),
  requestPasswordReset: (email: string) =>
    request<{ detail: string }>("/auth/password-reset", { method: "POST", body: JSON.stringify({ email }) }),
  confirmPasswordReset: (token: string, password: string) =>
    request<TokenResponse>("/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Upload>("/uploads", { method: "POST", body });
  },
  getUpload: (id: number) => request<Upload>(`/uploads/${id}`),
  /** The original file, as a blob (it needs the auth header, so no plain URL). */
  getUploadFile: async (id: number) => (await send(`/uploads/${id}/file`)).blob(),
  getUploadText: (id: number) => request<{ text: string }>(`/uploads/${id}/text`),
  applyUpload: (id: number) => request<Upload>(`/uploads/${id}/apply`, { method: "POST" }),

  /** null until the first upload has been read. */
  getProfile: () => request<Profile | null>("/profile"),
  /** `version` is the one last loaded (0 to create); a stale one gets a 409. */
  saveProfile: (version: number, data: ResumeData) =>
    request<Profile>("/profile", { method: "PUT", body: JSON.stringify({ version, data }) }),
  /** Resume lines from the person's own notes about a project or job (not saved). */
  writeProfileLines: (kind: "project" | "experience", context: string, notes: string) =>
    request<DraftedLines>("/profile/lines", { method: "POST", body: JSON.stringify({ kind, context, notes }) }),
  /** A summary from the saved profile's facts (not saved). */
  writeProfileSummary: (length: SummaryLength) =>
    request<{ text: string }>("/profile/summary", { method: "POST", body: JSON.stringify({ length }) }),
  /** Reads the posting (a few seconds); the same text twice returns the first reading. */
  addJob: (text: string) =>
    request<Job>("/jobs", { method: "POST", body: JSON.stringify({ text, source: "paste" }) }),
  getJob: (id: number) => request<Job>(`/jobs/${id}`),

  /** Tailor the profile to a job: waits for the model, usually 20–40 seconds. */
  createResume: (jobId: number, template: string) =>
    request<ResumeFull>("/resumes", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, template }),
    }),
  listResumes: () => request<ResumeSummary[]>("/resumes"),
  getResume: (id: number) => request<ResumeFull>(`/resumes/${id}`),
  previewResume: (id: number, template: string) =>
    request<Preview>(`/resumes/${id}/preview?template=${encodeURIComponent(template)}`),
  /** The person's own edits; `version` is the one last loaded (a stale one gets 409). */
  saveResume: (id: number, version: number, content: ResumeData, template: string, layout: Layout) =>
    request<ResumeFull>(`/resumes/${id}`, {
      method: "PUT",
      body: JSON.stringify({ version, content, template, layout }),
    }),
  /** AI edits. Each takes the version being edited; an edit in between gets a 409. */
  /** Write the summary from this resume's facts: shorter, about as long, or longer than now. */
  writeSummary: (id: number, version: number, length: SummaryLength) =>
    request<ResumeFull>(`/resumes/${id}/summary`, { method: "POST", body: JSON.stringify({ version, length }) }),
  lineKeywords: (id: number, version: number, lineId: string, keywords: string[], again = false) =>
    request<ResumeFull>(`/resumes/${id}/lines/${encodeURIComponent(lineId)}/keywords`, {
      method: "POST",
      body: JSON.stringify({ version, keywords, again }),
    }),
  bridgeSkills: (id: number, version: number) =>
    request<{ resume: ResumeFull; added: string[] }>(`/resumes/${id}/bridge`, {
      method: "POST",
      body: JSON.stringify({ version }),
    }),
  condenseEntry: (id: number, version: number, entryId: string, bullets: number) =>
    request<FitResult>(`/resumes/${id}/condense`, {
      method: "POST",
      body: JSON.stringify({ version, entry_id: entryId, bullets }),
    }),
  fitToPages: (id: number, version: number, pages: number) =>
    request<FitResult>(`/resumes/${id}/fit`, { method: "POST", body: JSON.stringify({ version, pages }) }),
  /** Tailor again from the profile as it is now; replaces this resume's edits. */
  retailorResume: (id: number) => request<ResumeFull>(`/resumes/${id}/retailor`, { method: "POST" }),
  /** Write (or rewrite) the cover letter from this resume: waits for the model, ~15–30 s. */
  writeCoverLetter: (id: number) => request<ResumeFull>(`/resumes/${id}/cover-letter`, { method: "POST" }),
  saveCoverLetter: (id: number, text: string) =>
    request<ResumeFull>(`/resumes/${id}/cover-letter`, { method: "PUT", body: JSON.stringify({ text }) }),
  coverLetterPdf: (id: number, template: string) =>
    pdfDownload(`/resumes/${id}/cover-letter/pdf?template=${encodeURIComponent(template)}`),
  duplicateResume: (id: number) => request<ResumeFull>(`/resumes/${id}/duplicate`, { method: "POST" }),
  deleteResume: (id: number) => send(`/resumes/${id}`, { method: "DELETE" }).then(() => undefined),
  resumePdf: (id: number, template: string) =>
    pdfDownload(`/resumes/${id}/pdf?template=${encodeURIComponent(template)}`),

  listTemplates: () => request<TemplateInfo[]>("/templates"),
  /** The user's profile in this template; `pages` comes from the real PDF layout. */
  previewTemplate: (slug: string) => request<Preview>(`/templates/${slug}/preview`),
  /** The user's profile in this template as a PDF, with the file name the API chose. */
  templatePdf: (slug: string) => pdfDownload(`/templates/${slug}/pdf`),

  /** "I have this": a skill, and optionally where it was used with the person's own line. */
  addSkill: (skill: string, entryId?: string, line?: string) =>
    request<{ profile: Profile; bullet: { id: string; text: string } | null }>("/profile/skills", {
      method: "POST",
      body: JSON.stringify({ skill, entry_id: entryId ?? null, line: line ?? null }),
    }),

  confirmProfile: (version: number) =>
    request<Profile>("/profile/confirm", { method: "POST", body: JSON.stringify({ version }) }),
};
