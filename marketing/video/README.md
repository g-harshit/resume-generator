# Reel recorder

Records a 9:16 screen video of the website for Instagram Reels / Shorts, with captions,
tap marks and the AI wait times cut out. Uses a fictional person (`resume.html`) and job
(`jd.txt`) against the **local** app, so no real data and no production accounts.

```bash
make api                                            # API on 8100 (needs OPENAI_API_KEY in backend/.env)
NEXT_PUBLIC_APP_NAME="QuickFit CV" pnpm build:web   # the site, with the real name
node marketing/video/setup.mjs                      # demo PDF + local test account + confirmed profile
node marketing/video/record.mjs                     # frames → output/
marketing/video/encode.sh                           # → output/reel.mp4
```

`record.mjs` is Reel 1 ("Tailor a resume in 30 seconds"); the other ideas are in
`docs/marketing.md`. Captions sit near the top: Instagram's own buttons cover the bottom
third and the right edge.
