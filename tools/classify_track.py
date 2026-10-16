# 逐秒逐站點的三狀態分類追蹤：每秒對 22 個塔站點各切 45x45 彩色小圖，輸出 P(存活)、P(消失)、P(遮擋)。
# 從標準輸入讀 1 fps 的 BGR 原始畫格（1920x1080）。用法：... | python tools/classify_track.py - <out.csv> <t0>
import csv, json, pickle, sys
import numpy as np
sys.path.insert(0, "tools")
from state_feats import feats

OUT, T0 = sys.argv[2], int(sys.argv[3])
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0, K, R = int(1085 * 1.5), int(525 * 1.5), 1.5 / 5, 22
sites = [(s["id"], int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"]
bundle = pickle.load(open("data/state_clf.pkl", "rb")); model, classes = bundle["model"], bundle["classes"]
ia, id_, io = classes.index("A"), classes.index("D"), classes.index("O")
fb = 1920 * 1080 * 3; stream = sys.stdin.buffer; rows = []; t = T0
cols = ["t"] + [f"{s}_{c}" for s, _, _ in sites for c in "ADO"]
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    fr = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)
    crops = []; ok = []
    for sid, cx, cy in sites:
        c = fr[Y0 + cy - R:Y0 + cy + R + 1, X0 + cx - R:X0 + cx + R + 1]
        ok.append(c.shape[:2] == (2 * R + 1, 2 * R + 1)); crops.append(feats(c) if ok[-1] else np.zeros(503, np.float32))
    P = model.predict_proba(np.stack(crops))
    rec = {"t": t}
    for k, (sid, _, _) in enumerate(sites):
        pa, pd_, po = (P[k, ia], P[k, id_], P[k, io]) if ok[k] else (0.0, 0.0, 1.0)
        rec[f"{sid}_A"], rec[f"{sid}_D"], rec[f"{sid}_O"] = round(float(pa), 3), round(float(pd_), 3), round(float(po), 3)
    rows.append(rec); t += 1
    if len(rows) % 200 == 0: print("progress", len(rows), flush=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print("done", len(rows), flush=True)
