// One voiceover clip per scene, then each clip's length into
// videos/<slug>/output/<lang>/timing.json — the scenes are timed to it.
// Usage: node voice.mjs <slug> en|hi
//
// Two voices, picked by script.json's "provider":
// - "elevenlabs" (ELEVENLABS_API_KEY in backend/.env): the most human, and Eleven v3 acts on
//   cues in the lines — [excited], [sighs], [laughs], [whispers]. Use it whenever the key is set.
// - "openai" (OPENAI_API_KEY): gpt-4o-mini-tts, steered by "instructions"; cues are stripped.
// Clips are cached by what was asked for, so editing one line regenerates only that line.
import fs from "fs";
import crypto from "crypto";
import { execFileSync } from "child_process";

const [slug, lang = "en"] = process.argv.slice(2);
if (!slug) throw new Error("usage: node voice.mjs <slug> en|hi");
const here = new URL(".", import.meta.url).pathname;
const video = `${here}videos/${slug}/`;
const out = `${video}output/${lang}/`;
fs.mkdirSync(out, { recursive: true });
const script = JSON.parse(fs.readFileSync(video + "script.json", "utf8"));
const env = fs.readFileSync(here + "../../backend/.env", "utf8");
const secret = (name) => env.match(new RegExp(`^${name}=["']?([^"'\\n]+)`, "m"))?.[1];
const provider = script.provider || "openai";
const ffmpeg = execFileSync("uvx", ["--with", "imageio-ffmpeg", "python", "-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"]).toString().trim();

const seconds = (file) => {
  let err = "";
  try { execFileSync(ffmpeg, ["-hide_banner", "-i", file], { stdio: "pipe" }); } catch (e) { err = e.stderr.toString(); }
  const [, h, m, s] = err.match(/Duration: (\d+):(\d+):([\d.]+)/);
  return +h * 3600 + +m * 60 + +s;
};

/** The request for one line, and where its audio goes. */
function request(text) {
  if (provider === "elevenlabs") {
    const key = secret("ELEVENLABS_API_KEY");
    if (!key) throw new Error("ELEVENLABS_API_KEY is not in backend/.env");
    const el = script.elevenlabs;
    return {
      url: `https://api.elevenlabs.io/v1/text-to-speech/${el.voice_id}?output_format=mp3_44100_128`,
      headers: { "xi-api-key": key, "Content-Type": "application/json" },
      body: { text, model_id: el.model || "eleven_v3", ...(el.settings ? { voice_settings: el.settings } : {}) },
    };
  }
  return {
    url: "https://api.openai.com/v1/audio/speech",
    headers: { Authorization: `Bearer ${secret("OPENAI_API_KEY")}`, "Content-Type": "application/json" },
    body: { model: "gpt-4o-mini-tts", voice: script.voice, input: text.replace(/\[[^\]]*\]\s*/g, ""), instructions: script.instructions[lang], response_format: "mp3" },
  };
}

async function clip(s) {
  const req = request(s[lang]);
  const hash = crypto.createHash("sha1").update(req.url + JSON.stringify(req.body)).digest("hex").slice(0, 10);
  // One cache for every video, keyed by the request: a line that repeats across videos
  // (the end card's) is paid for once.
  const cached = `${here}cache/${hash}.raw.mp3`, legacy = `${out}${s.id}.${hash}.raw.mp3`, file = `${out}${s.id}.mp3`;
  fs.mkdirSync(`${here}cache`, { recursive: true });
  if (!fs.existsSync(cached) && fs.existsSync(legacy)) fs.copyFileSync(legacy, cached);
  const raw = cached;
  if (!fs.existsSync(raw)) {
    const res = await fetch(req.url, { method: "POST", headers: req.headers, body: JSON.stringify(req.body) });
    if (!res.ok) {
      const body = await res.text();
      // Out of characters: say so plainly, so a batch can stop at the last video that fit.
      if (/quota_exceeded/.test(body)) { console.error(`QUOTA ${slug}: ${body}`); process.exit(3); }
      throw new Error(`${s.id}: ${res.status} ${body}`);
    }
    fs.writeFileSync(raw, Buffer.from(await res.arrayBuffer()));
  }
  // Optional speed-up (pitch kept), and the silence the model leaves at either end trimmed,
  // so scenes are timed to the speech itself.
  const trim = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse";
  execFileSync(ffmpeg, ["-y", "-loglevel", "error", "-i", raw, "-filter:a", `${trim},atempo=${script.speed || 1}`, file]);
  return { id: s.id, text: s[lang], voice: +seconds(file).toFixed(2), hold: s.hold || 0 };
}

// Two at a time: ElevenLabs' smaller plans refuse more parallel requests.
const timing = [];
for (let i = 0; i < script.scenes.length; i += 2) timing.push(...(await Promise.all(script.scenes.slice(i, i + 2).map(clip))));
fs.writeFileSync(out + "timing.json", JSON.stringify(timing, null, 2));
console.log(`${provider}:`, timing.map((t) => `${t.id} ${t.voice}s`).join(", "), "\ntotal", timing.reduce((a, t) => a + t.voice, 0).toFixed(1));
