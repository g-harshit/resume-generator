import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/config";

// Written out at build time: the site is deployed as static files.
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    // The signed-in app and the extension handoff aren't for search engines.
    rules: { userAgent: "*", allow: "/", disallow: ["/app", "/extension", "/reset-password"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
