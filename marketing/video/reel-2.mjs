// Reel 2: "Why the ATS skips you" — the job's skills the resume is missing, then covering
// more of them honestly: name a skill a line already proves, add one the person really has,
// and leave the rest missing. The model reads the job a little differently each run, so
// every number and keyword in the captions is taken from the page, never written in.
import fs from "fs";
import { here } from "./common.mjs";
import { startReel, LOGO } from "./reel.mjs";

const r = await startReel("reel-2");
const { p, wait, cap, card, tap, scrollToEl } = r;

// Off camera: read the job, so the hook can quote its real numbers.
await p.goto("http://localhost:3100/app/new/");
await p.fill("#jd", fs.readFileSync(here + "jd.txt", "utf8"));
await p.locator("button[type=submit]").dispatchEvent("click");
await p.waitForSelector("text=Choose a template", { timeout: 120000 });
const [have, total] = (await p.getByText(/^\d+ of \d+$/).first().innerText()).split(" of ").map(Number);
console.log("step: job", have, "of", total);
await r.start(p.url(), "text=Choose a template");

// Hook
await card(`<h1>Your resume is missing <span class="red">${total - have} of ${total}</span> skills the job asks for</h1><p>The ATS sees it before any human does 👀</p>`, true);
await wait(2900);
await card(null);
await wait(300);

await cap(`Dashed = missing.<br>That's what the ATS checks.`);
await scrollToEl(p.getByText("What we found", { exact: false }).first(), 185, 1000);
await wait(3000);
await cap(`Only ${have} of ${total} 👎`);
await scrollToEl(p.getByText("Your profile covers"), 400, 800);
await wait(2000);

// Into the editor, off camera
console.log("step: editor");
r.pause();
await p.locator("a", { hasText: "Choose a template" }).dispatchEvent("click");
await p.waitForSelector("text=Make my resume with");
await p.locator("button", { hasText: "Make my resume with" }).dispatchEvent("click");
await p.waitForURL(/resume\/\?id=/, { timeout: 120000, waitUntil: "commit" });
const covered = p.getByText("Job keywords covered");
await covered.waitFor({ timeout: 120000 });
await wait(2500);
const ring = async () => (await p.getByText(/^\d+\/\d+$/).first().innerText()).trim();
const start = await ring();
await scrollToEl(covered, 260, 10);
await wait(300);
r.resume();
await cap(`Let's fix it. <b>Honestly.</b>`);
await wait(2200);

// 1. A line that already proves a skill: say it in the job's words
console.log("step: line");
const line = p.locator("textarea").filter({ hasText: "200M-row" }).first();
// The line's own box. Pinned with a marker, because opening the picker hides the button
// this XPath finds it by.
await line.locator("xpath=ancestor::div[.//button[contains(., 'job keywords') or contains(., 'Edit keywords')]][1]").evaluate((el) => el.setAttribute("data-reel", "line"));
const box = p.locator("[data-reel=line]");
await cap(`1. This line <b>is</b> retention analysis.<br>Say it in the job's words.`);
await scrollToEl(line, 250, 1300);
await line.evaluate((el) => el.classList.add("reel-glow"));
await wait(1800);
await tap(box.locator("button", { hasText: /job keywords|Edit keywords/ }));
await wait(500);
// The job's retention terms this resume doesn't have yet, as the picker offers them.
const missing = box.locator("ul[aria-label='Not in your resume yet'] button");
const terms = (await missing.allInnerTexts()).map((t) => t.replace(/^[+✓]\s*/, "").trim()).filter((t) => /retention/i.test(t)).slice(0, 2);
console.log("keywords:", terms);
if (!terms.length) throw new Error("the job has no retention keyword this run");
const chip = (k) => missing.filter({ hasText: k }).first();
await scrollToEl(chip(terms[0]), 330, 700);
await wait(500);
for (const t of terms) {
  await tap(chip(t));
  await wait(500);
}
await wait(200);
const apply = box.locator("button", { hasText: "Apply" });
console.log("apply:", await apply.innerText());
await scrollToEl(apply, 520, 500);
await tap(apply);
await wait(700);
r.pause();
await p.waitForFunction((el) => /retention/i.test(el.value), await line.elementHandle(), { timeout: 120000 });
await wait(800);
await scrollToEl(line, 250, 10);
await wait(300);
r.resume();
await cap(`Same facts. The job's words. <b>✓</b>`);
await wait(3000);

// 2. A skill the person really has, in their own words
console.log("step: i have this");
const row = p.locator("li, div").filter({ hasText: /^cohort analys[ie]s · /i }).last();
await cap(`2. Really did cohort analysis?<br>Add it in your own words.`);
await scrollToEl(covered, 200, 1300);
await wait(1500);
await scrollToEl(row, 330, 700);
await tap(row.locator("button", { hasText: "I have this" }));
await wait(500);
const form = p.locator("form").filter({ hasText: /Where did you use cohort/i });
await tap(form.locator("select"));
await form.locator("select").selectOption({ index: 1 });
await wait(600);
await form.locator("textarea").pressSequentially("Built monthly cohort reports on repeat buyers for the loyalty team.", { delay: 14 });
await wait(500);
await tap(form.locator("button[type=submit]"));
await wait(600);
r.pause();
await form.waitFor({ state: "detached", timeout: 120000 });
await wait(1500);
const end = await ring();
await scrollToEl(covered, 200, 10);
await wait(300);
r.resume();
await cap(`${start.split("/")[0]} → ${end} <b>✓</b>`);
await wait(2600);

// 3. What she doesn't have stays missing
console.log("step: missing");
const still = p.locator("div").filter({ has: p.getByText("Not in this resume yet", { exact: true }) }).last();
// Rows read "dbt · nice to have".
const left = (await still.innerText()).split("\n").filter((l) => / · (must|nice)/.test(l)).map((l) => l.split(" · ")[0].trim());
const two = left.slice(0, 2);
console.log("still missing:", left);
await cap(two.length === 2 ? `No ${two[0]} or ${two[1]}?<br>They stay missing. <b>No fake skills.</b>` : `Don't have a skill?<br>It stays missing. <b>No fake skills.</b>`);
await scrollToEl(p.getByText("Not in this resume yet").first(), 260, 900);
await wait(3400);

// End card
await cap(null);
await card(`<div class="brand">${LOGO}QuickFit CV</div><h1>Match the job<br>without lying on your resume</h1><div class="pill">quickfitcv.com</div><p>Free to try · link in bio</p>`);
await wait(3400);
await r.finish();
