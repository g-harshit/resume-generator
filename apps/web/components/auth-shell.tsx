import Link from "next/link";
import { APP_NAME } from "@/lib/config";

/** The frame of the signed-out pages: sign-in, password reset. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex flex-1 flex-col">
      <header className="flex h-18 items-center border-b border-line px-4 sm:px-10">
        <Link href="/" className="font-display text-3xl text-ink hover:text-ink">
          {APP_NAME}
        </Link>
      </header>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col gap-7 px-4 py-14">{children}</div>
    </main>
  );
}

export const authInput =
  "h-11 rounded-lg border border-line-strong bg-surface px-3 text-base text-ink " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

export const authButton =
  "h-12 rounded-[10px] bg-accent text-base font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-60";
