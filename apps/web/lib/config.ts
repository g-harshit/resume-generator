// The product has no name yet. Everything user-facing reads it from here
// (and the API from its APP_NAME setting), so renaming is a one-line change.
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Tailor";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

// The Chrome extension's ID, fixed by the public key in apps/extension/wxt.config.ts.
// The Chrome Web Store gives a published extension its own; set this for that build.
export const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID ?? "pjddbiflcebndfljpckcgkigckfpmndm";

// Where the site is served from publicly (canonical links, sitemap). Set for deploys.
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";
