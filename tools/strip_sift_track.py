# 底部列選角追蹤：每秒一張，10 格各做 SIFT 比對 Data Dragon 經典立繪，寫 CSV（逐格、逐秒）。
# 只記格子→英雄；不做選手對應。用法：python tools/strip_sift_track.py <vod> <start> <end> <out.csv>
import subprocess, sys, csv, glob, os
import numpy as np, cv2

VOD, START, END, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 1280, 720
SLOTS = [(0, 106), (106, 214), (214, 320), (320, 426), (426, 534),
         (746, 854), (854, 960), (960, 1066), (1066, 1174), (1174, 1280)]
Y0, Y1 = 528, 720

sift = cv2.SIFT_create()
bf = cv2.BFMatcher()
arts = {}
for p in sorted(glob.glob("hero-art/*.jpg")):
    g = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY)
    kp, des = sift.detectAndCompute(g, None)
    arts[os.path.splitext(os.path.basename(p))[0]] = des

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
    for i, (a, b) in enumerate(SLOTS):
        crop = cv2.resize(im[Y0:Y1, a:b], ((b - a) * 2, (Y1 - Y0) * 2), interpolation=cv2.INTER_CUBIC)
        kp, des = sift.detectAndCompute(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None)
        best = ("", 0, 0)
        if des is not None:
            for n, d2 in arts.items():
                if d2 is None:
                    continue
                m = bf.knnMatch(des, d2, k=2)
                good = sum(1 for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance)
                if good > best[1]:
                    best = (n, good, 0)
        rec[f"s{i+1}_name"] = best[0]
        rec[f"s{i+1}_score"] = best[1]
    rows.append(rec)
    if len(rows) % 20 == 0:
        print("progress", len(rows), flush=True)
    t += 1
p.wait()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
