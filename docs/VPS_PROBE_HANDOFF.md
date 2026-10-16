# VPS 探針交接（2026-10-17）

目的：在把 Stream CV 服務搬上 VPS 之前，先量三件事。任何一件不行，部署方式就要改。

1. VPS 能不能從 YouTube 拉到 LoL Esports 的直播（資料中心 IP 常被要求「確認不是機器人」）。
2. 1080p 串流解碼成 1 fps 畫格，VPS 的 CPU 跟不跟得上即時。
3. VPS 連得到官方 feed（`feed.lolesports.com`，免金鑰）。

本測試**不需要** API 金鑰，也不需要本 repo 的程式碼。

## 0. 環境（請把輸出貼回來）

```bash
uname -a; nproc; free -h; df -h /; python3 --version; ffmpeg -version | head -1
```

需要的工具（沒有就裝）：

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg python3-pip curl
python3 -m pip install --user -U yt-dlp
~/.local/bin/yt-dlp --version
```

## 1. YouTube 可不可達（最重要）

```bash
# 1a. 頻道直播頁的狀態（Play-In 開打時應為 is_live，其他時間 is_upcoming 或錯誤訊息）
~/.local/bin/yt-dlp --no-warnings --print "%(id)s %(live_status)s %(title)s" "https://www.youtube.com/@lolesports/live"

# 1b. Day 1 錄影版的格式清單（看有沒有 1080p，以及有沒有出現 "Sign in to confirm you're not a bot"）
~/.local/bin/yt-dlp --no-warnings -F "https://www.youtube.com/watch?v=ERhHyo_Z1Hc" | tail -15
```

判讀：
- 出現 `Sign in to confirm you're not a bot` 或 HTTP 403 → **不可達**，請直接回報，不要再試第 2 步。
- 有 `1920x1080` 的格式 → 可達。

## 2. 解碼效能（錄影版模擬串流，2 分鐘）

```bash
U=$(~/.local/bin/yt-dlp --no-warnings -f "bv*[height=1080]" -g "https://www.youtube.com/watch?v=ERhHyo_Z1Hc" | head -1)
/usr/bin/time -v ffmpeg -v error -ss 4200 -t 120 -i "$U" -vf fps=1 -f rawvideo -pix_fmt bgr24 - 2>time.txt | wc -c
grep -E "Elapsed|Percent of CPU|Maximum resident" time.txt
```

判讀：
- `wc -c` 應約為 120 × 1920 × 1080 × 3 = 746,496,000 位元組（120 格）。
- `Elapsed` 遠小於 120 秒 → 跟得上即時（錄影版下載不受即時限制，所以這裡量的是「解碼加下載」的上限）。
- 回報 `Percent of CPU` 和 `Maximum resident set size`。

## 3. 直播實拉（Play-In 開打時才做；Day 3 = 台灣 10/18 02:00 起，Day 4 = 10/19 02:00 起）

```bash
/usr/bin/time -v sh -c '~/.local/bin/yt-dlp --no-warnings -q -f "bv*[height<=1080]" -o - "https://www.youtube.com/@lolesports/live" | ffmpeg -v error -i - -t 300 -vf fps=1 -f rawvideo -pix_fmt bgr24 - | wc -c' 2>live_time.txt
grep -E "Elapsed|Percent of CPU" live_time.txt
```

判讀：5 分鐘應得約 300 格（`wc -c` ≈ 300 × 6,220,800 = 1,866,240,000）；格數明顯偏少代表斷流或跟不上。

## 4. 官方 feed 可不可達

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" "https://feed.lolesports.com/livestats/v1/window/115660588583171785"
```

判讀：`200` 為正常。

## 請回報

每一步的原始輸出（指令與輸出貼回來即可）。我根據結果決定：

| 結果 | 部署方式 |
| --- | --- |
| 1、2、4 都正常 | 整套（擷取＋服務）搬上 VPS |
| 1 不可達，4 正常 | 混合：本機或家用網路擷取畫面、只把判讀結果送上 VPS；VPS 跑服務與 feed |
| 2 跟不上 | 降成 720p 或改 0.5 fps 再測（小地圖辨識在 2025 曾用 720p 做過，但 2026 的門檻只在 1080p 驗證過） |
