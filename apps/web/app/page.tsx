import Link from "next/link";
import type { Metadata } from "next";
import { HomeActions } from "@/components/home-actions";
import { APP_NAME } from "@/lib/config";

export const metadata: Metadata = {
  title: { absolute: `${APP_NAME} — a resume for every job, from the one you already have` },
  description:
    "Upload your resume once, paste a job description, and get an ATS-friendly resume tailored to it — built only from what's true about you.",
};

// Every claim on this page is something the product does today. The examples in
// "It never makes things up" are real rewordings the guard rejected in testing.

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

function HeroVisual() {
  return (
    <div aria-hidden="true" className="relative flex flex-col gap-3">
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[11px] font-semibold tracking-wider text-muted uppercase">Senior Backend Engineer — Northwind Labs</div>
        <div className="mt-3 flex items-center gap-3">
          <div
            className="flex size-14 shrink-0 items-center justify-center rounded-full"
            style={{ background: "conic-gradient(var(--color-accent) 0 78%, var(--color-sunken) 78% 100%)" }}
          >
            <span className="flex size-10 items-center justify-center rounded-full bg-surface text-sm font-semibold">7/9</span>
          </div>
          <div className="flex flex-wrap gap-1.5 text-[12px]">
            {["Go", "PostgreSQL", "Kafka", "AWS", "Terraform", "on-call", "Kubernetes"].map((t) => (
              <span key={t} className="rounded-full bg-accent-soft px-2 py-0.5 text-accent-ink">
                ✓ {t}
              </span>
            ))}
            {["gRPC", "Distributed systems"].map((t) => (
              <span key={t} className="rounded-full border border-dashed border-warn bg-warn-soft px-2 py-0.5 text-warn-ink">
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[13px] leading-relaxed">
          Migrated settlement jobs from cron scripts to Kafka consumers on AWS ECS.
        </div>
        <div className="mt-2 flex items-center gap-2 text-[12px] text-muted">
          <span className="font-medium text-accent-ink">Kept in your words</span>
          <span>· the rewording added “optimizing job scheduling”</span>
        </div>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[13px] leading-relaxed">
          Built an order-matching API in Go handling 1,200 requests per second.
        </div>
        <div className="mt-2 text-[12px] font-medium text-accent-ink">Reworded for this job · checked against your original</div>
      </div>
    </div>
  );
}

const STEPS = [
  {
    title: "Upload the resume you have",
    body: "PDF or Word. We read it into a profile you check and correct once — every resume after that is built from it.",
  },
  {
    title: "Paste the job description",
    body: "We pick out the role and the skills it asks for, and show which ones your profile already covers — and where.",
  },
  {
    title: "Get a tailored resume",
    body: "Your most relevant lines first, worded for the job, in an ATS-friendly template. Edit anything, then download the PDF.",
  },
];

// Real: each was written by a model in testing and rejected (rule or second check).
const GUARDS = [
  {
    rule: "No skills the line didn't mention",
    tried:
      "Developed a reconciliation service in Go for processing over 3 million bank transactions daily, reducing manual review efforts significantly.",
    kept: "Designed the reconciliation service that matches 3M bank transactions a day, cutting manual review by 60%.",
  },
  {
    rule: "No added claims",
    tried: "Migrated settlement jobs to Kafka consumers on AWS ECS for more robust processing.",
    kept: "Migrated settlement jobs from cron scripts to Kafka consumers on AWS ECS.",
  },
  {
    rule: "No added scale",
    tried: "Implemented Postgres table partitioning for large-scale trade history.",
    kept: "Introduced Postgres table partitioning for trade history.",
  },
];

const TEMPLATES = [
  { name: "Classic", note: "Serif, centred header" },
  { name: "Modern", note: "Sans-serif, one accent colour" },
  { name: "Compact", note: "Fits a long career on a page" },
  { name: "Executive", note: "Summary-led, for senior roles" },
];

const FAQ = [
  {
    q: "Does it make things up?",
    a: "No. The AI can only choose, order and reword lines from your own profile. Code then checks every reworded line against your original — no new numbers, no skills the line didn't mention, no new claims — and a second check reads each one side by side. Anything that fails stays in your words, and the editor shows you what was kept and why.",
  },
  {
    q: "What if the job asks for a skill I don't have listed?",
    a: "It shows up as missing. If you do have it, click “I have this”, say where you used it and write the line yourself; it's saved to your profile for every future resume. If you don't, it stays missing — we never add it for you.",
  },
  {
    q: "Will my resume get past an ATS?",
    a: "No tool can promise that. What we do control: one column, real text (not images), standard section headings, and contact details in the page itself rather than a header. We test every template's PDF by reading the text back out, the way an ATS does.",
  },
  {
    q: "Which files can I upload?",
    a: "PDF and Word (.docx), up to 5 MB. Scanned images don't work yet — export a PDF from your editor instead.",
  },
  {
    q: "Does editing my profile change resumes I've already sent?",
    a: "No. Each resume is a snapshot. Re-tailor it if you want it rebuilt from your profile as it is now.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="sticky top-0 z-10 border-b border-line bg-ground/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <span className="font-display text-3xl">{APP_NAME}</span>
          <HomeActions compact />
        </div>
      </header>

      <main className="flex flex-col">
        {/* Hero */}
        <section className="mx-auto grid w-full max-w-6xl gap-12 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-center">
          <div className="flex flex-col gap-6">
            <h1 className="font-display text-5xl leading-[1.05] sm:text-6xl">
              A resume for every job, built from the one you already have.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted">
              Upload your resume once. Paste a job description, and get an ATS-friendly resume
              tailored to it — using only what&apos;s true about you.
            </p>
            <HomeActions />
            <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted">
              {["Never invents a skill or a number", "PDF in four ATS-friendly templates", "Edit everything"].map((t) => (
                <li key={t} className="flex items-center gap-1.5">
                  <span className="text-accent">
                    <Check />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <HeroVisual />
        </section>

        {/* How it works */}
        <section aria-labelledby="how" className="border-t border-line bg-surface">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6">
            <h2 id="how" className="font-display text-4xl">How it works</h2>
            <ol className="grid gap-6 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <li key={s.title} className="flex flex-col gap-3 rounded-xl border border-line bg-ground p-6">
                  <span className="flex size-8 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">
                    {i + 1}
                  </span>
                  <h3 className="text-lg font-semibold">{s.title}</h3>
                  <p className="leading-relaxed text-muted">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* The guard */}
        <section aria-labelledby="guard" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6">
          <div className="flex max-w-2xl flex-col gap-3">
            <h2 id="guard" className="font-display text-4xl">It never makes things up</h2>
            <p className="text-lg leading-relaxed text-muted">
              AI loves to embellish a resume. That gets people caught out in interviews. So every
              line it rewords is checked against what you actually wrote — and when it overreaches,
              your own words stay. These are real rewordings it refused while we tested it:
            </p>
          </div>
          <ul className="grid gap-5 md:grid-cols-3">
            {GUARDS.map((g) => (
              <li key={g.rule} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5">
                <span className="text-sm font-semibold text-accent-ink">{g.rule}</span>
                <p className="text-[14px] leading-relaxed text-muted">
                  <span className="sr-only">Rejected: </span>
                  <s>{g.tried}</s>
                </p>
                <p className="border-t border-sunken pt-3 text-[14px] leading-relaxed">
                  <span className="sr-only">Kept: </span>
                  {g.kept}
                </p>
              </li>
            ))}
          </ul>
        </section>

        {/* Templates + honest gaps */}
        <section aria-labelledby="templates" className="border-t border-line bg-surface">
          <div className="mx-auto grid w-full max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2">
            <div className="flex flex-col gap-5">
              <h2 id="templates" className="font-display text-4xl">Templates an ATS can read</h2>
              <p className="leading-relaxed text-muted">
                One column, real text, standard headings, contact details on the page. Every
                template is checked by reading its PDF back the way an applicant tracking system
                does.
              </p>
              <ul className="grid grid-cols-2 gap-3">
                {TEMPLATES.map((t) => (
                  <li key={t.name} className="flex flex-col gap-2 rounded-lg border border-line bg-ground p-3">
                    <div aria-hidden="true" className="flex aspect-[3/4] flex-col gap-1.5 rounded bg-surface p-3">
                      <div className={`h-2 w-1/2 rounded-sm bg-ink ${t.name === "Classic" ? "self-center" : ""}`} />
                      <div className="h-1 w-3/4 rounded-sm bg-line" />
                      {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="mt-1.5 flex flex-col gap-1">
                          <div className={`h-1.5 w-1/3 rounded-sm ${t.name === "Modern" ? "bg-accent" : "bg-muted"}`} />
                          <div className="h-1 rounded-sm bg-line" />
                          <div className="h-1 w-5/6 rounded-sm bg-line" />
                          <div className="h-1 w-11/12 rounded-sm bg-line" />
                          {i < 2 && <div className="h-1 w-4/5 rounded-sm bg-line" />}
                        </div>
                      ))}
                    </div>
                    <span className="text-sm font-semibold">{t.name}</span>
                    <span className="-mt-1.5 text-xs text-muted">{t.note}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col gap-5">
              <h2 className="font-display text-4xl">Honest about the gaps</h2>
              <p className="leading-relaxed text-muted">
                You see which of the job&apos;s skills your resume covers, and where each one comes
                from. Missing one you actually have? Say “I have this”, write a line about where you
                used it, and it&apos;s in your profile for good. Missing one you don&apos;t? It stays
                missing.
              </p>
              <div aria-hidden="true" className="flex flex-col gap-2 rounded-xl bg-warn-soft p-4 text-warn-ink">
                <span className="text-sm font-semibold">Not in your profile</span>
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span>
                    <strong>Kubernetes</strong> · must have
                  </span>
                  <span className="rounded-lg border border-warn bg-surface px-2.5 py-1 text-[13px]">I have this</span>
                </div>
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span>
                    <strong>gRPC</strong> · must have
                  </span>
                  <span className="rounded-lg border border-warn bg-surface px-2.5 py-1 text-[13px]">I have this</span>
                </div>
              </div>
              <p className="text-sm text-muted">
                A Chrome extension that reads the job straight from LinkedIn, Naukri, Indeed or a
                careers page is coming to the Chrome Web Store.
              </p>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section aria-labelledby="faq" className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-16 sm:px-6">
          <h2 id="faq" className="font-display text-4xl">Questions</h2>
          <div className="flex flex-col divide-y divide-line border-y border-line">
            {FAQ.map((f) => (
              <details key={f.q} className="group py-4">
                <summary className="cursor-pointer list-none text-lg font-semibold marker:hidden">
                  <span className="mr-2 inline-block text-accent transition-transform group-open:rotate-90">›</span>
                  {f.q}
                </summary>
                <p className="mt-2 pl-5 leading-relaxed text-muted">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="border-t border-line bg-surface">
          <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-5 px-4 py-16 sm:px-6">
            <h2 className="font-display text-4xl">Start with the resume you already have.</h2>
            <HomeActions />
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-3 px-4 py-6 text-sm text-muted sm:px-6">
          <span>{APP_NAME}</span>
          <span>Built only from what&apos;s true about you.</span>
          <nav aria-label="Legal" className="flex gap-4">
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
