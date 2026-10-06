#!/bin/sh
# Frames → output/reel.mp4 (1080x1920, H.264, silent track; add music in Instagram).
set -e
cd "$(dirname "$0")/output"
FFMPEG=$(uvx --with imageio-ffmpeg python -c "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())")
"$FFMPEG" -y -hide_banner -loglevel error -f concat -safe 0 -i frames.txt -f lavfi -i anullsrc=r=44100:cl=stereo \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xf4f2ec,fps=30,format=yuv420p" \
  -c:v libx264 -preset slow -crf 18 -profile:v high -c:a aac -b:a 128k -shortest -movflags +faststart reel.mp4
echo "$(pwd)/reel.mp4"
