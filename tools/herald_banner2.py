# 預示者歸屬 v2：取代 herald_banner.py 的整句比對（2026-10-18 Day 3 直播 0/4 全錯：「Blue team has summoned…」被判成 Red）。
# 公告區（1080p 的 fr[190:255, 560:1360]，或 720p 的 crop=534:44:373:126）縮到 534×44 後拆兩步：
#   1. 是不是預示者公告：句尾「Rift Herald!」比對（軟文字遮罩，x 362–436，左右滑動 −10…+20；
#      擊殺／召喚句長不同，句子置中，所以句尾會移動）。「Rift Herald has spawned!」句尾不同，不會命中。
#   2. 是哪一方：公告底下的底線顏色，藍方藍色、紅方紅色（rows 32–44、x 150–400 的高飽和像素數）。
# 驗收（2026-10-18）：錄影版 12 局留一局，擊殺＋召喚 23 段全對，公告分數 0.96–0.98、非公告最高 0.68；
#   Day 3 直播 1080p 盲測（模板只用錄影版）：比賽時間內 9 段全為藍方，4/4 局與 Leaguepedia 一致。
# 用法：python tools/herald_banner2.py build   （存 assets/herald_banner2.npz）
import sys, os, glob
import numpy as np, cv2
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "herald_banner2.npz")
X0, X1 = 362, 436                                           # 擊殺公告的「Rift Herald!」位置（534 寬尺度）
THR = 0.85

def tmask(img):
    im = cv2.resize(img, (534, 44), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    t = np.clip((hsv[..., 2] - 120) / 80, 0, 1) * np.clip((120 - hsv[..., 1]) / 60, 0, 1)
    return cv2.GaussianBlur(t, (0, 0), 0.8)[6:38]

def end_score(img, T, lo=-10, hi=20):
    m = tmask(img); w = T.shape[1]; t = T - T.mean(); best = -1.0
    for dx in range(lo, hi + 1):
        a = m[:, X0 + dx:X0 + dx + w]
        if a.shape[1] < w: continue
        a = a - a.mean(); best = max(best, float((a * t).sum() / (np.sqrt((a * a).sum() * (t * t).sum()) + 1e-9)))
    return best

def bar(img):
    """底線的（藍, 紅）高飽和像素數。"""
    im = cv2.resize(img, (534, 44), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
    band = hsv[32:44, 150:400]; h, s, v = band[..., 0], band[..., 1], band[..., 2]
    strong = (s > 110) & (v > 110)
    return int((strong & (h >= 95) & (h <= 125)).sum()), int((strong & ((h <= 8) | (h >= 168))).sum())

def load(path=OUT):
    return np.load(path)["herald_end"]

def detect(img_seq, T, thr=THR):
    """img_seq：依時間排序的 (key, img)。回傳每段預示者公告 [{"first": key, "last": key, "n": 張數, "score": 最高分, "team": "B"/"R"/None, "bar": (藍, 紅)}]。
    同一段內加總底線像素；一方 >= 另一方兩倍且 >= 100 才給隊伍，否則 None。"""
    segs, cur, gap = [], None, 0
    for key, img in img_seq:
        s = end_score(img, T)
        if s >= thr:
            b, r = bar(img)
            if cur is None: cur = {"first": key, "last": key, "n": 0, "score": s, "bar": [0, 0]}
            cur["last"] = key; cur["n"] += 1; cur["score"] = max(cur["score"], s); cur["bar"][0] += b; cur["bar"][1] += r; gap = 0
        elif cur is not None:
            gap += 1
            if gap > 2: segs.append(cur); cur = None
    if cur is not None: segs.append(cur)
    for c in segs:
        b, r = c["bar"]
        c["team"] = "B" if b >= 100 and b >= 2 * r else "R" if r >= 100 and r >= 2 * b else None
        c["bar"] = tuple(c["bar"])
    return segs

# ── 標註（錄影版 data/herald_ann/<gameId>/a_<n>.png 的擊殺公告第一張，人工目視）──
HERALD = {"115660588583040711": (44, "B"), "115660588583171784": (70, "B"), "115660588583171785": (151, "B"),
          "115660588583171788": (25, "R"), "115660588583171791": (133, "B"), "115660588583171792": (50, "B"),
          "115660588583171793": (39, "R"), "115660588583171795": (47, "B"), "115660588583171796": (28, "B"),
          "115660588583171797": (231, "B"), "116299649500204436": (240, "B"), "116299649500204440": (36, "B")}

def frames(gid): return sorted(glob.glob(f"data/herald_ann/{gid}/a_*.png"))

def build(gids):
    return np.mean([tmask(cv2.imread(f))[:, X0:X1] for g in gids for f in frames(g)[HERALD[g][0] - 1:HERALD[g][0] + 3]], axis=0)

if __name__ == "__main__" and sys.argv[1] == "eval":
    sys.stdout.reconfigure(encoding="utf-8")
    gids = sorted(HERALD); ok = 0
    for g in gids:
        T = build([x for x in gids if x != g])
        segs = detect([(i + 1, cv2.imread(f)) for i, f in enumerate(frames(g))], T)
        good = bool(segs) and all(s["team"] == HERALD[g][1] for s in segs); ok += good
        print(g[-3:], "正解", HERALD[g][1], [(s["first"], s["last"], round(s["score"], 2), s["team"], s["bar"]) for s in segs], "OK" if good else "NG")
    print(f"錄影版留一局：{ok}/{len(gids)}")

if __name__ == "__main__" and sys.argv[1] == "build":
    np.savez(OUT, herald_end=build(sorted(HERALD))); print("已存", OUT)
