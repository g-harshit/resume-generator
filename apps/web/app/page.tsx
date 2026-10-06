import Link from "next/link";
import type { Metadata } from "next";
import { HomeActions } from "@/components/home-actions";
import { APP_NAME } from "@/lib/config";

export const metadata: Metadata = {
  title: { absolute: `${APP_NAME} — a resume for every job, in your own words` },
  description:
    "Upload your resume once. For each job, see which of its keywords you cover, add them to the lines they fit, rewrite only the lines you pick, and download an ATS-friendly PDF that fills the page.",
};

// Every claim on this page is something the product does today. The examples in
// "When you ask for a rewrite" are real rewordings the guard rejected in testing.

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

function Chip({ children, tone = "accent" }: { children: React.ReactNode; tone?: "accent" | "warn" | "plain" }) {
  const tones = {
    accent: "bg-accent-soft text-accent-ink",
    warn: "border border-dashed border-warn bg-warn-soft text-warn-ink",
    plain: "border border-line-strong bg-surface text-ink",
  };
  return <span className={`rounded-full px-2 py-0.5 text-[12px] ${tones[tone]}`}>{children}</span>;
}

/** The editor in miniature: the job match, a line given keywords, a line reworded on request. */
function HeroVisual() {
  return (
    <div aria-hidden="true" className="relative flex flex-col gap-3">
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[11px] font-semibold tracking-wider text-muted uppercase">Tech Lead — Swish</div>
        <div className="mt-3 flex items-center gap-3">
          <div
            className="flex size-14 shrink-0 items-center justify-center rounded-full"
            style={{ background: "conic-gradient(var(--color-accent) 0 78%, var(--color-sunken) 78% 100%)" }}
          >
            <span className="flex size-10 items-center justify-center rounded-full bg-surface text-sm font-semibold">7/9</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {["Go", "Kafka", "AWS", "System design", "Microservices", "Mentoring", "CI/CD"].map((t) => (
              <Chip key={t}>✓ {t}</Chip>
            ))}
            {["Kubernetes", "Low-latency systems"].map((t) => (
              <Chip key={t} tone="warn">
                {t}
              </Chip>
            ))}
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[13px] leading-relaxed">
          Designed and built a scalable, robust end-to-end event-driven Go microservice using queues, built for
          high throughput.
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[12px]">
          <span className="font-medium text-accent-ink">Added keywords:</span>
          <Chip>Microservices</Chip>
          <Chip>Queues</Chip>
          <Chip>High-throughput systems</Chip>
          <span className="ml-1 text-accent">Edit keywords</span>
        </div>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="text-[13px] leading-relaxed">
          Reduced ledger API p99 latency from 800ms to 120ms by tuning PostgreSQL indexes.
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 text-[12px]">
          <span className="font-medium text-accent-ink">Reworded for this job</span>
          <span className="text-muted">See original</span>
          <span className="text-accent">Use original</span>
          <span className="text-accent">Rewrite again</span>
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  {
    title: "Your profile, once",
    body: "Upload your resume (PDF or Word) and check what we read — or build one step by step, with a projects section if you're just starting out.",
  },
  {
    title: "Paste the job",
    body: "Or open it on LinkedIn, Naukri or Indeed and use the Chrome extension (coming to the Chrome Web Store). You see which of the job's skills and keywords your resume covers, and which it doesn't.",
  },
  {
    title: "Your resume, as you wrote it",
    body: "In seconds: every line, in your words and your order, in an ATS-friendly template. Nothing changes until you say so.",
  },
  {
    title: "You choose what changes",
    body: "Add the job's keywords to the lines they fit. Rewrite a line or a whole role for the job. Fit it to one page, or fill the page. Download the PDF.",
  },
];

const FEATURES = [
  {
    title: "Keywords where you want them",
    body: "Under every line, the job's keywords that line doesn't have — the ones missing from your resume first, then ones used elsewhere. Tick the ones that fit, untick any to drop, apply once.",
  },
  {
    title: "Rewrite only what you pick",
    body: "“Rewrite for this job” on one line, or all the lines of a role in one go. Don't like it? Use original, or rewrite again.",
  },
  {
    title: "Fits the page — and fills it",
    body: "Fit to one or two pages without losing your latest role's detail. Or fill the empty space: your own left-out lines first, then larger text and spacing, down to the bottom margin.",
  },
  {
    title: "Your layout",
    body: "Margins (the same on all four sides), section order, which sections and header details show, how many lines each role keeps. A live preview of every page as you edit.",
  },
  {
    title: "A cover letter, too",
    body: "Written for the job from what's in the resume — and checked the same way, so it doesn't claim what your resume doesn't.",
  },
  {
    title: "From the job page",
    body: "The Chrome extension reads the posting on LinkedIn, Naukri, Indeed, Greenhouse, Lever or Workday, makes the resume and lets you add keywords right in the side panel. Coming to the Chrome Web Store.",
  },
];

// Real: each was written by a model in testing and rejected (a rule or the second check).
const GUARDS = [
  {
    rule: "No added claims",
    tried: "Migrated settlement jobs to Kafka consumers on AWS ECS for more robust processing.",
    kept: "Migrated settlement jobs from cron scripts to Kafka consumers on AWS ECS.",
  },
  {
    rule: "No dropped numbers",
    tried: "Reduced ledger API p99 latency by tuning PostgreSQL indexes.",
    kept: "Cut p99 latency of the ledger API from 800ms to 120ms with PostgreSQL index tuning.",
  },
  {
    rule: "No added scale",
    tried: "Implemented Postgres table partitioning for large-scale trade history.",
    kept: "Introduced Postgres table partitioning for trade history.",
  },
];

const TEMPLATES = [
  { slug: "classic", name: "Classic", note: "Serif, centred header" },
  { slug: "modern", name: "Modern", note: "Sans-serif, one accent colour" },
  { slug: "compact", name: "Compact", note: "Fits a long career on a page" },
  { slug: "executive", name: "Executive", note: "Summary-led, for senior roles" },
];

const FAQ = [
  {
    q: "Do you change my resume when I paste a job?",
    a: "No. A new resume is your profile exactly as you wrote it — every line, in your words and order. You decide what changes: which keywords go into which lines, and which lines (or roles) get rewritten for the job.",
  },
  {
    q: "Does the AI make things up?",
    a: "Not when it rewrites. “Rewrite for this job” is checked against your line: no new numbers, skills, claims or scale, no dropped metrics, and a second check reads each one side by side. Anything that fails stays in your words, and the editor says why.",
  },
  {
    q: "Can I add a keyword my line doesn't mention?",
    a: "Yes — that's your call, not ours. You pick the keywords for each line, and the line is rewritten to include them. Only add what that work really involved: you'll be asked about it.",
  },
  {
    q: "What if the job asks for a skill I don't have listed?",
    a: "It shows as “Not in this resume yet”. Add it to a line that fits, or click “I have this” to save it to your profile for every future resume. If you don't have it, leave it — we never add it for you.",
  },
  {
    q: "Will my resume get past an ATS?",
    a: "No tool can promise that. What we do control: one column, real text (not images), standard section headings, and contact details in the page itself rather than a header. We test every template's PDF by reading the text back out, the way an ATS does.",
  },
  {
    q: "Which files can I upload?",
    a: "PDF and Word (.docx), up to 5 MB. Scanned images don't work yet — export a PDF from your editor instead. No resume yet? Build one step by step.",
  },
  {
    q: "Does editing my profile change resumes I've already made?",
    a: "No. Each resume is a snapshot. Use “Refresh from profile” if you want it rebuilt from your profile as it is now.",
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
              A resume for every job, in your own words.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted">
              Upload your resume once. For each job, see which of its keywords you cover, add them to
              the lines they fit, and rewrite only the lines you choose — then download an
              ATS-friendly PDF that fills the page.
            </p>
            <HomeActions />
            <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted">
              {["Nothing changes unless you ask", "Keywords exactly where you want them", "Four ATS-friendly templates"].map(
                (t) => (
                  <li key={t} className="flex items-center gap-1.5">
                    <span className="text-accent">
                      <Check />
                    </span>
                    {t}
                  </li>
                ),
              )}
            </ul>
          </div>
          <HeroVisual />
        </section>

        {/* How it works */}
        <section aria-labelledby="how" className="border-t border-line bg-surface">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6">
            <h2 id="how" className="font-display text-4xl">How it works</h2>
            <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
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

        {/* Features */}
        <section aria-labelledby="features" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6">
          <div className="flex max-w-2xl flex-col gap-3">
            <h2 id="features" className="font-display text-4xl">You&apos;re in charge of every line</h2>
            <p className="text-lg leading-relaxed text-muted">
              The AI does the typing; you make the calls. Everything it changes is marked, and every
              change can be undone.
            </p>
          </div>
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-5">
                <h3 className="text-base font-semibold">{f.title}</h3>
                <p className="text-[15px] leading-relaxed text-muted">{f.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* Keywords + honest gaps */}
        <section aria-labelledby="keywords" className="border-t border-line bg-surface">
          <div className="mx-auto grid w-full max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center">
            <div className="flex flex-col gap-5">
              <h2 id="keywords" className="font-display text-4xl">Every keyword, accounted for</h2>
              <p className="leading-relaxed text-muted">
                See which of the job&apos;s skills your resume already shows. For the rest, pick the lines
                they belong in — one keyword on several lines is fine — and add or remove any of them
                in a single apply. Missing one you actually have? Save it to your profile with
                “I have this”. Missing one you don&apos;t? It stays missing.
              </p>
            </div>
            <div aria-hidden="true" className="flex flex-col gap-2.5 rounded-xl border border-line bg-ground p-4">
              <span className="text-[13px] leading-snug">
                Led system design and technical architecture for a Spark- and Airflow-based data archival
                pipeline…
              </span>
              <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
                <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">On this line</span>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-full border border-accent bg-accent px-2.5 py-0.5 text-[12px] text-white">✓ system design</span>
                  <span className="rounded-full border border-accent bg-accent px-2.5 py-0.5 text-[12px] text-white">✓ technical architecture</span>
                </div>
                <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">Not in your resume yet</span>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-full border border-accent bg-accent px-2.5 py-0.5 text-[12px] text-white">✓ microservices</span>
                  <Chip tone="plain">+ Kubernetes</Chip>
                  <Chip tone="plain">+ observability</Chip>
                </div>
                <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">In other lines — add here too</span>
                <div className="flex flex-wrap gap-1.5">
                  <Chip tone="plain">+ system reliability</Chip>
                  <Chip tone="plain">+ engineering standards</Chip>
                </div>
                <span className="mt-1 self-start rounded-md bg-accent px-3 py-1.5 text-[12px] font-medium text-white">
                  Apply: add 1
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* The guard */}
        <section aria-labelledby="guard" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6">
          <div className="flex max-w-2xl flex-col gap-3">
            <h2 id="guard" className="font-display text-4xl">When you ask for a rewrite, it doesn&apos;t embellish</h2>
            <p className="text-lg leading-relaxed text-muted">
              AI loves to puff a resume up — and that gets people caught out in interviews. So every
              rewrite is checked against what you actually wrote, and when it overreaches, your own
              words stay. These are real rewordings it refused while we tested it:
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

        {/* Templates */}
        <section aria-labelledby="templates" className="border-t border-line bg-surface">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-16 sm:px-6">
            <div className="flex max-w-2xl flex-col gap-3">
              <h2 id="templates" className="font-display text-4xl">Templates an ATS can read</h2>
              <p className="leading-relaxed text-muted">
                One column, real text, standard headings, contact details on the page. Every template&apos;s
                PDF is checked by reading it back the way an applicant tracking system does. Shown here
                with a sample resume.
              </p>
            </div>
            <ul className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {TEMPLATES.map((t) => (
                <li key={t.slug} className="flex flex-col gap-2">
                  {/* eslint-disable-next-line @next/next/no-img-element -- a static export: no image optimiser */}
                  <img
                    src={`/templates/${t.slug}.jpg`}
                    alt={`The ${t.name} template, with a sample resume`}
                    width={1191}
                    height={1684}
                    loading="lazy"
                    className="block h-auto w-full rounded-lg border border-line bg-white shadow-sm"
                  />
                  <span className="text-sm font-semibold">{t.name}</span>
                  <span className="-mt-1.5 text-xs text-muted">{t.note}</span>
                </li>
              ))}
            </ul>
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
          <span>Your resume, in your own words.</span>
          <nav aria-label="Legal" className="flex gap-4">
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
