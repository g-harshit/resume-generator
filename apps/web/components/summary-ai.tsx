"use client";

import { useState } from "react";
import type { SummaryLength } from "@/lib/api";

/** Write the summary with AI, at a length the person picks. */
export function SummaryAi({
  has,
  busy,
  disabled,
  write,
  undo,
  note = "Only from what's in this resume.",
}: {
  /** Is there a summary now? Lengths are relative to it, or absolute without one. */
  has: boolean;
  busy: boolean;
  disabled: boolean;
  write: (length: SummaryLength) => void;
  undo: (() => void) | null;
  note?: string;
}) {
  const [length, setLength] = useState<SummaryLength>("same");
  // With a summary there, lengths are relative to it; without one, they're absolute.
  const choices: [SummaryLength, string][] = has
    ? [["shorter", "Shorter"], ["same", "Same length"], ["longer", "Longer"]]
    : [["shorter", "Short"], ["same", "Medium"], ["longer", "Long"]];
  return (
    <div className="flex flex-col gap-2 border-t border-sunken pt-3">
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="sr-only">Length of the {has ? "new " : ""}summary</legend>
        <span aria-hidden className="text-[13px] text-muted">Length</span>
        <div className="flex overflow-hidden rounded-lg border border-line-strong text-[13px]">
          {choices.map(([value, label]) => (
            <label
              key={value}
              className={`cursor-pointer px-2.5 py-1.5 has-[:focus-visible]:outline-2 ${
                length === value ? "bg-accent-soft font-medium text-accent-ink" : "hover:bg-sunken"
              }`}
            >
              <input
                type="radio"
                name="summary-length"
                value={value}
                checked={length === value}
                onChange={() => setLength(value)}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => write(length)}
          disabled={disabled}
          className="h-9 rounded-lg border border-line-strong px-3 text-[13px] hover:bg-sunken disabled:opacity-50"
        >
          {busy ? "Writing…" : has ? "Rewrite with AI" : "Write with AI"}
        </button>
        {undo && (
          <button type="button" onClick={undo} className="text-[13px] text-accent underline-offset-2 hover:underline">
            Undo
          </button>
        )}
        <span className="text-xs text-muted">{note}</span>
      </div>
    </div>
  );
}
