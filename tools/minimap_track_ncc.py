# 灰階外觀 NCC 追蹤：每個站點取開局底圖（G1 鍍層消失後的逐像素中位數）的 15x15 灰階模板，
# 在當下畫面 ±6px 範圍內取最大正規化相關。存活約 0.9–0.99，消失約 0.4–0.55。
# 從標準輸入讀 1 fps 的灰階原始畫格（1920x1080）。用法：... | python tools/minimap_track_ncc.py - <out.csv> <t0>
import csv, json, sys
import numpy as np, cv2

OUT, T0 = sys.argv[2], int(sys.argv[3])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
medg = cv2.imread("data/minimap_median_gray_postplate.png", cv2.IMREAD_GRAYSCALE)
X0, Y0, S, K = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5
RT, SR = 7, 6
sites = []
for s in cfg["sites"]:
    cx, cy = int(round(s["x"] * K)), int(round(s["y"] * K))
    sites.append((s["id"], cx, cy, medg[cy - RT:cy + RT + 1, cx - RT:cx + RT + 1].copy()))
fb = 1920 * 1080; stream = sys.stdin.buffer; rows = []; t = T0
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    fr = np.frombuffer(b, np.uint8).reshape(1080, 1920)[Y0:Y0 + S, X0:X0 + S]
    rec = {"t": t}
    for sid, cx, cy, tpl in sites:
        win = fr[cy - RT - SR:cy + RT + SR + 1, cx - RT - SR:cx + RT + SR + 1]
        if win.shape[0] < tpl.shape[0] + 1 or win.shape[1] < tpl.shape[1] + 1: rec[sid] = 0.0; continue
        v = float(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED).max())
        rec[sid] = round(v if np.isfinite(v) else 0.0, 3)
    rows.append(rec); t += 1
    if len(rows) % 200 == 0: print("progress", len(rows), flush=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
