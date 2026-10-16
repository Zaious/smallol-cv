# 1080p 版：逐秒追蹤小地圖站點，當下遮罩 vs 1080p 開局底圖遮罩，取 ±3px 偏移下的最大 IoU。
# 站點座標沿用 720p 校準表（x,y 為 5 倍圖座標），換算倍率 k = 1.5 / 5。
import json, subprocess, sys, csv
import numpy as np, cv2
VOD, START, DUR, OUT, T0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0, S = int(1085 * 1.5), int(525 * 1.5), 285
R = 9
K = 1.5 / 5
def masks(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, sa, v = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    red = ((h < 8) | (h > 170)) & (sa > 110) & (v > 70)
    blue = (h > 88) & (h < 108) & (sa > 110) & (v > 60)
    return red, blue
med = cv2.imread("data/minimap_median_1080.png")
mr, mb = masks(med)
tpl = {}
for s in cfg["sites"]:
    cx, cy = int(round(s["x"] * K)), int(round(s["y"] * K))
    m = mr if s["team"] == "R" else mb
    tpl[s["id"]] = (cx, cy, m[cy - R:cy + R + 1, cx - R:cx + R + 1].copy())
def iou(a, b):
    u = np.logical_or(a, b).sum()
    return 0.0 if u == 0 else float(np.logical_and(a, b).sum()) / float(u)
# VOD == "-"：從標準輸入讀原始 BGR 畫格（1 fps），與產品路徑相同；否則由本程式啟動 ffmpeg。
if VOD == "-":
    stream = sys.stdin.buffer; p = None
else:
    cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(DUR), "-i", VOD, "-vf", "fps=1",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE); stream = p.stdout
fb = 1920 * 1080 * 3
rows = []; t = T0
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    im = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)
    cr, cb = masks(im[Y0:Y0 + S, X0:X0 + S])
    rec = {"t": t}
    for s in cfg["sites"]:
        cx, cy, tm = tpl[s["id"]]
        m = cr if s["team"] == "R" else cb
        best = 0.0
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                y0, x0 = cy - R + dy, cx - R + dx
                if y0 < 0 or x0 < 0: continue
                patch = m[y0:y0 + 2 * R + 1, x0:x0 + 2 * R + 1]
                if patch.shape != tm.shape: continue
                best = max(best, iou(patch, tm))
        rec[s["id"]] = round(best, 3)
    rows.append(rec); t += 1
    if len(rows) % 200 == 0: print("progress", len(rows), flush=True)
if p: p.wait()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
