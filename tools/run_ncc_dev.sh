#!/usr/bin/env bash
# 用 NCC 追蹤器重跑五場開發集（平行，從標準輸入讀灰階畫格）
cd "$(dirname "$0")/.."
run() { g=$1; f=$2; t0=$3
  ffmpeg -v error -i "$f" -vf fps=1 -f rawvideo -pix_fmt gray - | python tools/minimap_track_ncc.py - data/minimap_ncc_$g.csv $t0 > data/ncc_$g.log 2>&1
  echo "$g done" >> data/ncc_progress_v1.txt; }
run g1 vod/probe1080/seg_10000_11304.mp4 10000 &
run g2 vod/probe1080/g2_13500_15300.mp4 13500 &
run g3 vod/probe1080/g3_17546_19008.mp4 17546 &
wait
run g4 vod/probe1080/g4_21094_22183.mp4 21094 &
run g5 vod/probe1080/g5_24270_25741.mp4 24270 &
wait
echo ALLDONE >> data/ncc_progress_v1.txt
