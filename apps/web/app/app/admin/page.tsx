"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ACTION_LABEL, AdminError, ago, card, Pill, when } from "@/components/admin/shared";
import { Loading } from "@/components/loading";
import { type AdminAction, type AdminUserRow, api, type FailedUpload, saveFile } from "@/lib/api";

type Tab = "overview" | "users" | "uploads" | "log";
const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["users", "Users"],
  ["uploads", "Failed uploads"],
  ["log", "Admin log"],
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("overview");
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-4xl">Admin</h1>
        <p className="text-sm text-muted">Who&apos;s using the app, and account actions. Resume text stays private.</p>
      </div>
      <div role="tablist" aria-label="Admin sections" className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === id ? "border-accent font-semibold text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "overview" && <Overview />}
      {tab === "users" && <Users />}
      {tab === "uploads" && <Failed />}
      {tab === "log" && <Log />}
    </div>
  );
}

function useLoad<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let cancelled = false;
    load()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [load]);
  return { data, error };
}

// --- overview ---------------------------------------------------------------------------

function Stat({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className={`${card} flex flex-col gap-0.5 p-4`}>
      <span className="text-sm text-muted">{label}</span>
      <span className="text-3xl font-semibold">{value.toLocaleString()}</span>
      {sub && <span className="text-xs text-muted">{sub}</span>}
    </div>
  );
}

function Overview() {
  const { data: s, error } = useLoad(api.admin.stats);
  if (error) return <AdminError error={error} />;
  if (!s) return <Loading />;
  const peak = Math.max(1, ...s.signups_by_day.map((d) => d.count));
  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Users" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Users" value={s.users} sub={`${s.disabled_users} disabled`} />
        <Stat label="New today" value={s.users_today} sub={`${s.users_7d} this week · ${s.users_30d} in 30 days`} />
        <Stat label="Active, last 7 days" value={s.active_7d} />
        <Stat label="Sign-in" value={s.google_users} sub={`with Google · ${s.password_users} with a password`} />
      </section>
      <section aria-label="Activity" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Profiles" value={s.profiles} sub={`${s.profiles_confirmed} confirmed`} />
        <Stat label="Resumes" value={s.resumes} sub={`${s.resumes_7d} this week · ${s.cover_letters} with a cover letter`} />
        <Stat label="Jobs read" value={s.jobs} sub={`${s.jobs_from_extension} from the extension`} />
        <Stat label="Uploads" value={s.uploads} sub={`${s.uploads_failed} failed`} />
      </section>
      <section aria-label="Sign-ups, last 30 days" className={`${card} flex flex-col gap-3 p-5`}>
        <h2 className="text-[15px] font-semibold">Sign-ups, last 30 days</h2>
        <div className="flex h-32 items-end gap-1">
          {s.signups_by_day.map((d) => (
            <div key={d.day} className="group relative flex h-full flex-1 items-end" title={`${d.day}: ${d.count}`}>
              <div
                className="w-full rounded-t bg-accent/80 group-hover:bg-accent"
                style={{ height: `${(d.count / peak) * 100}%`, minHeight: d.count ? 3 : 1 }}
              />
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-muted">
          <span>{s.signups_by_day[0]?.day}</span>
          <span>{s.signups_by_day.at(-1)?.day}</span>
        </div>
      </section>
    </div>
  );
}

// --- users ------------------------------------------------------------------------------

const PAGE = 50;

function Users() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => api.admin.users(query, offset, PAGE), [query, offset]);
  const { data, error } = useLoad(load);
  const [exporting, setExporting] = useState(false);

  // Search as they type, after a short pause.
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  async function exportCsv() {
    setExporting(true);
    try {
      saveFile(await api.admin.exportUsers(query));
    } finally {
      setExporting(false);
    }
  }

  if (error) return <AdminError error={error} />;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name or email"
          aria-label="Search users"
          className="h-10 w-full max-w-sm rounded-lg border border-line-strong bg-surface px-3 text-sm"
        />
        <span className="text-sm text-muted">{data ? `${data.total} users` : ""}</span>
        <button
          type="button"
          onClick={exportCsv}
          disabled={exporting}
          className="ml-auto h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm hover:bg-sunken disabled:opacity-50"
        >
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>
      {!data ? (
        <Loading />
      ) : (
        <div className={`${card} overflow-x-auto`}>
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="border-b border-line text-xs tracking-wide text-muted uppercase">
              <tr>
                <th className="px-4 py-2.5 font-medium">User</th>
                <th className="px-3 py-2.5 font-medium">Sign-in</th>
                <th className="px-3 py-2.5 font-medium">Joined</th>
                <th className="px-3 py-2.5 font-medium">Last seen</th>
                <th className="px-3 py-2.5 font-medium">Profile</th>
                <th className="px-3 py-2.5 text-right font-medium">Resumes</th>
                <th className="px-3 py-2.5 text-right font-medium">Jobs</th>
                <th className="px-4 py-2.5 text-right font-medium">Uploads</th>
              </tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <UserTableRow key={u.id} u={u} />
              ))}
              {data.users.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-muted">
                    No users match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {data && data.total > PAGE && (
        <div className="flex items-center gap-3 text-sm">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="h-9 rounded-md border border-line-strong px-3 disabled:opacity-40">
            Previous
          </button>
          <span className="text-muted">
            {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
          </span>
          <button type="button" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)} className="h-9 rounded-md border border-line-strong px-3 disabled:opacity-40">
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function UserTableRow({ u }: { u: AdminUserRow }) {
  return (
    <tr className="border-b border-sunken last:border-0 hover:bg-ground">
      <td className="px-4 py-2.5">
        <Link href={`/app/admin/user?id=${u.id}`} className="flex flex-col text-ink hover:text-ink">
          <span className="font-medium">
            {u.name} {u.disabled && <Pill tone="warn">disabled</Pill>}
          </span>
          <span className="text-xs text-muted">{u.email}</span>
        </Link>
      </td>
      <td className="px-3 py-2.5">
        <span className="flex flex-wrap gap-1">
          {u.sign_in.map((m) => (
            <Pill key={m}>{m === "google" ? "Google" : "Password"}</Pill>
          ))}
          {u.email_verified && <Pill tone="good">verified</Pill>}
        </span>
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap text-muted">{when(u.created_at)}</td>
      <td className="px-3 py-2.5 whitespace-nowrap text-muted">{ago(u.last_seen_at)}</td>
      <td className="px-3 py-2.5">
        <Pill tone={u.profile === "confirmed" ? "good" : u.profile === "draft" ? "warn" : "muted"}>{u.profile}</Pill>
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums">{u.resumes}</td>
      <td className="px-3 py-2.5 text-right tabular-nums">{u.jobs}</td>
      <td className="px-4 py-2.5 text-right tabular-nums">{u.uploads}</td>
    </tr>
  );
}

// --- failed uploads and log -------------------------------------------------------------

function Failed() {
  const { data, error } = useLoad(api.admin.failedUploads);
  if (error) return <AdminError error={error} />;
  if (!data) return <Loading />;
  if (!data.length) return <p className="text-muted">No failed uploads.</p>;
  return (
    <ul className={`${card} divide-y divide-sunken`}>
      {data.map((f: FailedUpload) => (
        <li key={f.id} className="flex flex-col gap-1 px-4 py-3 text-sm">
          <span className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-medium">{f.filename}</span>
            <Link href={`/app/admin/user?id=${f.user_id}`} className="text-xs">
              {f.user_email}
            </Link>
            <span className="ml-auto text-xs text-muted">{when(f.created_at)}</span>
          </span>
          <span className="text-warn-ink">{f.error || "No error message"}</span>
        </li>
      ))}
    </ul>
  );
}

function Log() {
  const { data, error } = useLoad(api.admin.log);
  if (error) return <AdminError error={error} />;
  if (!data) return <Loading />;
  if (!data.length) return <p className="text-muted">No admin actions yet.</p>;
  return (
    <ul className={`${card} divide-y divide-sunken`}>
      {data.map((a: AdminAction, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2.5 text-sm">
          <span className="font-medium">{ACTION_LABEL[a.action] ?? a.action}</span>
          {a.target_email && <span>{a.target_email}</span>}
          <span className="text-xs text-muted">by {a.admin_email}</span>
          <span className="ml-auto text-xs text-muted">{when(a.created_at)}</span>
        </li>
      ))}
    </ul>
  );
}
