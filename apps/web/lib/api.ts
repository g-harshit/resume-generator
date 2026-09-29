import type { ResumeData } from "@rg/schema";
import { API_URL } from "@/lib/config";

export type User = { id: number; email: string; name: string };
type TokenResponse = { token: string; user: User };

export type ParseWarning = { path: string; message: string };

export type Upload = {
  id: number;
  filename: string;
  status: "pending" | "running" | "done" | "failed";
  error: string | null;
  warnings: ParseWarning[];
  /** True when the user's profile currently holds this upload. */
  applied: boolean;
  created_at: string;
};

export type Profile = {
  data: ResumeData;
  version: number;
  reviewed_at: string | null;
  source_document_id: number | null;
  updated_at: string;
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  // FormData sets its own multipart Content-Type (with the boundary); everything else is JSON.
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(res.status, body));
  return body as T;
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

  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Upload>("/uploads", { method: "POST", body });
  },
  getUpload: (id: number) => request<Upload>(`/uploads/${id}`),
  applyUpload: (id: number) => request<Upload>(`/uploads/${id}/apply`, { method: "POST" }),

  /** null until the first upload has been read. */
  getProfile: () => request<Profile | null>("/profile"),
};
