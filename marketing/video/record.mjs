// Reel 1: "Tailor a resume in 30 seconds". Records 1080x1920 frames from Chrome's screencast,
// skipping the time spent waiting on the AI, then writes frames.txt for ffmpeg's concat demuxer.
import { chromium, serveStatic, account, dir, here } from "./common.mjs";
import fs from "fs";

const FR = dir + "frames/";
fs.rmSync(FR, { recursive: true, force: true });
fs.mkdirSync(FR);

const b = await chromium.launch();
const ctx = await b.newContext({
  viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5, isMobile: true, hasTouch: true, acceptDownloads: true,
});
await serveStatic(ctx);
await ctx.addInitScript((t) => localStorage.setItem("rg:token", t), account().token);
const p = await ctx.newPage();
p.on("pageerror", (e) => console.log("pageerror", e.message));

// --- overlay helpers, injected into the page -------------------------------------------
const OVERLAY = () => {
  if (window.__reel) return;
  window.__reel = true;
  const st = document.createElement("style");
  st.textContent = `
  #reel-cap{position:fixed;left:50%;top:92px;transform:translate(-50%,10px);opacity:0;z-index:99999;
    width:max-content;max-width:86%;text-align:center;padding:12px 18px;border-radius:16px;
    background:rgba(20,28,25,.92);color:#fff;font:700 22px/1.25 system-ui,-apple-system,sans-serif;
    box-shadow:0 8px 30px rgba(0,0,0,.25);transition:opacity .25s, transform .25s;pointer-events:none}
  #reel-cap.on{opacity:1;transform:translate(-50%,0)}
  #reel-cap b{color:#9be3c4}
  #reel-card{position:fixed;inset:0;z-index:99998;display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:18px;padding:32px;text-align:center;background:rgba(244,242,236,.97);opacity:0;transition:opacity .35s;pointer-events:none}
  #reel-card.on{opacity:1}
  #reel-card h1{font:700 40px/1.12 system-ui,-apple-system,sans-serif;color:#15201c;margin:0;letter-spacing:-.5px}
  #reel-card p{font:500 21px/1.35 system-ui,-apple-system,sans-serif;color:#4a5550;margin:0}
  #reel-card .brand{font-family:var(--font-display, Georgia),serif;font-size:46px;color:#15201c}
  #reel-card .pill{background:#2f5d50;color:#fff;border-radius:999px;padding:12px 22px;font:700 22px system-ui,sans-serif}
  #reel-card mark{background:#ffe08a;padding:0 6px;border-radius:6px}
  .reel-tap{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;z-index:99999;
    background:rgba(47,93,80,.35);border:3px solid rgba(47,93,80,.8);pointer-events:none;animation:reeltap .55s ease-out forwards}
  @keyframes reeltap{0%{transform:scale(.4);opacity:1}100%{transform:scale(1.5);opacity:0}}
  .reel-glow{box-shadow:0 0 0 4px #ffd65a !important;transition:box-shadow .3s}`;
  document.documentElement.appendChild(st);
  const cap = document.createElement("div"); cap.id = "reel-cap"; document.documentElement.appendChild(cap);
  const card = document.createElement("div"); card.id = "reel-card"; document.documentElement.appendChild(card);
  window.__cap = (html) => { if (!html) return cap.classList.remove("on"); cap.innerHTML = html; cap.classList.add("on"); };
  window.__card = (html) => { if (!html) return card.classList.remove("on"); card.innerHTML = html; card.classList.add("on"); };
  window.__tap = (x, y) => { const d = document.createElement("div"); d.className = "reel-tap"; d.style.left = x + "px"; d.style.top = y + "px"; document.documentElement.appendChild(d); setTimeout(() => d.remove(), 700); };
  window.__scroll = (to, ms) => new Promise((res) => {
    const from = window.scrollY, t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo(0, from + (to - from) * e); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  });
};

// --- screencast capture with pausable clock --------------------------------------------
const cdp = await ctx.newCDPSession(p);
const frames = []; // { file, t } t = video seconds
let recording = false, offset = 0, pausedAt = 0, lastPaused = null, n = 0;
const now = () => performance.now() / 1000;
cdp.on("Page.screencastFrame", async ({ data, sessionId }) => {
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  const buf = Buffer.from(data, "base64");
  if (!recording) { lastPaused = buf; return; }
  const file = `f${String(n++).padStart(5, "0")}.jpg`;
  fs.writeFileSync(FR + file, buf);
  frames.push({ file, t: now() - offset });
});
const pause = () => { recording = false; pausedAt = now(); };
const resume = () => {
  offset += now() - pausedAt; recording = true;
  if (lastPaused) { const file = `f${String(n++).padStart(5, "0")}.jpg`; fs.writeFileSync(FR + file, lastPaused); frames.push({ file, t: now() - offset }); lastPaused = null; }
};
const wait = (ms) => p.waitForTimeout(ms);
const cap = (html) => p.evaluate((h) => window.__cap(h), html);
const card = (html) => p.evaluate((h) => window.__card(h), html);
const scrollTo = (y, ms = 900) => p.evaluate(([y, ms]) => window.__scroll(y, ms), [y, ms]);
// Scroll so the element's top sits `top` px below the viewport top.
const scrollToEl = async (loc, top = 230, ms = 900) => {
  const y = await loc.evaluate((el, top) => el.getBoundingClientRect().top + window.scrollY - top, top);
  await scrollTo(Math.max(0, y), ms);
};
const tap = async (loc) => {
  const bb = await loc.boundingBox();
  await p.evaluate(([x, y]) => window.__tap(x, y), [bb.x + bb.width / 2, bb.y + bb.height / 2]);
  await wait(250);
  await loc.dispatchEvent("click");
};

// --- the reel ------------------------------------------------------------------------
await p.goto("http://localhost:3100/app/new/");
await p.waitForSelector("#jd");
await p.evaluate(OVERLAY);
await wait(800);
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1080, maxHeight: 1920, everyNthFrame: 1 });
await wait(300);
recording = true;
const T0 = now();

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
pause();
await p.waitForSelector("text=Choose a template", { timeout: 120000 });
await wait(400);
resume();

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
pause();
await p.waitForURL(/resume\/\?id=/, { timeout: 120000, waitUntil: "commit" });
await p.locator("button", { hasText: "Rewrite for this job" }).first().waitFor({ timeout: 120000 });
await wait(2500);
resume();

// 3. Rewrite chosen lines
await cap(`3. Rewrite only the lines<br>you choose`);
const line = p.locator("textarea").filter({ hasText: "dashboards" }).first();
await scrollToEl(line, 300, 1300);
await wait(1300);
await tap(p.locator("button", { hasText: "Rewrite for this job" }).first());
await wait(900);
pause();
await p.getByText("Reworded for this job").first().waitFor({ timeout: 120000 });
await wait(600);
await scrollToEl(line, 300, 10);
await line.evaluate((el) => el.classList.add("reel-glow"));
await wait(300);
resume();
await cap(`Uses the job's words.<br>Keeps <b>your</b> facts.`);
await wait(3200);

// 4. Download
await cap(`4. Download a clean PDF`);
await scrollTo(0, 1100);
await wait(500);
const dl = p.waitForEvent("download", { timeout: 60000 }).catch(() => null);
await tap(p.locator("button", { hasText: "Download PDF" }));
await wait(700);
pause();
await dl;
await wait(300);
resume();
await wait(1400);

// End card
await cap(null);
await card(`<div class="brand">QuickFit CV</div><h1>One resume per job,<br>in your own words</h1><div class="pill">quickfitcv.com</div><p>Free to try · link in bio</p>`);
await wait(3400);

const END = now() - offset;
recording = false;
await cdp.send("Page.stopScreencast");
await b.close();

// concat list: each frame lasts until the next one
let list = "";
frames.forEach((f, i) => {
  const next = i + 1 < frames.length ? frames[i + 1].t : END;
  list += `file '${FR}${f.file}'\nduration ${Math.max(0.001, next - f.t).toFixed(4)}\n`;
});
list += `file '${FR}${frames.at(-1).file}'\n`;
fs.writeFileSync(dir + "frames.txt", list);
console.log("frames", frames.length, "video seconds", (END - (T0 - 0)).toFixed(1), "first t", frames[0].t - (T0));
