# HUD 判斷：以一張確定有 HUD 的畫格為參考，逐秒計算中央 KT/T1 區塊的相關值。
# 相關值高＝HUD 在畫面上；低＝鏡頭切換、全螢幕動畫或浮層遮住。
import subprocess, sys
import numpy as np, cv2

VOD, START, END, REF = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 640, 360
Y0, Y1, X0, X1 = 262, 300, 268, 372   # 中央 KT / T1 區塊
ref = cv2.imread(REF)
ref_g = cv2.cvtColor(ref[Y0:Y1, X0:X1], cv2.COLOR_BGR2GRAY).astype(np.float32)
ref_g = (ref_g - ref_g.mean()) / (ref_g.std() + 1e-6)

cmd = ["ffmpeg", "-v", "error", "-ss", str(START), "-t", str(END - START), "-i", VOD,
       "-vf", "fps=1,scale=640:360", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
fb = W * H * 3
t = START
out = []
while True:
    buf = p.stdout.read(fb)
    if len(buf) < fb:
        break
    im = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    g = cv2.cvtColor(im[Y0:Y1, X0:X1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = (g - g.mean()) / (g.std() + 1e-6)
    ncc = float((g * ref_g).mean())
    out.append((t, round(ncc, 3)))
    t += 1
p.wait()
for tt, v in out:
    print(f"{tt//60}:{tt%60:02d} {v:+.3f}")
