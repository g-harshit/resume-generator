// The extension, end to end, in real Chromium: sign-in handoff from the website, reading
// a job posting, tailoring, downloading the PDF. Against the local stack:
//
//   make dev                                   # API on 8100, website on 3100
//   E2E_TOKEN=<a local test account's token> pnpm --filter @rg/extension e2e
//
// Builds the extension with WXT_E2E=1 (localhost readable without Chrome's permission
// prompt, which a test can't click). Saves screenshots to e2e/out/ (also used for the
// Chrome Web Store listing).
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EXT = path.resolve(HERE, "../.output/chrome-mv3");
const OUT = path.resolve(HERE, "out");
const WEB = "http://localhost:3100";
const JOB_PORT = 3399;
const EXPECTED_ID = "pjddbiflcebndfljpckcgkigckfpmndm";
const TOKEN = process.env.E2E_TOKEN;
if (!TOKEN) throw new Error("Set E2E_TOKEN to a signed-in local test account's token.");

const step = (msg) => console.log(`• ${msg}`);
function check(ok, msg) {
  if (!ok) throw new Error(`FAILED: ${msg}`);
  console.log(`  ✓ ${msg}`);
}

step("build the extension (test build)");
execSync("pnpm exec wxt build", {
  cwd: path.resolve(HERE, ".."),
  stdio: "inherit",
  env: { ...process.env, WXT_E2E: "1", WXT_APP_NAME: "QuickFit CV" },
});

// A job posting like the ones on careers pages: structured data plus visible text.
const job = readFileSync(path.resolve(HERE, "job.html"), "utf8");
const server = http.createServer((_, res) => res.writeHead(200, { "Content-Type": "text/html" }).end(job));
await new Promise((r) => server.listen(JOB_PORT, r));

mkdirSync(OUT, { recursive: true });
const context = await chromium.launchPersistentContext(path.join(tmpdir(), `qf-e2e-${Date.now()}`), {
  channel: "chromium",
  headless: true,
  acceptDownloads: true,
  viewport: { width: 1280, height: 800 },
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
});

try {
  let [worker] = context.serviceWorkers();
  worker ??= await context.waitForEvent("serviceworker");
  const id = new URL(worker.url()).host;
  check(id === EXPECTED_ID, `extension loaded with the fixed ID (${id})`);

  step("sign in on the website, and hand the login to the extension");
  const site = await context.newPage();
  await site.goto(WEB);
  await site.evaluate((t) => localStorage.setItem("rg:token", t), TOKEN);
  await site.goto(`${WEB}/extension/connect`);
  await site.getByText("The extension is signed in.").waitFor({ timeout: 60_000 });
  check(true, "website says the extension is signed in");
  const stored = await worker.evaluate(() => chrome.storage.local.get("rg:token"));
  check(stored["rg:token"] === TOKEN, "extension stored the login");

  step("open a job posting, and the side panel beside it");
  const posting = await context.newPage();
  await posting.goto(`http://localhost:${JOB_PORT}/careers/senior-backend-engineer`);
  const panel = await context.newPage();
  await panel.setViewportSize({ width: 400, height: 800 });
  await panel.goto(`chrome-extension://${id}/sidepanel.html`);
  await panel.getByText(/Signed in as|Sign out/).first().waitFor({ timeout: 60_000 });
  check(true, "panel is signed in (it asked the API who this is)");
  // The panel reads the active tab in its window: make the posting active.
  await posting.bringToFront();
  await panel.getByText("Job found on this page").waitFor({ timeout: 30_000 });
  const found = await panel.locator("section[aria-label='This page']").innerText();
  check(/Senior Backend Engineer/.test(found), "panel read the job title from the page");
  await panel.screenshot({ path: path.join(OUT, "panel-job-found.png") });
  await posting.screenshot({ path: path.join(OUT, "posting.png") });

  step("a page the extension may not read yet offers to allow job sites");
  // The test build may read localhost only; 127.0.0.1 is "another site".
  const elsewhere = await context.newPage();
  await elsewhere.goto(`http://127.0.0.1:${JOB_PORT}/careers/elsewhere`);
  await elsewhere.bringToFront();
  await panel.getByRole("button", { name: "Allow on job sites" }).waitFor({ timeout: 30_000 });
  check(true, "panel asks to allow job sites instead of a dead end");
  await panel.screenshot({ path: path.join(OUT, "panel-allow.png") });
  await elsewhere.close();
  await posting.bringToFront();
  await panel.getByText("Job found on this page").waitFor({ timeout: 30_000 });
  check(true, "back on the posting, the panel reads it again");

  step("tailor (real model calls: ~20–60 s)");
  await panel.getByRole("button", { name: "Tailor my resume" }).click();
  await panel.getByText("Your resume is ready").waitFor({ timeout: 180_000 });
  check(true, "resume tailored");
  await panel.screenshot({ path: path.join(OUT, "panel-ready.png") });

  step("download the PDF");
  const [download] = await Promise.all([
    panel.waitForEvent("download", { timeout: 60_000 }),
    panel.getByRole("button", { name: "Download PDF" }).click(),
  ]);
  const file = path.join(OUT, download.suggestedFilename());
  await download.saveAs(file);
  const head = readFileSync(file).subarray(0, 5).toString();
  check(head === "%PDF-", `PDF downloaded (${download.suggestedFilename()})`);

  console.log("\nAll good.");
} finally {
  await context.close();
  server.close();
}
