import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/config";

export default function robots(): MetadataRoute.Robots {
  return {
    // The signed-in app and the extension handoff aren't for search engines.
    rules: { userAgent: "*", allow: "/", disallow: ["/app", "/extension", "/reset-password"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
