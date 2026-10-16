# 消失模板：每個站點在「確定已消失」時的外觀（地形），取多局、多時間點的逐像素中位數。
# 「確定已消失」只用影片本身判定（不使用 feed 時間）：該站點在比賽最後 90 秒的 NCC 中位數 < 0.70，
# 且最後 90 秒內 NCC >= 0.85 的秒數 <= 2，且曾經存活（NCC >= 0.85 的秒數 >= 60）。取「最後存活 + 60 秒」之後到結束前 15 秒的 12 張畫格。
import csv, json, subprocess, sys
import numpy as np, cv2

games = sys.argv[1:]            # 例：g1:vod/probe1080/seg_10000_11304.mp4:10000 ...
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
X0, Y0, S, K = int(1085 * 1.5), int(525 * 1.5), 285, 1.5 / 5
RT, MARG = 7, 6
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"]}
patches = {s: [] for s in TOW}
for spec in games:
    name, video, t0 = spec.split(":"); t0 = int(t0)
    rows = list(csv.DictReader(open(f"data/minimap_ncc_{name}.csv")))
    T = np.array([int(r["t"]) for r in rows], float)
    hid = np.array([sum(1 for s in TOW if float(r[s]) < 0.45) >= 0.7 * len(TOW) for r in rows])
    ok = ~hid; end = T[-1]
    want = []                                                   # (site, 取樣影片時間)
    for s in TOW:
        x = np.array([float(r[s]) for r in rows])
        tail = (T >= end - 105) & (T <= end - 15) & ok
        if tail.sum() < 30: continue
        dead = np.median(x[tail]) < 0.70 and (x[tail] >= 0.85).sum() <= 2
        alive_idx = np.where((x >= 0.85) & ok)[0]
        if not dead or len(alive_idx) < 60: continue
        last_alive = T[alive_idx[-1]]
        a, b = last_alive + 60, end - 15
        if b - a < 30: continue
        for tt in np.linspace(a, b, 12): want.append((s, float(tt)))
    # 去重取樣時間，逐張解碼
    times = sorted(set(round(t) for _, t in want))
    cache = {}
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, t - t0)), "-i", video, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             stdout=subprocess.PIPE).stdout
        if len(raw) == 1920 * 1080: cache[t] = np.frombuffer(raw, np.uint8).reshape(1080, 1920)[Y0:Y0 + S, X0:X0 + S]
    for s, tt in want:
        fr = cache.get(round(tt))
        if fr is None: continue
        cx, cy = pos[s]; patches[s].append(fr[cy - RT - MARG:cy + RT + MARG + 1, cx - RT - MARG:cx + RT + MARG + 1].copy())
    print(name, "dead sites:", sorted(set(s for s, _ in want)), flush=True)
out = {}
for s in TOW:
    if len(patches[s]) >= 12:
        out[s] = np.median(np.stack(patches[s]), axis=0).astype(np.uint8)
        print(f"{s:20s} frames={len(patches[s])}")
    else: print(f"{s:20s} 樣本不足（{len(patches[s])}），無消失模板")
np.savez("data/minimap_dead_templates.npz", **out)
