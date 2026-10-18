# 存下轉播 BP 卡片（已知正解）中，與自己的 Data Dragon 原畫對不好的那些（內點 < KEEP_BELOW），供 draft_picks 直接比對。
# 正解：官方 feed 的最終選角（位置順序）；用 BP 最後一張畫面（卡片已依位置排好）。卡片圖存 hero-art/cards/（Riot 美術，不進 repo）。
# 用法：python tools/draft_cards_build.py   （來源：Day 1 錄影 data/bans26/d1g*/、Day 2/3 直播 data/live_worlds2026/snap/off_*）
import sys, os, glob, json, csv, datetime as dt
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import draft_picks as DP, live_service as L
KEEP_BELOW = 8                                             # 只收自己原畫完全對不上的（Ornn、Rakan）；收太多會讓空格對到卡上的介面線條（2026-10-18 Day 1 測試錯誤鎖定 16）
ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "hero-art", "cards")

def last_overlay(paths, R):
    for p in reversed(paths):
        im = cv2.imread(p)
        if im is not None and R.overlay(im) >= 0.6: return im
    return None

def sources():
    for l in open(os.path.join(ROOT, "data", "bans26", "draft_windows.txt"), encoding="utf-8").read().replace("\r", "").splitlines():
        if l.strip(): name, gid, *_ = l.split(); yield gid, sorted(glob.glob(os.path.join(ROOT, "data", "bans26", name, "f_*.jpg")))
    D = os.path.join(ROOT, "data", "live_worlds2026"); ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    offs = []
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        run = os.path.basename(p)[9:-4]; rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        anc = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows]))
        offs += [(int(f[-11:-4]) + anc, f) for f in glob.glob(f"{D}/snap/off_{run}_*.jpg")]
    offs.sort()
    for f in sorted(glob.glob(f"{D}/feed_*.jsonl")):
        gid = os.path.basename(f)[5:-6]; st = L.feed_start(gid)
        if st: yield gid, [p for w, p in offs if st + 46 - 1500 <= w <= st + 46]

if __name__ == "__main__":
    R = DP.Reader(); os.makedirs(OUT, exist_ok=True); n = 0
    for f in glob.glob(os.path.join(OUT, "*.png")): os.remove(f)
    aliased = {c for pts in R.alias.values() for _, _, c in pts}   # 別名表已處理的（Rakan）不收：Rakan 的卡和 Xayah 的卡出自同一張原畫，收了會把 Xayah 對成 Rakan
    for gid, paths in sources():
        if not paths: continue
        im = last_overlay(paths, R); pk = L.game_picks(gid)
        if im is None or not pk: continue
        for s in "BR":
            for i, champ in enumerate(pk[s]["picks"]):
                x0, x1 = DP.card_box(s, i); crop = im[DP.Y0:DP.Y1, x0:x1]
                own = R.ident_one(crop, champ)
                if own < KEEP_BELOW and champ not in aliased:
                    cv2.imwrite(os.path.join(OUT, f"{champ}__{gid}_{s}{i}.png"), crop); n += 1
                    print(gid[-3:], s, i, champ, "自己原畫內點", own, flush=True)
    print("存下", n, "張")
