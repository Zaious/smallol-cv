#!/usr/bin/env bash
# 依序下載 G3–G5 的 1080p60 片段，並用乾淨模板 IoU 追蹤器處理（從標準輸入讀畫格，不改參數）。
cd "$(dirname "$0")/.."
URL="https://www.youtube.com/watch?v=ADaZLxI3uWg"
for spec in "g3 17546 19008" "g4 21094 22183" "g5 24270 25741"; do
  set -- $spec; g=$1; a=$2; b=$3
  yt-dlp -f 299 --download-sections "*$a-$b" -o "vod/probe1080/${g}_${a}_${b}.%(ext)s" "$URL" > data/dl_$g.log 2>&1
  ffmpeg -v error -i "vod/probe1080/${g}_${a}_${b}.mp4" -vf fps=1 -f rawvideo -pix_fmt bgr24 - | python tools/minimap_track_tiou.py - data/minimap_tiou_$g.csv $a > data/tiou_$g.log 2>&1
  echo "$g done" >> data/g345_progress.txt
done
echo ALLDONE >> data/g345_progress.txt
