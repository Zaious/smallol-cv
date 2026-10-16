#!/usr/bin/env bash
# 下載準決賽 GEN vs KT 四局單局影片（1080p H.264）。四個平行，完成寫入 data/semi_dl_done_v1.txt
cd "$(dirname "$0")/.."
mkdir -p vod/semi
dl() { n=$1; id=$2
  yt-dlp -f "bv*[height=1080][vcodec^=avc1]" -o "vod/semi/s$n.%(ext)s" "https://www.youtube.com/watch?v=$id" > data/dl_semi_s$n.log 2>&1
  echo "s$n done" >> data/semi_dl_done_v1.txt; }
dl 1 jEMKzyJElws &
dl 2 lwS8mBsBv3w &
dl 3 -xuXNryO3CA &
dl 4 4lVbhCxL3CI &
wait
echo ALLDONE >> data/semi_dl_done_v1.txt
