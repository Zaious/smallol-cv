# 2026 半自動預標：從直播小地圖截圖抽站點小圖，存活模板 NCC 高者預標 A，其餘以 2025 分類器分 D/O；輸出依預標分組的對照圖供人工改錯。
# 用法：python tools/prelabel_2026.py <N> <seed>
import json, pickle, random, sys, glob, re
import numpy as np, cv2
sys.path.insert(0, "tools"); from state_feats import feats
N, seed = int(sys.argv[1]), int(sys.argv[2]); rnd = random.Random(seed)
cfg = json.load(open("data/minimap_sites_2026_worlds.json", encoding="utf-8")); K, R = 1.5 / 5, 22
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"}
med = cv2.imread("data/minimap_median_2026_early.png")
def crop(im, sid): cx, cy = pos[sid]; c = im[cy - R:cy + R + 1, cx - R:cx + R + 1]; return c if c.shape[:2] == (45, 45) else None
def ncc(a, b):
    a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)[9:36, 9:36]; b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)[9:36, 9:36]
    a -= a.mean(); b -= b.mean(); return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))
tpl = {s: crop(med, s) for s in pos}
a = np.load("data/live_worlds2026/mm_ncc.npy"); good = [int(n) for n, v in a if v > 0.3]
clf = pickle.load(open("data/state_clf.pkl", "rb")); model, classes = clf["model"], clf["classes"]
pool = [(n, s) for n in good for s in pos]; rnd.shuffle(pool)
crops, meta, pre = [], [], []
cnt = {"A": 0, "X": 0}
for n, s in pool:
    if len(crops) >= N: break
    im = cv2.imread(f"data/live_worlds2026/snap/mm_{n:07d}.png"); c = crop(im, s)
    if c is None: continue
    v = ncc(c, tpl[s]); g = "A" if v >= 0.75 else "X"
    if g == "A" and cnt["A"] >= N * 0.45: continue          # 存活太多，限額以多收 D/O
    cnt[g] += 1
    if g == "X":
        p = model.predict_proba(feats(c)[None])[0]; g = "D" if p[classes.index("D")] >= p[classes.index("O")] else "O"
    crops.append(c); meta.append({"game": "w26", "n": n, "site": s, "ncc": round(v, 3)}); pre.append(g)
np.savez_compressed("data/labels/w26.npz", crops=np.stack(crops)); json.dump(meta, open("data/labels/w26_meta.json", "w"))
open("data/labels/w26_prelabels.txt", "w").write("\n".join(f"{i} {g}" for i, g in enumerate(pre)))
COLS, ROWS, SC = 10, 6, 3; side = 45 * SC
for g in "ADO":
    idx = [i for i, x in enumerate(pre) if x == g]
    for k in range(0, len(idx), COLS * ROWS):
        part = idx[k:k + COLS * ROWS]; sh = np.zeros((ROWS * (side + 14), COLS * (side + 4), 3), np.uint8)
        for j, i in enumerate(part):
            r, c = divmod(j, COLS); y, x = r * (side + 14), c * (side + 4)
            sh[y + 14:y + 14 + side, x:x + side] = cv2.resize(crops[i], (side, side), interpolation=cv2.INTER_CUBIC)
            cv2.putText(sh, str(i), (x + 2, y + 11), 0, 0.42, (0, 255, 255), 1)
        cv2.imwrite(f"frames/w26_{g}_{k // (COLS * ROWS):02d}.png", sh)
from collections import Counter; print("pre", Counter(pre))
