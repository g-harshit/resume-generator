import { API_URL } from "@/lib/config";
import { getToken, setToken } from "@/lib/session";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export type User = { id: number; email: string; name: string };
export type TemplateInfo = { slug: string; name: string; description: string };
export type TermMatch = { term: string; covered: boolean };
export type Match = {
  must_have: TermMatch[];
  nice_to_have: TermMatch[];
  keywords: TermMatch[];
  covered: number;
  total: number;
};
export type Job = { id: number; title: string; company: string; location: string; match: Match | null };
export type Bullet = { id: string; text: string };
export type LineHistory = {
  status: string;
  original: string;
  keywords?: string[];
  skills?: { skill: string; evidence: string }[];
};
export type Resume = {
  id: number;
  title: string;
  template: string;
  version: number;
  content: {
    experience: { id: string; title: string; company: string; bullets: Bullet[] }[];
    projects: { id: string; name: string; bullets: Bullet[] }[];
  };
  /** `missing_in_lines`: job terms no line names; `missing_by_line`: per line, the
   * job terms that line doesn't name. */
  match: (Match & { missing_in_lines?: string[]; missing_by_line?: Record<string, string[]> }) | null;
  provenance: Record<string, LineHistory>;
};

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = await getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    // A rejected login means the extension is signed out (the website's rule too:
    // only a 401 signs anyone out).
    if (res.status === 401) await setToken(null);
    throw new ApiError(
      res.status,
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? String(detail[0].msg)
          : res.status >= 500
            ? "Something went wrong on our side. Try again in a moment."
            : "Request failed",
    );
  }
  return res;
}

const json = async <T,>(path: string, init?: RequestInit) => (await send(path, init)).json() as Promise<T>;

export const api = {
  /** Start the API waking up (it sleeps when idle on the free plan); nothing comes back. */
  wake: () => {
    fetch(`${API_URL}/health`, { cache: "no-store" }).catch(() => {});
  },
  me: () => json<User>("/auth/me"),
  templates: () => json<TemplateInfo[]>("/templates"),
  addJob: (text: string, url: string) =>
    json<Job>("/jobs", { method: "POST", body: JSON.stringify({ text, url, source: "extension" }) }),
  tailor: (jobId: number, template: string) =>
    json<Resume>("/resumes", { method: "POST", body: JSON.stringify({ job_id: jobId, template }) }),
  /** Rewrite one line to have exactly these keywords (empty puts it back). */
  lineKeywords: (resumeId: number, version: number, lineId: string, keywords: string[]) =>
    json<Resume>(`/resumes/${resumeId}/lines/${encodeURIComponent(lineId)}/keywords`, {
      method: "POST",
      body: JSON.stringify({ version, keywords }),
    }),
  pdf: async (resumeId: number) => {
    const res = await send(`/resumes/${resumeId}/pdf`);
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1];
    return { blob: await res.blob(), filename: name ?? "Resume.pdf" };
  },
};
