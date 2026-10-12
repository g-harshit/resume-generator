---
name: explainer-video
description: Make a short animated explainer video for QuickFit CV — motion graphics (word-by-word headlines, rebuilt UI cards, counters, stamps, before/after numbers), an AI voiceover in English or Hinglish, rendered as MP4 in 9:16 (Instagram Reels, Shorts) and 16:9 (X, LinkedIn, the site). Use whenever the user asks for a promo, explainer, ad, marketing or "Opus-style" video, a new Reel that isn't a screen recording, or another language version of one.
---

# Explainer videos

Each video is a folder under `marketing/explainer/videos/<slug>/`:

- `script.json` — the voiceover, one entry per scene (`id`, `en`, `hi`), plus the voice.
- `scenes.html` — the scenes: HTML/CSS, animated with a GSAP timeline the renderer seeks
  frame by frame (so every frame is exact, at any speed of machine).
- `output/` — git-ignored: voice clips, `timing.json`, stills, frames, the MP4s.

The shared tools are in `marketing/explainer/`:

```bash
node marketing/explainer/voice.mjs <slug> en          # voice clips + timing.json (OpenAI TTS, key from backend/.env)
node marketing/explainer/render.mjs <slug> en v --still # one PNG per scene, 9:16 — look before rendering
node marketing/explainer/render.mjs <slug> en v       # → videos/<slug>/output/<slug>-en-9x16.mp4
node marketing/explainer/render.mjs <slug> en h       # → …-en-16x9.mp4
```

The voice sets the pace: each scene lasts its clip plus 0.35 s, the headline's words appear
over the clip, and the clips are mixed in at each scene's start. A Hinglish version is
`voice.mjs <slug> hi` then the same renders — no scene changes. A full render takes a few
minutes per shape; run it in the background.

### Kit-built videos (the default)

Most videos need no HTML at all: `marketing/explainer/kit.html` builds scenes from
`script.json`. Each scene names a `type` and its parameters, plus `say` (the headline,
"line one|line two", each line ≤ 19 characters or it wraps), `en`/`hi` (the voice) and an
optional `hold`. Types: `stat`, `resume`, `job`, `paste`, `rewrite`, `missing`, `ihave`,
`compare`, `chat`, `strike`, `checklist`, `pages`, `templates`, `atstext`, `letter`,
`steps`, `text`, `end` — read their parameters in the kit's `B` object, and copy a scene
from any `videos/*/script.json` that uses the type. The script also carries `poster`
(`head`: up to three lines, the third in red; `scene`: whose finished visual to show) and
`captions` (`ig_en`, `ig_hi`, `linkedin`, `x`, `comment`). Each type has a minimum time on
screen, so short lines still let the animation land.

```bash
marketing/explainer/batch.sh [slug …]          # voices (one at a time), stills, posters, captions.md
marketing/explainer/batch.sh render [slug …]   # both MP4s, three videos in parallel
```

Without slugs, batch.sh does every kit-built video. Review every still and poster before
`render`. A video with its own `scenes.html`/`poster.html` (`ats-rejected`, `fake-skills`)
uses those instead — only for visuals the kit can't do; better to add a type to the kit.

## Making one

1. **The story. 20–25 s in total, never more** — the user rejected a 46 s cut: "people
   will leave". About 7 scenes, 1.5–5 s of voice each. The shape that works: a hook that
   is on screen in the very first frame (the pain, with a number: "50 applications. Zero
   callbacks?") → why it happens → the product fixing it → what makes it trustworthy →
   end card ("Link in bio!"). Cut every scene that only restates another. If the user
   gave only a topic, write the story yourself and state it in a line; ask only when the
   angle is genuinely unclear.
2. **`script.json`.** Write lines the way a creator talks, not an announcer: short,
   punchy, with exclamations and asides ("Fifty!", "Ugh.", "That's it!"), numbers in
   words. The user judged a flat, read-out voice "not even close" to the reference — the
   delivery matters as much as the visuals. Put ElevenLabs cues before the words they
   colour: `[excited]`, `[sighs]`, `[incredulous]`, `[frustrated]`, `[warmly]`. Keep `hi`
   natural Hinglish in Devanagari, as people actually speak it.
   - `"provider": "elevenlabs"`, model `eleven_v3`: the key is in `backend/.env`. The
     default voice is Liam (`TX3LPaxmHKxFdv7VOQHJ`, "Energetic, Social Media Creator");
     list the account's voices with `GET https://api.elevenlabs.io/v1/voices` (header
     `xi-api-key`) when the user wants another. `"openai"` is the fallback, whose
     `instructions` do what they can and whose input has the cues stripped.
   - `"speed"`: 1.0 for ElevenLabs, ~1.05 for OpenAI (voice.mjs also trims each clip's
     silence). Clips are cached by request, so changing speed or one line costs only that
     line. ElevenLabs bills by character: don't regenerate unchanged lines.
3. **`scenes.html`.** One `<section class="scene" id="…">` per script entry. The script
   decides which scenes play and in what order (sections it leaves out stay hidden, so
   `ats-rejected/scenes.html` doubles as a library of scenes: applied, same, match,
   rejected, byhand, seconds, paste, rewrite, honest, end). Guard each scene's animation
   block with `if (has("<id>"))`. The first scene is fully on screen at frame 0. Per scene:
   - `<div class="copy" data-say="Line one|line two">` — the on-screen headline: two short
     lines, ≤ 6 words each, ink then grey. A shorthand of the voice, not a transcript.
   - `<div class="vis">` — an 860×860 box (scaled up in 9:16) with the visual: cards,
     chips, counters, stamps. Rebuild UI as HTML in the brand; never screenshots.
   - Its animations in the timeline section, at `starts.<id> + offset`, inside `dur(id)`.
     Use `tl.fromTo`/`tl.to`/`tl.set` (all reversible) and `counter(...)` for numbers —
     never `tl.call` or class toggles, which a seek can't undo.
   - The `end` scene: logo, line, `quickfitcv.com`.
4. **Voice**, then **stills** for both shapes. Read every still: text clipped or orphaned
   words, overlaps, anything inside Instagram's covered areas (in 9:16, the top ~220 px
   and the bottom ~340 px; keep the right edge clear too). Fix and re-run stills.
5. **Render** both shapes, make a contact sheet of each MP4 (ffmpeg `fps=1/2.5,tile`)
   and check it, then send the MP4s with SendUserFile.
6. **Posters and captions**, every time, without being asked:
   - `poster.html` (copy `ats-rejected`'s): the hook headline plus the video's key visual,
     and the logo. `node marketing/explainer/poster.mjs <slug>` renders the Reel cover
     (9:16, content kept inside the middle 4:5 the profile grid shows), a 4:5 feed post
     and a 16:9 thumbnail. Read all three for overlaps before sending.
   - `captions.md`: Instagram in English and Hinglish (hook line first, the steps, "link
     in bio", a comment prompt, 8 hashtags), X (≤ 280 counting the link as 23; check it),
     LinkedIn (founder voice, the honesty rule stated plainly), and a first comment to pin.
7. Commit `script.json`, `captions.md` (and `scenes.html`/`poster.html` where a video has
   them), never `output/`.

## Rules

- **Honest numbers only.** The product's promise is that it never invents facts; its ads
  can't either. Demo figures come from the real demo (the Priya Sharma profile and the
  Northwind job in `marketing/video/`: 5 of 11 skills, 5 → 7 after tailoring). Claims like
  "45 minutes by hand" must be stated as typical, never as measured stats.
- **Brand**: ground `#f7f6f2`, ink `#17181c`, accent `#2f5d50`, missing/warning
  `#c66a1e` on `#fbebdd`; IBM Plex Sans (text), IBM Plex Mono (numbers, labels),
  Instrument Serif (the name only); the logo from `brand/logo-mark.svg`.
- No music in the file — the user adds a trending track in Instagram (copyright mutes).
- Name the product only through what's on screen and in the voice; `APP_NAME` rules for
  the app don't apply to marketing assets.

## Gotchas

- `window.seek` must return nothing: returning the GSAP timeline makes Playwright try to
  serialise it, and the render hangs.
- Fonts come from Google Fonts and GSAP from cdnjs, so rendering needs the network.
- ffmpeg comes from `uvx --with imageio-ffmpeg` (no system ffmpeg needed).
- Screen-recorded Reels of the real app are a different tool: `marketing/video/`
  (`reel-1.mjs`, `reel-2.mjs`).
