"use client";

import { useRef, useState } from "react";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function UploadIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}

/** Drag-and-drop or click to pick one PDF/DOCX. The server re-checks type and size
 *  from the bytes; the checks here only save a pointless upload. */
export function ResumeDropzone({
  onFile,
  disabled = false,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function pick(file: File | undefined) {
    if (!file || disabled) return;
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setProblem("Upload a PDF or a Word (.docx) file. Older .doc files: save as .docx first.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setProblem("That file is over 5 MB.");
      return;
    }
    setProblem(null);
    onFile(file);
  }

  return (
    <div className="flex flex-col gap-3">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={`flex cursor-pointer flex-col items-center gap-3.5 rounded-2xl border-[1.5px] border-dashed bg-surface px-6 py-11 text-center transition-colors ${
          dragging ? "border-accent bg-accent-soft" : "border-[#9e998b]"
        } ${disabled ? "pointer-events-none opacity-60" : ""}`}
      >
        <span className="flex size-14 items-center justify-center rounded-full bg-accent-soft text-accent">
          <UploadIcon />
        </span>
        <span className="text-lg font-semibold">Drop your resume here</span>
        <span className="text-sm text-muted">PDF or Word (.docx), up to 5 MB</span>
        <span className="mt-1 inline-flex h-11 items-center rounded-[10px] bg-ink px-5 text-[15px] font-medium text-white">
          Choose file
        </span>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = ""; // choosing the same file again should still fire
          }}
        />
      </label>
      {problem && (
        <p role="alert" className="rounded-lg bg-warn-soft px-3 py-2.5 text-sm text-warn-ink">
          {problem}
        </p>
      )}
    </div>
  );
}
