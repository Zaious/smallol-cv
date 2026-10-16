# 以標準地圖座標推算塔在小地圖上的位置，疊在畫格上供目視校準。座標來自記憶，需以畫面驗證。
import cv2, sys
import numpy as np

IMG, OUT = sys.argv[1], sys.argv[2]
X0, Y0, S = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])   # 地圖左上角與邊長（像素）
M = 14870.0
BLUE = {"top_outer": (981, 10441), "top_inner": (1512, 6699), "top_inhib": (1169, 4287),
        "mid_outer": (5846, 6396), "mid_inner": (5048, 4812), "mid_inhib": (3651, 3696),
        "bot_outer": (10504, 1029), "bot_inner": (6919, 1483), "bot_inhib": (4281, 1253),
        "nexus_a": (1748, 2270), "nexus_b": (2177, 1807)}
RED = {"top_outer": (4318, 13875), "top_inner": (7943, 13411), "top_inhib": (10481, 13651),
       "mid_outer": (8955, 8510), "mid_inner": (9767, 10113), "mid_inhib": (11134, 11207),
       "bot_outer": (13866, 4505), "bot_inner": (13327, 8226), "bot_inhib": (13624, 10572),
       "nexus_a": (12611, 13084), "nexus_b": (13052, 12612)}

def px(g):
    return int(round(X0 + g[0] / M * S)), int(round(Y0 + (1 - g[1] / M) * S))

im = cv2.imread(IMG)
for name, g in BLUE.items():
    cv2.circle(im, px(g), 4, (255, 255, 0), 1)
for name, g in RED.items():
    cv2.circle(im, px(g), 4, (0, 255, 255), 1)
crop = im[520:720, 1080:1280]
cv2.imwrite(OUT, cv2.resize(crop, (800, 800), interpolation=cv2.INTER_NEAREST))
print("ok")
