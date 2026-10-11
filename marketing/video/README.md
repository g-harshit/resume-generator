# Reel recorder

Records a 9:16 screen video of the website for Instagram Reels / Shorts, with captions,
tap marks and the AI wait times cut out. Uses a fictional person (`resume.html`) and job
(`jd.txt`) against the **local** app, so no real data and no production accounts.

```bash
make api                                            # API on 8100 (needs OPENAI_API_KEY in backend/.env)
NEXT_PUBLIC_APP_NAME="QuickFit CV" pnpm build:web   # the site, with the real name
node marketing/video/setup.mjs                      # demo PDF + a fresh local test account
node marketing/video/reel-1.mjs                     # frames → output/reel-1/
marketing/video/encode.sh reel-1                    # → output/reel-1.mp4
```

Run `setup.mjs` before every recording: a Reel can change the demo profile ("I have this"
saves the skill to it), and the next run must start from the same place.

- `reel-1.mjs` — "Tailor a resume in 30 seconds": paste a job, keywords, rewrite a line, PDF.
- `reel-2.mjs` — "Why the ATS skips you": 5 of 11 skills, then honestly up to 7; what she
  doesn't have stays missing.
- `reel.mjs` — what they share: captions, cards, tap marks, scrolling, and a screencast
  clock that pauses while the AI works.

The model reads the job a little differently each run (wording, capitals), so Reel scripts
take numbers and keyword names from the page rather than hard-coding them. Captions sit
near the top: Instagram's own buttons cover the bottom third and the right edge. Animated
explainers (not screen recordings) are made with `marketing/explainer/` — see the
`explainer-video` skill. Other Reel ideas are in `docs/marketing.md`.
