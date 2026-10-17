# 預示者歸屬：畫面上方公告「Blue/Red team has defeated the Rift Herald!」。
# 特徵：公告區（1080p 的 560–1360 × 190–255；720p 錄影版為 534×44 的裁切）米白色文字的軟遮罩，縮成固定大小後做 NCC，允許水平位移。
# 標註（人工目視，Day 1+2 共 12 局）：每局的「defeated the Rift Herald」公告出現在哪一張、是 Blue 還是 Red；與 Leaguepedia 12/12 一致。
# 用法：python tools/herald_banner.py eval    （留一局驗證）  |  python tools/herald_banner.py build （以全部標註存模板到 assets/）
import sys, os, glob, json
import numpy as np, cv2
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "herald_banner_templates.npz")
W, H = 267, 22                                              # 特徵大小（720p 裁切 534×44 的一半）
LABELS = {   # gameId 結尾: (公告第一張的檔名編號, 方)
    "115660588583040711": (44, "B"), "115660588583171784": (70, "B"), "115660588583171785": (151, "B"),
    "115660588583171788": (25, "R"), "115660588583171791": (133, "B"), "115660588583171792": (50, "B"),
    "115660588583171793": (39, "R"), "115660588583171795": (47, "B"), "115660588583171796": (28, "B"),
    "115660588583171797": (231, "B"), "116299649500204436": (240, "B"), "116299649500204440": (36, "B")}

def mask(img):
    """img：720p 錄影版裁切（44×534）或 1080p 即時裁切（65×800）。回傳文字特徵（H×W）。
    軟文字遮罩：亮度高且飽和度低者為字（不硬切二值），再輕微模糊。二值遮罩在 720p 模板對 1080p 畫面只有 0.72；軟遮罩為 0.89–0.91。"""
    im = cv2.resize(img, (534, 44), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    t = np.clip((hsv[..., 2] - 120) / 80, 0, 1) * np.clip((120 - hsv[..., 1]) / 60, 0, 1)
    t = cv2.GaussianBlur(t, (0, 0), 1.0)
    return cv2.resize(t[6:38], (W, H), interpolation=cv2.INTER_AREA)

def ncc_shift(a, t, max_shift=8):
    best = -1.0
    for dx in range(-max_shift, max_shift + 1):
        b = np.roll(a, dx, axis=1); x, y = b - b.mean(), t - t.mean()
        best = max(best, float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-9)))
    return best

def frames(gid): return sorted(glob.glob(f"data/herald_ann/{gid}/a_*.png"))

def runs(gid, i0):
    """從標註的第一張起，文字持續出現的連續畫格（公告約顯示 4 秒）。"""
    out = []
    for f in frames(gid)[i0 - 1:i0 + 6]:
        m = mask(cv2.imread(f))
        if m.mean() < 0.04: break
        out.append(m)
    return out

def templates(gids):
    T = {"B": [], "R": []}
    for g in gids:
        i0, side = LABELS[g]; T[side] += runs(g, i0)
    return {k: np.mean(v, axis=0) for k, v in T.items() if v}

def detect(img_seq, T, thr):
    """img_seq：依時間排序的公告區裁切。回傳 (方, 第幾張, 分數) 或 None：第一張任一方模板分數 >= thr 的畫格。"""
    for i, im in enumerate(img_seq):
        m = mask(im)
        if m.mean() < 0.04: continue
        sc = {k: ncc_shift(m, t) for k, t in T.items()}
        k = max(sc, key=sc.get)
        if sc[k] >= thr: return k, i, sc[k]
    return None

if __name__ == "__main__" and sys.argv[1] == "eval":
    sys.stdout.reconfigure(encoding="utf-8")
    gids = sorted(LABELS)
    # 先看分數分布：每局「預示者公告」與「其他公告」對兩個模板的最高分（模板不含本局）
    for thr in (0.6, 0.7, 0.8):
        ok = 0; rows = []
        for g in gids:
            T = templates([x for x in gids if x != g])
            r = detect([cv2.imread(f) for f in frames(g)], T, thr)
            truth = LABELS[g]
            good = r is not None and r[0] == truth[1] and abs(r[1] + 1 - truth[0]) <= 3
            ok += good; rows.append((g[-3:], truth, None if r is None else (r[0], r[1] + 1, round(r[2], 2)), "OK" if good else "NG"))
        print(f"門檻 {thr}：{ok}/{len(gids)}"); [print("   ", *x) for x in rows if x[3] == "NG"]
    # 其他公告（非預示者擊殺）的最高分，看有沒有誤判空間
    T = templates(gids); worst = []
    for g in gids:
        i0, _ = LABELS[g]
        for j, f in enumerate(frames(g), 1):
            if i0 - 1 <= j <= i0 + 7: continue
            m = mask(cv2.imread(f))
            if m.mean() < 0.04: continue
            worst.append((max(ncc_shift(m, t) for t in T.values()), g[-3:], j))
    worst.sort(reverse=True); print("其他公告對模板的最高分（前 5）:", [(round(s, 2), g, j) for s, g, j in worst[:5]])

if __name__ == "__main__" and sys.argv[1] == "build":
    T = templates(sorted(LABELS)); np.savez(OUT, **T); print("已存", OUT, sorted(T))
