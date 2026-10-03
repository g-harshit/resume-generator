// Everything user-facing reads the name from here (and the API from its APP_NAME
// setting), so renaming is a one-line change. Production sets it in render.yaml.
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Tailor";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

// The Chrome extension's IDs, comma-separated: the fixed one an unpacked build has (from
// the public key in apps/extension/wxt.config.ts), and the Chrome Web Store's once it's
// published there. The sign-in handoff tries each.
export const EXTENSION_IDS = (process.env.NEXT_PUBLIC_EXTENSION_IDS ?? "pjddbiflcebndfljpckcgkigckfpmndm")
  .split(",")
  .map((id) => id.trim())
  .filter(Boolean);

// "Sign in with Google": the OAuth client ID (public). Unset hides the button.
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

// Where people write to us (privacy requests, support).
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "gharshit1237@gmail.com";

// Where the site is served from publicly (canonical links, sitemap). Set for deploys.
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";
