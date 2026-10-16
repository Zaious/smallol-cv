# 終局回溯：用整場證據一次判定「哪些塔被摧毀、依序是誰」。不使用 feed 時間戳，只用 feed 的各隊總數當上限。
#   last_alive(s) = 該塔最後一次連續 ALIVE_RUN 個有效秒回到自己存活水準的時間
#   已摧毀 = last_alive 之後仍有 >= MIN_AFTER 個有效秒（遮擋不產生存活證據；塔不會重生）
#   每隊取 K（feed 計數）座，依 last_alive 由早到晚；套用路線前綴（外→內→水晶塔）；基地塔須在水晶塔之後。
# 用法：python tools/final_state.py <ncc.csv> <feed_events.txt> <G0> <START_ISO> [--quiet]
import csv, json, re, sys
import datetime as dt
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
QUIET = "--quiet" in sys.argv
ALIVE_RUN, MIN_AFTER = 3, 60
TIERS = ["outer", "inner", "inhib_tower"]
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
tower_ev = {"R": [], "B": []}; last_ev = 0.0
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (\w+) (\d+)->(\d+)", line)
    if not m: continue
    g = (dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) - start).total_seconds(); last_ev = max(last_ev, g)
    if m.group(2) == "B_towers": tower_ev["R"].append(g)
    elif m.group(2) == "R_towers": tower_ev["B"].append(g)
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
rows = [r for r in rows if int(r["t"]) <= END]
t_all = np.array([int(r["t"]) for r in rows]); X = {s: np.array([float(r[s]) for r in rows]) for s in TOW}
hidden = np.array([sum(1 for s in TOW if X[s][i] < 0.45) >= 0.7 * len(TOW) for i in range(len(rows))])
first_tower = min([e for t in "RB" for e in tower_ev[t]] or [9999])
base_idx = np.where((~hidden) & (t_all >= G0 + 14 * 60 + 30) & (t_all <= G0 + first_tower - 10))[0]
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"

MU, BACK = {}, {}
for s in TOW:
    v = X[s][base_idx]
    if len(v) < 40: continue
    mu = float(np.median(v)); sig = max(0.01, 1.4826 * float(np.median(np.abs(v - mu))))
    MU[s] = mu; BACK[s] = mu - max(0.04, 2.5 * sig)

valid = np.where(~hidden & (t_all >= G0 + 14 * 60))[0]
info = {}
for s in TOW:
    if s not in MU: continue
    ok = X[s][valid] >= BACK[s]; last = None; run = 0
    for k in range(len(valid)):
        run = run + 1 if ok[k] else 0
        if run >= ALIVE_RUN: last = k
    if last is None: info[s] = (None, 0, 0.0); continue
    after = X[s][valid][last + 1:]
    info[s] = (int(t_all[valid[last]]), len(after), float(np.median(after)) if len(after) else 1.0)

def feasible(s, D):
    p = s.split("_"); team, lane = p[0], p[1]
    if lane == "nexus": return all(f"{team}_{l}_inhib_tower" in D or True for l in ("top",)) and any("inhib_tower" in d for d in D)
    k = TIERS.index("_".join(p[2:])); return all(f"{team}_{lane}_{TIERS[j]}" in D for j in range(k))

res = {}
for team in "RB":
    K = len([e for e in tower_ev[team] if G0 + e <= END - 3])
    cands = [(info[s][0], s) for s in TOW if s.startswith(team + "_") and s in info and info[s][0] is not None and info[s][1] >= MIN_AFTER]
    cands.sort()
    D = {}
    changed = True
    while changed and len(D) < K:
        changed = False
        for la, s in cands:
            if s in D or not feasible(s, D): continue
            D[s] = la; changed = True; break
    res[team] = (K, D, len(cands))
print(f"{CSV.split('/')[-1]}  比賽結束 遊戲 {gt(END - G0)}")
for team in "RB":
    K, D, nc = res[team]
    seq = sorted(D.items(), key=lambda kv: kv[1])
    print(f"  {team} 隊 feed {K} / 候選 {nc} / 採用 {len(D)} {'OK' if len(D) == K else 'DIFF'}： " + "  ".join(f"{s[2:]}@{gt(t - G0)}" for s, t in seq))
json.dump({tm: {s: t - G0 for s, t in res[tm][1].items()} for tm in "RB"}, open(CSV.replace("minimap_ncc_", "final_state_").replace(".csv", ".json"), "w"), ensure_ascii=False)
