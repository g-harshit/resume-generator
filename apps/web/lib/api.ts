import type { ResumeData } from "@rg/schema";
import { API_URL } from "@/lib/config";

export type User = { id: number; email: string; name: string };
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
export type Preview = { html: string; pages: number };

/** What tailoring did to one line (by bullet id, or "summary"). */
export type LineHistory = {
  original: string;
  status: "kept" | "reworded" | "reverted";
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

export type ResumeFull = ResumeSummary & {
  content: ResumeData;
  provenance: Record<string, LineHistory>;
  match: Job["match"];
  cover_letter: CoverLetter | null;
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
  saveResume: (id: number, version: number, content: ResumeData, template: string) =>
    request<ResumeFull>(`/resumes/${id}`, {
      method: "PUT",
      body: JSON.stringify({ version, content, template }),
    }),
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
