# 探針：以灰階外觀的正規化相關（NCC）比較「存在」與「消失」的分離度。模板取 G1 開局底圖（乾淨、無英雄）。
import json, subprocess, sys
import numpy as np, cv2
VOD, T0, G0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
med = cv2.imread("data/minimap_median_1080.png", cv2.IMREAD_GRAYSCALE)
X0, Y0, S, K, R = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5, 11
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"]}
sites = sys.argv[4].split(",")
tpl = {s: med[pos[s][1] - 9:pos[s][1] + 10, pos[s][0] - 9:pos[s][0] + 10] for s in sites}
cmd = ["ffmpeg", "-v", "error", "-ss", "0", "-i", VOD, "-vf", "fps=1/10", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
raw = subprocess.Popen(cmd, stdout=subprocess.PIPE)
fb = 1920 * 1080; t = T0
print("game  " + "  ".join(s[:14].ljust(14) for s in sites))
while True:
    b = raw.stdout.read(fb)
    if len(b) < fb: break
    g = np.frombuffer(b, np.uint8).reshape(1080, 1920)[Y0:Y0 + S, X0:X0 + S]
    vals = []
    for s in sites:
        cx, cy = pos[s]; win = g[cy - R - 3:cy + R + 4, cx - R - 3:cx + R + 4]
        res = cv2.matchTemplate(win, tpl[s], cv2.TM_CCOEFF_NORMED)
        vals.append(float(res.max()))
    gg = t - G0
    print(f"{gg//60}:{gg%60:02d}  " + "  ".join(f"{v:14.2f}" for v in vals))
    t += 10
