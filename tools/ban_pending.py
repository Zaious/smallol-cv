# 「待選中」格子的模板：BP 進行中，正在禁用的那格會顯示一個閃動的畫面，舊比對常把它讀成 Sona。
# 從 Day 2 的非比賽畫面（off_<RUN>_*.jpg）收集「某格先讀到 Sona、該局最終禁用卻不是 Sona」的小圖，平均成 PENDING 模板。
# 驗證：Day 1 的 BP 畫面（沒參與建模板），看 BP 進行中把 Sona 報出來的次數有沒有降到 0，以及最終禁用是否仍為 80/80。
# 用法：python tools/ban_pending.py build <RUN>   |   python tools/ban_pending.py eval
import sys, glob, json, csv, datetime as dt
import numpy as np, cv2
sys.path.insert(0, "tools"); import bans26 as B
sys.stdout.reconfigure(encoding="utf-8")
OUT = "assets/ban_pending.npy"

def crops(im):
    return [im[B.Y0 + B.M:B.Y1 - B.M, a + B.M:b - B.M] for side in "LR" for a, b in B.SLOTS[side]]

if sys.argv[1] == "build":
    RUN = sys.argv[2]; D = "data/live_worlds2026"
    fs = sorted(glob.glob(f"{D}/snap/off_{RUN}_*.jpg"))
    # 依時間切成各局的 BP（相鄰畫格間隔 > 10 分鐘視為不同局）
    groups, cur, last = [], [], None
    for f in fs:
        n = int(f[-11:-4])
        if last is not None and n - last > 600: groups.append(cur); cur = []
        cur.append(f); last = n
    if cur: groups.append(cur)
    feats = []
    for g in groups:
        ims = [cv2.imread(f) for f in g]; vis = [im for im in ims if im is not None and B.visible(im)]
        if len(vis) < 10: continue
        fb = B.final_bans(vis)
        if not fb: continue
        final = fb[0] + fb[1][::-1]                             # 回到格子順序（右列由左而右）
        for im in vis:
            S = B.slot_scores(im)
            for j, c in enumerate(crops(im)):
                if B.NAMES[int(S[j].argmax())] == "Sona" and final[j] != "Sona" and S[j].max() >= 0.45: feats.append(B.feat(c))
    T = np.mean(feats, axis=0); T /= np.linalg.norm(T); np.save(OUT, T)
    print("待選中小圖", len(feats), "張，已存", OUT)

if sys.argv[1] == "eval":
    P = np.load(OUT)
    sona_before = sona_after = filled = 0
    for k in range(1, 9):
        fs = sorted(glob.glob(f"data/bans26/d1g{k}/f_*.jpg")); vis = [im for im in (cv2.imread(f) for f in fs) if B.visible(im)]
        fb = B.final_bans(vis); final = fb[0] + fb[1][::-1]
        for im in vis:
            S = B.slot_scores(im)
            for j, c in enumerate(crops(im)):
                top = B.NAMES[int(S[j].argmax())]; sc = float(S[j].max()); pend = float(P @ B.feat(c))
                if sc < 0.45: continue
                if top == "Sona" and final[j] != "Sona": sona_before += 1
                if pend < sc:
                    filled += 1
                    if top == "Sona" and final[j] != "Sona": sona_after += 1
    print(f"Day 1（未參與建模板）：BP 中被讀成 Sona 的待選格 改前 {sona_before} 次 → 改後 {sona_after} 次；改後仍回報的格子 {filled} 次")
