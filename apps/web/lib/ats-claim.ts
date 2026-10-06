/**
 * The free ATS checker hands its check over at sign-up: the token is remembered here
 * (this browser only) until the person is signed in, then claimed. Storage can be
 * blocked (private windows); then the hand-over simply doesn't happen.
 */

const TOKEN = "ats-check-token";
const JOB = "ats-check-job";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Not available: nothing to remember it in.
  }
}

/** The check to carry into the account, kept with when it was made (they last 24 h). */
export function rememberAtsCheck(token: string) {
  write(TOKEN, JSON.stringify({ token, at: Date.now() }));
}

export function pendingAtsCheck(): string | null {
  const raw = read(TOKEN);
  if (!raw) return null;
  try {
    const { token, at } = JSON.parse(raw) as { token: string; at: number };
    if (Date.now() - at < 24 * 3600 * 1000) return token;
  } catch {
    // Unreadable: drop it.
  }
  write(TOKEN, null);
  return null;
}

export function forgetAtsCheck() {
  write(TOKEN, null);
}

/** The job pasted into the checker, now one of the person's jobs: offered on Home. */
export function rememberCheckedJob(jobId: number | null) {
  write(JOB, jobId === null ? null : String(jobId));
}

export function checkedJob(): number | null {
  const raw = read(JOB);
  return raw && /^\d+$/.test(raw) ? Number(raw) : null;
}
