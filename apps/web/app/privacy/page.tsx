import type { Metadata } from "next";
import { LegalPage } from "@/components/legal-page";
import { APP_NAME, CONTACT_EMAIL } from "@/lib/config";

export const metadata: Metadata = { title: "Privacy policy" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy" updated="4 October 2026">
      <p>
        {APP_NAME} turns the resume you already have into a profile, and tailors it to job
        descriptions you choose. This page says what we keep, why, who helps us run the
        service, and how to have your data deleted.
      </p>

      <h2>What we keep</h2>
      <ul>
        <li>
          <strong>Your account:</strong> name, email address, and a password hash (never the
          password itself). If you sign in with Google, we receive your name, email address
          and Google account ID — nothing else from your Google account.
        </li>
        <li>
          <strong>What you upload or write:</strong> your resume file, the profile made
          from it, job descriptions you paste or read with the extension, and the resumes and
          cover letters made from them, with their edit history.
        </li>
        <li>
          <strong>From the Chrome extension:</strong> the text of the job posting on the page
          you open it on — only that page, only when you use it — to read the job. It
          doesn&apos;t look at other tabs or your browsing history.
        </li>
        <li>
          <strong>Security records:</strong> failed sign-in attempts and similar events,
          with the IP address they came from, kept for one day to stop abuse.
        </li>
      </ul>
      <p>
        We don&apos;t use advertising or tracking cookies. Your browser stores a sign-in
        token so you stay signed in; signing out removes it.
      </p>

      <h2>How it&apos;s used</h2>
      <p>
        Only to provide the service: reading your resume into a profile, matching it to a
        job, writing tailored resumes and cover letters, and keeping your account secure.
        We don&apos;t sell your data or use it for advertising.
      </p>

      <h2>Who helps run the service</h2>
      <ul>
        <li>
          <strong>OpenAI</strong> reads your resume and job descriptions to structure and
          tailor them. We send only what each step needs (not your email or phone), and ask
          OpenAI not to store the requests.
        </li>
        <li>
          <strong>Render</strong> hosts the website and the application (Singapore).
        </li>
        <li>
          <strong>Aiven</strong> hosts the database (India).
        </li>
        <li>
          <strong>Cloudflare</strong> stores uploaded files (R2, private).
        </li>
        <li>
          <strong>Google</strong> handles &ldquo;Sign in with Google&rdquo;, if you use it.
        </li>
      </ul>

      <h2>Your choices</h2>
      <ul>
        <li>You can edit your profile, and delete resumes, at any time in the app.</li>
        <li>
          To have your account and everything in it deleted, or to get a copy of your data,
          email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> from the address on
          your account. We act on it within 30 days.
        </li>
      </ul>

      <h2>Changes</h2>
      <p>
        If this policy changes, we&apos;ll update this page and the date above. Questions:{" "}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalPage>
  );
}
