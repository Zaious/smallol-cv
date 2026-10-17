# 2026 世界賽 BP 列的禁用辨識：COACH 列左右各 5 格方形圖示（畫面 1920x1080），和 Data Dragon 16.20.1 方形圖示比對。
# 轉播的圖示是同一張圖放大裁切，所以每個英雄模板取 1.0／1.15／1.3 三種放大倍率的最高分。
# 最終禁用：BP 列消失前最後 3 張可見畫格的分數加總，10 格一對一指派（同一局禁用不重複）。
# 規則以 Day 1 第 1–4 局調定（40/40），第 5–8 局為盲測。左列 = 左側隊伍禁用 1–5（由左而右）；右列 = 右側隊伍禁用 1–5（由右而左）。
# 用法：python tools/bans26.py <frame.jpg> [...]   → 每格最佳英雄與分數
import sys, glob, os
import numpy as np, cv2
Y0, Y1 = 711, 776
SLOTS = {"L": [(2, 69), (74, 140), (148, 212), (221, 280), (292, 356)],
         "R": [(1563, 1625), (1636, 1700), (1706, 1773), (1778, 1846), (1850, 1917)]}
M = 6                                                       # 內縮避開邊框
ZOOMS = (1.0, 1.15, 1.3)
ICONS = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "hero-icons", "16.20.1", "*.png")))
NAMES = [os.path.splitext(os.path.basename(p))[0] for p in ICONS]

def feat(a):
    a = cv2.resize(a, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32); a -= a.mean(axis=(0, 1)); return (a / (np.linalg.norm(a) + 1e-6)).ravel()

def _variants(p):
    a = cv2.imread(p); h, w = a.shape[:2]; c = int(h * 0.06); a = a[c:h - c, c:w - c]; n = a.shape[0]; out = []
    for z in ZOOMS:
        s = int(n / z); o = (n - s) // 2; out.append(feat(a[o:o + s, o:o + s]))
    return out

F = np.stack([v for p in ICONS for v in _variants(p)])     # (英雄數 × 倍率數, 特徵)

def slot_scores(im):
    """回傳 10 × 英雄數 的分數矩陣（左 5 格、右 5 格）。"""
    rows = []
    for side in "LR":
        for a, b in SLOTS[side]:
            s = F @ feat(im[Y0 + M:Y1 - M, a + M:b - M]); rows.append(s.reshape(len(NAMES), len(ZOOMS)).max(axis=1))
    return np.stack(rows)

_PEND_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ban_pending.npy")
PEND = np.load(_PEND_PATH) if os.path.exists(_PEND_PATH) else None

def slot_scores_live(im):
    """BP 進行中用：正在禁用的格子會閃動，舊比對常讀成 Sona。該格若比任何英雄都像 PENDING 模板（tools/ban_pending.py，
    以 Day 2 建立），整列分數歸零＝視為未定。Day 1（未參與建模板）的 Sona 誤報 146 次 → 0 次。"""
    S = slot_scores(im)
    if PEND is not None:
        j = 0
        for side in "LR":
            for a, b in SLOTS[side]:
                if float(PEND @ feat(im[Y0 + M:Y1 - M, a + M:b - M])) >= S[j].max(): S[j] = 0
                j += 1
    return S

def visible(im):
    gr = im.mean(axis=2)
    return all(gr[700:709, x0:x1].mean() < 25 and gr[714:774, x0:x1].mean() > 30 for x0, x1 in ((0, 360), (1560, 1915)))

def final_bans(frames, last=3):
    """frames：依時間排序的 BGR 畫格。回傳 (左側隊伍禁用 1–5, 右側隊伍禁用 1–5)；看不到 BP 列時回 None。"""
    from scipy.optimize import linear_sum_assignment
    vis = [im for im in frames if visible(im)]
    if not vis: return None
    S = sum(slot_scores(im) for im in vis[-last:])
    _, c = linear_sum_assignment(-S); res = [NAMES[i] for i in c]
    return res[:5], res[5:][::-1]

def read(im):
    S = slot_scores(im); out = {}
    for k, side in enumerate("LR"):
        out[side] = []
        for i in range(5):
            o = np.argsort(-S[k * 5 + i]); out[side].append((NAMES[o[0]], float(S[k * 5 + i, o[0]]), float(S[k * 5 + i, o[0]] - S[k * 5 + i, o[1]]), NAMES[o[1]]))
    return out

if __name__ == "__main__":
    for f in sys.argv[1:]:
        r = read(cv2.imread(f)); print(os.path.basename(f))
        for side in "LR": print(" ", side, "  ".join(f"{n}({s:.2f},+{d:.2f}|{n2})" for n, s, d, n2 in r[side]))
