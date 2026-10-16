#!/usr/bin/env bash
cd "$(dirname "$0")/.."
( ffmpeg -v error -i vod/probe1080/seg_10000_11304.mp4 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_tiou.py - data/minimap_tiou_g1.csv 10000 > data/tiou_g1.log 2>&1 ) &
( ffmpeg -v error -i vod/probe1080/g2_13500_15300.mp4 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_tiou.py - data/minimap_tiou_g2.csv 13500 > data/tiou_g2.log 2>&1 ) &
wait
echo ALLDONE > data/tiou_g12.done
