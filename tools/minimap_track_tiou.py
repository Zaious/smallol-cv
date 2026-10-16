# 乾淨模板 IoU 追蹤：當下畫面的隊伍顏色遮罩 vs 固定模板的 IoU（±3px 偏移取最大）。
# 從標準輸入讀 1 fps 的 BGR 原始畫格（1920x1080）。用法：... | python tools/minimap_track_cov.py - <out.csv> <t0>
import json, sys, csv
import numpy as np, cv2
OUT, T0 = sys.argv[2], int(sys.argv[3])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
import os
tpl = np.load(os.environ.get("TEMPLATES", "data/minimap_templates_1080.npz"))
X0, Y0, S, K, R = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5, 9
def masks(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, sa, v = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    return (((h < 8) | (h > 170)) & (sa > 110) & (v > 70)), ((h > 88) & (h < 108) & (sa > 110) & (v > 60))
sites = [(s["id"], s["team"], int(round(s["x"] * K)), int(round(s["y"] * K)), tpl[s["id"]]) for s in cfg["sites"]]
fb = 1920 * 1080 * 3; stream = sys.stdin.buffer; rows = []; t = T0
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    im = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)
    cr, cb = masks(im[Y0:Y0 + S, X0:X0 + S]); rec = {"t": t}
    for sid, team, cx, cy, tp in sites:
        m = cr if team == "R" else cb; n = int(tp.sum()); best = 0.0
        if n >= 10:
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    patch = m[cy - R + dy:cy + R + 1 + dy, cx - R + dx:cx + R + 1 + dx]
                    if patch.shape == tp.shape:
                        u = int((patch | tp).sum()); best = max(best, float((patch & tp).sum()) / u if u else 0.0)
        rec[sid] = round(best, 3)
    rows.append(rec); t += 1
    if len(rows) % 200 == 0: print("progress", len(rows), flush=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
