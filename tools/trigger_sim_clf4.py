# 觸發式因果模擬：畫面端持續記錄每個站點每秒的三種狀態；feed 計數增加時進入待決，影片出現持續的「消失」證據就配對命名。
# 狀態由 D = 空地 NCC − 存活 NCC 決定：D <= -ALIVE_T 存活、D >= DEAD_T 消失、其餘未知；小地圖不可見的秒跳過。
# clf4 = clf3 + 補滿時主堡塔優先（見 complete_by_elimination）。
# 用法（分類器版）：python tools/trigger_sim_clf4.py <clf.csv> <feed_events.txt> <G0> <START_ISO> <lead_seconds> [--json out.json]
import csv, json, re, sys
import datetime as dt
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO, LEAD = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
OUTJSON = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
ALIVE_T, DEAD_T = 0.12, 0.12
ALIVE_RUN, NEED_DEAD_TOTAL, REVOKE_RUN = 4, 8, 5
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
    inc = int(m.group(4)) - int(m.group(3))                  # 一幀可能跳 2 以上（例如 7->9），每座各算一次（clf4 修正）
    if m.group(2) == "B_towers": tower_ev["R"] += [g] * inc
    elif m.group(2) == "R_towers": tower_ev["B"] += [g] * inc
    elif m.group(2) == "B_inhib": inhib_ev["R"] += [g] * inc
    elif m.group(2) == "R_inhib": inhib_ev["B"] += [g] * inc
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
if "--live" in sys.argv: END = int(rows[-1]["t"])            # 即時服務：不在最後一個 feed 事件後截斷（clf4 新增）
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

D = {"R": {}, "B": {}}; events = []
run_alive = {s_: 0 for s_ in TOW}; dead_since = {s_: 0 for s_ in TOW}; first_dead = {s_: None for s_ in TOW}; alive_run_seen = {s_: False for s_ in TOW}
for i, t in enumerate(t_all):
    if hidden[i] or t < G0 + 14 * 60: continue
    for s_ in TOW:
        st = ST[s_][i]
        run_alive[s_] = run_alive[s_] + 1 if st == -1 else 0
        if run_alive[s_] >= ALIVE_RUN:                      # 連續存活證據：重置累積的消失秒數
            dead_since[s_] = 0; first_dead[s_] = None; alive_run_seen[s_] = True
        elif st == 1:
            dead_since[s_] += 1
            if first_dead[s_] is None: first_dead[s_] = int(t)
    for team in "RB":
        for s_ in list(D[team]):                              # 撤銷：塔不會重生；需連續 REVOKE_RUN 秒存活
            if run_alive[s_] >= REVOKE_RUN and D[team][s_][0] < t - 2:
                del D[team][s_]; events.append((team, int(t), s_, "撤銷", None))
        K = known(tower_ev[team], t)
        while len(D[team]) < K:
            cands = []
            for s_ in TOW:
                if not s_.startswith(team + "_") or s_ in D[team] or not feasible(s_, D, t): continue
                if dead_since[s_] >= NEED_DEAD_TOTAL and run_alive[s_] == 0: cands.append((-dead_since[s_], first_dead[s_], s_))
            if not cands: break
            cands.sort(); s_ = cands[0][2]
            D[team][s_] = (int(t), first_dead[s_]); events.append((team, int(t), s_, "命名", first_dead[s_]))
def complete_by_elimination(team, t_end):
    """名額未滿時，從路線前綴可選的站點裡挑最近 30 個有效秒平均存活機率最低者補滿；一座一座補，補完後前綴更新。"""
    K = known(tower_ev[team], t_end); added = []
    valid_idx = [j for j in range(len(rows)) if not hidden[j] and t_all[j] <= t_end][-30:]
    # 主堡塔優先（clf4 新增）：水晶被破之後 feed 又記到的塔損失，優先補給主堡塔（最多 2 座，扣掉已命名者）。
    # 起因：英雄頭像圍住主堡塔時，頭像外框被判成存活，補滿誤挑其他路的塔（MVK vs FUR 第 1 局）。
    inh = [e for e in inhib_ev[team] if G0 + e - LEAD <= t_end]
    if inh:
        after = sum(1 for e in tower_ev[team] if e > min(inh) and G0 + e - LEAD <= t_end)
        quota = min(2, after) - sum(1 for s_ in D[team] if "_nexus_" in s_)
        for s_ in [f"{team}_nexus_t1", f"{team}_nexus_t2"]:
            if quota <= 0 or len(D[team]) >= K: break
            if s_ not in D[team]:
                D[team][s_] = (int(t_end), int(t_end)); added.append((s_, "nexus-first")); quota -= 1
    while len(D[team]) < K:
        cands = [(float(np.mean(PA[s_][valid_idx])), s_) for s_ in TOW if s_.startswith(team + "_") and s_ not in D[team] and feasible(s_, D, t_end)]
        if not cands: break
        cands.sort(); pa, s_ = cands[0]
        if pa > 0.5: break                                    # 最像存活的也 > 0.5 表示證據不足，不硬補
        D[team][s_] = (int(t_end), int(t_end)); added.append((s_, round(pa, 2)))
    return added
COMPLETED = {}
if "--complete" in sys.argv:
    for team in "RB": COMPLETED[team] = complete_by_elimination(team, int(t_all[-1]))
print(f"{CSV.split('/')[-1]}  lead={LEAD:.0f}s  比賽結束 遊戲 {gt(END - G0)}  撤銷 {sum(1 for e in events if e[3]=='撤銷')} 次")
delays = []
for team in "RB":
    K = known(tower_ev[team], END)
    seq = sorted(D[team].items(), key=lambda kv: kv[1][1])
    delays += [nm - on for _, (nm, on) in seq]
    print(f"  {team} 隊 feed {K} / 命名 {len(D[team])} {'OK' if len(D[team]) == K else 'DIFF'}：" + "  ".join(f"{s[2:]}@{gt(on - G0)}(+{nm - on}s)" for s, (nm, on) in seq))
if COMPLETED: print("  排除法補上：", {t: c for t, c in COMPLETED.items() if c})
if delays: print(f"  命名延遲（從影片開始顯示消失到命名）：中位數 {int(np.median(delays))} 秒，最大 {int(max(delays))} 秒")
if OUTJSON:
    json.dump({tm: {s: {"named": v[0] - G0, "onset": v[1] - G0} for s, v in D[tm].items()} for tm in "RB"}, open(OUTJSON, "w"), ensure_ascii=False)
