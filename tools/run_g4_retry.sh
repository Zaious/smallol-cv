#!/usr/bin/env bash
cd "$(dirname "$0")/.."
URL="https://www.youtube.com/watch?v=ADaZLxI3uWg"
rm -f vod/probe1080/g4_21094_22183.mp4*
yt-dlp -f 299 --download-sections "*21094-22183" -o "vod/probe1080/g4_21094_22183.%(ext)s" "$URL" > data/dl_g4b.log 2>&1
ffmpeg -v error -i vod/probe1080/g4_21094_22183.mp4 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_tiou.py - data/minimap_tiou_g4.csv 21094 > data/tiou_g4.log 2>&1
echo G4RETRY_DONE > data/g4_retry.done
