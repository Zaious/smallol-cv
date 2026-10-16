# 從 1080p 的逐秒 IoU 推出「哪座塔、何時消失」：先穩定存在；之後連續低分；小地圖不可見的秒不計；鎖定後不復原。
import csv, json, re, sys
sys.stdout.reconfigure(encoding="utf-8")
CSV, FEED = sys.argv[1], sys.argv[2]
G0 = int(sys.argv[3])          # 遊戲 0:00 對應的影片秒
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
sites = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
PRESENT, ABSENT, NEED_P, NEED_A, HIDDEN_N = 0.30, 0.08, 5, 8, 15
def hidden(r):  # 太多站點同時為 0：小地圖不在畫面上
    return sum(1 for s in sites if float(r[s]) == 0.0) >= HIDDEN_N
destroyed = {}
for sid in sites:
    seen = 0; est = True; run = 0   # 產品從開局起跑，所有塔預設存在
    for r in rows:
        if hidden(r): continue
        v = float(r[sid])
        if not est:
            seen = seen + 1 if v >= PRESENT else 0
            if seen >= NEED_P: est = True
            continue
        run = run + 1 if v <= ABSENT else 0
        if run >= NEED_A and sid not in destroyed:
            destroyed[sid] = int(r["t"]) - NEED_A + 1
def fmt(t): g = t - G0; return f"{g//60}:{g%60:02d}"
print("偵測到的塔消失（按時間）：")
for sid, t in sorted(destroyed.items(), key=lambda x: x[1]): print(f"  game {fmt(t):>6}  {sid}")
feed = {}
for line in open(FEED, encoding="utf-8", errors="replace"):
    m = re.match(r"(\d+)min .* blueTowers=(\d+) .* redTowers=(\d+)", line)
    if m: feed[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
print("\nfeed 每分鐘 (紅塔消失數, 藍塔消失數) vs 偵測")
ok_n = 0; n = 0
for k in sorted(feed):
    clip = G0 + 41 + 60 * k
    if clip < int(rows[0]["t"]) or clip > int(rows[-1]["t"]): continue
    rl = sum(1 for s, t in destroyed.items() if s.startswith("R_") and t <= clip)
    bl = sum(1 for s, t in destroyed.items() if s.startswith("B_") and t <= clip)
    ok = (rl, bl) == feed[k]; n += 1; ok_n += ok
    print(f"  {k:2d}min feed={feed[k]} det=({rl}, {bl}) {'OK' if ok else 'DIFF'}")
print(f"一致 {ok_n}/{n} 分鐘")
