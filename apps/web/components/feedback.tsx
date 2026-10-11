"use client";

import { useEffect, useRef, useState } from "react";
import { api, type FeedbackKind } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const KINDS: [FeedbackKind, string, string][] = [
  ["problem", "Something's wrong", "What happened, and where? What did you expect?"],
  ["idea", "Idea for a feature", "What would you like it to do, and what would it help you with?"],
  ["other", "Other", "Tell us anything."],
];

/**
 * "Send feedback": a link that opens a small form. Works signed in (we know who) or
 * out (an email is asked for, so we can reply). Sends the page it was opened on.
 */
export function Feedback({ className = "", label = "Send feedback" }: { className?: string; label?: string }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<FeedbackKind>("problem");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [problem, setProblem] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  function close() {
    setOpen(false);
    if (state === "sent") {
      setState("idle");
      setMessage("");
    }
  }

  async function send() {
    setState("sending");
    setProblem(null);
    try {
      await api.sendFeedback({
        kind,
        message,
        page: window.location.pathname + window.location.search,
        ...(user ? {} : { email }),
      });
      setState("sent");
    } catch (err) {
      setProblem(err instanceof TypeError ? "Can't reach the server. Try again in a moment." : (err as Error).message);
      setState("idle");
    }
  }

  const hint = KINDS.find(([k]) => k === kind)![2];

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={className}>
        {label}
      </button>
      <dialog
        ref={dialog}
        onClose={close}
        aria-label="Send feedback"
        className="m-auto w-[min(92vw,480px)] rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/30"
      >
        {state === "sent" ? (
          <div className="flex flex-col gap-3 p-6">
            <h2 className="font-display text-2xl">Thank you</h2>
            <p className="text-sm leading-relaxed text-muted">
              We read every message.{" "}
              {user || email ? "If we need more detail, we'll get in touch." : "Thanks for taking the time."}
            </p>
            <button type="button" onClick={close} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white">
              Close
            </button>
          </div>
        ) : (
          <form
            method="dialog"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
            className="flex flex-col gap-4 p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-2xl">Send feedback</h2>
              <button type="button" onClick={close} aria-label="Close" className="text-xl leading-none text-muted hover:text-ink">
                ×
              </button>
            </div>
            <div role="radiogroup" aria-label="What is it about?" className="flex flex-wrap gap-1.5">
              {KINDS.map(([k, name]) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={kind === k}
                  onClick={() => setKind(k)}
                  className={`rounded-full border px-3 py-1 text-[13px] ${
                    kind === k ? "border-accent bg-accent text-white" : "border-line-strong bg-surface hover:bg-sunken"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Message</span>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                maxLength={4000}
                required
                placeholder={hint}
                className="rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm"
              />
            </label>
            {!user && (
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium">
                  Your email <span className="font-normal text-muted">(optional, so we can reply)</span>
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={320}
                  className="rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm"
                />
              </label>
            )}
            {problem && (
              <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn-ink">
                {problem}
              </p>
            )}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={state === "sending" || message.trim().length < 3}
                className="h-11 rounded-[10px] bg-accent px-5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {state === "sending" ? "Sending…" : "Send"}
              </button>
              <span className="text-xs text-muted">We also note which page you were on.</span>
            </div>
          </form>
        )}
      </dialog>
    </>
  );
}
