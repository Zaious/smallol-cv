# 小地圖結構存在判斷：各站點的畫格影像與開局中位數底圖的差異（平均絕對差）。
import json, subprocess, sys
import numpy as np, cv2
VOD = sys.argv[1]
times = [int(x) for x in sys.argv[2:]]
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
med = cv2.imread("data/minimap_median_start.png")
X0, Y0 = cfg["crop_origin_in_frame"]
R = 4   # 底圖像素半徑（9x9）
def grab(t):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t), "-i", VOD, "-frames:v", "1", "-vf", "scale=1280:720",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, np.uint8).reshape(720, 1280, 3)
def mad(im, s):
    cx, cy = int(round(s["x"] / 5)), int(round(s["y"] / 5))
    a = med[cy - R:cy + R + 1, cx - R:cx + R + 1].astype(float)
    b = im[Y0 + cy - R:Y0 + cy + R + 1, X0 + cx - R:X0 + cx + R + 1].astype(float)
    return float(np.abs(a - b).mean())
print("site".ljust(20), *[f"{t:>6d}" for t in times])
frames = [grab(t) for t in times]
for s in cfg["sites"]:
    print(s["id"].ljust(20), *[f"{mad(f, s):6.1f}" for f in frames])
