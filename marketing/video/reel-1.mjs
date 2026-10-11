// Reel 1: "Tailor a resume in 30 seconds" — paste a job, see the keywords, rewrite a line,
// download the PDF.
import fs from "fs";
import { here } from "./common.mjs";
import { startReel, LOGO } from "./reel.mjs";

const r = await startReel("reel-1");
const { p, wait, cap, card, tap, scrollTo, scrollToEl } = r;
await r.start("http://localhost:3100/app/new/", "#jd");

// Hook
await card(`<h1>Stop sending the <mark>same resume</mark> to every job</h1><p>Tailor it to the job in 30 seconds 👇</p>`);
await wait(2600);
await card(null);
await wait(350);

// 1. Paste the job
await cap(`1. Paste the job description`);
const jd = fs.readFileSync(here + "jd.txt", "utf8");
await tap(p.locator("#jd"));
await p.locator("#jd").pressSequentially(jd.slice(0, 48), { delay: 18 });
await p.fill("#jd", jd);
await wait(500);
const read = p.locator("button[type=submit]");
await scrollToEl(read, 420, 500);
await tap(read);
await wait(900);
r.pause();
await p.waitForSelector("text=Choose a template", { timeout: 120000 });
await wait(400);
r.resume();

// Keywords
await cap(`See what the job wants <b>✓</b><br>and what you're missing`);
await scrollToEl(p.getByText("What we found", { exact: false }).first(), 185, 1100);
await wait(3000);
await cap(`It never adds a skill<br>you don't have`);
await scrollToEl(p.getByText("Your profile covers"), 400, 900);
await wait(2600);

// 2. Template
await tap(p.locator("a", { hasText: "Choose a template" }));
await cap(`2. Pick an ATS-friendly template`);
await p.waitForSelector("text=Make my resume with");
await wait(1700);
const make = p.locator("button", { hasText: "Make my resume with" });
await scrollToEl(make, 520, 700);
await wait(400);
await tap(make);
await wait(700);
r.pause();
await p.waitForURL(/resume\/\?id=/, { timeout: 120000, waitUntil: "commit" });
await p.locator("button", { hasText: "Rewrite for this job" }).first().waitFor({ timeout: 120000 });
await wait(2500);
r.resume();

// 3. Rewrite chosen lines
await cap(`3. Rewrite only the lines<br>you choose`);
const line = p.locator("textarea").filter({ hasText: "dashboards" }).first();
await scrollToEl(line, 300, 1300);
await wait(1300);
await tap(p.locator("button", { hasText: "Rewrite for this job" }).first());
await wait(900);
r.pause();
await p.getByText("Reworded for this job").first().waitFor({ timeout: 120000 });
await wait(600);
await scrollToEl(line, 300, 10);
await line.evaluate((el) => el.classList.add("reel-glow"));
await wait(300);
r.resume();
await cap(`Uses the job's words.<br>Keeps <b>your</b> facts.`);
await wait(3200);

// 4. Download
await cap(`4. Download a clean PDF`);
await scrollTo(0, 1100);
await wait(500);
const dl = p.waitForEvent("download", { timeout: 60000 }).catch(() => null);
await tap(p.locator("button", { hasText: "Download PDF" }));
await wait(700);
r.pause();
await dl;
await wait(300);
r.resume();
await wait(1400);

// End card
await cap(null);
await card(`<div class="brand">${LOGO}QuickFit CV</div><h1>One resume per job,<br>in your own words</h1><div class="pill">quickfitcv.com</div><p>Free to try · link in bio</p>`);
await wait(3400);
await r.finish();
