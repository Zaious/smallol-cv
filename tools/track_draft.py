# 追蹤草稿段：1 fps 解碼，逐秒計算 COACH 列（禁用）與底部列（選角）每格的亮度／飽和度，寫 CSV
# 不寫出整張畫格，只寫數值。用法：python tools/track_draft.py <vod> <start_sec> <end_sec> <out.csv>
import subprocess, sys, csv
import numpy as np, cv2

VOD, START, END, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 640, 360
COACH_Y0, COACH_Y1 = 230, 256
COACH_L = [(4, 26), (28, 50), (52, 74), (76, 98), (100, 122)]
COACH_R = [(518, 540), (542, 564), (566, 588), (590, 612), (614, 636)]
STRIP_Y0, STRIP_Y1 = 262, 360
STRIP_L = [(0, 53), (53, 107), (107, 160), (160, 213), (213, 267)]
STRIP_R = [(373, 427), (427, 480), (480, 533), (533, 587), (587, 640)]

cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(END - START), "-i", VOD,
       "-vf", "fps=1,scale=640:360", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
frame_bytes = W * H * 3
rows = []
t = START
while True:
    buf = p.stdout.read(frame_bytes)
    if len(buf) < frame_bytes:
        break
    im = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    rec = {"t": t}
    for name, Y0, Y1, slots in [("coach", COACH_Y0, COACH_Y1, COACH_L + COACH_R),
                                 ("strip", STRIP_Y0, STRIP_Y1, STRIP_L + STRIP_R)]:
        for i, (a, b) in enumerate(slots):
            c = hsv[Y0:Y1, a:b]
            rec[f"{name}{i}_v"] = round(float(c[:, :, 2].mean()), 1)
            rec[f"{name}{i}_s"] = round(float(c[:, :, 1].mean()), 1)
    rows.append(rec)
    t += 1
p.wait()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("frames", len(rows), "->", OUT)
