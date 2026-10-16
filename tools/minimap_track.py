# 逐秒追蹤小地圖站點的隊伍顏色像素數，輸出 CSV。用法：python tools/minimap_track.py <vod> <start> <dur> <out.csv>
import json, subprocess, sys, csv
import numpy as np, cv2
VOD, START, DUR, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0 = cfg["crop_origin_in_frame"]
R = 5
cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(DUR), "-i", VOD, "-vf", "fps=1,scale=1280:720",
       "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
fb = 1280 * 720 * 3
rows = []; t = START
while True:
    b = p.stdout.read(fb)
    if len(b) < fb: break
    im = np.frombuffer(b, np.uint8).reshape(720, 1280, 3)
    crop = im[Y0:Y0 + 190, X0:X0 + 190]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, sa, v = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    red = ((h < 8) | (h > 170)) & (sa > 110) & (v > 70)
    blue = (h > 88) & (h < 108) & (sa > 110) & (v > 60)
    rec = {"t": t}
    for s in cfg["sites"]:
        cx, cy = int(round(s["x"] / 5)), int(round(s["y"] / 5))
        m = red if s["team"] == "R" else blue
        rec[s["id"]] = int(m[cy - R:cy + R + 1, cx - R:cx + R + 1].sum())
    rows.append(rec); t += 1
    if len(rows) % 300 == 0: print("progress", len(rows), flush=True)
p.wait()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
