#!/bin/bash
# 每天 09:00 UTC（沒有比賽的時段）跑一次，見 smallol-daily.timer：
#   1. 更新 yt-dlp（Twitch 一改版舊版就可能讀不到轉播）；有新版且目前沒比賽時重開讀轉播的程序。
#   2. 刪掉 7 天前的轉播畫面（snap/，每天約 0.7 GB）。
cd "$(dirname "$0")/../.."
before=$(venv/bin/yt-dlp --version 2>/dev/null)
venv/bin/pip install -q -U yt-dlp
after=$(venv/bin/yt-dlp --version 2>/dev/null)
echo "yt-dlp $before -> $after"
if [ "$before" != "$after" ]; then tools/safe_restart.sh watch || echo "現在不能重開讀轉播的程序，下次重開時自然用新版"; fi
n=$(find data/live_worlds2026/snap -type f -mtime +7 | wc -l)
find data/live_worlds2026/snap -type f -mtime +7 -delete
echo "刪掉 $n 張 7 天前的畫面"
