# 即時三狀態判讀（2026 世界賽版面）：從標準輸入讀 1 fps 的 BGR 原始畫格（1920x1080），每秒立刻寫一列（含牆鐘時間），不等串流結束。
# 狀態用站點中心 13x13 的隊伍色像素比例：紅 >= 0.30、藍 >= 0.15 為存活（A）；< 0.06 為消失（D）；其餘為遮擋（O）。
# 小地圖不是標準版面（與 2025 中位數灰階圖 NCC <= 0.3）時，該秒全部記為遮擋，layout=0。
# 另外定期存小地圖裁切與全解析度畫面（供事後核對與標註），不存影片。每次啟動寫獨立檔案（檔名帶啟動時間）。
# 用法：<畫格來源> | python tools/live_classify.py <out_dir> [--snap-every 15] [--full-every 60] [--hud-every 5]
import csv, json, os, sys, time, datetime as dt
import numpy as np, cv2

OUT = sys.argv[1]; os.makedirs(os.path.join(OUT, "snap"), exist_ok=True)
arg = lambda k, d: int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
SNAP, FULL, HUD, OFFG = arg("--snap-every", 15), arg("--full-every", 60), arg("--hud-every", 5), arg("--offgame-every", 3)
RA, BA, DEAD = 0.30, 0.15, 0.06
root = os.path.join(os.path.dirname(__file__), "..")
cfg = json.load(open(os.path.join(root, "assets/minimap_sites_2026_worlds.json"), encoding="utf-8"))
X0, Y0, K, MM = int(1085 * 1.5), int(525 * 1.5), 1.5 / 5, 285
sites = [(s["id"], int(round(s["x"] * K)), int(round(s["y"] * K))) for s in cfg["sites"] if s["kind"] == "tower"]
med = cv2.imread(os.path.join(root, "assets/minimap_median_gray_postplate.png"), 0).astype(np.float32); med -= med.mean(); mednorm = np.sqrt((med * med).sum())
RUN = dt.datetime.now(dt.timezone.utc).strftime("%m%dT%H%M")
cols = ["n", "wall_utc", "layout"] + [f"{s}_{c}" for s, _, _ in sites for c in "ADO"] + [f"{s}_frac" for s, _, _ in sites]
f = open(os.path.join(OUT, f"clf_live_{RUN}.csv"), "w", newline="", encoding="utf-8"); w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
fb = 1920 * 1080 * 3; stream = sys.stdin.buffer; n = 0; t_start = time.time(); lat = []
while True:
    b = stream.read(fb)
    if len(b) < fb: break
    t0 = time.time(); fr = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3); mm = fr[Y0:Y0 + MM, X0:X0 + MM]
    g = cv2.cvtColor(mm, cv2.COLOR_BGR2GRAY).astype(np.float32); g -= g.mean()
    lay = float((g * med).sum() / (np.sqrt((g * g).sum()) * mednorm + 1e-9)) > 0.3
    hsv = cv2.cvtColor(mm, cv2.COLOR_BGR2HSV).astype(int)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rec = {"n": n, "wall_utc": now, "layout": int(lay)}
    for sid, x, y in sites:
        c = hsv[y - 6:y + 7, x - 6:x + 7]; H, S, V = c[..., 0], c[..., 1], c[..., 2]
        m = (((H < 12) | (H > 165)) if sid[0] == "R" else ((H >= 88) & (H <= 118))) & (S > 120) & (V > 25); v = float(m.mean())
        a = lay and v >= (RA if sid[0] == "R" else BA); d = lay and v < DEAD
        rec[f"{sid}_A"], rec[f"{sid}_D"], rec[f"{sid}_O"] = int(a), int(d), int(not (a or d)); rec[f"{sid}_frac"] = round(v, 3)
    w.writerow(rec); f.flush()
    if SNAP and n % SNAP == 0: cv2.imwrite(os.path.join(OUT, "snap", f"mm_{RUN}_{n:07d}.png"), mm)
    if FULL and n % FULL == 0: cv2.imwrite(os.path.join(OUT, "snap", f"full_{RUN}_{n:07d}.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if OFFG and not lay and n % OFFG == 0: cv2.imwrite(os.path.join(OUT, "snap", f"off_{RUN}_{n:07d}.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 85])   # 非比賽畫面（BP、局間）：禁用辨識素材
    if HUD and n % HUD == 0: cv2.imwrite(os.path.join(OUT, "snap", f"obj_{RUN}_{n:07d}.png"), fr[0:70, 0:300])   # 左上角物件計時框（下一條龍、上方野怪坑）
    if lay: cv2.imwrite(os.path.join(OUT, "snap", f"ann_{RUN}_{n:07d}.png"), fr[190:255, 740:1180])   # 畫面上方擊殺公告區（每秒；預示者歸屬素材）
    if HUD and n % HUD == 0: cv2.imwrite(os.path.join(OUT, "snap", f"hud_{RUN}_{n:07d}.png"), fr[0:110, 500:1420])   # 上方計分列（物件計數、龍、時鐘）
    lat.append(time.time() - t0); n += 1
    if n % 60 == 0:
        print(f"n={n} wall={now} 單格處理 中位數 {np.median(lat[-60:])*1000:.0f} ms 最大 {max(lat[-60:])*1000:.0f} ms", flush=True)
print(f"結束：共 {n} 格，經過 {time.time()-t_start:.0f} 秒", flush=True)
