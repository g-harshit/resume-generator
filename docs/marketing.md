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


## Content calendar — 70 explainer videos

**Use v2:** `marketing/explainer/export-v2/` (every video 21–25 s, slower end card, Instagram + LinkedIn covers, captions). The first versions stay in `export/`.

All in `marketing/explainer/videos/<slug>/`: `captions.md` (Instagram EN + Hinglish, LinkedIn,
X, pinned comment), and in `output/` the 9:16 MP4 (Reels), 16:9 MP4 (LinkedIn, X) and three
posters. Five a week for 14 weeks: Instagram every day listed, LinkedIn on Tue and Thu
(16:9 + its LinkedIn text). Reel 1 (the screen recording, now voiced) can go out any time.

| # | When | Video | Hook |
|---|---|---|---|
| 1 | W1 Mon | `ats-rejected` | 50 applications. Zero callbacks? |
| 2 | W1 Tue | `tailor-30s` | Tailor a resume in 30 seconds. |
| 3 | W1 Thu | `ats-basics` | 3 things an ATS needs from your resume |
| 4 | W1 Fri | `fake-skills` | Can you explain every line? If AI wrote it, maybe not. |
| 5 | W1 Sun | `two-columns` | Two-column resume? The ATS reads it straight across. |
| 6 | W2 Mon | `job-words` | Same work. Different words. That's why the ATS missed you. |
| 7 | W2 Tue | `five-to-seven` | 5 of 11 → 7 of 11 without a single lie. |
| 8 | W2 Thu | `ats-checker` | What does the ATS actually read? Check free. No sign-up. |
| 9 | W2 Fri | `interview-questions` | Every line on your resume is an interview question. |
| 10 | W2 Sun | `one-page` | Two pages? Make it one. One click. |
| 11 | W3 Mon | `same-resume` | 50 jobs. One resume. That's the problem. |
| 12 | W3 Tue | `lines-prove` | Your line says Django. The job wants Python. Same thing. |
| 13 | W3 Thu | `image-pdf` | Your resume is an image? The ATS sees nothing. |
| 14 | W3 Fri | `your-words` | AI rewrote your whole resume? Pick the lines instead. |
| 15 | W3 Sun | `buzzwords` | Results-driven team player? Show the numbers. |
| 16 | W4 Mon | `profile-once` | Upload once. Tailor every time. |
| 17 | W4 Tue | `cover-letter` | Your cover letter sounds like everyone else's. |
| 18 | W4 Thu | `summary` | Same summary for every job? |
| 19 | W4 Fri | `templates` | Four templates. All ATS-safe. |
| 20 | W4 Sun | `deadline` | Closes at midnight. It's 11:30 PM. Still time. |
| 21 | W5 Mon | `chatbot` | Why not just use a chatbot? It doesn't know what's true. |
| 22 | W5 Tue | `ats-score-myth` | Your ATS score is 62/100? Real ATSs don't score you. |
| 23 | W5 Thu | `fresher` | Fresher? No experience? Your projects count. |
| 24 | W5 Fri | `tableau-not-looker` | Job wants Looker. You know Tableau. Don't write Looker. |
| 25 | W5 Sun | `must-have` | Not every keyword matters the same. |
| 26 | W6 Mon | `contact-header` | Email in the header? Many ATSs skip it. |
| 27 | W6 Tue | `headings` | "Where I've made an impact"? The ATS doesn't know it. |
| 28 | W6 Thu | `dates` | "Summer '22 – now"? Give the ATS real dates. |
| 29 | W6 Fri | `naukri` | Applying on Naukri? Its RMS reads your file into text. |
| 30 | W6 Sun | `placement` | Placement season. 30 companies. One resume? |
| 31 | W7 Mon | `skills-list` | 40 tools in your skills section? |
| 32 | W7 Tue | `quantify` | No numbers on your resume? Look for these 3. |
| 33 | W7 Thu | `verbs` | "Responsible for"? Say what you actually did. |
| 34 | W7 Fri | `condense` | 4-line bullet? Same facts, half the words. |
| 35 | W7 Sun | `both-ways` | A/B testing or experimentation? Write both. |
| 36 | W8 Mon | `ai-cant-change` | Can the AI change your dates? No. |
| 37 | W8 Tue | `career-gap` | Career gap? Don't fake the dates. |
| 38 | W8 Thu | `i-have-this` | Forgot a skill you really have? |
| 39 | W8 Fri | `fill-page` | Half your page empty? |
| 40 | W8 Sun | `one-or-two` | One page or two? Your call. One click. |
| 41 | W9 Mon | `refresh` | Updated your profile? Refresh any resume. |
| 42 | W9 Tue | `sections` | Skills first for this job? |
| 43 | W9 Thu | `lines-per-role` | 6 bullets for an old job? |
| 44 | W9 Fri | `what-you-see` | What you see is what downloads. |
| 45 | W9 Sun | `recruiter-search` | How recruiters actually find you. |
| 46 | W10 Mon | `referral` | Got a referral? Your resume still goes through the ATS. |
| 47 | W10 Tue | `fewer-better` | 100 applications. Same resume? |
| 48 | W10 Thu | `three-places` | 3 places to tailor a resume |
| 49 | W10 Fri | `job-reader` | Long job post? We pull out what it asks for. |
| 50 | W10 Sun | `hidden-keywords` | Hidden white keywords? The ATS reads them. |
| 51 | W11 Mon | `layoff` | Laid off? Tailor the ones you want most. |
| 52 | W11 Tue | `sunday-hour` | 1 hour on Sunday. 5 tailored applications. |
| 53 | W11 Thu | `soft-skills` | "Excellent communication"? Show it. |
| 54 | W11 Fri | `my-resumes` | Every resume you tailored, in one place. |
| 55 | W11 Sun | `duplicate` | Similar job? Duplicate and tweak. |
| 56 | W12 Mon | `keyword-ring` | What does 7/11 mean? |
| 57 | W12 Tue | `other-words` | The job's other words. |
| 58 | W12 Thu | `upload-any` | PDF or Word? Upload either. |
| 59 | W12 Fri | `internship` | Internship? Write it like a job. |
| 60 | W12 Sun | `narrow-margins` | 2 lines over one page? |
| 61 | W13 Mon | `cover-match` | Cover letter, same template. |
| 62 | W13 Tue | `monday-checklist` | Before you hit apply: |
| 63 | W13 Thu | `data-analyst` | Data analyst? Here's what one job asked for. |
| 64 | W13 Fri | `interview-prep` | Prep for the interview from your own lines. |
| 65 | W13 Sun | `review-once` | We read it. You check it once. |
| 66 | W14 Mon | `ats-friendly-design` | ATS-friendly doesn't mean ugly. |
| 67 | W14 Tue | `no-fake-numbers` | AI changed your 12% to 15%? Not here. |
| 68 | W14 Thu | `tailor-summary-skills` | Your summary, for this job. |
| 69 | W14 Fri | `first-impression` | The top third of your resume does the work. |
| 70 | W14 Sun | `apply-confidence` | Apply knowing every line is true. |

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
