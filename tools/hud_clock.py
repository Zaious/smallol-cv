# 讀轉播上方計分列的遊戲時鐘（2026 世界賽版面）。時鐘在全畫面 (920–1000, 70–104)；固定格寬：分十位、分個位、冒號、秒十位、秒個位。
# 建模板：python tools/hud_clock.py build   （以第 3 局每 60 秒一張的全畫面建立 0–9 模板，起點 00:40 為人工目視讀值）
# 讀取：from hud_clock import read_clock; read_clock(bgr_full_frame) -> 秒數或 None（低信心時）
import sys, os, glob
import numpy as np, cv2
CELLS = [(16, 27), (27, 38), (43, 53), (53, 64)]           # 相對於 (920, 70) 的 x 範圍；y 範圍 8–30
Y0, Y1, X0 = 78, 100, 920
TPL = os.path.join(os.path.dirname(__file__), "..", "data", "clock_digits.npz")

def _norm(c):
    c = cv2.resize(c, (10, 22)); c = c - c.mean(); return c / (np.linalg.norm(c) + 1e-6)

def cells(img, x0=X0, y0=0, dx=0, dy=0):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return [_norm(g[y0 + Y0 + dy:y0 + Y1 + dy, x0 + a + dx:x0 + b + dx]) for a, b in CELLS]

def _match(g, a, b, x0, y0, T):
    """對單一格位做 ±2 px 水平、±1 px 垂直的位移搜尋，回傳 (數字, 分數)。"""
    best = (-1, -9.0)
    for dy in (-1, 0, 1):
        for dx in (-2, -1, 0, 1, 2):
            c = _norm(g[y0 + Y0 + dy:y0 + Y1 + dy, x0 + a + dx:x0 + b + dx]); s = (T * c).sum(axis=(1, 2)); k = int(s.argmax())
            if s[k] > best[1]: best = (k, float(s[k]))
    return best

def read_clock(img, x0=X0, y0=0, min_score=0.8):
    T = np.load(TPL)["t"]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    r = [_match(g, a, b, x0, y0, T) for a, b in CELLS]; digs = [k for k, _ in r]
    if min(sc for _, sc in r) < min_score or digs[2] > 5: return None
    return (digs[0] * 10 + digs[1]) * 60 + digs[2] * 10 + digs[3]

# 已知時鐘的序列（全畫面每 60 秒一張；起點為人工目視讀值，之後每張 +60 秒，期間無暫停——以讀值連續性驗證）
SEQS = {"g3": ("full_1016T0043_", 1140, 27, 40), "g2": ("full_1015T2334_", 2460, 26, 8 * 60 + 52)}

def colon_ok(g):
    """冒號兩點都亮才算時鐘畫面（排除重播、特效遮擋）。"""
    return g[70 + 13:70 + 16, 920 + 38:920 + 42].mean() > 150 and g[70 + 25:70 + 28, 920 + 38:920 + 42].mean() > 150

def samples(names, D="data/live_worlds2026/snap"):
    for nm in names:
        pre, n0, cnt, t0 = SEQS[nm]
        for k in range(cnt):
            p = f"{D}/{pre}{n0 + 60 * k:07d}.jpg"
            if not os.path.exists(p): continue
            g = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if not colon_ok(g): continue
            t = t0 + 60 * k; yield g, [t // 600, (t // 60) % 10, (t % 60) // 10, t % 10], p, t

def build(names):
    acc = {d: [] for d in range(10)}
    for g, digs, _, _ in samples(names):
        for (a, b), d in zip(CELLS, digs): acc[d].append(_norm(g[Y0:Y1, X0 + a:X0 + b]))
    T = np.stack([_norm(np.median(acc[d], axis=0)) if acc[d] else np.zeros((22, 10), np.float32) for d in range(10)])
    for _ in range(2):
        acc2 = {d: [] for d in range(10)}
        for g, digs, _, _ in samples(names):
            for (a, b), d in zip(CELLS, digs):
                best = max(((float((T[d] * _norm(g[Y0 + dy:Y1 + dy, X0 + a + dx:X0 + b + dx])).sum()), dx, dy) for dy in (-1, 0, 1) for dx in (-2, -1, 0, 1, 2)))
                acc2[d].append(_norm(g[Y0 + best[2]:Y1 + best[2], X0 + a + best[1]:X0 + b + best[1]]))
        T = np.stack([_norm(np.median(acc2[d], axis=0)) if acc2[d] else T[d] for d in range(10)])
    return T, {d: len(v) for d, v in acc.items()}

if __name__ == "__main__" and sys.argv[1] == "build":
    names = sys.argv[2:] or ["g3", "g2"]
    T, cnt = build(names); np.savez(TPL, t=T); print("模板來源", names, "各數字樣本數", cnt)

if __name__ == "__main__" and sys.argv[1] == "test":
    names = sys.argv[2:]; right = wrong = none = 0
    for g, digs, p, t in samples(names):
        v = read_clock(cv2.merge([g.astype(np.uint8)] * 3))
        if v is None: none += 1
        elif v == t: right += 1
        else: wrong += 1; print("錯", os.path.basename(p), "真", f"{t//60}:{t%60:02d}", "讀", f"{v//60}:{v%60:02d}")
    print("測試", names, "正確", right, "錯誤", wrong, "低信心未讀", none)
