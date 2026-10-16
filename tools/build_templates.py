# 以固定出現的像素建立站點模板：60 張畫格中，隊伍顏色遮罩出現比例 >= 0.5 的像素才保留（去掉兵線軌跡）。
import json, subprocess, sys
import numpy as np, cv2
VOD = sys.argv[1]
SS = sys.argv[2] if len(sys.argv) > 2 else "0"
DUR = sys.argv[3] if len(sys.argv) > 3 else "100000"
OUTNPZ = sys.argv[4] if len(sys.argv) > 4 else "data/minimap_templates_1080.npz"
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0, S, K, R = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5, 9
def masks(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, sa, v = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    return (((h < 8) | (h > 170)) & (sa > 110) & (v > 70)), ((h > 88) & (h < 108) & (sa > 110) & (v > 60))
cmd = ["ffmpeg", "-v", "error", "-ss", SS, "-t", DUR, "-i", VOD, "-vf", "fps=1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE); fb = 1920 * 1080 * 3
accR = np.zeros((S, S)); accB = np.zeros((S, S)); n = 0
while True:
    b = p.stdout.read(fb)
    if len(b) < fb: break
    im = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)
    r, bl = masks(im[Y0:Y0 + S, X0:X0 + S]); accR += r; accB += bl; n += 1
p.wait()
fracR, fracB = accR / n, accB / n
out = {}
for s in cfg["sites"]:
    cx, cy = int(round(s["x"] * K)), int(round(s["y"] * K))
    f = fracR if s["team"] == "R" else fracB
    patch = (f[cy - R:cy + R + 1, cx - R:cx + R + 1] >= 0.5)
    out[s["id"]] = patch
    print(f"{s['id']:20s} template px = {int(patch.sum())}")
np.savez(OUTNPZ, **{k: v for k, v in out.items()})
print("frames", n)
