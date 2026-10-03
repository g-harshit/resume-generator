import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/config";

// Written out at build time: the site is deployed as static files.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", "/register", "/login"].map((path) => ({ url: `${SITE_URL}${path}` }));
}
