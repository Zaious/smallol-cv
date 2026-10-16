# 2026 自動標註：每局每站點以「存活模板 NCC」的時間序列找永久消失點（塔不重生），終局消失數對官方 feed 塔數驗收。
# 輸出 data/labels/auto26.json：每局每站點的消失點（快照編號 n，未消失為 null）。
import json, glob, sys, datetime as dt
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
cfg = json.load(open("data/minimap_sites_2026_worlds.json", encoding="utf-8")); K, R = 1.5 / 5, 22
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"}
med = cv2.imread("data/minimap_median_2026_early.png")
def g(c): x = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32)[9:36, 9:36]; x -= x.mean(); return x / (np.sqrt((x * x).sum()) + 1e-9)
tpl = {s: g(med[y - R:y + R + 1, x - R:x + R + 1]) for s, (x, y) in pos.items()}
a = np.load("data/live_worlds2026/mm_ncc.npy"); good = {int(n): v for n, v in a}
import csv
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
LAG = 31.0                                                   # 直播畫面比 feed 時間戳晚（以 HUD 時鐘量得 30–33 秒）
nwall = {}
with open("data/live_worlds2026/clf_live.csv") as f:
    for i, row in enumerate(csv.reader(f)):
        if i == 0: continue
        if i > 21601: break                                      # 只用第一段（17:01–23:01），快照檔名屬於這段
        nwall[int(row[0])] = ts(row[1])
ALIVE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25
MINAFTER = int(sys.argv[2]) if len(sys.argv) > 2 else 2
ALIVE_B = float(sys.argv[3]) if len(sys.argv) > 3 else 0.15   # 藍方圖示的藍色像素比例本來就低（存活約 0.2–0.5）
out = {}
for p in sorted(glob.glob("data/live_worlds2026/feed_*.jsonl")):
    r = [json.loads(l) for l in open(p)]; ig = [x for x in r if x["state"] == "in_game"]
    if not ig or ig[-1]["wall"] > "2026-10-15T23:00": continue
    gid = p.split("_")[-1][:-6]; t0, t1 = ts(ig[0]["ts"]) + LAG, ts(r[-1]["ts"]) + LAG + 45
    ns = [n for n in sorted(good) if n in nwall and t0 <= nwall[n] <= t1 and good[n] > 0.3 and n % 15 == 0]
    V = {s: [] for s in pos}
    for n in ns:
        im = cv2.imread(f"data/live_worlds2026/snap/mm_{n:07d}.png")
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
        for s, (x, y) in pos.items():
            c = hsv[y - 6:y + 7, x - 6:x + 7]; H, S_, Vv = c[..., 0], c[..., 1], c[..., 2]
            m = (((H < 12) | (H > 165)) if s[0] == "R" else ((H >= 88) & (H <= 118))) & (S_ > 120) & (Vv > 25)
            V[s].append(float(m.mean()))
    fin = r[-1]; feedD = {"B": fin["R"]["t"], "R": fin["B"]["t"]}   # 紅隊打掉的塔數 = 藍方失去的塔
    res = {}
    for s in pos:
        v = np.array(V[s]); alive = v >= (ALIVE if s[0] == "R" else ALIVE_B); c = None
        for i in range(len(v)):
            if not alive[i:].any() and len(v) - i >= MINAFTER: c = ns[i]; break
        res[s] = c
    lost = {t: sum(1 for s in pos if s[0] == t and res[s] is not None) for t in "BR"}
    print(gid, f"快照 {len(ns)}", "  ".join(f"{t}方 CV 消失 {lost[t]} / feed {feedD[t]} {'OK' if lost[t] == feedD[t] else 'DIFF'}" for t in "BR"))
    out[gid] = {"ns": ns, "cp": res, "V": V}
json.dump(out, open("data/labels/auto26.json", "w"))
