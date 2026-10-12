// What every Reel shares: a phone-sized browser signed in as the demo account, captions,
// cards and tap marks drawn over the page, and a screencast whose clock can pause, so time
// spent waiting on the AI never reaches the video. A Reel script calls startReel(), plays
// its storyboard, then finish() writes output/<name>/frames.txt for encode.sh.
import { chromium, serveStatic, account, dir } from "./common.mjs";
import fs from "fs";

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
  #reel-cap s{color:#ffb38a;text-decoration-thickness:2px}
  #reel-card{position:fixed;inset:0;z-index:99998;display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:18px;padding:32px;text-align:center;background:rgba(244,242,236,.97);opacity:0;transition:opacity .35s;pointer-events:none}
  #reel-card.on{opacity:1}
  #reel-card.dark{background:rgba(23,24,28,.97)}
  #reel-card h1{font:700 40px/1.12 system-ui,-apple-system,sans-serif;color:#15201c;margin:0;letter-spacing:-.5px}
  #reel-card.dark h1{color:#fff}
  #reel-card p{font:500 21px/1.35 system-ui,-apple-system,sans-serif;color:#4a5550;margin:0}
  #reel-card.dark p{color:#c9cdc8}
  #reel-card .brand{font-family:var(--font-display, Georgia),serif;font-size:46px;color:#15201c;display:flex;align-items:center;gap:10px}
  #reel-card .pill{background:#2f5d50;color:#fff;border-radius:999px;padding:12px 22px;font:700 22px system-ui,sans-serif}
  #reel-card mark{background:#ffe08a;padding:0 6px;border-radius:6px}
  #reel-card .red{color:#ff5a4f}
  .reel-tap{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;z-index:99999;
    background:rgba(47,93,80,.35);border:3px solid rgba(47,93,80,.8);pointer-events:none;animation:reeltap .55s ease-out forwards}
  @keyframes reeltap{0%{transform:scale(.4);opacity:1}100%{transform:scale(1.5);opacity:0}}
  .reel-glow{box-shadow:0 0 0 4px #ffd65a !important;transition:box-shadow .3s}`;
  document.documentElement.appendChild(st);
  const cap = document.createElement("div"); cap.id = "reel-cap"; document.documentElement.appendChild(cap);
  const card = document.createElement("div"); card.id = "reel-card"; document.documentElement.appendChild(card);
  window.__cap = (html) => { if (!html) return cap.classList.remove("on"); cap.innerHTML = html; cap.classList.add("on"); };
  window.__card = (html, dark) => {
    if (!html) return card.classList.remove("on");
    card.innerHTML = html; card.classList.toggle("dark", !!dark); card.classList.add("on");
  };
  window.__tap = (x, y) => { const d = document.createElement("div"); d.className = "reel-tap"; d.style.left = x + "px"; d.style.top = y + "px"; document.documentElement.appendChild(d); setTimeout(() => d.remove(), 700); };
  window.__scroll = (to, ms) => new Promise((res) => {
    const from = window.scrollY, t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo(0, from + (to - from) * e); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
    // Animation frames can stop (a hidden or busy page): land there anyway.
    setTimeout(() => { window.scrollTo(0, to); res(); }, ms + 1500);
  });
};

/** The logo, for end cards (brand/logo-mark.svg). */
export const LOGO = fs.readFileSync(new URL("../../brand/logo-mark.svg", import.meta.url), "utf8").replace('width="64" height="64"', 'width="48" height="48"');

export async function startReel(name) {
  const FR = `${dir}${name}/frames/`;
  fs.rmSync(FR, { recursive: true, force: true });
  fs.mkdirSync(FR, { recursive: true });

  const b = await chromium.launch();
  const ctx = await b.newContext({
    viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5, isMobile: true, hasTouch: true, acceptDownloads: true,
  });
  await serveStatic(ctx);
  await ctx.addInitScript((t) => localStorage.setItem("rg:token", t), account().token);
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.log("pageerror", e.message));

  const cdp = await ctx.newCDPSession(p);
  const frames = []; // { file, t }: t in video seconds
  const marks = []; // { t, kind, html }: when each caption or card appeared
  let recording = false, offset = 0, pausedAt = 0, lastPaused = null, n = 0;
  const now = () => performance.now() / 1000;
  const keep = (buf) => {
    const file = `f${String(n++).padStart(5, "0")}.jpg`;
    fs.writeFileSync(FR + file, buf);
    frames.push({ file, t: now() - offset });
  };
  cdp.on("Page.screencastFrame", ({ data, sessionId }) => {
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
    const buf = Buffer.from(data, "base64");
    if (recording) keep(buf);
    else lastPaused = buf;
  });

  const wait = (ms) => p.waitForTimeout(ms);
  const scrollTo = (y, ms = 900) => p.evaluate(([y, ms]) => window.__scroll(y, ms), [y, ms]);
  const r = {
    p,
    wait,
    scrollTo,
    // Each caption and card is logged with its time in the video, so a voiceover can be
    // laid over it afterwards (voiceover.mjs).
    cap: (html) => { if (html) marks.push({ t: now() - offset, kind: "cap", html }); return p.evaluate((h) => window.__cap(h), html); },
    card: (html, dark = false) => { if (html) marks.push({ t: now() - offset, kind: "card", html }); return p.evaluate(([h, d]) => window.__card(h, d), [html, dark]); },
    /** Scroll so the element's top sits `top` px below the viewport's top. */
    async scrollToEl(loc, top = 230, ms = 900) {
      const y = await loc.evaluate((el, top) => el.getBoundingClientRect().top + window.scrollY - top, top);
      await scrollTo(Math.max(0, y), ms);
    },
    async tap(loc) {
      const bb = await loc.boundingBox();
      await p.evaluate(([x, y]) => window.__tap(x, y), [bb.x + bb.width / 2, bb.y + bb.height / 2]);
      await wait(250);
      await loc.dispatchEvent("click");
    },
    /** Stop the clock (while the AI works); resume() picks up from the latest frame. */
    pause() { recording = false; pausedAt = now(); },
    resume() {
      offset += now() - pausedAt; recording = true;
      if (lastPaused) { keep(lastPaused); lastPaused = null; }
    },
    /** Open the first page and start recording. */
    async start(url, ready) {
      await p.goto(url);
      await p.waitForSelector(ready);
      await p.evaluate(OVERLAY);
      await wait(800);
      await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1080, maxHeight: 1920, everyNthFrame: 1 });
      await wait(300);
      recording = true;
    },
    /** Stop, and write the concat list: each frame lasts until the next one. */
    async finish() {
      const end = now() - offset;
      recording = false;
      await cdp.send("Page.stopScreencast");
      await b.close();
      let list = "";
      frames.forEach((f, i) => {
        const next = i + 1 < frames.length ? frames[i + 1].t : end;
        list += `file '${FR}${f.file}'\nduration ${Math.max(0.001, next - f.t).toFixed(4)}\n`;
      });
      list += `file '${FR}${frames.at(-1).file}'\n`;
      fs.writeFileSync(`${dir}${name}/frames.txt`, list);
      const t0 = frames[0].t;
      fs.writeFileSync(`${dir}${name}/marks.json`, JSON.stringify(marks.map((m) => ({ ...m, t: +(m.t - t0).toFixed(2) })), null, 2));
      console.log(`${name}: ${frames.length} frames, ${(end - frames[0].t).toFixed(1)} s`);
    },
  };
  return r;
}
