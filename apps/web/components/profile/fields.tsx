"use client";

import { useId, useState } from "react";

export const inputClass =
  "w-full rounded-lg border border-line-strong bg-surface px-3 text-[15px] text-ink " +
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

const warnInput = "border-warn bg-[#fff8f2]";

/** Messages shown under a field: things to check there. */
export function Issues({ id, messages }: { id?: string; messages: string[] }) {
  if (!messages.length) return null;
  return (
    <ul id={id} className="flex flex-col gap-1 text-[13px] leading-snug text-warn-ink">
      {messages.map((m) => (
        <li key={m}>{m}</li>
      ))}
    </ul>
  );
}

export function TextField({
  label,
  value,
  onChange,
  issues = [],
  type = "text",
  placeholder,
  autoComplete,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  issues?: string[];
  type?: string;
  placeholder?: string;
  autoComplete?: string;
  className?: string;
}) {
  const issuesId = useId();
  return (
    <label className={`flex flex-col gap-1 text-[13px] text-muted ${className}`}>
      {label}
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={issues.length > 0 || undefined}
        aria-describedby={issues.length ? issuesId : undefined}
        className={`h-10 ${inputClass} ${issues.length ? warnInput : ""}`}
      />
      <Issues id={issuesId} messages={issues} />
    </label>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  issues = [],
  rows = 3,
  hideLabel = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  issues?: string[];
  rows?: number;
  hideLabel?: boolean;
  placeholder?: string;
}) {
  const issuesId = useId();
  return (
    <label className="flex flex-1 flex-col gap-1 text-[13px] text-muted">
      <span className={hideLabel ? "sr-only" : ""}>{label}</span>
      <textarea
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={issues.length > 0 || undefined}
        aria-describedby={issues.length ? issuesId : undefined}
        className={`field-sizing-content min-h-10 resize-none py-2 leading-normal ${inputClass} ${issues.length ? warnInput : ""}`}
      />
      <Issues id={issuesId} messages={issues} />
    </label>
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * A "YYYY" or "YYYY-MM" date as a month (optional) and a year. Year-only is common
 * for education, so the month can be left out. The value only changes once the
 * year is four digits; a half-typed year or a month picked before the year is held
 * here until then.
 */
export function DateField({
  label,
  value,
  onChange,
  issues = [],
  disabled = false,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  issues?: string[];
  disabled?: boolean;
}) {
  const [yearDraft, setYearDraft] = useState<string | null>(null);
  const [pendingMonth, setPendingMonth] = useState("");
  const issuesId = useId();
  const year = value?.slice(0, 4) ?? "";
  const month = value && value.length === 7 ? value.slice(5) : value ? "" : pendingMonth;

  function emit(y: string, m: string) {
    if (!y) return onChange(null);
    onChange(m ? `${y}-${m}` : y);
  }

  return (
    <fieldset className="flex flex-col gap-1" disabled={disabled}>
      <legend className="mb-1 text-[13px] text-muted">{label}</legend>
      <div className="flex gap-2">
        <select
          aria-label={`${label} month`}
          value={month}
          onChange={(e) => {
            if (year) emit(year, e.target.value);
            else setPendingMonth(e.target.value);
          }}
          className={`h-10 w-24 ${inputClass} ${issues.length ? warnInput : ""} disabled:opacity-50`}
        >
          <option value="">Month</option>
          {MONTHS.map((m, i) => (
            <option key={m} value={String(i + 1).padStart(2, "0")}>
              {m}
            </option>
          ))}
        </select>
        <input
          aria-label={`${label} year`}
          inputMode="numeric"
          placeholder="Year"
          maxLength={4}
          value={yearDraft ?? year}
          onChange={(e) => {
            const y = e.target.value.replace(/\D/g, "");
            setYearDraft(y);
            if (y === "" || /^(19|20)\d{2}$/.test(y)) {
              emit(y, month);
              if (y) setPendingMonth("");
            }
          }}
          onBlur={() => setYearDraft(null)}
          aria-invalid={issues.length > 0 || undefined}
          aria-describedby={issues.length ? issuesId : undefined}
          className={`h-10 w-20 ${inputClass} ${issues.length ? warnInput : ""} disabled:opacity-50`}
        />
      </div>
      <Issues id={issuesId} messages={issues} />
    </fieldset>
  );
}

function Icon({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

const iconButton =
  "flex size-9 items-center justify-center rounded-lg text-muted hover:bg-sunken hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent";

/** Move up / move down / remove, for any item in a list. */
export function ItemControls({
  what,
  index,
  count,
  onMove,
  onRemove,
}: {
  what: string;
  index: number;
  count: number;
  onMove: (from: number, to: number) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex shrink-0">
      <button type="button" aria-label={`Move ${what} up`} disabled={index === 0} onClick={() => onMove(index, index - 1)} className={iconButton}>
        <Icon d="M12 19V5M6 11l6-6 6 6" />
      </button>
      <button type="button" aria-label={`Move ${what} down`} disabled={index === count - 1} onClick={() => onMove(index, index + 1)} className={iconButton}>
        <Icon d="M12 5v14M6 13l6 6 6-6" />
      </button>
      <button type="button" aria-label={`Remove ${what}`} onClick={onRemove} className={iconButton}>
        <Icon d="M6 6l12 12M18 6L6 18" />
      </button>
    </div>
  );
}

export function AddButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-10 self-start rounded-lg border border-dashed border-[#9e998b] px-3 text-sm text-ink hover:bg-sunken"
    >
      + {children}
    </button>
  );
}

// --- list helpers ---------------------------------------------------------------

export function move<T>(list: T[], from: number, to: number): T[] {
  if (to < 0 || to >= list.length) return list;
  const next = list.slice();
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item!);
  return next;
}

export function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((x, i) => (i === index ? item : x));
}

export function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, i) => i !== index);
}
