import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Resume, type TemplateInfo, type User } from "@/lib/api";
import { APP_NAME, WEB_URL } from "@/lib/config";
import { type ExtractedJob, extractJob } from "@/lib/extract";
import { getToken, onTokenChange, setToken } from "@/lib/session";

const MIN_CHARS = 200; // the API's minimum for a job description

type Reading =
  | { kind: "idle" }
  | { kind: "reading" }
  // Chrome hasn't given the extension this page: the icon wasn't clicked on it, and the
  // site isn't allowed yet. `origin` when we know which site it is.
  | { kind: "needs-permission"; origin: string | null }
  | { kind: "found"; job: ExtractedJob }
  | { kind: "not-found"; message: string };

function errorMessage(err: unknown) {
  return err instanceof TypeError ? "Can't reach the server. Is it running?" : (err as Error).message;
}

function openTab(path: string) {
  void browser.tabs.create({ url: `${WEB_URL}${path}` });
}

const primary =
  "flex h-12 w-full items-center justify-center rounded-[10px] bg-accent text-[15px] font-medium text-white hover:bg-accent-hover disabled:opacity-50";
const secondary =
  "flex h-11 w-full items-center justify-center rounded-[10px] border border-line-strong bg-surface text-[15px] text-ink hover:bg-sunken";

// --- reading the page ------------------------------------------------------------------

// Where people find jobs. One "Allow on job sites" click covers them all, so the panel
// can read postings however it was opened and follow the person from job to job.
const JOB_SITES = [
  "https://*.linkedin.com/*",
  "https://*.naukri.com/*",
  "https://*.indeed.com/*",
  "https://*.foundit.in/*",
  "https://*.instahyre.com/*",
  "https://*.wellfound.com/*",
  "https://*.glassdoor.com/*",
  "https://*.glassdoor.co.in/*",
  "https://*.greenhouse.io/*",
  "https://*.lever.co/*",
  "https://*.ashbyhq.com/*",
  "https://*.myworkdayjobs.com/*",
  "https://*.smartrecruiters.com/*",
];

async function activeTab() {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  return tab;
}

/** Run the reader in the active tab. Throws with `origin` (null if Chrome won't even
 *  say which site) when the extension may not read this page yet: only the tab the
 *  toolbar icon was clicked in, and sites the person allowed, are readable. */
async function readTab(mode: "auto" | "selection"): Promise<ExtractedJob | null> {
  const tab = await activeTab();
  if (!tab?.id) throw new Error("Open a job posting in this tab, then read it.");
  // No URL means no access to this tab (Chrome hides it until the page is granted).
  if (!tab.url) throw Object.assign(new Error("permission"), { origin: null });
  if (!tab.url.startsWith("http")) throw new Error("Open a job posting in this tab, then read it.");
  try {
    const [result] = await browser.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractJob,
      args: [mode],
    });
    return (result?.result as ExtractedJob | null) ?? null;
  } catch {
    throw Object.assign(new Error("permission"), { origin: `${new URL(tab.url).origin}/*` });
  }
}

/** Does a match pattern like "https://*.linkedin.com/*" cover "https://www.linkedin.com/*"? */
function matches(pattern: string, origin: string): boolean {
  const host = (p: string) => p.replace(/^https?:\/\//, "").replace(/\/\*$/, "");
  const want = host(pattern);
  const have = host(origin);
  return want.startsWith("*.") ? have === want.slice(2) || have.endsWith(want.slice(1)) : have === want;
}

// --- screens ---------------------------------------------------------------------------

function SignedOut() {
  return (
    <div className="flex flex-col gap-5 px-5 pt-14">
      <h1 className="font-display text-[34px] leading-tight">A resume for this job, in one click.</h1>
      <p className="text-[15px] leading-relaxed text-muted">
        Sign in to use the profile you built on the website. We read the job from the page you&apos;re
        on and tailor your resume to it — using only what&apos;s in your profile.
      </p>
      <button type="button" onClick={() => openTab("/extension/connect")} className={primary}>
        Sign in to {APP_NAME}
      </button>
      <ol className="flex flex-col gap-3.5 text-sm leading-normal">
        {[
          "Open any job posting — LinkedIn, Naukri, Indeed, or a company's careers page.",
          `Click the ${APP_NAME} icon. We find the job description for you.`,
          "Pick a template and download an ATS-ready PDF.",
        ].map((step, i) => (
          <li key={step} className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[13px] font-semibold text-accent-ink">
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <p className="text-[13px] text-muted">
        New here? Signing in opens the website, where you can upload your current resume first.
      </p>
    </div>
  );
}

function Header({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const initials = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
  return (
    <header className="flex items-center justify-between">
      <span className="font-display text-2xl">{APP_NAME}</span>
      <div className="flex items-center gap-2">
        <button type="button" onClick={onSignOut} className="h-9 rounded-lg px-2 text-[13px] text-muted hover:bg-sunken">
          Sign out
        </button>
        <span
          title={user.email}
          className="flex size-8 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white"
        >
          {initials}
        </span>
      </div>
    </header>
  );
}

function Done({ resume, onBack }: { resume: Resume; onBack: () => void }) {
  const [downloading, setDownloading] = useState(false);
  const missing = resume.match
    ? [...resume.match.must_have, ...resume.match.nice_to_have].filter((m) => !m.covered).map((m) => m.term)
    : [];

  async function download() {
    setDownloading(true);
    try {
      const { blob, filename } = await api.pdf(resume.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <button type="button" onClick={onBack} className="self-start text-sm text-muted hover:text-ink">
        ← Another job
      </button>
      <div className="flex flex-col gap-0.5">
        <h1 className="font-display text-[30px] leading-tight">Your resume is ready</h1>
        <span className="text-sm text-muted">{resume.title}</span>
      </div>
      {resume.match && (
        <div className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3">
          <span className="text-2xl font-semibold">
            {resume.match.covered}/{resume.match.total}
          </span>
          <span className="text-[13px] leading-snug text-muted">of the job&apos;s skills appear in this resume</span>
        </div>
      )}
      {missing.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-xl bg-warn-soft px-4 py-3 text-warn-ink">
          <span className="text-sm font-semibold">
            {missing.length === 1 ? "1 skill" : `${missing.length} skills`} not in your profile
          </span>
          <span className="text-[13px] leading-normal">
            {missing.join(", ")}. If you have them, open the editor and use &ldquo;I have this&rdquo;.
          </span>
        </div>
      )}
      <div className="flex flex-col gap-2 pt-2">
        <button type="button" onClick={download} disabled={downloading} className={primary}>
          {downloading ? "Making PDF…" : "Download PDF"}
        </button>
        <button type="button" onClick={() => openTab(`/app/resume?id=${resume.id}`)} className={secondary}>
          Open in editor
        </button>
      </div>
    </div>
  );
}

function Tailor({ user }: { user: User }) {
  const [reading, setReading] = useState<Reading>({ kind: "idle" });
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [template, setTemplate] = useState("classic");
  const [working, setWorking] = useState<null | "job" | "tailor">(null);
  const [error, setError] = useState<{ message: string; needsProfile: boolean } | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);

  // Each read gets a number; a slower, older read (or its retry) never overwrites a newer
  // one — the person may have moved to another tab or job meanwhile.
  const generation = useRef(0);

  const read = useCallback(async (mode: "auto" | "selection" = "auto", attempt = 0) => {
    const mine = attempt === 0 ? ++generation.current : generation.current;
    setReading({ kind: "reading" });
    setError(null);
    try {
      const job = await readTab(mode);
      if (generation.current !== mine) return;
      if (job && job.text.length >= MIN_CHARS) setReading({ kind: "found", job });
      else if (mode === "auto" && attempt < 2)
        // Job sites often fill in the description a moment after the page appears.
        setTimeout(() => {
          if (generation.current === mine) void read("auto", attempt + 1);
        }, attempt === 0 ? 1500 : 3000);
      else
        setReading({
          kind: "not-found",
          message:
            mode === "selection"
              ? "Select the whole job description on the page first (at least a few paragraphs)."
              : "We couldn't find a job description on this page. Select it on the page and use your selection.",
        });
    } catch (err) {
      if (generation.current !== mine) return;
      const origin = (err as { origin?: string | null }).origin;
      if (origin !== undefined) setReading({ kind: "needs-permission", origin });
      else setReading({ kind: "not-found", message: (err as Error).message });
    }
  }, []);

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => {});
    // Read the page the icon was clicked on; follow the person to other tabs.
    // Deferred a tick so the effect body itself doesn't set state.
    const t = setTimeout(() => void read(), 0);
    const onActivated = () => void read();
    // A finished load, or a new address in the same tab (LinkedIn changes job without
    // reloading the page).
    const onUpdated = (_id: number, info: { status?: string; url?: string }, tab: { active?: boolean }) => {
      if (tab.active && (info.status === "complete" || info.url)) void read();
    };
    browser.tabs.onActivated.addListener(onActivated);
    browser.tabs.onUpdated.addListener(onUpdated);
    return () => {
      clearTimeout(t);
      browser.tabs.onActivated.removeListener(onActivated);
      browser.tabs.onUpdated.removeListener(onUpdated);
    };
  }, [read]);

  async function allow(origin: string | null) {
    // Asking needs this click (a user gesture), which is why it's a button. The job
    // sites go together, plus this page's own site when it's another one.
    const origins = origin && !JOB_SITES.some((p) => matches(p, origin)) ? [...JOB_SITES, origin] : JOB_SITES;
    const granted = await browser.permissions.request({ origins });
    if (granted) await read();
  }

  async function tailor(job: ExtractedJob) {
    setError(null);
    try {
      setWorking("job");
      const saved = await api.addJob(job.text, job.url);
      setWorking("tailor");
      setResume(await api.tailor(saved.id, template));
    } catch (err) {
      setError({
        message: errorMessage(err),
        needsProfile: err instanceof ApiError && err.status === 409,
      });
    } finally {
      setWorking(null);
    }
  }

  if (resume) return <Done resume={resume} onBack={() => setResume(null)} />;

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="This page" className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface p-4">
        {reading.kind === "reading" || reading.kind === "idle" ? (
          <p role="status" className="text-sm text-muted">Reading this page…</p>
        ) : reading.kind === "needs-permission" ? (
          <>
            <p className="text-sm leading-normal">
              To read this page, {APP_NAME} needs your permission
              {reading.origin ? (
                <>
                  {" "}for <strong>{new URL(reading.origin.replace("/*", "")).hostname}</strong>
                </>
              ) : null}
              . One click allows it on LinkedIn, Naukri, Indeed and other job sites — it only
              reads a page when you use it.
            </p>
            <button type="button" onClick={() => allow(reading.origin)} className={primary}>
              Allow on job sites
            </button>
            <p className="text-xs leading-normal text-muted">
              Or click the {APP_NAME} icon in Chrome&apos;s toolbar while on the job page.
            </p>
          </>
        ) : reading.kind === "not-found" ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm leading-normal text-muted">{reading.message}</p>
            <button type="button" onClick={() => void read()} className="self-start text-[13px] text-accent hover:underline">
              Read this page again
            </button>
          </div>
        ) : (
          <>
            <span className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-accent-ink uppercase">
              ✓ Job found on this page
            </span>
            <div className="flex flex-col">
              <span className="text-[17px] font-semibold">{reading.job.title || "Untitled role"}</span>
              {reading.job.company && <span className="text-sm text-muted">{reading.job.company}</span>}
            </div>
            <p className="line-clamp-4 rounded-lg bg-ground p-2.5 text-[13px] leading-normal whitespace-pre-line text-muted">
              {reading.job.text.slice(0, 400)}
            </p>
          </>
        )}
        {reading.kind !== "reading" && reading.kind !== "needs-permission" && (
          <div className="flex items-center justify-between gap-2 border-t border-sunken pt-2.5 text-[13px] text-muted">
            <span>Not the right text?</span>
            <button
              type="button"
              onClick={() => read("selection")}
              className="h-8 rounded-lg border border-line-strong bg-surface px-2.5 text-ink hover:bg-sunken"
            >
              Use my selection
            </button>
          </div>
        )}
      </section>

      {templates.length > 0 && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-semibold">Template</legend>
          <div className="grid grid-cols-2 gap-2">
            {templates.map((t) => (
              <label
                key={t.slug}
                className={`flex h-11 cursor-pointer items-center gap-2 rounded-[10px] bg-surface px-3 text-sm ${
                  template === t.slug ? "border-2 border-accent font-semibold" : "border border-line"
                }`}
              >
                <input
                  type="radio"
                  name="template"
                  value={t.slug}
                  checked={template === t.slug}
                  onChange={() => setTemplate(t.slug)}
                  className="accent-accent"
                />
                {t.name}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-[13px] leading-normal text-warn-ink">
          {error.needsProfile ? (
            <>
              First review and confirm your profile —{" "}
              <button type="button" onClick={() => openTab("/app/profile")} className="underline">
                open it on the website
              </button>
              .
            </>
          ) : (
            error.message
          )}
        </p>
      )}

      <div className="flex flex-col gap-1.5">
        <button
          type="button"
          disabled={reading.kind !== "found" || working !== null}
          onClick={() => reading.kind === "found" && tailor(reading.job)}
          className={primary}
        >
          {working === "job"
            ? "Reading the job…"
            : working === "tailor"
              ? "Tailoring… (20–40 s)"
              : "Tailor my resume"}
        </button>
        <span className="text-center text-xs text-muted">
          Built from your profile, {user.name.split(/\s+/)[0]}. Nothing is added that isn&apos;t in it.
        </span>
      </div>
    </div>
  );
}

export default function App() {
  const [token, setTokenState] = useState<string | null | undefined>(undefined);
  const [user, setUser] = useState<User | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    void getToken().then(setTokenState);
    return onTokenChange(setTokenState);
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .me()
      .then((u) => !cancelled && setUser(u))
      .catch((err) => !cancelled && setProblem(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (token === undefined) return null;
  if (!token) return <SignedOut />;
  if (problem && !user) return <p className="p-5 text-sm text-warn-ink">{problem}</p>;
  if (!user) return <p className="p-5 text-sm text-muted">Signing in…</p>;

  return (
    <main className="flex flex-col gap-4 p-4">
      <Header
        user={user}
        onSignOut={() => {
          setUser(null);
          void setToken(null);
        }}
      />
      <Tailor user={user} />
    </main>
  );
}
