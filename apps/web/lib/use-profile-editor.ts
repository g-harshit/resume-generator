"use client";

import type { ResumeData } from "@rg/schema";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Check, type Note, type Profile } from "@/lib/api";

const DEBOUNCE_MS = 800;

export type SaveState =
  | { kind: "saved" }
  | { kind: "unsaved" }
  | { kind: "saving" }
  | { kind: "error"; message: string }
  | { kind: "conflict" };

/**
 * Local editing state for a profile, saved automatically.
 *
 * Saves are debounced and never overlap: an edit made while a save is in flight is
 * saved right after it, with the latest data. The server's response updates the
 * version and checks but never the data being edited, so typing isn't clobbered.
 */
export function useProfileEditor(initial: Profile) {
  const [data, setDataState] = useState<ResumeData>(initial.data);
  const [checks, setChecks] = useState<Check[]>(initial.checks);
  const [notes, setNotes] = useState<Note[]>(initial.notes);
  const [reviewedAt, setReviewedAt] = useState(initial.reviewed_at);
  const [save, setSave] = useState<SaveState>({ kind: "saved" });

  const latest = useRef(data);
  const version = useRef(initial.version);
  const dirty = useRef(false);
  const inFlight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Save until nothing is pending (edits made during a save go out right after it).
   *  Resolves false if a save failed. */
  const flush = useCallback(async (): Promise<boolean> => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    while (inFlight.current) await inFlight.current;

    let ok = true;
    while (ok && dirty.current) {
      dirty.current = false;
      setSave({ kind: "saving" });
      inFlight.current = (async () => {
        try {
          const saved = await api.saveProfile(version.current, latest.current);
          version.current = saved.version;
          setChecks(saved.checks);
          setNotes(saved.notes);
        } catch (err) {
          ok = false;
          dirty.current = true; // still unsaved; the next edit tries again
          if (err instanceof ApiError && err.status === 409) setSave({ kind: "conflict" });
          else
            setSave({
              kind: "error",
              message: err instanceof TypeError ? "Can't reach the server." : (err as Error).message,
            });
        }
      })();
      await inFlight.current;
      inFlight.current = null;
    }
    if (ok) setSave({ kind: "saved" });
    return ok;
  }, []);

  const setData = useCallback(
    (update: (d: ResumeData) => ResumeData) => {
      setDataState((d) => {
        const next = update(d);
        latest.current = next;
        return next;
      });
      dirty.current = true;
      setSave((s) => (s.kind === "conflict" ? s : { kind: "unsaved" }));
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), DEBOUNCE_MS);
    },
    [flush],
  );

  /** Save anything pending, then mark the profile reviewed. */
  const confirm = useCallback(async () => {
    if (!(await flush())) return null;
    const confirmed = await api.confirmProfile(version.current);
    setReviewedAt(confirmed.reviewed_at);
    setNotes(confirmed.notes);
    return confirmed;
  }, [flush]);

  // Don't let someone close the tab on an unsaved edit.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty.current || inFlight.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  return { data, setData, checks, notes, reviewedAt, save, flush, confirm };
}
