# v5：事件驅動的塔指派。feed 給確切事件時間，小地圖給「事件前有存在證據、事件後持續低」的站點。
# 用法：python tools/event_step_assign.py <iou.csv> <feed_events.txt> <G0> <START_ISO> [--quiet]
import csv, json, re, sys, statistics as st, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
QUIET = "--quiet" in sys.argv
PRE_A, PRE_B = 60, 8        # 事件前窗口：v-60 .. v-8
POST_A, POST_B = 6, 40      # 事件後近窗：v+6 .. v+40
LATE_B = 150                # 事件後遠窗：v+40 .. v+150
MINSCORE, MINMARGIN = 0.12, 0.08
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
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
END = min(G0 + int(last_ev) + 5, int(rows[-1]["t"]))
rows = [r for r in rows if int(r["t"]) <= END]
T = {int(r["t"]): r for r in rows}
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
def seg(sid, a, b):
    return [float(T[t][sid]) for t in range(int(a), int(b) + 1) if t in T and not hidden(T[t])]
def med(v): return st.median(v) if len(v) >= 6 else None
def best_pre(sid, v):
    best = None
    for a in range(int(v - PRE_A), int(v - PRE_B) - 9, 3):
        m = med(seg(sid, a, a + 9))
        if m is not None and (best is None or m > best): best = m
    return best
ORDER = {"outer": 0, "inner": 1, "inhib_tower": 2}
def lane_ok(sid, gone):
    p = sid.split("_")
    if p[1] == "nexus": return True
    i = ORDER["_".join(p[2:])]
    return all(f"{p[0]}_{p[1]}_{k}" in gone for k, j in ORDER.items() if j < i)
def gt(g): g = int(g); return f"{g//60}:{g%60:02d}"
n_veto = 0
result = []; per_team_gone = {"R": set(), "B": set()}
for team in "RB":
    evs = sorted(e for e in ev[team] if G0 + e <= END - 3)
    gone = per_team_gone[team]
    for e in evs:
        v = G0 + e; cands = []
        for sid in TOW:
            if not sid.startswith(team + "_") or sid in gone or not lane_ok(sid, gone): continue
            if "nexus" in sid and not any(g < e and tm == team for g, tm in inh): continue
            pre = best_pre(sid, v); post = med(seg(sid, v + POST_A, v + POST_B)); late = med(seg(sid, v + POST_B, min(v + LATE_B, END)))
            if pre is None or post is None: continue
            after = max(post, late if late is not None else post)
            if pre < 0.40: continue
            veto = False
            for a in range(int(v + 10), END - 5, 2):
                m5 = med(seg(sid, a, a + 4))
                if m5 is not None and m5 >= 0.55: veto = True; break
            if veto: n_veto += 1; continue
            # 下降時間必須落在事件前後 12 秒內：先降到事件前水準的一半以下，且之後 22 秒中位數仍低於 60%
            step_t = None
            for tt in range(int(v - 12), int(v + 12) + 1):
                a = med(seg(sid, tt, tt + 7)); b = med(seg(sid, tt + 8, tt + 30))
                if a is not None and b is not None and a <= 0.5 * pre and b <= 0.6 * pre: step_t = tt; break
            if step_t is None: continue
            cands.append((pre - after, sid, pre, post, late))
        cands.sort(reverse=True)
        if cands and cands[0][0] >= MINSCORE:
            margin = cands[0][0] - (cands[1][0] if len(cands) > 1 else 0)
            conf = "確定" if margin >= MINMARGIN else "接近"
            gone.add(cands[0][1]); result.append((team, e, cands[0][1], cands[0][0], margin, conf))
        else:
            result.append((team, e, None, cands[0][0] if cands else None, None, "不確定"))
import os
gname = os.path.basename(CSV).split("_")[-1].replace(".csv", "")
json.dump([{"team": t, "event": e, "site": sid, "score": sc, "margin": mg, "conf": cf} for t, e, sid, sc, mg, cf in result],
          open(f"data/assign_v7_{gname}.json", "w"), ensure_ascii=False)
print(f"比賽結束點 遊戲 {gt(END - G0)}；強存在否決次數 {n_veto}")
n_ok = 0; n_unc = 0; n_close = 0
for team, e, sid, score, margin, conf in sorted(result, key=lambda x: x[1]):
    if sid: n_ok += conf == "確定"; n_close += conf == "接近"
    else: n_unc += 1
    if not QUIET:
        print(f"  {team} 事件 {gt(e):>6} → {sid or '（不確定）':20s} 下降={score if score is None else round(score,2)} 與第二名差={margin if margin is None else round(margin,2)} [{conf}]")
# 一致性檢查
bad = 0; seen = {}
for team, e, sid, *_ in sorted(result, key=lambda x: x[1]):
    if not sid or "nexus" in sid: continue
    key = (team, sid.split("_")[1]); k = ORDER["_".join(sid.split("_")[2:])]
    bad += k < seen.get(key, -1); seen[key] = max(seen.get(key, -1), k)
ih = sorted(g for g, tm in inh)
chk_ok = chk_n = 0
for team, e, sid, *_ in result:
    if sid and sid.endswith("inhib_tower"):
        chk_n += 1; chk_ok += any(0 <= g - e <= 40 and tm == team for g, tm in inh)
print(f"事件 {len(result)} 件：確定 {n_ok}、接近 {n_close}、不確定 {n_unc}；路線違規 {bad}；水晶塔後 40 秒內有水晶事件 {chk_ok}/{chk_n}")
