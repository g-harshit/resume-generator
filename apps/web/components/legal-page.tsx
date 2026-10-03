import Link from "next/link";
import { APP_NAME } from "@/lib/config";

/** The frame for the privacy policy and terms: plain, readable, linkable sections. */
export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex h-18 items-center border-b border-line px-4 sm:px-10">
        <Link href="/" className="font-display text-3xl text-ink hover:text-ink">
          {APP_NAME}
        </Link>
      </header>
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-12 text-[15px] leading-relaxed [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-5xl leading-tight">{title}</h1>
          <p className="text-sm text-muted">Last updated {updated}</p>
        </div>
        {children}
      </main>
      <LegalFooter />
    </div>
  );
}

export function LegalFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-3 px-4 py-6 text-sm text-muted sm:px-6">
        <span>{APP_NAME}</span>
        <nav aria-label="Legal" className="flex gap-4">
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </nav>
      </div>
    </footer>
  );
}
