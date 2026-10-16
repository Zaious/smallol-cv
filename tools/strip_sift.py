# 底部列選角：SIFT 特徵點比對 Data Dragon 經典立繪（預設皮膚）。輸出每格前 3 名與分數。
# 只輸出格子→英雄，不做選手對應（選手↔角色在進場前會交換，屬無效資訊）。
import cv2, glob, os, sys
import numpy as np

IMG = sys.argv[1]
SLOTS = [(0, 106), (106, 214), (214, 320), (320, 426), (426, 534),
         (746, 854), (854, 960), (960, 1066), (1066, 1174), (1174, 1280)]
Y0, Y1 = 528, 720

im = cv2.imread(IMG)
sift = cv2.SIFT_create()
bf = cv2.BFMatcher()
def kd(img):
    return sift.detectAndCompute(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None)
arts = {}
for p in sorted(glob.glob("hero-art/*.jpg")):
    arts[os.path.splitext(os.path.basename(p))[0]] = kd(cv2.imread(p))

for i, (a, b) in enumerate(SLOTS):
    crop = cv2.resize(im[Y0:Y1, a:b], (b - a) * 2, (Y1 - Y0) * 2) if False else cv2.resize(im[Y0:Y1, a:b], ((b - a) * 2, (Y1 - Y0) * 2), interpolation=cv2.INTER_CUBIC)
    kp, des = kd(crop)
    scores = []
    for n, (k2, d2) in arts.items():
        if des is None or d2 is None:
            scores.append((0, n)); continue
        m = bf.knnMatch(des, d2, k=2)
        good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
        scores.append((len(good), n))
    scores.sort(reverse=True)
    print(f"slot{i+1}", " ".join(f"{n}({c})" for c, n in scores[:3]), flush=True)
