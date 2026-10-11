// Renders a video's poster.html as images: the Reel cover (9:16), a feed post (4:5) and a
// thumbnail (16:9). Usage: node poster.mjs <slug>  →  videos/<slug>/output/poster-*.png
import fs from "fs";
import { createRequire } from "module";

const [slug] = process.argv.slice(2);
if (!slug) throw new Error("usage: node poster.mjs <slug>");
const video = new URL(`videos/${slug}/`, import.meta.url).pathname;
const { chromium } = createRequire(new URL("../../apps/extension/package.json", import.meta.url))("playwright");
fs.mkdirSync(video + "output", { recursive: true });

const b = await chromium.launch();
for (const [f, w, h, name] of [["v", 1080, 1920, "cover-9x16"], ["p", 1080, 1350, "feed-4x5"], ["h", 1920, 1080, "thumbnail-16x9"]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto(`file://${video}poster.html?f=${f}`);
  await p.waitForFunction(() => window.READY, null, { timeout: 60000 });
  const out = `${video}output/poster-${name}.png`;
  await p.locator("#poster").screenshot({ path: out });
  console.log(out);
  await p.close();
}
await b.close();
