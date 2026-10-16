# 觸發式因果模擬：畫面端持續記錄每個站點每秒的三種狀態；feed 計數增加時進入待決，影片出現持續的「消失」證據就配對命名。
# 狀態由 D = 空地 NCC − 存活 NCC 決定：D <= -ALIVE_T 存活、D >= DEAD_T 消失、其餘未知；小地圖不可見的秒跳過。
# 用法（分類器版）：python tools/trigger_sim_clf.py <clf.csv> <feed_events.txt> <G0> <START_ISO> <lead_seconds> [--json out.json]
import csv, json, re, sys
import datetime as dt
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO, LEAD = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
OUTJSON = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
ALIVE_T, DEAD_T = 0.12, 0.12
N, NEED_DEAD, MAX_ALIVE, REVOKE_ALIVE = 10, 7, 1, 6
TIERS = ["outer", "inner", "inhib_tower"]

rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
tower_ev = {"R": [], "B": []}; inhib_ev = {"R": [], "B": []}; last_ev = 0.0
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (\w+) (\d+)->(\d+)", line)
    if not m: continue
    g = (dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) - start).total_seconds(); last_ev = max(last_ev, g)
    if m.group(2) == "B_towers": tower_ev["R"].append(g)
    elif m.group(2) == "R_towers": tower_ev["B"].append(g)
    elif m.group(2) == "B_inhib": inhib_ev["R"].append(g)
    elif m.group(2) == "R_inhib": inhib_ev["B"].append(g)
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
rows = [r for r in rows if int(r["t"]) <= END]
t_all = np.array([int(r["t"]) for r in rows])
PD = {s: np.array([float(r[s + "_D"]) for r in rows]) for s in TOW}
PA = {s: np.array([float(r[s + "_A"]) for r in rows]) for s in TOW}
PO = {s: np.array([float(r[s + "_O"]) for r in rows]) for s in TOW}
# 小地圖不可見：七成以上的站點被判成遮擋（機率 O >= 0.5）
hidden = np.array([sum(1 for s in TOW if PO[s][i] >= 0.5) >= 0.7 * len(TOW) for i in range(len(rows))])
THR = float(sys.argv[sys.argv.index("--thr") + 1]) if "--thr" in sys.argv else 0.6
ST = {}
for s in TOW:
    st = np.zeros(len(rows), dtype=int); st[PD[s] >= THR] = 1; st[PA[s] >= THR] = -1
    ST[s] = st
Dd = {s: PD[s] for s in TOW}; A = {s: PA[s] for s in TOW}
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"
def known(evl, t): return sum(1 for e in evl if G0 + e - LEAD <= t)
def feasible(s, D, t):
    p = s.split("_"); team, lane = p[0], p[1]
    if lane == "nexus": return any(G0 + e - LEAD <= t for e in inhib_ev[team])
    k = TIERS.index("_".join(p[2:])); return all(f"{team}_{lane}_{TIERS[j]}" in D[team] for j in range(k))

D = {"R": {}, "B": {}}; events = []; hist = []
for i, t in enumerate(t_all):
    if hidden[i] or t < G0 + 14 * 60: continue
    hist.append(i)
    if len(hist) < N: continue
    win = hist[-N:]
    for team in "RB":
        for s in list(D[team]):                               # 撤銷：塔不會重生
            if int((ST[s][win] == -1).sum()) >= REVOKE_ALIVE:
                del D[team][s]; events.append((team, int(t), s, "撤銷", None))
        K = known(tower_ev[team], t)
        while len(D[team]) < K:
            cands = []
            for s in TOW:
                if not s.startswith(team + "_") or s in D[team] or not feasible(s, D, t): continue
                dead_n = int((ST[s][win] == 1).sum()); alive_n = int((ST[s][win] == -1).sum())
                if dead_n >= NEED_DEAD and alive_n <= MAX_ALIVE: cands.append((-dead_n, float(np.mean(Dd[s][win] - A[s][win])) * -1, s))
            if not cands: break
            cands.sort(); s = cands[0][2]
            onset = next((int(t_all[j]) for j in win if ST[s][j] == 1), int(t))
            D[team][s] = (int(t), onset); events.append((team, int(t), s, "命名", onset))
print(f"{CSV.split('/')[-1]}  lead={LEAD:.0f}s  比賽結束 遊戲 {gt(END - G0)}  撤銷 {sum(1 for e in events if e[3]=='撤銷')} 次")
delays = []
for team in "RB":
    K = known(tower_ev[team], END)
    seq = sorted(D[team].items(), key=lambda kv: kv[1][1])
    delays += [nm - on for _, (nm, on) in seq]
    print(f"  {team} 隊 feed {K} / 命名 {len(D[team])} {'OK' if len(D[team]) == K else 'DIFF'}：" + "  ".join(f"{s[2:]}@{gt(on - G0)}(+{nm - on}s)" for s, (nm, on) in seq))
if delays: print(f"  命名延遲（從影片開始顯示消失到命名）：中位數 {int(np.median(delays))} 秒，最大 {int(max(delays))} 秒")
if OUTJSON:
    json.dump({tm: {s: {"named": v[0] - G0, "onset": v[1] - G0} for s, v in D[tm].items()} for tm in "RB"}, open(OUTJSON, "w"), ensure_ascii=False)
