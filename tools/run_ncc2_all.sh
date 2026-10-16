#!/usr/bin/env bash
# 雙模板追蹤：開發集 G1–G5、準決賽 S1–S4、八強賽 Q3 Q5（已完整下載者）。輸出 data/minimap_ncc2_<name>.csv
cd "$(dirname "$0")/.."
run() { name=$1; f=$2; t0=$3
  ffmpeg -v error -i "$f" -vf fps=1 -f rawvideo -pix_fmt gray - | python tools/minimap_track_ncc2.py - data/minimap_ncc2_$name.csv $t0 > data/ncc2_$name.log 2>&1
  echo "$name done" >> data/ncc2_progress_v1.txt; }
run g1 vod/probe1080/seg_10000_11304.mp4 10000 &
run g2 vod/probe1080/g2_13500_15300.mp4 13500 &
run g3 vod/probe1080/g3_17546_19008.mp4 17546 &
run g4 vod/probe1080/g4_21094_22183.mp4 21094 &
wait
run g5 vod/probe1080/g5_24270_25741.mp4 24270 &
run s1 vod/semi/s1.mp4 0 &
run s2 vod/semi/s2.mp4 0 &
run s3 vod/semi/s3.mp4 0 &
wait
run s4 vod/semi/s4.mp4 0 &
run q3 vod/qf/q3.mp4 0 &
run q5 vod/qf/q5.mp4 0 &
wait
echo ALLDONE >> data/ncc2_progress_v1.txt
