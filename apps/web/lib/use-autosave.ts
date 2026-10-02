"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

const DEBOUNCE_MS = 800;

export type SaveState =
  | { kind: "saved" }
  | { kind: "unsaved" }
  | { kind: "saving" }
  | { kind: "error"; message: string }
  | { kind: "conflict" };

/**
 * Local editing state, saved automatically with optimistic versioning.
 *
 * Saves are debounced and never overlap: an edit made while a save is in flight is
 * saved right after it, with the latest data. A save's response updates the version
 * (and whatever `onSaved` takes from it) but never the data being edited, so typing
 * isn't clobbered. A 409 means someone else saved first: the state becomes
 * "conflict" and stays there until the page reloads.
 *
 * Used by the profile editor and the resume editor.
 */
export function useAutosave<T, R extends { version: number }>({
  initial,
  version: initialVersion,
  save: saveFn,
  onSaved,
}: {
  initial: T;
  version: number;
  save: (version: number, data: T) => Promise<R>;
  onSaved?: (saved: R) => void;
}) {
  const [data, setDataState] = useState<T>(initial);
  const [save, setSave] = useState<SaveState>({ kind: "saved" });

  const latest = useRef(initial);
  const version = useRef(initialVersion);
  const dirty = useRef(false);
  const inFlight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Kept current so the stable callbacks below always call the newest versions.
  const saveRef = useRef(saveFn);
  const onSavedRef = useRef(onSaved);
  useEffect(() => {
    saveRef.current = saveFn;
    onSavedRef.current = onSaved;
  });

  /** Save until nothing is pending. Resolves false if a save failed. */
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
          const saved = await saveRef.current(version.current, latest.current);
          version.current = saved.version;
          onSavedRef.current?.(saved);
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
    (update: (d: T) => T) => {
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

  /** Take data the server produced (a re-tailor, say) as the new saved state. */
  const replace = useCallback((next: T, nextVersion: number) => {
    if (timer.current) clearTimeout(timer.current);
    latest.current = next;
    version.current = nextVersion;
    dirty.current = false;
    setDataState(next);
    setSave({ kind: "saved" });
  }, []);

  const currentVersion = useCallback(() => version.current, []);

  // Don't let someone close the tab on an unsaved edit.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty.current || inFlight.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  return { data, setData, save, flush, replace, version: currentVersion };
}
