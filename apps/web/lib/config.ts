// Everything user-facing reads the name from here (and the API from its APP_NAME
// setting), so renaming is a one-line change. Production sets it in render.yaml.
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Tailor";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

// The Chrome extension's ID, fixed by the public key in apps/extension/wxt.config.ts.
// The Chrome Web Store gives a published extension its own; set this for that build.
export const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID ?? "pjddbiflcebndfljpckcgkigckfpmndm";

// "Sign in with Google": the OAuth client ID (public). Unset hides the button.
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

// Where people write to us (privacy requests, support).
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "gharshit1237@gmail.com";

// Where the site is served from publicly (canonical links, sitemap). Set for deploys.
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";
