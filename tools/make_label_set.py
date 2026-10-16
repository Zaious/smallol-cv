# 產生標註用小圖：從指定的場次隨機抽（站點, 時間），存 45x45 彩色小圖與中繼資料，並輸出編號對照圖。
# 用法：python tools/make_label_set.py <out_prefix> <N> <seed> <game1:video:G0:t0:ncc_csv> ...
import csv, json, random, subprocess, sys
import numpy as np, cv2

prefix, N, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); specs = sys.argv[4:]
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
X0, Y0, K, R = int(1085 * 1.5), int(525 * 1.5), 1.5 / 5, 22
pos = {s["id"]: (int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"}
TOW = list(pos); rnd = random.Random(seed)
games = []
for sp in specs:
    name, video, g0, t0, ncc = sp.split(":"); g0, t0 = int(g0), int(t0)
    rows = list(csv.DictReader(open(ncc)))
    ok = [int(r["t"]) for r in rows if sum(1 for s in TOW if float(r[s]) < 0.45) < 0.7 * len(TOW) and int(r["t"]) >= g0 + 14 * 60 + 30 and int(r["t"]) <= int(rows[-1]["t"]) - 30]
    games.append((name, video, g0, t0, ok))
samples = []
per_game = N // len(games)
for name, video, g0, t0, ok in games:
    for _ in range(per_game): samples.append((name, rnd.choice(ok), rnd.choice(TOW)))
rnd.shuffle(samples)
crops, meta = [], []
cache = {}
for i, (name, t, site) in enumerate(samples):
    video, g0, t0 = next((v, g, t0_) for n, v, g, t0_, _ in games if n == name)
    key = (name, t)
    if key not in cache:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, t - t0)), "-i", video, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE).stdout
        cache = {key: np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3) if len(raw) == 1920 * 1080 * 3 else None}
    fr = cache[key]
    if fr is None: continue
    cx, cy = pos[site]; c = fr[Y0 + cy - R:Y0 + cy + R + 1, X0 + cx - R:X0 + cx + R + 1].copy()
    if c.shape[:2] != (2 * R + 1, 2 * R + 1): continue
    crops.append(c); meta.append({"game": name, "t": int(t), "site": site})
    if (i + 1) % 50 == 0: print("progress", i + 1, flush=True)
np.savez_compressed(f"{prefix}.npz", crops=np.stack(crops)); json.dump(meta, open(f"{prefix}_meta.json", "w"))
# 編號對照圖：每張 8 欄 x 5 列 = 40 個
COLS, ROWS, SC = 8, 5, 3
per = COLS * ROWS; side = (2 * R + 1) * SC
for k in range(0, len(crops), per):
    sheet = np.zeros((ROWS * (side + 14), COLS * (side + 4), 3), np.uint8)
    for j in range(per):
        idx = k + j
        if idx >= len(crops): break
        r, c = divmod(j, COLS); t = cv2.resize(crops[idx], (side, side), interpolation=cv2.INTER_CUBIC)
        y, x = r * (side + 14), c * (side + 4); sheet[y + 14:y + 14 + side, x:x + side] = t
        cv2.putText(sheet, str(idx), (x + 2, y + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
    cv2.imwrite(f"{prefix}_sheet_{k // per:02d}.png", sheet)
print("samples", len(crops), "sheets", (len(crops) + per - 1) // per)
