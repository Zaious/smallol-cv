# 塔事件指派：feed 給「何時、幾座」，小地圖 IoU 給「哪座」。
# 同一事件在兩種模式下各挑一次：free（只看小地圖訊號）與 lane（再加上「同一路外→內→水晶塔」限制）。
import csv, json, re, sys, statistics as st
sys.stdout.reconfigure(encoding="utf-8")
CSV, FEED, G0 = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = list(csv.DictReader(open(CSV)))
cfg = json.load(open("data/minimap_sites_2025_worlds.json", encoding="utf-8"))
LANES = ["top", "mid", "bot"]
ORDER = ["outer", "inner", "inhib_tower"]
sites = {t: [f"{t}_{l}_{o}" for l in LANES for o in ORDER] for t in "RB"}
T = [int(r["t"]) for r in rows]
ALL_TOWERS = [s["id"] for s in cfg["sites"] if s["kind"] == "tower"]
def hidden(r):   # 同一秒太多站點同時為 0：小地圖不在畫面上（單一站點的 0.0 是被摧毀的訊號，要保留）
    return sum(1 for s in ALL_TOWERS if float(r[s]) == 0.0) >= 15
def window_median(sid, a, b):
    v = [float(r[sid]) for r in rows if a <= int(r["t"]) <= b and not hidden(r)]
    return st.median(v) if len(v) >= 10 else None
feed = {}
for line in open(FEED, encoding="utf-8", errors="replace"):
    m = re.match(r"(\d+)min .* blueTowers=(\d+) .* redTowers=(\d+)", line)
    if m: feed[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
events = []; prev = (0, 0)
for k in sorted(feed):
    b, r = feed[k]
    if b > prev[0]: events.append((k, "R", b - prev[0]))   # 藍方摧毀 -> 紅塔消失
    if r > prev[1]: events.append((k, "B", r - prev[1]))   # 紅方摧毀 -> 藍塔消失
    prev = (b, r)
def lane_ok(sid, gone):
    t, lane, rest = sid.split("_", 2)
    i = ORDER.index(rest)
    return all(f"{t}_{lane}_{ORDER[j]}" in gone for j in range(i))
def pick(team, k, d, gone, constrained):
    a = G0 + 41 + 60 * (k - 1); b = a + 60 + 150     # 該分鐘起，往後再看 150 秒（下一環節開始後才確認）
    cands = []
    for sid in sites[team]:
        if sid in gone: continue
        if constrained and not lane_ok(sid, gone): continue
        v = window_median(sid, a, b)
        if v is not None: cands.append((v, sid))
    cands.sort()
    return cands[:d], cands[d:d + 2]
def run(constrained):
    gone = {"R": set(), "B": set()}; out = []
    for k, team, d in events:
        chosen_all, nxt = [], []
        for _ in range(d):   # 一座一座挑：同一分鐘內可連鎖（外塔倒了，內塔才可選）
            ch, nxt = pick(team, k, 1, gone[team], constrained)
            for v, sid in ch: gone[team].add(sid); chosen_all.append((v, sid))
        out.append((k, team, d, chosen_all, nxt))
    return out, gone
def violates(sid, gone_before):
    return not lane_ok(sid, gone_before)
print("== free 模式（只用小地圖分數，不套路線限制）==")
free, gf = run(False)
viol = 0; gone_acc = {"R": set(), "B": set()}
for k, team, d, chosen, nxt in free:
    for v, sid in chosen:
        bad = violates(sid, gone_acc[team]); viol += bad
        gone_acc[team].add(sid)
        nx = f"{nxt[0][1]}({nxt[0][0]:.2f})" if nxt else "-"
        print(f"  min{k:2d} {team} {sid:20s} IoU={v:.2f}  下一名={nx}  {'路線違規' if bad else '合乎路線'}")
print("free 模式路線違規數:", viol, "/", sum(len(c) for _, _, _, c, _ in free))
print("\n== lane 模式（套路線限制）==")
lane, gl = run(True)
for k, team, d, chosen, nxt in lane:
    for v, sid in chosen:
        nx = f"{nxt[0][1]}({nxt[0][0]:.2f})" if nxt else "-"
        print(f"  min{k:2d} {team} {sid:20s} IoU={v:.2f}  下一名={nx}")
sf = {t: gf[t] for t in "RB"}; sl = {t: gl[t] for t in "RB"}
print("\n兩模式最後集合是否相同:", sf == sl)
for t in "RB":
    print(f"  {t}: free-only={sorted(sf[t]-sl[t])}  lane-only={sorted(sl[t]-sf[t])}")
