import type { Metadata } from "next";
import { IBM_Plex_Sans, Instrument_Serif } from "next/font/google";
import Script from "next/script";
import { AuthProvider } from "@/lib/auth-context";
import { APP_NAME } from "@/lib/config";
import "./globals.css";

// Google Analytics. Unset in dev and in any deploy that has no NEXT_PUBLIC_GA_ID,
// so local runs and previews do not post events into the real property - which
// would be indistinguishable from traffic once it arrived.
//
// The shape is checked rather than trusted: a typo here is a tag that loads,
// reports nothing, and looks exactly like a site with no visitors. A measurement
// id is public (it ships in the page source), so there is nothing to protect -
// it lives in an env var to stay configurable, not to stay secret.
const rawGaId = process.env.NEXT_PUBLIC_GA_ID;
const GA_ID = rawGaId && /^G-[A-Z0-9]+$/.test(rawGaId) ? rawGaId : undefined;

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: "Tailor your resume to every job — ATS-friendly, built from your own profile.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${instrumentSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {GA_ID && (
          <>
            {/* afterInteractive: analytics must never delay first paint. */}
            <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
            <Script id="ga-init" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
            </Script>
          </>
        )}
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
