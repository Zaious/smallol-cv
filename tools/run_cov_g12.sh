#!/usr/bin/env bash
cd "$(dirname "$0")/.."
ffmpeg -v error -i vod/probe1080/seg_10000_11304.mp4 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_cov.py - data/minimap_cov_g1.csv 10000 > data/cov_g1.log 2>&1
ffmpeg -v error -i vod/probe1080/g2_13500_15300.mp4 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_cov.py - data/minimap_cov_g2.csv 13500 > data/cov_g2.log 2>&1
echo ALLDONE > data/cov_g12.done
