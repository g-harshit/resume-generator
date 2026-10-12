// Renders a video's poster.html as images: the Reel cover (9:16), a feed post (4:5) and a
// thumbnail (16:9). Usage: node poster.mjs <slug>  →  videos/<slug>/output/poster-*.png
import fs from "fs";
import { createRequire } from "module";

const [slug] = process.argv.slice(2);
if (!slug) throw new Error("usage: node poster.mjs <slug>");
const video = new URL(`${process.env.VIDEOS || "videos"}/${slug}/`, import.meta.url).pathname;
const { chromium } = createRequire(new URL("../../apps/extension/package.json", import.meta.url))("playwright");
fs.mkdirSync(video + "output", { recursive: true });

// A video with its own poster.html uses it; otherwise the kit lays out script.json's
// "poster" (headline + one scene's finished visual), timed by the English voice.
const own = fs.existsSync(video + "poster.html");
const script = JSON.parse(fs.readFileSync(video + "script.json", "utf8"));
const timingFile = `${video}output/en/timing.json`;
const timing = fs.existsSync(timingFile) ? JSON.parse(fs.readFileSync(timingFile, "utf8")) : undefined;
const here = new URL(".", import.meta.url).pathname;
const b = await chromium.launch();
for (const [f, w, h, name] of [["v", 1080, 1920, "cover-9x16"], ["p", 1080, 1350, "feed-4x5"], ["h", 1920, 1080, "thumbnail-16x9"]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  if (own) await p.goto(`file://${video}poster.html?f=${f}`);
  else {
    await p.addInitScript(([t, sc]) => { if (t) window.__TIMING = t; window.__SCRIPT = sc; }, [timing, script]);
    await p.goto(`file://${here}kit.html?poster=${f}`);
  }
  await p.waitForFunction(() => window.READY, null, { timeout: 60000 });
  const out = `${video}output/poster-${name}.png`;
  await p.locator("#poster").screenshot({ path: out });
  console.log(out);
  await p.close();
}
await b.close();
