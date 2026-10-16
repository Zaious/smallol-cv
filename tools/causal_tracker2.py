# 因果式（可串流）塔追蹤：只用「當下以前」的 NCC 與 feed 計數，不使用任何 feed 時間戳對位。
# 規則：
#   1) feed 計數 K 是硬上限：每隊最多只標 K 座為已摧毀。
#   2) 持續證據：最近 W 秒（有效秒 >= MINV）中，NCC 全程 < DEAD 且從未 >= BACK（塔不會重生，回來過就不是消失）。
#   3) 路線前綴：內塔須外塔已倒、水晶塔須內塔已倒；基地塔須該隊已有水晶事件。
#   4) 候選超過空位時取證據最強者；兩者差距 < TIE 且只剩一個空位 → 先等（標 ambiguous）。
# 用法：python tools/causal_tracker.py <ncc.csv> <feed_events.txt> <G0> <START_ISO> <lead_seconds> [--json out.json]
import csv, json, re, sys
import datetime as dt
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO, LEAD = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
OUTJSON = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
W, MINV, DEAD, BACK, TIE = 45, 30, 0.70, 0.85, 0.05
LANES = ["top", "mid", "bot"]; TIERS = ["outer", "inner", "inhib_tower"]

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
t_all = np.array([int(r["t"]) for r in rows]); X = {s: np.array([float(r[s]) for r in rows]) for s in TOW}
hidden = np.array([sum(1 for s in TOW if X[s][i] < 0.45) >= 0.7 * len(TOW) for i in range(len(rows))])

def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"
def known(evlist, t):       # feed 比影片早 LEAD 秒到：影片時間 t 時，已知的事件 = 影片時間 G0+E-LEAD <= t
    return sum(1 for e in evlist if G0 + e - LEAD <= t)
def feasible(s, D):
    p = s.split("_"); team, lane = p[0], p[1]
    if lane == "nexus": return any(G0 + e - LEAD <= cur_t for e in inhib_ev[team])
    k = TIERS.index("_".join(p[2:]))
    return all(f"{team}_{lane}_{TIERS[j]}" in D[team] for j in range(k))

D = {"R": {}, "B": {}}; log = []; cur_t = 0
for i, t in enumerate(t_all):
    cur_t = t
    if t < G0 + 14 * 60: continue
    lo = max(0, i - W * 2); idx = [j for j in range(lo, i + 1) if not hidden[j] and t_all[j] > t - W]
    if len(idx) < MINV: continue
    for team in "RB":
        for s_ in list(D[team].keys()):
            if D[team][s_][0] >= t - 2: continue
            v = [X[s_][j] for j in range(max(0, i - 10), i + 1) if not hidden[j]]
            if len(v) >= 6 and min(v[-6:]) >= 0.90:
                del D[team][s_]; log.append((team, t, s_, "revoked", None))
        K = known(tower_ev[team], t)
        while len(D[team]) < K:
            cands = []
            for s in TOW:
                if not s.startswith(team + "_") or s in D[team] or not feasible(s, D): continue
                x = X[s][idx]
                if x.max() < BACK and x.max() < 0.85 and (x < DEAD).mean() >= 0.95:
                    cands.append((float(np.median(x)), s))
            if not cands: break
            cands.sort()
            room = K - len(D[team])
            if room == 1 and len(cands) > 1 and cands[1][0] - cands[0][0] < TIE:
                log.append((team, t, None, "ambiguous", [c[1] for c in cands[:2]])); break
            s = cands[0][1]
            onset = next((int(t_all[j]) for j in idx if X[s][j] < DEAD), int(t))
            D[team][s] = (int(t), onset); log.append((team, t, s, "named", onset))
print(f"{CSV.split('/')[-1]} lead={LEAD:.0f}s  比賽結束 遊戲 {gt(END - G0)}  撤銷 {sum(1 for l in log if l[3]=='revoked')} 次")
for team in "RB":
    K = known(tower_ev[team], END)
    seq = sorted(D[team].items(), key=lambda kv: kv[1][1])
    print(f"  {team} 隊 feed {K} 件 / 已標名 {len(D[team])} 座：" + "  ".join(f"{s[2:]}@onset{gt(on - G0)}(命名{gt(nm - G0)})" for s, (nm, on) in seq))
if OUTJSON:
    json.dump({tm: {s: {"named": v[0] - G0, "onset": v[1] - G0} for s, v in D[tm].items()} for tm in "RB"}, open(OUTJSON, "w"), ensure_ascii=False)
