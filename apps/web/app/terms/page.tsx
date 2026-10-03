import type { Metadata } from "next";
import { LegalPage } from "@/components/legal-page";
import { APP_NAME, CONTACT_EMAIL } from "@/lib/config";

export const metadata: Metadata = { title: "Terms of service" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of service" updated="3 October 2026">
      <p>By using {APP_NAME} you agree to these terms.</p>

      <h2>Your content</h2>
      <p>
        You own your resume and everything you add. You let us process it only to provide
        the service to you (see the <a href="/privacy">privacy policy</a>). Only upload
        information about yourself that you have the right to share.
      </p>

      <h2>Accuracy is yours to check</h2>
      <p>
        {APP_NAME} is built not to add skills, employers, dates or numbers that aren&apos;t
        in your profile, and checks every change against it. It is still software: read
        every resume and cover letter before you send it. You are responsible for what you
        submit to employers.
      </p>

      <h2>Fair use</h2>
      <p>
        Don&apos;t misuse the service: no attempts to break it, get into other people&apos;s
        accounts, or automate it at scale. Daily limits apply to AI features. We may
        suspend accounts that misuse it.
      </p>

      <h2>The service</h2>
      <p>
        We work to keep {APP_NAME} available and your data safe, but it is provided as is,
        without guarantees that it will always be available or error-free, or that it will
        get you a job. To the extent the law allows, we aren&apos;t liable for indirect
        losses from using it.
      </p>

      <h2>Ending</h2>
      <p>
        You can stop using {APP_NAME} at any time and ask for your account to be deleted (
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>). If these terms change,
        we&apos;ll update this page and the date above.
      </p>
    </LegalPage>
  );
}
