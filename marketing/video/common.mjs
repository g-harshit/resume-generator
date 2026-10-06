import { createRequire } from "module";
import fs from "fs";
import path from "path";
// Playwright comes from the extension package's dev dependencies.
const pw = createRequire(new URL("../../apps/extension/package.json", import.meta.url))("playwright");
export const chromium = { launch: (o = {}) => pw.chromium.launch({ ...o, args: ["--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights", ...(o.args || [])] }) };
export const here = new URL(".", import.meta.url).pathname;
// Everything a run makes (demo PDF, test account, frames, the .mp4) goes here; git-ignored.
export const dir = here + "output/";
fs.mkdirSync(dir, { recursive: true });
// Build first: NEXT_PUBLIC_APP_NAME="QuickFit CV" pnpm build:web
export const OUT = new URL("../../apps/web/out", import.meta.url).pathname;
const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".txt": "text/plain", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".json": "application/json", ".webp": "image/webp", ".jpg": "image/jpeg" };
// Chrome blocks a page from calling the local API without this.
// Serve the static export as if it were http://localhost:3100 (the origin the API allows).
export async function serveStatic(ctx) {
  await ctx.route("http://localhost:3100/**", (route) => {
    const u = new URL(route.request().url());
    let p = path.join(OUT, decodeURIComponent(u.pathname));
    if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "index.html");
    if (!fs.existsSync(p) && fs.existsSync(p + ".html")) p += ".html";
    if (!fs.existsSync(p)) return route.fulfill({ status: 404, body: "nf" });
    route.fulfill({ status: 200, contentType: types[path.extname(p)] || "application/octet-stream", body: fs.readFileSync(p) });
  });
}
export const account = () => JSON.parse(fs.readFileSync(dir + "account.json"));
