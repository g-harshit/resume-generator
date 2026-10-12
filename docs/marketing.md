# Marketing — getting traffic to quickfitcv.com

Ideas, ordered by likely payoff for a solo founder with no budget. Tick them off as they land.

## Positioning

Lead with what's different: **the AI resume tool that won't lie for you.** Tailoring never
adds a skill, employer, date or number that isn't in the profile; a skill the job wants and
the profile lacks is shown as a gap. Supporting points:

- Keyword match: see which of the job's keywords the resume has and which it's missing.
- Pick which lines to rewrite; the rest stays in your words.
- Fit to N pages in one click.
- ATS-safe PDFs (single column, real text, standard headings — tested).
- Chrome extension that reads the job post from the page (once it's published).

## 1. Free tools that rank (highest leverage)

Each is a page that ranks on its own and funnels into signup. Usable without an account;
ask for signup only to save or download.

- [ ] **ATS resume checker** — upload a resume, get a parse / headings / layout score
  (reuses the ATS test logic).
- [ ] **Resume vs job description keyword match** — paste both, see the missing keywords
  (reuses the keyword panel).
- [ ] **"Will it fit on one page?"** checker / page-length fitter.

## 2. SEO pages (programmatic, but genuinely useful)

`sitemap.ts` lists only a handful of pages today.

- [ ] "Resume for [job title]" with a tailored example (Software Engineer, Data Analyst,
  Product Manager, Nurse, … hundreds possible).
- [ ] "[Company] resume tips / keywords" (Google, Amazon, Deloitte, …).
- [ ] Guides: "How to tailor a resume to a job description", "ATS-friendly resume format",
  each linking to a free tool.

Every page must be useful alone — thin generated pages get penalised.

## 3. Chrome Web Store (when the extension ships)

- [ ] Title with keywords: "QuickFit CV – Tailor Resume to Job Description (ATS)".
- [ ] Screenshots of the side panel on LinkedIn / Indeed / Greenhouse job pages.
- [ ] First 20–50 reviews: ask happy users in-app right after a download.

## 4. Communities (helpful, not spammy)

- [ ] Reddit: r/resumes, r/jobs, r/cscareerquestions, r/careerguidance, r/layoffs —
  answer properly, mention the tool only when it fits. Free resume reviews work well.
- [ ] LinkedIn: before/after tailoring posts.
- [ ] Discord / Slack groups: bootcamp grads, new-grad hiring, international students.

## Instagram profile

- **Username:** @quickfitcv. **Name** (searchable, so it carries keywords):
  `QuickFit CV | AI Resume Builder`. **Category:** Software.
- **Profile picture:** `brand/instagram-profile.png` (logo on green; Instagram crops it to a circle).
- **Link:** `https://quickfitcv.com/?utm_source=instagram&utm_medium=bio`
- **Bio** (≤150 characters; pick one, or match the language of the Reels):

  ```
  Tailor your resume to every job in 30 sec ⚡
  ATS-friendly · your words · no fake skills
  Free resume tips every week 👇
  ```

  ```
  Har job ke liye sahi resume, 30 sec mein ⚡
  ATS-friendly · aapke words · koi fake skill nahi
  Free resume tips 👇
  ```

- **Highlights:** How it works · Before/After · ATS tips · FAQ.

## 5. Short video (Instagram Reels, YouTube Shorts, TikTok)

Screen recordings of the website are enough — no extension needed.

**Recording:** phone screen recorder on quickfitcv.com (already 9:16), or a scripted
recording of the site at phone width (`marketing/video/`). Edit in CapCut: auto-captions,
zoom on the key moment, trending audio. Always use a fake demo profile.

Reel ideas (15–30 s each):

1. [ ] **"Tailor a resume in 30 seconds"** — hook: *"Stop sending the same resume to every
   job"*. Paste JD → keyword matches → rewrite 2 lines → download PDF. End: link in bio.
2. [ ] **"Why ATS rejects you"** — hook: *"Your resume is missing 7 of the job's keywords"*.
   Zoom on the missing keywords, then after tailoring most are present.
3. [ ] **"The AI that refuses to lie"** — hook: *"Most AI resume tools make things up. This
   one won't."* Job wants Kubernetes, profile lacks it → shown as a gap, not invented.
4. [ ] **"2-page resume → 1 page in one click"** — Fit to 1 page, before/after.
5. [ ] **"Same person, 3 different jobs"** — one profile tailored for Data Analyst /
   Product Analyst / Business Analyst, side by side.
6. [ ] **"POV: you applied to 50 jobs with one resume"** — meme audio → "do this instead".

What matters on Instagram:

- The first 1–2 seconds decide everything: hook text on screen in frame one.
- Captions on (most people watch muted); 15–25 s.
- 4–5 Reels a week; test 2–3 hooks per idea.
- CTA that drives DMs: *"Comment 'RESUME' and I'll check your keywords"* (ManyChat can
  automate the replies).


## Content calendar — 20 explainer videos

All in `marketing/explainer/videos/<slug>/`: `captions.md` (Instagram EN + Hinglish, LinkedIn,
X, pinned comment), and in `output/` the 9:16 MP4 (Reels), 16:9 MP4 (LinkedIn, X) and three
posters. Five a week: Instagram every day listed, LinkedIn on Tue and Thu (16:9 + its
LinkedIn text). Mix keeps each week to one hook, one demo, one tip, one trust video.

| # | When | Video | Hook | Why this slot |
|---|---|---|---|---|
| 1 | W1 Mon | `ats-rejected` | 50 applications. Zero callbacks? | Hook: the ATS problem |
| 2 | W1 Tue | `tailor-30s` | Tailor a resume in 30 seconds. | Demo: the whole flow |
| 3 | W1 Thu | `ats-basics` | 3 things an ATS needs from your resume | Tip (save-worthy) |
| 4 | W1 Fri | `fake-skills` | Can you explain every line? If AI wrote it, maybe not. | Trust: never invents |
| 5 | W1 Sun | `two-columns` | Two-column resume? The ATS reads it straight across. | Tip: templates |
| 6 | W2 Mon | `job-words` | Same work. Different words. That's why the ATS missed you. | Problem: different words |
| 7 | W2 Tue | `five-to-seven` | 5 of 11 → 7 of 11 without a single lie. | Demo: honest 5→7 |
| 8 | W2 Thu | `ats-checker` | What does the ATS actually read? Check free. No sign-up. | Free tool |
| 9 | W2 Fri | `interview-questions` | Every line on your resume is an interview question. | Trust: interviews |
| 10 | W2 Sun | `one-page` | Two pages? Make it one. One click. | Feature: fit to one page |
| 11 | W3 Mon | `same-resume` | 50 jobs. One resume. That's the problem. | Problem: one file, 50 jobs |
| 12 | W3 Tue | `lines-prove` | Your line says Django. The job wants Python. Same thing. | Feature: skills your lines prove |
| 13 | W3 Thu | `image-pdf` | Your resume is an image? The ATS sees nothing. | Tip: image PDFs |
| 14 | W3 Fri | `your-words` | AI rewrote your whole resume? Pick the lines instead. | Trust: your words |
| 15 | W3 Sun | `buzzwords` | Results-driven team player? Show the numbers. | Tip: numbers over buzzwords |
| 16 | W4 Mon | `profile-once` | Upload once. Tailor every time. | Feature: upload once |
| 17 | W4 Tue | `cover-letter` | Your cover letter sounds like everyone else's. | Feature: cover letters |
| 18 | W4 Thu | `summary` | Same summary for every job? | Feature: summary per job |
| 19 | W4 Fri | `templates` | Four templates. All ATS-safe. | Feature: 4 templates |
| 20 | W4 Sun | `deadline` | Closes at midnight. It's 11:30 PM. Still time. | Story: 11:30 PM |

## 6. Launches (one-time spikes + backlinks)

- [ ] Product Hunt, Show HN, Indie Hackers, BetaList.
- [ ] AI tool directories: There's An AI For That, Futurepedia, Toolify (backlinks for SEO).

## 7. Partnerships

- [ ] University career centres and bootcamps: free accounts for students.
- [ ] Career coaches / resume writers: affiliate or referral cut.
- [ ] Small job-seeker newsletters: cheap sponsorships.

## 8. Referral loop

- [ ] "Give a friend 5 free tailorings, get 5." Job seekers know job seekers, and layoffs
  hit whole teams at once.

## 9. Measure from day one

- [ ] Google Search Console.
- [ ] Plausible or PostHog, UTM tags on every channel.
- [ ] Track the funnel: visit → signup → upload → tailor → download, per channel.

## First 30 days

1. Search Console + analytics.
2. Free ATS checker and keyword match tools.
3. 10 strong "resume for [job title]" pages.
4. Product Hunt + directories.
5. 3–4 Reels a week from the ideas above.
6. 20 minutes a day on Reddit / LinkedIn.
