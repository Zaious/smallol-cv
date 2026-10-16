# 與 train_state_clf.py 相同的特徵（單獨成檔，供訓練與追蹤共用）。輸入：45x45 BGR 小圖。
import numpy as np, cv2
def feats(img):
    c = img[9:36, 9:36]
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32); g = (g - g.mean()) / (g.std() + 1e-6)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).astype(np.float32)
    h = cv2.resize(hsv[:, :, 0] / 180.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    s = cv2.resize(hsv[:, :, 1] / 255.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    v = cv2.resize(hsv[:, :, 2] / 255.0, (9, 9), interpolation=cv2.INTER_AREA).ravel()
    sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    e = cv2.resize(np.hypot(sx, sy)[6:21, 6:21], (8, 8), interpolation=cv2.INTER_AREA).ravel()
    return np.concatenate([cv2.resize(g, (14, 14), interpolation=cv2.INTER_AREA).ravel(), h, s, v, e])
