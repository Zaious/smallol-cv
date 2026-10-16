# 取遊戲開頭一段的小地圖逐像素中位數，去除移動物件，留下固定圖示（塔、兵營、目標）。
import subprocess, sys
import numpy as np, cv2
VOD, START, DUR, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
X0, Y0, X1, Y1 = 1085, 525, 1275, 715
cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(DUR), "-i", VOD, "-vf", "fps=1,scale=1280:720",
       "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
fb = 1280 * 720 * 3
stack = []
while True:
    b = p.stdout.read(fb)
    if len(b) < fb: break
    im = np.frombuffer(b, np.uint8).reshape(720, 1280, 3)
    stack.append(im[Y0:Y1, X0:X1].copy())
p.wait()
med = np.median(np.stack(stack), axis=0).astype(np.uint8)
cv2.imwrite(OUT, med)
cv2.imwrite(OUT.replace(".png", "_x5.png"), cv2.resize(med, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC))
print("frames", len(stack), "->", OUT)
