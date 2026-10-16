# 塔不會重生：每座塔「最後一次有穩定存在證據」的時間 = 摧毀時間的下界。
# 再把 feed 的確切事件時間，配對給「最後存在證據不晚於事件」且最接近事件的塔（貪婪、每座塔一次）。
import csv, json, re, sys, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
CSV, EVENTS, G0, START_ISO = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
ALIVE, NEED = 0.25, 3
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
TOW = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
def hidden(r): return sum(1 for s in TOW if float(r[s]) == 0.0) >= 15
tmin, tmax = int(rows[0]["t"]), int(rows[-1]["t"])
import statistics as st
WIN, MED = 20, 0.30   # 以 20 秒窗口的中位數判斷「存在」：短暫經過的小兵／英雄不算
valid = [r for r in rows if not hidden(r)]
last_seen = {}
for sid in TOW:
    last = None
    for i in range(len(valid) - WIN):
        w = [float(r[sid]) for r in valid[i:i + WIN]]
        if st.median(w) >= MED: last = int(valid[i + WIN - 1]["t"])
    last_seen[sid] = last
def gt(v): g = v - G0; return f"{g//60}:{g%60:02d}"
print("每座塔最後穩定存在時間（遊戲時間；影片結束＝{}）".format(gt(tmax)))
for team in "RB":
    for sid in sorted(TOW):
        if sid.startswith(team + "_"): print(f"  {sid:20s} {gt(last_seen[sid]) if last_seen[sid] else '從未'}")
start = dt.datetime.fromisoformat(START_ISO.replace("Z", "+00:00"))
ev = []
for line in open(EVENTS, encoding="utf-8"):
    m = re.match(r"(\S+) (B_towers|R_towers) (\d+)->(\d+)", line)
    if m:
        T = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        ev.append(((T - start).total_seconds(), "R" if m.group(2) == "B_towers" else "B", int(m.group(4))))
used = set()
print("\n事件配對（事件時間；配到的塔；該塔最後存在時間；與事件相差）")
for g, team, n in ev:
    v = G0 + g
    if v > tmax - 5: print(f"  {int(g)//60}:{int(g)%60:02d} {team}#{n}  影片已結束，不判斷"); continue
    cands = [(v - last_seen[s], s) for s in TOW if s.startswith(team + "_") and s not in used and last_seen[s] is not None and last_seen[s] <= v + 6]
    cands.sort()    # 離事件最近、且不晚於事件的最後存在時間
    top = cands[:3]
    txt = "; ".join(f"{s}(最後存在 {gt(last_seen[s])}, 差 {d:.0f}s)" for d, s in top)
    print(f"  {int(g)//60}:{int(g)%60:02d} {team}#{n}  {txt}")
    if top: used.add(top[0][1])
