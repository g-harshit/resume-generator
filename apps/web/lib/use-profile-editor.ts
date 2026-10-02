"use client";

import { useCallback, useState } from "react";
import { api, type Check, type Note, type Profile } from "@/lib/api";
import { useAutosave } from "@/lib/use-autosave";

export type { SaveState } from "@/lib/use-autosave";

/** A profile, saved automatically, plus its live checks and parse notes. */
export function useProfileEditor(initial: Profile) {
  const [checks, setChecks] = useState<Check[]>(initial.checks);
  const [notes, setNotes] = useState<Note[]>(initial.notes);
  const [reviewedAt, setReviewedAt] = useState(initial.reviewed_at);

  const { data, setData, save, flush, version } = useAutosave({
    initial: initial.data,
    version: initial.version,
    save: api.saveProfile,
    onSaved: (saved: Profile) => {
      setChecks(saved.checks);
      setNotes(saved.notes);
    },
  });

  /** Save anything pending, then mark the profile reviewed. */
  const confirm = useCallback(async () => {
    if (!(await flush())) return null;
    const confirmed = await api.confirmProfile(version());
    setReviewedAt(confirmed.reviewed_at);
    setNotes(confirmed.notes);
    return confirmed;
  }, [flush, version]);

  return { data, setData, checks, notes, reviewedAt, save, flush, confirm };
}
