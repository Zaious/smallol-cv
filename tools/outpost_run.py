# Outpost（VPS）上的常駐入口：把即時管線的三個行程一起拉起來，任一個結束就 10 秒後重啟。
#   1. node tools/live_feed_log.mjs <dir>          官方 feed 記錄（金鑰只讀環境變數 LOL_API_KEY，在 /etc/outpost/smallol.env）
#   2. python tools/live_watch.py <網址> <dir>      開播就拉流 → 1 fps 畫格 → 即時分類（VPS 的 IP 會被 YouTube 擋，預設 Twitch）
#   3. python tools/live_service.py --dir <dir> --port <APP_PORT>   對局狀態 HTTP（只聽 127.0.0.1，Caddy 在前面）
# 用法（systemd 的 ExecStart）：venv/bin/python tools/outpost_run.py
# 環境變數：APP_PORT（工廠注入）、LOL_API_KEY、STREAM_URL（預設 https://www.twitch.tv/riotgames）
import os, subprocess, sys, threading, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
D = os.path.join("data", "live_worlds2026")
URL = os.environ.get("STREAM_URL", "https://www.twitch.tv/riotgames")
PORT = os.environ.get("APP_PORT", "8787")
os.makedirs(os.path.join(ROOT, D), exist_ok=True)

env = dict(os.environ)
# yt-dlp 裝在 venv 裡：live_watch 用名字呼叫它。快取放在服務自己可寫的地方（家目錄在沙箱裡唯讀）。
env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
env.setdefault("XDG_CACHE_HOME", os.path.join(ROOT, "data", "cache"))
env["PYTHONUNBUFFERED"] = "1"
# 直播比官方 feed 落後的秒數（實測不到時的預設）：Twitch 約 46，YouTube 約 31。
env.setdefault("VIDEO_LAG", "46" if "twitch.tv" in URL else "31")
# feed 記錄器連線卡住時自己結束，由下面的 keep() 重開（見 live_feed_log.mjs）。
env["FEED_EXIT_ON_STUCK"] = "1"

def say(m):
    print(f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {m}", flush=True)

def keep(name, cmd):
    while True:
        say(f"啟動 {name}: {' '.join(cmd[:3])} …")
        p = subprocess.Popen(cmd, cwd=ROOT, env=env)
        code = p.wait()
        say(f"{name} 結束 code={code}，10 秒後重啟")
        time.sleep(10)

jobs = [("service", [sys.executable, os.path.join(HERE, "live_service.py"), "--dir", D, "--port", PORT]),
        ("watch", [sys.executable, os.path.join(HERE, "live_watch.py"), URL, D, "--poll", "30"])]
if env.get("LOL_API_KEY"):
    jobs.insert(0, ("feed", ["node", os.path.join(HERE, "live_feed_log.mjs"), D]))
else:
    say("缺 LOL_API_KEY：官方 feed 記錄不啟動（擊殺、經濟、龍、巴龍都來自 feed）。把它加進 /etc/outpost/smallol.env 後重啟服務。")
for name, cmd in jobs:
    threading.Thread(target=keep, args=(name, cmd), daemon=True).start()
while True:
    time.sleep(3600)
