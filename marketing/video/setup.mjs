// Off-camera setup: demo PDF, a local test account, upload, confirm the profile.
// Needs the local API running (make api). Creates a fresh local test account each run.
import fs from "fs";
import { chromium, dir, here } from "./common.mjs";
const API = "http://localhost:8100";

const browser = await chromium.launch();
const p = await browser.newPage();
await p.goto("file://" + here + "resume.html");
await p.pdf({ path: dir + "Priya_Sharma_Resume.pdf", format: "A4" });
await browser.close();

const email = `priya.demo.${Date.now()}@example.com`;
const password = "DemoReel-" + Math.random().toString(36).slice(2, 10);
const j = async (r) => { const t = await r.text(); if (!r.ok) throw new Error(r.status + " " + t); return JSON.parse(t); };
const { token } = await j(await fetch(API + "/auth/register", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password, name: "Priya Sharma" }) }));
const auth = { Authorization: "Bearer " + token };
const fd = new FormData();
fd.append("file", new Blob([fs.readFileSync(dir + "Priya_Sharma_Resume.pdf")], { type: "application/pdf" }), "Priya_Sharma_Resume.pdf");
let up = await j(await fetch(API + "/uploads", { method: "POST", headers: auth, body: fd }));
while (up.status !== "done") {
  if (up.status === "failed") throw new Error(up.error);
  await new Promise((r) => setTimeout(r, 2000));
  up = await j(await fetch(API + "/uploads/" + up.id, { headers: auth }));
}
let prof = await j(await fetch(API + "/profile", { headers: auth }));
prof = await j(await fetch(API + "/profile/confirm", { method: "POST", headers: { ...auth, "content-type": "application/json" }, body: JSON.stringify({ version: prof.version }) }));
fs.writeFileSync(dir + "account.json", JSON.stringify({ email, token }));
console.log("ok", email, "reviewed:", prof.reviewed_at, "skills:", JSON.stringify(prof.data.skills).slice(0, 200));
