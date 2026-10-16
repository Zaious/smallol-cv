# 校準用：把底部 10 個格子切出來拼成一張圖，人工檢查座標是否對齊
import sys, cv2, numpy as np

SLOTS_L = [(0, 53), (53, 107), (107, 160), (160, 213), (213, 267)]   # KT（左，藍）
SLOTS_R = [(373, 427), (427, 480), (480, 533), (533, 587), (587, 640)]  # T1（右，紅）
Y0, Y1 = 262, 360

im = cv2.imread(sys.argv[1])
crops = [im[Y0:Y1, a:b] for a, b in SLOTS_L + SLOTS_R]
crops = [cv2.resize(c, (120, 130)) for c in crops]
row = np.hstack(crops)
cv2.imwrite(sys.argv[2], row)
print("ok", row.shape)
