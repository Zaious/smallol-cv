#!/usr/bin/env bash
# 取 G3–G5 的第一幀時間，並掃整局 feed 事件（10 秒對齊起點）。
cd "$(dirname "$0")/.."
for n in 3:113475871524050786 4:113475871524050787 5:113475871524050788; do
  num=${n%%:*}; gid=${n##*:}
  first=$(curl -s "https://feed.lolesports.com/livestats/v1/window/$gid" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{const d=JSON.parse(s);console.log(d.frames[0].rfc460Timestamp)})')
  echo "G$num first_frame $first" >> data/g345_starts.txt
  start=$(node -e "const t=new Date(Date.parse('$first')+10000);t.setMilliseconds(0);t.setSeconds(Math.ceil(t.getSeconds()/10)*10);console.log(t.toISOString().replace(/\.\d+Z$/,'Z'))")
  node tools/feed_tower_events.mjs $gid $start 55 > data/feed_events_g$num.txt 2>&1
done
echo ALLDONE >> data/g345_starts.txt
