// Writes videos/<slug>/captions.md from script.json's "captions", and checks the X post fits
// (X counts any link as 23 characters). Usage: node captions.mjs <slug>
import fs from "fs";

const [slug] = process.argv.slice(2);
const video = new URL(`videos/${slug}/`, import.meta.url).pathname;
const { captions: c, poster } = JSON.parse(fs.readFileSync(video + "script.json", "utf8"));
if (!c) throw new Error(`${slug}: script.json has no "captions"`);
const xLen = c.x.replace(/https?:\/\/\S+/g, "x".repeat(23)).length;
if (xLen > 280) throw new Error(`${slug}: the X post is ${xLen} characters (max 280)`);
const block = (t) => "```\n" + t + "\n```\n";
fs.writeFileSync(video + "captions.md", `# Captions — ${slug}

Hook: ${(poster?.head || []).join(" ")}

Videos: \`output/${slug}-en-9x16.mp4\` (Instagram Reels), \`output/${slug}-en-16x9.mp4\` (LinkedIn, X).
Posters: \`output/poster-cover-9x16.png\` (Reel cover), \`poster-feed-4x5.png\` (feed post),
\`poster-thumbnail-16x9.png\` (LinkedIn, X, YouTube).

## Instagram Reel — English

${block(c.ig_en + "\n\n" + (c.tags || "#resumetips #jobsearch #ats #careertips #jobseekers #resume #interviewtips #hiring"))}
## Instagram Reel — Hinglish

${block(c.ig_hi + "\n\n" + (c.tags_hi || "#resumetips #jobsearch #naukri #freshers #placement #jobsinindia #careertips #ats"))}
## LinkedIn (16:9 video + this text)

${block(c.linkedin)}
## X (${xLen}/280)

${block(c.x)}
## First comment to pin

${block(c.comment)}`);
console.log(`${slug}: captions.md (X ${xLen}/280)`);
