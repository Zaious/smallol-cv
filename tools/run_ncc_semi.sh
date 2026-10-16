#!/usr/bin/env bash
# 準決賽四局（未看過的驗證集）NCC 追蹤。只產生原始 NCC 序列，不涉及任何判斷規則。
cd "$(dirname "$0")/.."
run() { n=$1
  ffmpeg -v error -i vod/semi/s$n.mp4 -vf fps=1 -f rawvideo -pix_fmt gray - | python tools/minimap_track_ncc.py - data/minimap_ncc_s$n.csv 0 > data/ncc_s$n.log 2>&1
  echo "s$n done" >> data/ncc_semi_progress_v1.txt; }
run 1 &
run 2 &
run 3 &
run 4 &
wait
echo ALLDONE >> data/ncc_semi_progress_v1.txt
