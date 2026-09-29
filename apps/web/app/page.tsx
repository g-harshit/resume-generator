import { APP_NAME } from "@/lib/config";
import { ApiStatus } from "./api-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <span className="font-display text-3xl">{APP_NAME}</span>
      <h1 className="font-display text-5xl leading-tight">
        A resume for every job, built from the one you already have.
      </h1>
      <p className="text-lg leading-relaxed text-muted">
        Upload your resume once. Paste a job description — or open it in Chrome — and get an
        ATS-friendly resume tailored to it, using only what&apos;s true about you.
      </p>
      <ApiStatus />
    </main>
  );
}
