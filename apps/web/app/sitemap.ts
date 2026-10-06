import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/config";

// Written out at build time: the site is deployed as static files.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", "/ats-checker", "/register", "/login", "/privacy", "/terms"].map((path) => ({ url: `${SITE_URL}${path}` }));
}
