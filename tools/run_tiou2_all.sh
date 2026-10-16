#!/usr/bin/env bash
# 用鍍層消失後的模板重跑五場（平行，從標準輸入讀畫格）
cd "$(dirname "$0")/.."
export TEMPLATES=data/minimap_templates_1080_postplate.npz
run() { g=$1; f=$2; t0=$3
  ffmpeg -v error -i "$f" -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_tiou.py - data/minimap_tiou2_$g.csv $t0 > data/tiou2_$g.log 2>&1
  echo "$g done" >> data/tiou2_progress.txt; }
rm -f data/tiou2_progress.txt
run g1 vod/probe1080/seg_10000_11304.mp4 10000 &
run g2 vod/probe1080/g2_13500_15300.mp4 13500 &
run g3 vod/probe1080/g3_17546_19008.mp4 17546 &
wait
run g4 vod/probe1080/g4_21094_22183.mp4 21094 &
run g5 vod/probe1080/g5_24270_25741.mp4 24270 &
wait
echo ALLDONE >> data/tiou2_progress.txt
