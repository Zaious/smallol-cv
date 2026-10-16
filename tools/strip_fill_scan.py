# 掃描所有畫格：每格算平均亮度與飽和度，印出時間軸（PoC，未校準閾值）
import glob, os, cv2, numpy as np

SLOTS = [(0, 53), (53, 107), (107, 160), (160, 213), (213, 267),
         (373, 427), (427, 480), (480, 533), (533, 587), (587, 640)]
Y0, Y1 = 262, 360
FPS_SEC = 30  # 抽樣間隔（秒）

for path in sorted(glob.glob("frames/g1/t_*.jpg")):
    idx = int(os.path.basename(path)[2:6])
    t = (idx - 1) * FPS_SEC
    im = cv2.imread(path)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    vals = []
    for a, b in SLOTS:
        v = hsv[Y0:Y1, a:b, 2].mean()
        s = hsv[Y0:Y1, a:b, 1].mean()
        vals.append((v, s))
    mm, ss = divmod(t, 60)
    print(f"{mm:02d}:{ss:02d} " + " ".join(f"{int(v):3d}/{int(s):3d}" for v, s in vals))
