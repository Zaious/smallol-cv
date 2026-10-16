# 2026 直播快照（每 15 秒）→ 逐秒的三狀態 CSV（格式同 classify_track 輸出）＋ feed 事件檔，供 trigger_sim_clf3 使用。
# 狀態用站點中心 13x13 的隊伍色像素比例：紅 >= 0.30、藍 >= 0.15 為存活；< 0.06 為消失；其餘為遮擋。快照之間沿用前一張狀態。
# 時間軸：t = 直播牆鐘 − LAG − 該局 feed 第一個 in_game 時間戳 + G0（G0 = 1000）。
# 擷取分段：clf_live.csv 每次重啟 n 從 0 起算；第 2 段的快照檔名覆蓋了第 1 段的同名檔，第 3 段起檔名帶啟動時間前綴。
# 用法：python tools/snap26_to_clf.py <gameId> [<gameId> ...]
import csv, json, sys, datetime as dt
import numpy as np, cv2
LAG, G0, RA, BA, DEAD = 31.0, 1000, 0.30, 0.15, 0.06
D = "data/live_worlds2026"
cfg = json.load(open("data/minimap_sites_2026_worlds.json", encoding="utf-8")); K = 1.5 / 5
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"}
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
segs = []                                                     # 每段：{n: 牆鐘}
with open(f"{D}/clf_live.csv") as f:
    for i, row in enumerate(csv.reader(f)):
        if i == 0: continue
        n = int(row[0])
        if n == 0: segs.append({})
        segs[-1][n] = ts(row[1])
PREFIX = {2: "1015T2334_"}                                    # 第 3 段（索引 2）的檔名前綴
seg2_max = max(segs[1]) if len(segs) > 1 else -1
snaps = []                                                    # (牆鐘, 檔案)
for k, sg in enumerate(segs):
    for n, w in sg.items():
        if n % 15: continue
        if k == 0 and n <= seg2_max: continue                 # 被第 2 段覆蓋
        snaps.append((w, f"{D}/snap/mm_{PREFIX.get(k, '')}{n:07d}.png"))
snaps.sort()
med = cv2.imread("data/minimap_median_gray_postplate.png", 0).astype(np.float32); med -= med.mean()
def layout_ok(g):
    g = g.astype(np.float32) - g.mean(); return float((g * med).sum() / np.sqrt((g * g).sum() * (med * med).sum() + 1e-9)) > 0.3
def frac(im, s):
    x, y = pos[s]; c = cv2.cvtColor(im[y - 6:y + 7, x - 6:x + 7], cv2.COLOR_BGR2HSV).astype(int); H, S, V = c[..., 0], c[..., 1], c[..., 2]
    m = (((H < 12) | (H > 165)) if s[0] == "R" else ((H >= 88) & (H <= 118))) & (S > 120) & (V > 25); return float(m.mean())
for gid in sys.argv[1:]:
    r = [json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl")]; ig = [x for x in r if x["state"] == "in_game"]
    st0 = ts(ig[0]["ts"]); end = ts(r[-1]["ts"])
    with open(f"data/feed_events_w26_{gid}.txt", "w") as f:
        prev = None
        for x in r:
            cur = {"B_towers": x["B"]["t"], "R_towers": x["R"]["t"], "B_inhib": x["B"]["i"], "R_inhib": x["R"]["i"]}
            if prev:
                for k in cur:
                    if cur[k] > prev[k]: f.write(f'{x["ts"]} {k} {prev[k]}->{cur[k]}\n')
            prev = cur
    states = {}
    for w, fp in snaps:
        if not (st0 - 60 <= w - LAG <= end + 60): continue
        im = cv2.imread(fp)
        if im is None: continue
        t = int(round(w - LAG - st0)) + G0
        if not layout_ok(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)): states[t] = None; continue
        rec = {}
        for s in pos:
            v = frac(im, s); a = v >= (RA if s[0] == "R" else BA); d = v < DEAD
            rec[s] = (1.0 if a else 0.0, 1.0 if d else 0.0, 0.0 if (a or d) else 1.0)
        states[t] = rec
    cols = ["t"] + [f"{s}_{c}" for s in pos for c in "ADO"]
    tl = sorted(states); out = []
    for i, t in enumerate(tl):
        t_next = tl[i + 1] if i + 1 < len(tl) else t + 15
        for u in range(t, min(t_next, t + 16)):              # 超過 16 秒的空檔（擷取中斷）不補
            row = {"t": u}
            for s in pos:
                a, d, o = states[t][s] if states[t] else (0.0, 0.0, 1.0)
                row[f"{s}_A"], row[f"{s}_D"], row[f"{s}_O"] = a, d, o
            out.append(row)
    with open(f"data/clf_w26_{gid}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
    print(gid, "start", ig[0]["ts"], "snaps", len(states), "visible", sum(1 for v in states.values() if v), "rows", len(out))
