// Renders a video's scenes.html frame by frame (30 fps, seeking its timeline, so every frame
// is exact) and mixes in the voiceover. Usage: node render.mjs <slug> en|hi v|h [--still]
//   v = 1080x1920 (Reels, Shorts), h = 1920x1080 (X, LinkedIn, the site).
//   --still writes one PNG per scene instead, for a quick look.
import fs from "fs";
import { execFileSync } from "child_process";
import { createRequire } from "module";

const [slug, lang = "en", f = "v"] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
if (!slug) throw new Error("usage: node render.mjs <slug> en|hi v|h [--still]");
const still = process.argv.includes("--still");
const here = new URL(".", import.meta.url).pathname;
const video = `${here}${process.env.VIDEOS || "videos"}/${slug}/`;
const out = `${video}output/${lang}/`;
const timing = JSON.parse(fs.readFileSync(out + "timing.json", "utf8"));
const { chromium } = createRequire(new URL("../../apps/extension/package.json", import.meta.url))("playwright");
const ffmpeg = execFileSync("uvx", ["--with", "imageio-ffmpeg", "python", "-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"]).toString().trim();
const [W, H] = f === "h" ? [1920, 1080] : [1080, 1920];
const FPS = 30;

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: W, height: H } });
p.on("pageerror", (e) => console.log("pageerror", e.message));
// A video with its own scenes.html uses it; otherwise the kit builds the scenes from the script.
const script = JSON.parse(fs.readFileSync(video + "script.json", "utf8"));
const page = fs.existsSync(video + "scenes.html") ? `${video}scenes.html` : `${here}kit.html`;
await p.addInitScript(([t, s]) => { window.__TIMING = t; window.__SCRIPT = s; }, [timing, script]);
await p.goto(`file://${page}?f=${f}`);
await p.waitForFunction(() => window.READY, null, { timeout: 60000 });
const { duration, starts } = await p.evaluate(() => ({ duration: window.DURATION, starts: window.STARTS }));
const stage = p.locator("#stage");

if (still) {
  const dir = `${out}stills-${f}/`;
  fs.mkdirSync(dir, { recursive: true });
  const ids = Object.keys(starts);
  for (const [i, id] of ids.entries()) {
    // Most of the way through each scene, when everything is on screen.
    const end = i + 1 < ids.length ? starts[ids[i + 1]] : duration;
    await p.evaluate((s) => window.seek(s), end - 0.35);
    await stage.screenshot({ path: `${dir}${i + 1}-${id}.png` });
  }
  await b.close();
  console.log(dir);
  process.exit(0);
}

const frames = `${out}frames-${f}/`;
fs.rmSync(frames, { recursive: true, force: true });
fs.mkdirSync(frames, { recursive: true });
const n = Math.ceil(duration * FPS);
for (let i = 0; i < n; i++) {
  await p.evaluate((s) => window.seek(s), i / FPS);
  await stage.screenshot({ path: `${frames}${String(i).padStart(5, "0")}.jpg`, type: "jpeg", quality: 92 });
  if (i % 300 === 0) console.log(`frame ${i}/${n}`);
}
await b.close();

// Each scene's clip starts just after its scene does.
const ids = Object.keys(starts);
const inputs = [], filters = [];
timing.forEach((t, i) => {
  inputs.push("-i", `${out}${t.id}.mp3`);
  const ms = Math.round((starts[ids[i]] + 0.12) * 1000);
  filters.push(`[${i + 1}:a]adelay=${ms}|${ms},aformat=channel_layouts=stereo[a${i}]`);
});
// Loudness normalised to what social apps expect (about -16 LUFS).
const mix = `${filters.join(";")};${timing.map((_, i) => `[a${i}]`).join("")}amix=inputs=${timing.length}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[aout]`;
const mp4 = `${video}output/${slug}-${lang}-${f === "h" ? "16x9" : "9x16"}.mp4`;
execFileSync(ffmpeg, ["-y", "-hide_banner", "-loglevel", "error", "-framerate", String(FPS), "-i", `${frames}%05d.jpg`, ...inputs,
  "-filter_complex", mix, "-map", "0:v", "-map", "[aout]", "-shortest",
  "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", mp4]);
console.log(mp4, `${duration.toFixed(1)} s`);
