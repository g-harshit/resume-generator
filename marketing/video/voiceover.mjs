// Lays an ElevenLabs voiceover over a recorded Reel: one line per caption or card, in the
// order they appeared (output/<reel>/marks.json, written by the recorder), each starting
// when its caption does, or just after the previous line if that one runs long.
// Usage: node voiceover.mjs reel-1   (lines in reel-1.voice.json) → output/reel-1-voiced.mp4
import fs from "fs";
import crypto from "crypto";
import { execFileSync } from "child_process";

const [reel] = process.argv.slice(2);
const here = new URL(".", import.meta.url).pathname;
const out = `${here}output/${reel}/`;
const marks = JSON.parse(fs.readFileSync(out + "marks.json", "utf8"));
// VOICE_FILE: another set of lines; EXTEND_END: seconds more on the final frame (the end
// card); OUT: the output's name. The defaults reproduce the original Reel.
const spec = JSON.parse(fs.readFileSync(process.env.VOICE_FILE || `${here}${reel}.voice.json`, "utf8"));
const extend = +(process.env.EXTEND_END || 0);
if (marks.length !== spec.lines.length) throw new Error(`${marks.length} captions but ${spec.lines.length} lines`);
const env = fs.readFileSync(here + "../../backend/.env", "utf8");
const key = env.match(/^ELEVENLABS_API_KEY=["']?([^"'\n]+)/m)[1];
const ffmpeg = execFileSync("uvx", ["--with", "imageio-ffmpeg", "python", "-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"]).toString().trim();
const seconds = (f) => { let e = ""; try { execFileSync(ffmpeg, ["-hide_banner", "-i", f], { stdio: "pipe" }); } catch (x) { e = x.stderr.toString(); } const [, h, m, s] = e.match(/Duration: (\d+):(\d+):([\d.]+)/); return +h * 3600 + +m * 60 + +s; };

// Shared with the explainer videos, so a line already voiced there costs nothing.
const cache = `${here}../explainer/cache/`;
fs.mkdirSync(cache, { recursive: true });
const clips = [];
for (const [i, text] of spec.lines.entries()) {
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${spec.voice_id}?output_format=mp3_44100_128`;
  const body = { text, model_id: spec.model };
  const raw = `${cache}${crypto.createHash("sha1").update(url + JSON.stringify(body)).digest("hex").slice(0, 10)}.raw.mp3`;
  if (!fs.existsSync(raw)) {
    const res = await fetch(url, { method: "POST", headers: { "xi-api-key": key, "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`line ${i}: ${res.status} ${await res.text()}`);
    fs.writeFileSync(raw, Buffer.from(await res.arrayBuffer()));
  }
  const clip = `${out}voice-${i}.mp3`;
  execFileSync(ffmpeg, ["-y", "-loglevel", "error", "-i", raw, "-filter:a", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse", clip]);
  clips.push({ clip, len: seconds(clip) });
}

let prevEnd = 0;
const placed = clips.map((c, i) => {
  const start = Math.max(marks[i].t + 0.15, prevEnd + 0.12);
  prevEnd = start + c.len;
  const next = marks[i + 1]?.t;
  const note = next !== undefined && prevEnd > next + 0.8 ? `  (runs ${(prevEnd - next).toFixed(1)} s into the next caption)` : "";
  console.log(`${start.toFixed(2)}s  ${c.len.toFixed(2)}s  ${spec.lines[i]}${note}`);
  return { ...c, start };
});

const inputs = placed.flatMap((c) => ["-i", c.clip]);
const mix = placed.map((c, i) => { const ms = Math.round(c.start * 1000); return `[${i + 1}:a]adelay=${ms}|${ms},aformat=channel_layouts=stereo[a${i}]`; }).join(";") +
  `;${placed.map((_, i) => `[a${i}]`).join("")}amix=inputs=${placed.length}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[aout]`;
const mp4 = `${here}output/${process.env.OUT || `${reel}-voiced`}.mp4`;
// The video's length, from the frame durations: padded audio would otherwise run forever.
let list = fs.readFileSync(`${out}frames.txt`, "utf8");
if (extend) {
  // The last "duration" belongs to the final frame shown: the end card.
  const i = list.lastIndexOf("duration ");
  const j = list.indexOf("\n", i);
  list = list.slice(0, i) + `duration ${(+list.slice(i + 9, j) + extend).toFixed(4)}` + list.slice(j);
}
const listFile = `${out}frames-voiced.txt`;
fs.writeFileSync(listFile, list);
const total = list.match(/duration [\d.]+/g).reduce((a, d) => a + +d.split(" ")[1], 0);
execFileSync(ffmpeg, ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listFile, ...inputs,
  "-filter_complex", `[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xf4f2ec,fps=30,format=yuv420p[v];${mix}`,
  "-map", "[v]", "-map", "[aout]", "-t", total.toFixed(2), "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", mp4]);
console.log(mp4);
