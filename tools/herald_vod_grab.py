# 預示者公告素材：從 Twitch 錄影版抓每局 15:00–19:50（預示者在場時段）每秒一張的「畫面上方擊殺公告區」裁切。
# 先抓一張 1080p 畫格讀計分列時鐘校正錄影版位置，再以 720p 抓整段（只裁公告區，存 PNG）。
# 用法：python tools/herald_vod_grab.py <twitch_video_id> <vod_start_iso> <gameId> [...]
import sys, os, json, subprocess, datetime as dt
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__)); from hud_clock import read_clock_safe, read_clock
VID, START = sys.argv[1], sys.argv[2]; GAMES = sys.argv[3:]
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
D = "data/live_worlds2026"; OUT = "data/herald_ann"
url = lambda h: subprocess.run(["yt-dlp", "--no-warnings", "-f", f"best[height<={h}]", "-g", f"https://www.twitch.tv/videos/{VID}"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip().splitlines()[0]

def frame(u, off, w, h):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(off), "-i", u, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3) if len(raw) == w * h * 3 else None

u1080 = url(1080); u720 = url(720)
for gid in GAMES:
    r = [json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl", encoding="utf-8")]
    st0 = ts(next(x["ts"] for x in r if x["state"] == "in_game"))
    guess = st0 + 46 + 900 - ts(START)                       # 錄影版中遊戲 15:00 的粗估位置
    clock = None
    for d in (0, 7, 13, 21, 37, 53, 71, 97, 131, -29, -61, -97):   # 讀不到（0/9、重播或遮擋）就前後挪幾秒再讀
        im = frame(u1080, guess + d, 1920, 1080)
        if im is None: continue
        c = read_clock_safe(im)
        if c is not None: clock = (guess + d, c); break
    if clock is None: print(gid, "時鐘校正失敗，略過", flush=True); continue
    off15 = clock[0] + (900 - clock[1])                      # 遊戲 15:00 在錄影版的位置
    os.makedirs(f"{OUT}/{gid}", exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(off15 - 5), "-t", "300", "-i", u720,
           "-vf", "fps=1,crop=534:44:373:126", f"{OUT}/{gid}/a_%04d.png"]   # 720p 下的公告區（1080p 的 560–1360 × 190–255 乘 2/3；整句「Blue team has defeated the Rift Herald」都在內）
    subprocess.run(cmd, stdin=subprocess.DEVNULL)
    n = len(os.listdir(f"{OUT}/{gid}"))
    json.dump({"vod": VID, "off15": off15, "first_frame_clock": 895}, open(f"{OUT}/{gid}/meta.json", "w"))
    print(gid, f"錄影版 15:00 位置 {off15:.0f} 秒，存 {n} 張", flush=True)
