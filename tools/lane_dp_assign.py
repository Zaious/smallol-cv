# v10：路線前綴 + 動態規劃。每個事件只決定「哪一路」，層級由該路先後次序決定（外→內→水晶塔，必為前綴）。
# 基地塔（nexus）只能在該隊第一個水晶事件之後被摧毀，且排在三路之後。
# 用法：python tools/lane_dp_assign.py <iou.csv> <feed_events.txt> <G0> <START_ISO> [--json out.json]
import csv, json, re, sys, itertools
import numpy as np
import datetime as dt

sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
OUTJSON = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

GAP, THETA_A, THETA_D, CAP, DEAD_FLOOR = 8, 0.60, 0.35, 0.40, 0.20
MARGIN_CONF = 0.15       # 全局成本差距 >= 此值才標「確定」
TIERS = ["outer", "inner", "inhib_tower"]; LANES = ["top", "mid", "bot"]

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
    if m.group(2) == "B_towers": ev["R"].append(g)
    elif m.group(2) == "R_towers": ev["B"].append(g)
    elif m.group(2) == "B_inhib": inh["R"].append(g)
    elif m.group(2) == "R_inhib": inh["B"].append(g)
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
rows = [r for r in rows if int(r["t"]) <= END]
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
valid = [r for r in rows if not hidden(r)]
T = np.array([int(r["t"]) - G0 for r in valid], dtype=float)
X = {s: np.array([float(r[s]) for r in valid]) for s in TOW}
first_tower = min([e for t in "RB" for e in ev[t]] or [9999])
def base_of(s):
    m = (T >= 14 * 60 + 30) & (T <= first_tower - 10)
    v = np.sort(X[s][m]); return float(v[int(0.75 * (len(v) - 1))]) if len(v) >= 20 else None
BASE = {s: base_of(s) for s in TOW}
def cost(s, E):
    b = BASE[s]
    if b is None or b <= 0.05: return 0.6
    a = (T >= 14 * 60 + 30) & (T <= E - GAP); d = (T >= E + GAP)
    if a.sum() < 10 or d.sum() < 10: return 0.6
    la = np.minimum(CAP, np.maximum(0.0, (THETA_A * b - X[s][a]) / b)).mean()
    ld = np.minimum(CAP, np.maximum(0.0, (X[s][d] - max(THETA_D * b, DEAD_FLOOR)) / b)).mean()
    return float(la + ld)
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"

def solve(team, evs, forbid=None):
    """動態規劃：state=(n_top,n_mid,n_bot,n_nexus)；回傳 (最小總成本, 每事件的 (lane, tier_index) 清單)。forbid=(事件索引, 選項) 禁止某個選擇。"""
    first_inh = min(inh[team]) if inh[team] else 1e9
    sites = {(l, t): f"{team}_{l}_{TIERS[t]}" for l in LANES for t in range(3)}
    nexus = [f"{team}_nexus_t1", f"{team}_nexus_t2"]
    INF = 1e9; best = {(0, 0, 0, 0): (0.0, [])}
    for i, E in enumerate(evs):
        nxt = {}
        for (a, b_, c, n), (acc, path) in best.items():
            counts = {"top": a, "mid": b_, "bot": c}
            opts = []
            for l in LANES:
                k = counts[l]
                if k < 3: opts.append(((l, k), sites[(l, k)]))
            if E >= first_inh and n < 2: opts.append((("nexus", n), nexus[n]))
            opts.append((("unknown", 0), None))
            for key, site in opts:
                if forbid and forbid[0] == i and forbid[1] == key: continue
                c0 = cost(site, E) if site else 0.55
                if key[0] == "unknown": ns = (a, b_, c, n)
                elif key[0] == "nexus": ns = (a, b_, c, n + 1)
                else:
                    cc = dict(counts); cc[key[0]] += 1; ns = (cc["top"], cc["mid"], cc["bot"], n)
                tot = acc + c0
                if ns not in nxt or tot < nxt[ns][0]: nxt[ns] = (tot, path + [(key, site, c0)])
        best = nxt
    return min(best.values(), key=lambda v: v[0])

result = []
for team in "RB":
    evs = sorted(e for e in ev[team] if G0 + e <= END - 3)
    if not evs: continue
    tot, path = solve(team, evs)
    for i, (key, site, c0) in enumerate(path):
        alt, _ = solve(team, evs, forbid=(i, key))
        margin = alt - tot
        conf = "不確定" if site is None else ("確定" if margin >= MARGIN_CONF else "接近")
        result.append((team, evs[i], site, round(c0, 2), round(margin, 2), conf))
print(f"比賽結束點 遊戲 {gt(END - G0)}")
for team, E, s, c, mg, cf in sorted(result, key=lambda x: x[1]):
    print(f"  {team} 事件 {gt(E):>6} → {s or '（不確定）':20s} 成本={c} 差距={mg} [{cf}]")
n_c = sum(1 for r in result if r[5] == "確定"); n_n = sum(1 for r in result if r[5] == "接近"); n_u = sum(1 for r in result if r[5] == "不確定")
print(f"事件 {len(result)} 件：確定 {n_c}、接近 {n_n}、不確定 {n_u}")
if OUTJSON:
    json.dump([{"team": t, "event": e, "site": s, "cost": c, "margin": m, "conf": cf} for t, e, s, c, m, cf in result], open(OUTJSON, "w"), ensure_ascii=False)
