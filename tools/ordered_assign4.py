# v4：消失 = 20 秒中位數 <= min(ABS, 0.5*基準) 並持續到比賽結束；比賽結束點由 feed 最後事件 +5 秒決定。
# 輸出：偵測數量 vs feed 數量、依序配對、三項一致性檢查。
import csv, json, re, sys, statistics as st, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
WIN, ABS, BASE_SECS = 20, 0.15, 90
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
LANE = [s for s in TOW if "nexus" not in s]
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
ev = {"R": [], "B": []}; inh = []; last_ev = 0
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (\w+) (\d+)->(\d+)", line)
    if not m: continue
    g = (dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) - start).total_seconds()
    last_ev = max(last_ev, g)
    if m.group(2) == "B_towers": ev["R"].append(g)
    elif m.group(2) == "R_towers": ev["B"].append(g)
    elif m.group(2) in ("B_inhib", "R_inhib"): inh.append((g, "R" if m.group(2) == "B_inhib" else "B"))
tmax_file = int(rows[-1]["t"])
END = min(G0 + last_ev + 5, tmax_file)
rows = [r for r in rows if int(r["t"]) <= END]
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
valid = [r for r in rows if not hidden(r)]
base = {s: st.median([float(r[s]) for r in valid[:BASE_SECS]]) for s in TOW}
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"
last = {}
for s in LANE:
    thr = min(ABS, 0.5 * base[s]); l = None
    for i in range(len(valid) - WIN):
        if st.median([float(r[s]) for r in valid[i:i + WIN]]) > thr: l = int(valid[i + WIN - 1]["t"])
    last[s] = l
LANEIDX = {"outer": 0, "inner": 1, "inhib_tower": 2}
print(f"比賽結束點（feed 最後事件+5s）= 遊戲 {gt(END - G0)}；有效秒 {len(valid)}/{len(rows)}")
tot_late = 0; tot_n = 0; tot_bad = 0; tower_t = {}
for team in "RB":
    exp = len([e for e in ev[team] if G0 + e <= END])
    gone = sorted([(last[s] - G0, s) for s in LANE if s.startswith(team + "_") and (last[s] is None or last[s] < END - 40)],
                  key=lambda x: (x[0] if last[x[1]] is not None else -1))
    gone = [(l if last[s] is not None else -1, s) for l, s in gone]
    evs = sorted(e for e in ev[team] if G0 + e <= END)
    print(f"\n=== {team} 隊：feed 事件 {len(evs)}（含基地塔），偵測消失（線上塔）{len(gone)}")
    n = min(len(gone), len(evs)); late = 0; bad = 0; seen = {}
    for i in range(n):
        ls, sid = gone[i]; e = evs[i]; d = ls - e
        late += d > 6; tower_t[(team, sid)] = e
        lane, kind = sid.split("_")[1], sid.split("_", 2)[2]
        bad += LANEIDX[kind] < seen.get(lane, -1); seen[lane] = max(seen.get(lane, -1), LANEIDX[kind])
        print(f"   事件 {gt(e):>6} ← {sid:20s} 最後存在 {gt(ls):>6} (差 {d:+.0f}s){'  <- 晚於事件' if d > 6 else ''}")
    extra = gone[len(evs):]
    if extra: print("   偵測多於 feed：", [(s, gt(l)) for l, s in extra])
    tot_late += late; tot_n += n; tot_bad += bad
    print(f"   (a) 最後存在晚於事件 {late}/{n}   (b) 路線違規 {bad}")
for team in "RB":
    tt = sorted(t for (tm, s), t in tower_t.items() if tm == team and s.endswith("inhib_tower"))
    ih = sorted(g for g, tm in inh if tm == team)
    ok = all(any(0 <= g - t <= 40 for g in ih) for t in tt) if tt else None
    print(f"(c) {team} 水晶塔配到的事件時間 {[gt(t) for t in tt]} vs 水晶事件 {[gt(g) for g in ih]} -> {ok}")
print(f"\n合計：(a) {tot_late}/{tot_n}   (b) {tot_bad}")
