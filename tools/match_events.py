# 以 feed 的確切事件時間，在小地圖 IoU 序列裡找「事件前後才消失、且之後不再回來」的站點（塔不會重生）。
import csv, json, re, sys, datetime as dt, statistics as st
sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
OFFSET = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
ts = {int(r["t"]): r for r in rows}
tmin, tmax = min(ts), max(ts)
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
def vals(sid, a, b):
    return [float(ts[t][sid]) for t in range(max(a, tmin), min(b, tmax) + 1) if t in ts and not hidden(ts[t])]
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
ev = []
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (B_towers|R_towers) (\d+)->(\d+)", line)
    if m:
        T = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        g = (T - start).total_seconds()
        # B_towers 增加 = 藍方摧毀 = 紅塔消失
        ev.append((g, "R" if m.group(2) == "B_towers" else "B", int(m.group(4))))
gone = {"R": set(), "B": set()}
print("事件(遊戲時間)  消失塔屬隊  候選（前窗IoU→後窗IoU，後60秒是否維持低）")
for g, team, n in ev:
    v = int(round(G0 + g + OFFSET))
    if v < tmin + 10 or v > tmax:
        print(f"{int(g)//60}:{int(g)%60:02d}  {team}#{n}  （影片範圍外，略過）"); continue
    cands = []
    for sid in TOW:
        if not sid.startswith(team + "_") or sid in gone[team]: continue
        pre = vals(sid, v - 25, v - 5); post = vals(sid, v + 8, v + 40); late = vals(sid, v + 8, v + 90)
        if len(pre) < 8 or len(post) < 8: continue
        a, b = st.median(pre), st.median(post)
        stays = st.median(late) if late else b
        cands.append((a - b, sid, a, b, stays))
    cands.sort(reverse=True)
    print(f"{int(g)//60}:{int(g)%60:02d}  {team}#{n}")
    for d, sid, a, b, stay in cands[:3]:
        print(f"     {sid:20s} {a:.2f} → {b:.2f}  (降 {d:.2f}, 後90秒中位 {stay:.2f})")
    if cands and cands[0][0] >= 0.2: gone[team].add(cands[0][1])
