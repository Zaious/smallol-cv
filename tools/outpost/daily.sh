#!/bin/bash
# 每天 09:00 UTC（沒有比賽的時段）跑一次，見 smallol-daily.timer：
#   1. 更新 yt-dlp（Twitch 一改版舊版就可能讀不到轉播）；有新版且目前沒比賽時重開讀轉播的程序。
#   2. 刪掉 7 天前的轉播畫面（snap/，每天約 0.7 GB）。
#   3. 重開資料服務：它的記憶體一天會長到 1.5–2 GB（2026-10-25、26 量測）；辨識快取會存檔再讀回，重開不必重算。
#      系統套件更新也不再自動重開它（tools/outpost/needrestart-smallol.conf），統一在這裡、沒有比賽的時候。
cd "$(dirname "$0")/../.."
before=$(venv/bin/yt-dlp --version 2>/dev/null)
venv/bin/pip install -q -U yt-dlp
after=$(venv/bin/yt-dlp --version 2>/dev/null)
echo "yt-dlp $before -> $after"
if [ "$before" != "$after" ]; then tools/safe_restart.sh watch || echo "現在不能重開讀轉播的程序，下次重開時自然用新版"; fi
n=$(find data/live_worlds2026/snap -type f -mtime +7 | wc -l)
find data/live_worlds2026/snap -type f -mtime +7 -delete
echo "刪掉 $n 張 7 天前的畫面"
tools/safe_restart.sh service || echo "現在不能重開資料服務（部署閘門擋下）"
