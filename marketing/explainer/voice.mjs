// One voiceover clip per scene (OpenAI TTS, the project's key from backend/.env), then
// each clip's length into videos/<slug>/output/<lang>/timing.json — the scenes are timed to it.
// Usage: node voice.mjs <slug> en|hi
import fs from "fs";
import { execFileSync } from "child_process";

const [slug, lang = "en"] = process.argv.slice(2);
if (!slug) throw new Error("usage: node voice.mjs <slug> en|hi");
const here = new URL(".", import.meta.url).pathname;
const video = `${here}videos/${slug}/`;
const out = `${video}output/${lang}/`;
fs.mkdirSync(out, { recursive: true });
const script = JSON.parse(fs.readFileSync(video + "script.json", "utf8"));
const env = fs.readFileSync(here + "../../backend/.env", "utf8");
const key = env.match(/^OPENAI_API_KEY=["']?([^"'\n]+)/m)[1];
const ffmpeg = execFileSync("uvx", ["--with", "imageio-ffmpeg", "python", "-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"]).toString().trim();

const seconds = (file) => {
  let err = "";
  try { execFileSync(ffmpeg, ["-hide_banner", "-i", file], { stdio: "pipe" }); } catch (e) { err = e.stderr.toString(); }
  const [, h, m, s] = err.match(/Duration: (\d+):(\d+):([\d.]+)/);
  return +h * 3600 + +m * 60 + +s;
};

const timing = await Promise.all(script.scenes.map(async (s) => {
  // The model's own pace is a little slow for social video: keep its clip as .raw.mp3 and
  // speed it up (pitch kept) by script.json's "speed".
  const raw = `${out}${s.id}.raw.mp3`, file = `${out}${s.id}.mp3`;
  if (!fs.existsSync(raw)) {
    const res = await fetch("https://api.openai.com/v1/audio/speech", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: "gpt-4o-mini-tts", voice: script.voice, input: s[lang], instructions: script.instructions[lang], response_format: "mp3" }),
    });
    if (!res.ok) throw new Error(`${s.id}: ${res.status} ${await res.text()}`);
    fs.writeFileSync(raw, Buffer.from(await res.arrayBuffer()));
  }
  execFileSync(ffmpeg, ["-y", "-loglevel", "error", "-i", raw, "-filter:a", `atempo=${script.speed || 1}`, file]);
  return { id: s.id, text: s[lang], voice: +seconds(file).toFixed(2) };
}));
fs.writeFileSync(out + "timing.json", JSON.stringify(timing, null, 2));
console.log(timing.map((t) => `${t.id} ${t.voice}s`).join("\n"), "\ntotal", timing.reduce((a, t) => a + t.voice, 0).toFixed(1));
