# COACH 列禁用追蹤（PoC）：1280 寬、每秒一張，切出 10 個方形格，和 Data Dragon 方形圖比對。
# 輸出每秒每格的最佳英雄與分數，寫 CSV。不使用任何外部禁用清單當先驗。
import subprocess, sys, csv, glob, os
import numpy as np, cv2

VOD, START, END, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 1280, 720
Y0, Y1 = 472, 518
SLOTS_L = [2, 50, 98, 146, 194]
SLOTS_R = [1038, 1086, 1134, 1182, 1230]
SZ = 44

icon_paths = sorted(glob.glob("hero-icons/*.png"))
names = [os.path.splitext(os.path.basename(p))[0] for p in icon_paths]

def feat(a):
    a = cv2.resize(a, (40, 40), interpolation=cv2.INTER_AREA).astype(np.float32)
    a = a - a.mean()
    return (a / (np.linalg.norm(a) + 1e-6)).ravel()

F = np.stack([feat(cv2.imread(p)) for p in icon_paths])

cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(END - START), "-i", VOD,
       "-vf", "fps=1,scale=1280:720", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
fb = W * H * 3
rows = []
t = START
while True:
    buf = p.stdout.read(fb)
    if len(buf) < fb:
        break
    im = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    rec = {"t": t}
    for side, xs in [("L", SLOTS_L), ("R", SLOTS_R)]:
        for i, x in enumerate(xs):
            crop = im[Y0 + 3:Y0 + SZ - 1, x + 3:x + SZ - 1]
            b, g, r = [float(v) for v in crop.reshape(-1, 3).mean(0)]
            if b > 200 and r < 60:          # 藍色佔位（尚未填入）
                state = "pending"
            elif r > 185 and g > 160 and b < 170 and b < g:   # 米色空格
                state = "empty"
            else:
                state = "filled"
            s = F @ feat(crop)
            j = int(s.argmax())
            rec[f"{side}{i+1}_state"] = state
            rec[f"{side}{i+1}_name"] = names[j]
            rec[f"{side}{i+1}_score"] = round(float(s[j]), 3)
    rows.append(rec)
    t += 1
p.wait()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("frames", len(rows))
