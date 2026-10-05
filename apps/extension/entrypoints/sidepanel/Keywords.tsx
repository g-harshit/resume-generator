import { useState } from "react";
import { api, type Bullet, type LineHistory, type Resume } from "@/lib/api";

/** The keywords added to a line: the person's picks, or skills its words proved. */
function addedKeywords(history: LineHistory | undefined): string[] {
  if (history?.status === "keywords") return history.keywords ?? [];
  if (history?.status === "bridged") return (history.skills ?? []).map((s) => s.skill);
  return [];
}

function Chips({
  label,
  keys,
  picked,
  toggle,
}: {
  label: string;
  keys: string[];
  picked: string[];
  toggle: (k: string) => void;
}) {
  if (!keys.length) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</span>
      <ul className="flex flex-wrap gap-1.5" aria-label={label}>
        {keys.map((k) => {
          const on = picked.includes(k);
          return (
            <li key={k}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => toggle(k)}
                className={`rounded-full border px-2 py-0.5 text-[12px] ${
                  on ? "border-accent bg-accent text-white" : "border-line-strong bg-surface text-ink hover:bg-sunken"
                }`}
              >
                {on ? "✓ " : "+ "}
                {k}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** One line: its text, its keywords, and the panel to change them in one apply. */
function Line({
  line,
  resume,
  busy,
  disabled,
  onApply,
}: {
  line: Bullet;
  resume: Resume;
  busy: boolean;
  disabled: boolean;
  onApply: (keywords: string[]) => void;
}) {
  const added = addedKeywords(resume.provenance[line.id]);
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>(added);
  const gaps = resume.match?.missing_in_lines ?? [];
  const forLine = (resume.match?.missing_by_line?.[line.id] ?? gaps).filter((k) => !added.includes(k));
  const nowhere = forLine.filter((k) => gaps.includes(k));
  const elsewhere = forLine.filter((k) => !gaps.includes(k));
  const adding = picked.filter((k) => !added.includes(k)).length;
  const removing = added.filter((k) => !picked.includes(k)).length;
  const changes = [adding && `add ${adding}`, removing && `remove ${removing}`].filter(Boolean);

  function toggle(k: string) {
    setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : p.length < 8 ? [...p, k] : p));
  }

  return (
    <li className="flex flex-col gap-1.5 border-t border-sunken pt-2 first:border-t-0 first:pt-0">
      <p className={`text-[13px] leading-snug ${busy ? "animate-pulse text-muted" : ""}`}>{line.text}</p>
      {added.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {added.map((k) => (
            <span key={k} className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent-ink">
              {k}
            </span>
          ))}
        </div>
      )}
      {busy ? (
        <span role="status" className="text-xs text-muted">
          Rewriting this line…
        </span>
      ) : !open ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            setPicked(added);
            setOpen(true);
          }}
          className="self-start text-xs text-accent hover:underline disabled:opacity-50"
        >
          {added.length ? "Edit keywords" : "+ Add job keywords"}
        </button>
      ) : (
        <div className="flex flex-col gap-2 rounded-lg border border-line bg-sunken/60 p-2">
          <Chips label="On this line" keys={added} picked={picked} toggle={toggle} />
          <Chips label="Not in your resume yet" keys={nowhere} picked={picked} toggle={toggle} />
          <Chips label="In other lines" keys={elsewhere} picked={picked} toggle={toggle} />
          {!added.length && !forLine.length && (
            <span className="text-xs text-muted">This line already has every job keyword.</span>
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!changes.length || disabled}
              onClick={() => {
                onApply(picked);
                setOpen(false);
              }}
              className="h-8 rounded-md bg-accent px-3 text-[12px] font-medium text-white disabled:opacity-50"
            >
              {!changes.length ? "No changes" : !picked.length ? "Remove all keywords" : `Apply: ${changes.join(", ")}`}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="h-8 px-2 text-[12px] text-muted">
              Cancel
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

/**
 * The resume's lines, by role and project, each with the job keywords it can take:
 * tick and untick, one Apply per line (one call).
 */
export function Keywords({ resume, onChange }: { resume: Resume; onChange: (r: Resume) => void }) {
  const [busyLine, setBusyLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const entries = [
    ...resume.content.experience.map((e) => ({
      id: e.id,
      label: [e.title, e.company].filter(Boolean).join(" · "),
      bullets: e.bullets,
    })),
    ...resume.content.projects.map((p) => ({ id: p.id, label: p.name, bullets: p.bullets })),
  ].filter((e) => e.bullets.length);

  async function apply(lineId: string, keywords: string[]) {
    setBusyLine(lineId);
    setError(null);
    try {
      onChange(await api.lineKeywords(resume.id, resume.version, lineId, keywords));
    } catch (err) {
      setError(err instanceof TypeError ? "Can't reach the server." : (err as Error).message);
    } finally {
      setBusyLine(null);
    }
  }

  return (
    <section aria-label="Job keywords" className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-3.5">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-[15px] font-semibold">Job keywords</h2>
        <span className="text-xs leading-snug text-muted">
          Add the job&apos;s keywords to the lines they fit, or remove them. Each line is rewritten to include the ones
          you tick.
        </span>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-warn-soft px-2.5 py-1.5 text-xs text-warn-ink">
          {error}
        </p>
      )}
      {entries.map((e) => (
        <div key={e.id} className="flex flex-col gap-2">
          <h3 className="text-[13px] font-semibold">{e.label}</h3>
          <ul className="flex flex-col gap-2">
            {e.bullets.map((b) => (
              <Line
                key={b.id}
                line={b}
                resume={resume}
                busy={busyLine === b.id}
                disabled={busyLine !== null}
                onApply={(k) => void apply(b.id, k)}
              />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
