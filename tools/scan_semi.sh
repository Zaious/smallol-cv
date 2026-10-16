#!/usr/bin/env bash
# 取準決賽 GEN vs KT 四局的第一幀時間，並掃整局 feed 事件（10 秒對齊起點）。
cd "$(dirname "$0")/.."
OUT=data/semi_starts_v1.txt
for n in 242:1 243:2 244:3 245:4; do
  gid=113475871523985${n%%:*}; num=${n##*:}
  first=$(curl -s "https://feed.lolesports.com/livestats/v1/window/$gid" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{const d=JSON.parse(s);console.log(d.frames[0].rfc460Timestamp)})')
  echo "S$num $first" >> $OUT
  st=$(node -e "const t=new Date(Date.parse('$first')+10000);t.setMilliseconds(0);t.setSeconds(Math.ceil(t.getSeconds()/10)*10);console.log(t.toISOString().replace(/\.\d+Z\$/,'Z'))")
  node tools/feed_tower_events.mjs $gid $st 55 > data/feed_events_s$num.txt 2>&1
done
echo ALLDONE >> $OUT
