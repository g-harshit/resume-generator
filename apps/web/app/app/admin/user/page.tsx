"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ACTION_LABEL, AdminError, ago, card, Pill, when } from "@/components/admin/shared";
import { Loading } from "@/components/loading";
import { type AdminUserDetail, api } from "@/lib/api";

export default function AdminUserPage() {
  // useSearchParams (?id=) needs a Suspense boundary.
  return (
    <Suspense fallback={<Loading />}>
      <Detail />
    </Suspense>
  );
}

const button = "h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm hover:bg-sunken disabled:opacity-50";

function Detail() {
  const id = Number(useSearchParams().get("id"));
  const router = useRouter();
  const [d, setD] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api.admin
      .user(id)
      .then((r) => !cancelled && setD(r))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function act(what: string, run: () => Promise<AdminUserDetail>) {
    setBusy(what);
    setProblem(null);
    try {
      setD(await run());
    } catch (e) {
      setProblem((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("delete");
    setProblem(null);
    try {
      await api.admin.remove(id, confirm);
      router.replace("/app/admin");
    } catch (e) {
      setProblem((e as Error).message);
      setBusy(null);
    }
  }

  if (!id) return <p className="text-muted">No user chosen.</p>;
  if (error) return <AdminError error={error} />;
  if (!d) return <Loading />;
  const u = d.user;
  const sections = Object.entries(d.profile_sections).filter(([, n]) => n > 0);

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href="/app/admin" className="text-sm">
          ← All users
        </Link>
        <h1 className="flex flex-wrap items-center gap-3 font-display text-4xl">
          {u.name}
          {u.disabled && <Pill tone="warn">disabled</Pill>}
          {d.is_admin && <Pill tone="accent">admin</Pill>}
        </h1>
        <p className="text-muted">{u.email}</p>
      </div>

      <section aria-label="Account" className={`${card} grid grid-cols-2 gap-x-6 gap-y-3 p-5 text-sm sm:grid-cols-4`}>
        <Fact label="Sign-in" value={u.sign_in.map((m) => (m === "google" ? "Google" : "Password")).join(" + ") || "—"} />
        <Fact label="Email" value={u.email_verified ? "Verified" : "Not verified"} />
        <Fact label="Joined" value={when(u.created_at)} />
        <Fact label="Last seen" value={ago(u.last_seen_at)} />
        <Fact label="Profile" value={u.profile === "none" ? "None yet" : u.profile === "draft" ? "Draft (not confirmed)" : "Confirmed"} />
        <Fact label="Profile updated" value={when(d.profile_updated_at)} />
        <Fact
          label="Profile has"
          value={sections.length ? sections.map(([k, n]) => `${n} ${k}`).join(", ") : "—"}
          wide
        />
      </section>

      <section aria-label="Actions" className={`${card} flex flex-col gap-3 p-5`}>
        <h2 className="text-[15px] font-semibold">Actions</h2>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy !== null} onClick={() => act("signout", () => api.admin.signOut(id))} className={button}>
            {busy === "signout" ? "Signing out…" : "Sign out everywhere"}
          </button>
          {u.disabled ? (
            <button type="button" disabled={busy !== null} onClick={() => act("enable", () => api.admin.enable(id))} className={button}>
              {busy === "enable" ? "Enabling…" : "Enable account"}
            </button>
          ) : (
            <button type="button" disabled={busy !== null} onClick={() => act("disable", () => api.admin.disable(id))} className={button}>
              {busy === "disable" ? "Disabling…" : "Disable account"}
            </button>
          )}
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => setDeleting(true)}
            className="h-10 rounded-lg border border-warn bg-surface px-3 text-sm text-warn-ink hover:bg-warn-soft disabled:opacity-50"
          >
            Delete account…
          </button>
        </div>
        <p className="text-xs text-muted">
          Disabling signs them out and blocks signing in until enabled. Deleting removes the account,
          its profile, resumes, jobs and uploaded files for good.
        </p>
        {deleting && (
          <div role="alertdialog" aria-label="Delete this account?" className="flex flex-col gap-2 rounded-lg bg-warn-soft p-4 text-sm text-warn-ink">
            <p>
              This can&apos;t be undone. Type <strong>{u.email}</strong> to confirm.
            </p>
            <div className="flex flex-wrap gap-2">
              <input
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-label="Type the account's email to confirm"
                className="h-10 min-w-64 flex-1 rounded-lg border border-warn bg-surface px-3 text-ink"
              />
              <button
                type="button"
                disabled={busy !== null || confirm.trim().toLowerCase() !== u.email}
                onClick={remove}
                className="h-10 rounded-lg bg-warn px-3 font-medium text-white disabled:opacity-50"
              >
                {busy === "delete" ? "Deleting…" : "Delete for good"}
              </button>
              <button type="button" onClick={() => setDeleting(false)} className="h-10 rounded-lg px-3 hover:bg-surface">
                Cancel
              </button>
            </div>
          </div>
        )}
        {problem && <p role="alert" className="text-sm text-warn-ink">{problem}</p>}
      </section>

      <List title={`Resumes · ${d.resumes.length}`} empty="No resumes yet.">
        {d.resumes.map((r) => (
          <li key={r.id} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2.5 text-sm">
            <span className="font-medium">{r.title}</span>
            <Pill>{r.template}</Pill>
            {r.has_cover_letter && <Pill tone="good">cover letter</Pill>}
            <span className="ml-auto text-xs text-muted">made {when(r.created_at)} · edited {ago(r.updated_at)}</span>
          </li>
        ))}
      </List>

      <List title={`Jobs · ${d.jobs.length}`} empty="No jobs yet.">
        {d.jobs.map((j) => (
          <li key={j.id} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2.5 text-sm">
            <span className="font-medium">{j.title || "Untitled job"}</span>
            {j.company && <span className="text-muted">{j.company}</span>}
            {j.source === "extension" && <Pill>extension</Pill>}
            <span className="ml-auto text-xs text-muted">{when(j.created_at)}</span>
          </li>
        ))}
      </List>

      <List title={`Uploads · ${d.uploads.length}`} empty="No uploads.">
        {d.uploads.map((f) => (
          <li key={f.id} className="flex flex-col gap-1 px-4 py-2.5 text-sm">
            <span className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-medium">{f.filename}</span>
              <span className="text-xs text-muted">{Math.round(f.size_bytes / 1024)} KB</span>
              <Pill tone={f.status === "done" ? "good" : f.status === "failed" ? "warn" : "muted"}>{f.status}</Pill>
              <span className="ml-auto text-xs text-muted">{when(f.created_at)}</span>
            </span>
            {f.error && <span className="text-warn-ink">{f.error}</span>}
          </li>
        ))}
      </List>

      <List title="Admin actions on this account" empty="None.">
        {d.actions.map((a, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2.5 text-sm">
            <span className="font-medium">{ACTION_LABEL[a.action] ?? a.action}</span>
            <span className="text-xs text-muted">by {a.admin_email}</span>
            <span className="ml-auto text-xs text-muted">{when(a.created_at)}</span>
          </li>
        ))}
      </List>
    </div>
  );
}

function Fact({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`flex flex-col gap-0.5 ${wide ? "col-span-2" : ""}`}>
      <span className="text-xs text-muted">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function List({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="text-[15px] font-semibold">{title}</h2>
      {children.length ? (
        <ul className={`${card} divide-y divide-sunken`}>{children}</ul>
      ) : (
        <p className="text-sm text-muted">{empty}</p>
      )}
    </section>
  );
}
