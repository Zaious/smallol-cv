# 2026 世界賽 BP 列的禁用辨識（PoC）：COACH 列左右各 5 格方形圖示（畫面 1920x1080），和 Data Dragon 16.20.1 方形圖示比對。
# 用法：python tools/bans26.py <frame.jpg> [...]   → 每格最佳英雄、分數、與第二名差距
import sys, glob, os
import numpy as np, cv2
Y0, Y1 = 711, 776
SLOTS = {"L": [(2, 69), (74, 140), (148, 212), (221, 280), (292, 356)],
         "R": [(1563, 1625), (1636, 1700), (1706, 1773), (1778, 1846), (1850, 1917)]}
M = 6                                                       # 內縮避開邊框
ICONS = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "hero-icons", "16.20.1", "*.png")))
NAMES = [os.path.splitext(os.path.basename(p))[0] for p in ICONS]
def feat(a):
    a = cv2.resize(a, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32); a -= a.mean(axis=(0, 1)); return (a / (np.linalg.norm(a) + 1e-6)).ravel()
def tpl(p):
    a = cv2.imread(p); h, w = a.shape[:2]; c = int(h * 0.06)          # Data Dragon 圖示本身有細邊，略裁
    return feat(a[c:h - c, c:w - c])
F = np.stack([tpl(p) for p in ICONS])
def read(im):
    out = {}
    for side, xs in SLOTS.items():
        out[side] = []
        for a, b in xs:
            c = im[Y0 + M:Y1 - M, a + M:b - M]
            s = F @ feat(c); o = np.argsort(-s)
            out[side].append((NAMES[o[0]], float(s[o[0]]), float(s[o[0]] - s[o[1]]), NAMES[o[1]]))
    return out
if __name__ == "__main__":
    for f in sys.argv[1:]:
        r = read(cv2.imread(f)); print(os.path.basename(f))
        for side in "LR": print(" ", side, "  ".join(f"{n}({s:.2f},+{d:.2f}|{n2})" for n, s, d, n2 in r[side]))
