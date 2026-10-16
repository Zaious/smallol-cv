# v9：全局指派。feed 給事件確切時間；小地圖整段序列給每座塔「在事件前存在、事件後不存在」的證據。
# 用法：python tools/global_assign.py <iou.csv> <feed_events.txt> <G0> <START_ISO> [--json out.json]
import csv, json, re, sys, statistics as st, datetime as dt
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
OUTJSON = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

GAP = 8                 # 事件前後各排除 8 秒（吸收 feed 與影片的延遲）
THETA_A, THETA_D = 0.60, 0.35
CAP = 0.40              # 截斷損失上限：偶爾遮擋不致命
DEAD_FLOOR = 0.20       # 消失後的雜訊底
UNKNOWN_COST = 0.55
CONF_MARGIN, CONF_COST = 0.10, 0.35

rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
ev = {"R": [], "B": []}; inh = {"R": [], "B": []}; last_ev = 0.0
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (\w+) (\d+)->(\d+)", line)
    if not m: continue
    g = (dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")) - start).total_seconds()
    last_ev = max(last_ev, g)
    if m.group(2) == "B_towers": ev["R"].append(g)          # 藍方摧毀 -> 紅塔消失
    elif m.group(2) == "R_towers": ev["B"].append(g)
    elif m.group(2) == "B_inhib": inh["R"].append(g)
    elif m.group(2) == "R_inhib": inh["B"].append(g)
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
rows = [r for r in rows if int(r["t"]) <= END]

def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
valid = [r for r in rows if not hidden(r)]
T = np.array([int(r["t"]) - G0 for r in valid], dtype=float)           # 遊戲秒
X = {s: np.array([float(r[s]) for r in valid]) for s in TOW}
first_tower = min([e for t in "RB" for e in ev[t]] or [9999])

def base_of(s):
    m = (T >= 14 * 60 + 30) & (T <= first_tower - 10)
    v = np.sort(X[s][m]); return float(v[int(0.75 * (len(v) - 1))]) if len(v) >= 20 else None
BASE = {s: base_of(s) for s in TOW}

def cost(s, E):
    b = BASE[s]
    if b is None or b <= 0.05: return None
    a_mask = (T >= 14 * 60 + 30) & (T <= E - GAP)
    d_mask = (T >= E + GAP)
    if a_mask.sum() < 10 or d_mask.sum() < 10: return None
    la = np.minimum(CAP, np.maximum(0.0, (THETA_A * b - X[s][a_mask]) / b)).mean()
    thr = max(THETA_D * b, DEAD_FLOOR)
    ld = np.minimum(CAP, np.maximum(0.0, (X[s][d_mask] - thr) / b)).mean()
    return float(la + ld)

ORDER = {"outer": 0, "inner": 1, "inhib_tower": 2}
def lane_of(s): return s.split("_")[1]
def kind_of(s): return "_".join(s.split("_")[2:])
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"

result = []
for team in "RB":
    sites = [s for s in TOW if s.startswith(team + "_")]
    evs = sorted(e for e in ev[team] if G0 + e <= END - 3)
    if not evs: continue
    first_inh = min(inh[team]) if inh[team] else 1e9
    C = np.full((len(evs), len(sites)), 9.0)
    for i, E in enumerate(evs):
        for j, s in enumerate(sites):
            if "nexus" in s and E < first_inh: continue
            c = cost(s, E)
            if c is not None: C[i, j] = c
    # 加入「不確定」虛擬站點：每個事件一個，成本 UNKNOWN_COST
    big = np.hstack([C, np.full((len(evs), len(evs)), UNKNOWN_COST)])
    ri, cj = linear_sum_assignment(big)
    assign = {}
    for i, j in zip(ri, cj): assign[i] = sites[j] if j < len(sites) else None
    # 同一路物理順序重排：該路被指派的事件按時間排序，依 外→內→水晶塔 取代原本的站點
    for lane in ("top", "mid", "bot"):
        idx = sorted([i for i, s in assign.items() if s and lane_of(s) == lane], key=lambda i: evs[i])
        used = sorted([assign[i] for i in idx], key=lambda s: ORDER[kind_of(s)])
        for i, s in zip(idx, used): assign[i] = s
    for i, E in enumerate(evs):
        s = assign[i]
        if s is None:
            result.append((team, E, None, None, None, "不確定")); continue
        j = sites.index(s); c = C[i, j]
        alt = sorted(C[i, k] for k in range(len(sites)) if k != j)
        margin = (alt[0] - c) if alt else 9.0
        conf = "確定" if (margin >= CONF_MARGIN and c <= CONF_COST) else "接近"
        result.append((team, E, s, round(float(c), 2), round(float(margin), 2), conf))

print(f"比賽結束點 遊戲 {gt(END - G0)}；低基準站點:", {s: round(BASE[s], 2) for s in TOW if BASE[s] is not None and BASE[s] < 0.35})
for team, E, s, c, mg, cf in sorted(result, key=lambda x: x[1]):
    print(f"  {team} 事件 {gt(E):>6} → {s or '（不確定）':20s} 成本={c} 差距={mg} [{cf}]")
n = len(result); n_c = sum(1 for r in result if r[5] == "確定"); n_n = sum(1 for r in result if r[5] == "接近"); n_u = sum(1 for r in result if r[5] == "不確定")
print(f"事件 {n} 件：確定 {n_c}、接近 {n_n}、不確定 {n_u}")
if OUTJSON:
    json.dump([{"team": t, "event": e, "site": s, "cost": c, "margin": m, "conf": cf} for t, e, s, c, m, cf in result], open(OUTJSON, "w"), ensure_ascii=False)
