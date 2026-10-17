# ⚠ 實驗失敗、未採用（2026-10-17）：以「畫面秒數 n + 偏移」推出的標籤有 ±1 秒抖動（HLS 分段送達），秒數個位標籤約一半是錯的，
#   重建後測試局正確率 61.6% → 50.8%。改採 hud_clock.read_clock_safe（只用不含 0、9 的讀值估偏移）。保留本檔以免重踩。
# 計分列時鐘模板重建（自動標註）：舊模板只有 0↔9 會互相讀錯，所以只用四位數都不含 0、9 的讀值，
# 以 5 分鐘滾動眾數估「遊戲時鐘 − 畫面秒數 n」的偏移，推出每張計分列的正確時鐘，當訓練標籤重建 0–9 模板。
# 用法：python tools/clock_selflabel.py <RUN> <訓練局 gameId,...> <測試局 gameId,...> [--save]
import sys, glob, json, os, datetime as dt
from collections import Counter
import numpy as np, cv2
sys.path.insert(0, "tools"); import hud_clock as HC
sys.stdout.reconfigure(encoding="utf-8")
RUN, TRAIN, TEST = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
D = "data/live_worlds2026"; X0 = 920 - 500
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
import csv
rows = list(csv.DictReader(open(f"{D}/clf_live_{RUN}.csv", encoding="utf-8")))
anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows]))
huds = {int(p[-11:-4]): p for p in glob.glob(f"{D}/snap/hud_{RUN}_*.png")}

def game_span(gid):
    r = [json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl", encoding="utf-8")]; ig = [x for x in r if x["state"] == "in_game"]
    return ts(ig[0]["ts"]), ts(r[-1]["ts"])

def labeled(gid, T):
    st0, end = game_span(gid)
    ns = sorted(n for n in huds if st0 <= n + anchor <= end + 120)
    reads = {}
    for n in ns:
        im = cv2.imread(huds[n]); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        r = [HC._match(g, a, b, X0, 0, T) for a, b in HC.CELLS]
        if min(s for _, s in r) < 0.8 or r[2][0] > 5: continue
        reads[n] = ([k for k, _ in r], g)
    out = []
    for n, (digs, g) in reads.items():
        win = [m for m in reads if abs(m - n) <= 150 and not ({0, 9} & set(reads[m][0]))]
        cs = Counter((reads[m][0][0] * 10 + reads[m][0][1]) * 60 + reads[m][0][2] * 10 + reads[m][0][3] - m for m in win)
        if not cs: continue
        c, k = cs.most_common(1)[0]
        if k < 5 or k < 0.6 * len(win): continue                 # 偏移不夠一致（可能是暫停、重播）就不標
        t = n + c
        if t < 0: continue
        out.append((g, [t // 600, (t // 60) % 10, (t % 60) // 10, t % 10], t, digs))
    return out

T0 = np.load(HC.TPL)["t"]
train = [x for gid in TRAIN for x in labeled(gid, T0)]
acc = {d: [] for d in range(10)}
for g, digs, _, _ in train:
    for (a, b), d in zip(HC.CELLS, digs):
        best = max(((float((T0[d] * HC._norm(g[HC.Y0 + dy:HC.Y1 + dy, X0 + a + dx:X0 + b + dx])).sum()), dx, dy) for dy in (-1, 0, 1) for dx in (-2, -1, 0, 1, 2)))
        acc[d].append(HC._norm(g[HC.Y0 + best[2]:HC.Y1 + best[2], X0 + a + best[1]:X0 + b + best[1]]))
T1 = np.stack([HC._norm(np.median(acc[d], axis=0)) if acc[d] else T0[d] for d in range(10)])
print("訓練樣本（張）", len(train), "各數字", {d: len(v) for d, v in acc.items()})
print("新模板 0 與 9 的相似度", round(float((T1[0] * T1[9]).sum()), 3), "（舊模板", round(float((T0[0] * T0[9]).sum()), 3), "）")

def evaluate(T, items):
    ok = bad = none = 0
    for g, _, t, _ in items:
        r = [HC._match(g, a, b, X0, 0, T) for a, b in HC.CELLS]; d = [k for k, _ in r]
        if min(s for _, s in r) < 0.8 or d[2] > 5: none += 1; continue
        v = (d[0] * 10 + d[1]) * 60 + d[2] * 10 + d[3]
        ok += v == t; bad += v != t
    return ok, bad, none

test = [x for gid in TEST for x in labeled(gid, T0)]
for name, T in (("舊模板", T0), ("新模板", T1)):
    ok, bad, none = evaluate(T, test)
    print(f"測試局 {name}：正確 {ok}  錯誤 {bad}  低信心 {none}  （正確率 {ok / max(1, ok + bad) * 100:.1f}%）")
if "--save" in sys.argv:
    np.savez(HC.TPL, t=T1); print("已存", HC.TPL)
