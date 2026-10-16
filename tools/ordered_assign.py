# 依序配對：每隊「已消失」的站點按最後存在時間排序，對到 feed 該隊事件（按時間排序）。
# 檢查：(a) 最後存在是否不晚於事件、(b) 同一路外→內→水晶塔順序、(c) 水晶（inhib）事件是否出現在其水晶塔之後。
import csv, json, re, sys, statistics as st, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
WIN, MED = 20, 0.30
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
valid = [r for r in rows if not hidden(r)]
tmax = int(rows[-1]["t"])
last = {}
for sid in TOW:
    l = None
    for i in range(len(valid) - WIN):
        if st.median([float(r[sid]) for r in valid[i:i + WIN]]) >= MED: l = int(valid[i + WIN - 1]["t"])
    last[sid] = l
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
ev = {"R": [], "B": []}; inh = []
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (B_towers|R_towers|B_inhib|R_inhib) (\d+)->(\d+)", line)
    if not m: continue
    g = (dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) - start).total_seconds()
    if m.group(2) == "B_towers": ev["R"].append(g)
    elif m.group(2) == "R_towers": ev["B"].append(g)
    else: inh.append((g, "R" if m.group(2) == "B_inhib" else "B"))
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"
LANE = {"outer": 0, "inner": 1, "inhib_tower": 2}
inhib_tower_time = {}
for team in "RB":
    gone = sorted([(last[s] - G0, s) for s in TOW if s.startswith(team + "_") and "nexus" not in s and last[s] is not None and last[s] < tmax - 30])
    evs = [e for e in sorted(ev[team]) if G0 + e < tmax - 5]
    n = min(len(gone), len(evs))
    print(f"\n=== {team} 隊：偵測已消失 {len(gone)} 座（不含基地塔），footage 內 feed 事件 {len(evs)} 件")
    late = 0; assign = []
    for i in range(n):
        ls, sid = gone[i]; e = evs[i]; d = ls - e
        flag = "" if d <= 6 else "  <- 最後存在晚於事件"
        late += d > 6
        assign.append((e, sid)); print(f"  事件 {gt(e):>6} ← {sid:20s} 最後存在 {gt(ls):>6} (差 {d:+.0f}s){flag}")
        if sid.endswith("inhib_tower"): inhib_tower_time[(team, sid)] = e
    seen = {}
    bad = 0
    for e, sid in sorted(assign):
        lane = sid.split("_")[1]; kind = sid.split("_", 2)[2]
        prev = seen.get(lane, -1)
        if LANE[kind] < prev: bad += 1
        seen[lane] = max(prev, LANE[kind])
    print(f"  (a) 最後存在晚於事件(>6s)：{late}/{n}   (b) 路線順序違規：{bad}")
# (c) 水晶事件
for team in "RB":
    tt = sorted(t for (tm, s), t in inhib_tower_time.items() if tm == team)
    ih = sorted(g for g, tm in inh if tm == team)
    print(f"\n(c) {team} 隊水晶塔倒塌時間 {[gt(t) for t in tt]}  vs  水晶事件 {[gt(g) for g in ih]}")
    ok = all(any(0 <= g - t <= 40 for g in ih) for t in tt) if tt else None
    print("    每座水晶塔後 40 秒內都有一次水晶事件：", ok)
