import Link from "next/link";
import type { Metadata } from "next";
import { Suspense } from "react";
import { AtsChecker } from "@/components/ats-checker";
import { HomeActions } from "@/components/home-actions";
import { APP_NAME } from "@/lib/config";
import { LogoMark } from "@/components/logo-mark";

export const metadata: Metadata = {
  title: { absolute: `Free ATS resume checker — see what an ATS reads | ${APP_NAME}` },
  description:
    "Upload your resume and see exactly what an applicant tracking system reads from it: columns, tables, headers, contact details, headings and dates — and which of a job's keywords you have. Free, no sign-up.",
};

const WHAT = [
  ["Text an ATS can read", "Scanned or image-only resumes are blank to an ATS."],
  ["One column", "Two-column layouts are often read straight across, mixing lines."],
  ["Tables, text boxes, headers", "Many ATSs skip them — with your contact details inside."],
  ["Contact details", "Email, phone and LinkedIn, where an ATS finds them."],
  ["Headings and dates", "Standard headings and readable dates sort your experience."],
  ["Job keywords", "Paste a job: see which of its skills your resume has."],
];

const FAQ = [
  {
    q: "Why no ATS score?",
    a: "Because real ATSs don't give one. Workday, Greenhouse, Lever and Naukri's RMS read your file into text and fields, and recruiters search that. A made-up score out of 100 can't tell you what went wrong; the text an ATS reads, and why, can.",
  },
  {
    q: "Is it really free?",
    a: "Yes, and no account is needed. You can run five checks a day. If you want to fix what it finds, you can sign up free and your resume comes with you.",
  },
  {
    q: "What happens to my file?",
    a: "We keep it for 24 hours so it can become your profile if you sign up, then delete it. We don't use it for anything else.",
  },
];

export default function AtsCheckerPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="sticky top-0 z-10 border-b border-line bg-ground/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 font-display text-3xl text-ink hover:text-ink">
            <LogoMark size={30} />
            {APP_NAME}
          </Link>
          <HomeActions compact />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-12 sm:px-6 sm:py-16">
        <div className="flex max-w-3xl flex-col gap-4">
          <h1 className="font-display text-5xl leading-[1.05] sm:text-6xl">Free ATS resume checker</h1>
          <p className="text-lg leading-relaxed text-muted">
            See exactly what an applicant tracking system reads from your resume — and what it misses.
            No sign-up, and no made-up score: just the text it gets, and what to fix.
          </p>
        </div>

        <Suspense fallback={null}>
          <AtsChecker />
        </Suspense>

        <section aria-labelledby="what" className="flex flex-col gap-5 border-t border-line pt-10">
          <h2 id="what" className="font-display text-3xl">What it checks</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {WHAT.map(([t, d]) => (
              <li key={t} className="flex flex-col gap-1 rounded-xl border border-line bg-surface p-4">
                <span className="font-semibold">{t}</span>
                <span className="text-sm leading-relaxed text-muted">{d}</span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="faq" className="flex max-w-3xl flex-col gap-4">
          <h2 id="faq" className="font-display text-3xl">Questions</h2>
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
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-3 px-4 py-6 text-sm text-muted sm:px-6">
          <Link href="/">{APP_NAME}</Link>
          <nav aria-label="Legal" className="flex gap-4">
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
