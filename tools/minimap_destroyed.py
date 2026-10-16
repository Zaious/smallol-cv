# 從逐秒站點像素數推出「哪座塔、何時被摧毀」：先穩定存在，之後連續接近 0，鎖定後不復原。
import csv, json, re, sys
sys.stdout.reconfigure(encoding="utf-8")
rows = list(csv.DictReader(open("data/minimap_track_g1.csv")))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
towers = [s for s in cfg["sites"] if s["kind"] == "tower"]
PRESENT, ABSENT, NEED_P, NEED_A = 8, 2, 5, 5
OFFSET = 541
destroyed = {}
for s in towers:
    seen = 0; run_a = 0; established = False
    for r in rows:
        c = int(r[s["id"]])
        if not established:
            seen = seen + 1 if c >= PRESENT else 0
            if seen >= NEED_P: established = True
            continue
        run_a = run_a + 1 if c <= ABSENT else 0
        if run_a >= NEED_A and s["id"] not in destroyed:
            destroyed[s["id"]] = int(r["t"]) - NEED_A + 1
print("檢測到消失的塔（鎖定後不復原）：")
for sid, t in sorted(destroyed.items(), key=lambda x: x[1]):
    g = t - OFFSET; print(f"  {sid:20s} clip {t}s  game {g//60}:{g%60:02d}")
feed = {}
for line in open("data/feed_objectives_g1.txt", encoding="utf-8", errors="replace"):
    m = re.match(r"(\d+)min .* blueTowers=(\d+) .* redTowers=(\d+)", line)
    if m: feed[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
print("\n逐分鐘對照 feed(紅塔消失=藍方摧毀數, 藍塔消失=紅方摧毀數) vs 偵測")
bad = []
for k in sorted(feed):
    clip = 582 + 60 * k
    rl = sum(1 for sid, t in destroyed.items() if sid.startswith("R_") and t <= clip)
    bl = sum(1 for sid, t in destroyed.items() if sid.startswith("B_") and t <= clip)
    ok = (rl, bl) == feed[k]
    if not ok: bad.append(k)
    print(f"{k:3d}min  feed={feed[k]}  detected=({rl}, {bl})  {'OK' if ok else 'DIFF'}")
print("不一致的分鐘:", bad, f"({len(bad)}/{len(feed)})")
