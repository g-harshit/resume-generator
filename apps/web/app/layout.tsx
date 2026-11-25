import type { Metadata } from "next";
import { IBM_Plex_Sans, Instrument_Serif } from "next/font/google";
import Script from "next/script";
import { AuthProvider } from "@/lib/auth-context";
import { APP_NAME, SITE_URL } from "@/lib/config";
import "./globals.css";

// Google Analytics, property "quickfitcv.com". The tag renders only for a build
// of the real site, so local runs and previews do not post events into the
// property - which would be indistinguishable from traffic once it arrived.
//
// "The real site" is decided by SITE_URL, not by NEXT_PUBLIC_GA_ID being set.
// It used to be the latter, with the id only in render.yaml - and Render applies
// a variable added to a Blueprint only when the Blueprint is synced, which a
// deploy does not do. So the site shipped for six weeks with no tag at all and
// every build green: an unset id and a site with no visitors look the same. The
// id is public (it is in the page source of every page), so it can live here,
// where a deploy cannot lose it. NEXT_PUBLIC_GA_ID still overrides it.
//
// The shape is checked rather than trusted: a typo is a tag that loads, reports
// nothing, and again looks exactly like a site with no visitors.
const PRODUCTION_HOST = "quickfitcv.com";
const PRODUCTION_GA_ID = "G-ZRGH9G0GJD";

function siteHost(): string | undefined {
  try {
    return new URL(SITE_URL).hostname.replace(/^www\./, "");
  } catch {
    return undefined;
  }
}

const rawGaId =
  process.env.NEXT_PUBLIC_GA_ID || (siteHost() === PRODUCTION_HOST ? PRODUCTION_GA_ID : undefined);
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
