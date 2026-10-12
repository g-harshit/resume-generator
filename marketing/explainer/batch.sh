#!/bin/sh
# Stage 1 for every kit-built video: voice, stills (both shapes), posters, captions.
# Stage 2 (with "render"): the two MP4s, three videos at a time.
# Usage: batch.sh [render] [slug …]
cd "$(dirname "$0")/../.."
MODE=prep; [ "$1" = render ] && { MODE=render; shift; }
SLUGS=${*:-$(for d in marketing/explainer/videos/*/; do [ -f "$d/scenes.html" ] || basename "$d"; done)}
one() {
  s=$1
  if [ $MODE = prep ]; then
    node marketing/explainer/render.mjs "$s" en v --still >/dev/null &&
    node marketing/explainer/render.mjs "$s" en h --still >/dev/null &&
    node marketing/explainer/poster.mjs "$s" >/dev/null &&
    node marketing/explainer/captions.mjs "$s" && echo "prep ok: $s" || echo "prep FAILED: $s"
  else
    node marketing/explainer/render.mjs "$s" en v >/dev/null && node marketing/explainer/render.mjs "$s" en h >/dev/null &&
    echo "render ok: $s" || echo "render FAILED: $s"
  fi
}
# Voices one video at a time: ElevenLabs' smaller plans refuse many parallel requests.
if [ $MODE = prep ]; then
  for s in $SLUGS; do node marketing/explainer/voice.mjs "$s" en >/dev/null || echo "voice FAILED: $s"; done
fi
n=0
for s in $SLUGS; do
  one "$s" &
  n=$((n + 1)); [ $((n % 3)) = 0 ] && wait
done
wait
