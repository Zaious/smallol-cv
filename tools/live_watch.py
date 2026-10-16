# 無人值守：輪詢來源，開播就拉流 → 1 fps 畫格 → 即時分類；串流結束或中斷就回到等待。不存影片。
# 用法：python tools/live_watch.py <網址> <out_dir> [--poll 60] [--rehearsal]
#   網址例：https://www.youtube.com/@lolesports/live
#   --rehearsal：不等待開播，直接拉該網址（用於點播影片預演同一條管線）
import os, subprocess, sys, time, datetime as dt

URL, OUT = sys.argv[1], sys.argv[2]
poll = int(sys.argv[sys.argv.index("--poll") + 1]) if "--poll" in sys.argv else 60
rehearsal = "--rehearsal" in sys.argv
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "watch.log"), "a", encoding="utf-8")
def say(m):
    line = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {m}"; print(line, flush=True); log.write(line + "\n"); log.flush()

def is_live():
    r = subprocess.run(["yt-dlp", "--no-warnings", "--print", "%(live_status)s", URL], capture_output=True, text=True, timeout=120)
    return r.stdout.strip().splitlines()[-1:] == ["is_live"]

here = os.path.dirname(os.path.abspath(__file__))
while True:
    try:
        if not rehearsal:
            while not is_live():
                say("尚未開播，等待"); time.sleep(poll)
        say("開始拉流")
        ydl = subprocess.Popen(["yt-dlp", "--no-warnings", "-q", "-f", "bv*[height<=1080]/b[height<=1080]", "-o", "-"] + os.environ.get("YDL_EXTRA", "").split() + [URL], stdout=subprocess.PIPE, stderr=open(os.path.join(OUT, "yt-dlp.err"), "a"))
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-i", "-", "-vf", "fps=1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdin=ydl.stdout, stdout=subprocess.PIPE)
        ydl.stdout.close()
        clf = subprocess.Popen([sys.executable, os.path.join(here, "live_classify.py"), OUT, "--snap-every", "15", "--full-every", "60"], stdin=ff.stdout, stdout=open(os.path.join(OUT, "classify.log"), "a"))
        ff.stdout.close(); clf.wait(); say(f"分類器結束 code={clf.returncode}")
        for p in (ff, ydl):
            try: p.terminate()
            except Exception: pass
    except Exception as e:
        say(f"例外：{e!r}")
    if rehearsal: break
    time.sleep(poll)
