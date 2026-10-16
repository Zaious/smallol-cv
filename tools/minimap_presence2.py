# 小地圖結構存在判斷（顏色版）：各站點 9x9 區域內「該隊顏色」的像素數。
import json, subprocess, sys
import numpy as np, cv2
VOD = sys.argv[1]
times = [int(x) for x in sys.argv[2:]]
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0 = cfg["crop_origin_in_frame"]
R = 5
def grab(t):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t), "-i", VOD, "-frames:v", "1", "-vf", "scale=1280:720",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, np.uint8).reshape(720, 1280, 3)
def count(im, s):
    cx, cy = int(round(s["x"] / 5)), int(round(s["y"] / 5))
    patch = im[Y0 + cy - R:Y0 + cy + R + 1, X0 + cx - R:X0 + cx + R + 1]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    h, sa, v = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    if s["team"] == "R": m = ((h < 8) | (h > 170)) & (sa > 110) & (v > 70)
    else: m = (h > 88) & (h < 108) & (sa > 110) & (v > 60)
    return int(m.sum())
print("site".ljust(20), *[f"{t:>6d}" for t in times])
frames = [grab(t) for t in times]
tot = {t: {"R": 0, "B": 0} for t in times}
for s in cfg["sites"]:
    row = []
    for t, f in zip(times, frames):
        c = count(f, s); row.append(c)
        if s["kind"] == "tower" and c >= 6: tot[t][s["team"]] += 1
    print(s["id"].ljust(20), *[f"{c:6d}" for c in row])
print("towers counted present:", {t: tot[t] for t in times})
