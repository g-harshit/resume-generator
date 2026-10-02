"use client";

import type { Link, ResumeData } from "@rg/schema";
import { removeAt, replaceAt, TextField } from "@/components/profile/fields";
import { newId } from "@/lib/ids";

type Basics = ResumeData["basics"];

/**
 * The top of this resume: name, job title and contact line. Each item can be left
 * off (and put back — the value stays), edited for this resume only, and links can
 * be added or removed. The profile isn't changed.
 */
export function HeaderEditor({
  basics,
  setBasics,
  hidden,
  setHidden,
  profileLinks,
}: {
  basics: Basics;
  setBasics: (update: (b: Basics) => Basics) => void;
  /** Header items left off: "headline", "location", "email", "phone", or a link id. */
  hidden: string[];
  setHidden: (update: (h: string[]) => string[]) => void;
  /** The profile's links, so one removed from this resume can be added back. */
  profileLinks: Link[];
}) {
  const shown = (key: string) => !hidden.includes(key);
  const toggle = (key: string, on: boolean) =>
    setHidden((h) => (on ? h.filter((k) => k !== key) : [...h.filter((k) => k !== key), key]));
  const set = (patch: Partial<Basics>) => setBasics((b) => ({ ...b, ...patch }));
  const setLinks = (links: Link[]) => set({ links });
  const missing = profileLinks.filter((p) => p.url && !basics.links.some((l) => l.id === p.id || l.url === p.url));

  const fields: { key: "headline" | "location" | "email" | "phone"; label: string; placeholder?: string }[] = [
    { key: "headline", label: "Job title", placeholder: "e.g. Backend Engineer" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "location", label: "Location", placeholder: "City, Country" },
  ];

  return (
    <section aria-label="Header" className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[15px] font-semibold">Header</h2>
        <span className="text-xs text-muted">Untick to leave off this resume</span>
      </div>

      <TextField label="Name" value={basics.name} onChange={(name) => set({ name })} />

      {fields.map(({ key, label, placeholder }) => (
        <div key={key} className="flex items-end gap-2">
          <input
            type="checkbox"
            aria-label={`Show ${label.toLowerCase()} on this resume`}
            checked={shown(key)}
            onChange={(e) => toggle(key, e.target.checked)}
            className="mb-3 size-4 shrink-0 accent-accent"
          />
          <TextField
            className={`flex-1 ${shown(key) ? "" : "opacity-50"}`}
            label={label}
            value={basics[key]}
            placeholder={placeholder}
            onChange={(value) => set({ [key]: value })}
          />
        </div>
      ))}

      <div className="flex flex-col gap-2 border-t border-sunken pt-3">
        <span className="text-[13px] text-muted">Links</span>
        {basics.links.map((link, i) => (
          <div key={link.id} className="flex items-end gap-2">
            <input
              type="checkbox"
              aria-label={`Show ${link.label || "this link"} on this resume`}
              checked={shown(link.id)}
              onChange={(e) => toggle(link.id, e.target.checked)}
              className="mb-3 size-4 shrink-0 accent-accent"
            />
            <TextField
              className={`w-28 shrink-0 ${shown(link.id) ? "" : "opacity-50"}`}
              label="Label"
              placeholder="LinkedIn"
              value={link.label}
              onChange={(label) => setLinks(replaceAt(basics.links, i, { ...link, label }))}
            />
            <TextField
              className={`min-w-0 flex-1 ${shown(link.id) ? "" : "opacity-50"}`}
              label="URL"
              value={link.url}
              onChange={(url) => setLinks(replaceAt(basics.links, i, { ...link, url }))}
            />
            <button
              type="button"
              aria-label={`Remove ${link.label || "link"} from this resume`}
              onClick={() => {
                setLinks(removeAt(basics.links, i));
                setHidden((h) => h.filter((k) => k !== link.id));
              }}
              className="mb-1 flex size-8 shrink-0 items-center justify-center rounded-md text-muted hover:bg-sunken hover:text-ink"
            >
              ×
            </button>
          </div>
        ))}
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          <button
            type="button"
            onClick={() => setLinks([...basics.links, { id: newId("lnk"), label: "", url: "" }])}
            className="self-start text-[13px] text-accent hover:underline"
          >
            + Add a link
          </button>
          {missing.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setLinks([...basics.links, { id: p.id, label: p.label, url: p.url }])}
              className="text-[13px] text-accent hover:underline"
            >
              + {p.label || p.url} (from your profile)
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs leading-normal text-muted">
        Changes here are for this resume only; your profile stays as it is.
      </p>
    </section>
  );
}
