#!/usr/bin/env bash
# 八強賽 T1 vs AL（最後驗證集）：下載五局單局影片 -> NCC 追蹤；同時掃 feed 事件。規則凍結前不得拿來調參。
cd "$(dirname "$0")/.."
mkdir -p vod/qf
PROG=data/qf_progress_v1.txt
one() { n=$1; vid=$2; gid=$3
  yt-dlp -f "bv*[height=1080][vcodec^=avc1]" -o "vod/qf/q$n.%(ext)s" "https://www.youtube.com/watch?v=$vid" > data/dl_qf_q$n.log 2>&1
  echo "q$n downloaded" >> $PROG
  ffmpeg -v error -i vod/qf/q$n.mp4 -vf fps=1 -f rawvideo -pix_fmt gray - | python tools/minimap_track_ncc.py - data/minimap_ncc_q$n.csv 0 > data/ncc_q$n.log 2>&1
  echo "q$n tracked" >> $PROG
  first=$(curl -s "https://feed.lolesports.com/livestats/v1/window/$gid" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{const d=JSON.parse(s);console.log(d.frames[0].rfc460Timestamp)})')
  echo "Q$n $first" >> data/qf_starts_v1.txt
  st=$(node -e "const t=new Date(Date.parse('$first')+10000);t.setMilliseconds(0);t.setSeconds(Math.ceil(t.getSeconds()/10)*10);console.log(t.toISOString().replace(/\.\d+Z\$/,'Z'))")
  node tools/feed_tower_events.mjs $gid $st 55 > data/feed_events_q$n.txt 2>&1
  echo "q$n feed" >> $PROG
}
one 1 tCJA61nFXHA 113475871523985212 &
one 2 YRnRL_q1XQg 113475871523985213 &
one 3 IFbTfJh8R3o 113475871523985214 &
one 4 zvALENbYZjU 113475871523985215 &
one 5 dVw8MykeXuk 113475871523985216 &
wait
echo ALLDONE >> $PROG
