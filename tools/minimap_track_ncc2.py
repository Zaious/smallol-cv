# 雙模板 NCC 追蹤：每個塔站點同時輸出
#   <site>   = 與「存活模板」（15x15）的最大 NCC（±6px）
#   <site>_d = 與「消失後空地背景模板」（27x27，來自 data/minimap_dead_templates.npz）的最大 NCC（±3px）
# 判斷：<site> 高 → 存活；<site>_d 高 → 已消失（看到空地）；兩者皆低 → 被遮擋／未知。
# 從標準輸入讀 1 fps 灰階畫格。用法：... | python tools/minimap_track_ncc2.py - <out.csv> <t0>
import csv, json, sys
import numpy as np, cv2

OUT, T0 = sys.argv[2], int(sys.argv[3])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
medg = cv2.imread("data/minimap_median_gray_postplate.png", cv2.IMREAD_GRAYSCALE)
dead = np.load("data/minimap_dead_templates.npz")
X0, Y0, S, K = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5
RT, SR, SRD = 7, 6, 3
sites = []
for s in cfg["sites"]:
    cx, cy = int(round(s["x"] * K)), int(round(s["y"] * K))
    d = dead[s["id"]] if s["id"] in dead.files else None
    sites.append((s["id"], cx, cy, medg[cy - RT:cy + RT + 1, cx - RT:cx + RT + 1].copy(), d))
fb = 1920 * 1080; stream = sys.stdin.buffer; rows = []; t = T0
def ncc(win, tpl):
    if win.shape[0] <= tpl.shape[0] or win.shape[1] <= tpl.shape[1]: return 0.0
    v = float(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED).max()); return v if np.isfinite(v) else 0.0
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    fr = np.frombuffer(b, np.uint8).reshape(1080, 1920)[Y0:Y0 + S, X0:X0 + S]
    rec = {"t": t}
    for sid, cx, cy, tpl, d in sites:
        rec[sid] = round(ncc(fr[cy - RT - SR:cy + RT + SR + 1, cx - RT - SR:cx + RT + SR + 1], tpl), 3)
        if d is not None:
            h = d.shape[0] // 2
            rec[sid + "_d"] = round(ncc(fr[cy - h - SRD:cy + h + SRD + 1, cx - h - SRD:cx + h + SRD + 1], d), 3)
        else: rec[sid + "_d"] = 0.0
    rows.append(rec); t += 1
    if len(rows) % 200 == 0: print("progress", len(rows), flush=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
