import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "wxt";

// Where the extension talks to. Dev defaults; set WXT_API_URL / WXT_WEB_URL to build
// for production. (Read in code as import.meta.env.WXT_API_URL / WXT_WEB_URL.)
const WEB_URL = process.env.WXT_WEB_URL ?? "http://localhost:3100";
const APP_NAME = process.env.WXT_APP_NAME ?? "Tailor";
// The public half of a key pair, so an unpacked build has the same ID on every machine
// (pjddbiflcebndfljpckcgkigckfpmndm). Only the public key is here.
const KEY =
  "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmp/mGNdzqqlEOMLEvSooKyCOL+pRjwRf8d/idhqcxDZShaHs/5kN8uLKn8Zf60ZxLfn9MeqduJKdPGi0/KGRXm1qYhCp1Z26hcFQ1XUsBAfA000Lt9UPT2hyEN6Rof+CmJGTBumcMYqvRpWDOcIDMzTCh0DgkbU79KqfmEcKYSWppna9SwBy1OeLluwTcw74avZD+vkPNe69XrwtXKWyqnxXpDERsk7kI3OKRMpOaA5WKqCNgRUyWQROBhjvZmGSlM5Mbj9c5c2XILoO96TjejAGmYqBU6w+hWGcJ6kn32QULmzMesuFhsuV4Z1KBYwHzKO4fPGyEf+Lm1VTiinrEQIDAQAB";

// The Chrome Web Store build: no `key` (the Store rejects it and gives the extension
// its own ID; the website and API are told that ID too — NEXT_PUBLIC_EXTENSION_IDS).
const FOR_STORE = process.env.WXT_STORE === "1";
// The automated real-Chromium test (e2e/run.mjs): a test can't click Chrome's own
// permission prompt, so that build may read localhost pages without asking.
const FOR_E2E = process.env.WXT_E2E === "1";

// Match patterns can't carry a port, so dev allows the localhost hosts on any port.
const webOrigins =
  new URL(WEB_URL).hostname === "localhost"
    ? ["http://localhost/*", "http://127.0.0.1/*"]
    : [`${new URL(WEB_URL).origin}/*`];

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  vite: () => ({ plugins: [tailwindcss()] }),
  manifest: {
    name: APP_NAME,
    description: "Tailor your resume to the job posting you're looking at.",
    // A fixed ID, so the website and the API know which extension to trust.
    ...(FOR_STORE ? {} : { key: KEY }),
    ...(FOR_E2E ? { host_permissions: ["http://localhost/*"] } : {}),
    // No access to any site up front. activeTab covers the tab where the toolbar icon
    // was clicked; anything else is asked for, per site, when the person clicks "Read
    // this page" (optional_host_permissions).
    permissions: ["sidePanel", "storage", "activeTab", "scripting"],
    optional_host_permissions: ["https://*/*", "http://*/*"],
    // Only our website may hand the extension a login.
    externally_connectable: { matches: webOrigins },
    action: { default_title: `${APP_NAME}: tailor your resume to this job` },
  },
});
