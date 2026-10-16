# 禁用辨識評估：用 tools/bans26.py 的 final_bans（最後 3 張可見畫格、10 格一對一指派）對照 Leaguepedia。
# 左列 = 左側隊伍禁用 1–5；右列 = 右側隊伍禁用 1–5。Leaguepedia Team1 = 左側（藍方）。
# 用法：python tools/bans26_eval.py <局目錄前綴 d1g> <起局> <迄局>
import sys, glob, json, cv2
sys.path.insert(0, "tools"); import bans26 as B
sys.stdout.reconfigure(encoding="utf-8")
pre, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
dd = json.load(open("hero-icons/16.20.1_champion.json", encoding="utf-8"))["data"]
name2id = {v["name"]: k for k, v in dd.items()}
lp = sorted([r["title"] for r in json.load(open("data/bans26/leaguepedia_d1.json", encoding="utf-8"))["cargoquery"] if r["title"]["DateTime UTC"] >= "2026-10-15 18"], key=lambda t: t["DateTime UTC"])
tot = ok = 0
for k in range(a, b + 1):
    t = lp[k - 1]; fs = sorted(glob.glob(f"data/bans26/{pre}{k}/f_*.jpg"))
    fb = B.final_bans([cv2.imread(f) for f in fs])
    t1 = [name2id.get(x.strip(), x.strip()) for x in t["Team1Bans"].split(",")]; t2 = [name2id.get(x.strip(), x.strip()) for x in t["Team2Bans"].split(",")]
    if fb is None: print(f"{pre}{k} 看不到 BP 列（畫格 {len(fs)}）"); tot += 10; continue
    L, R = fb
    c = sum(x == y for x, y in zip(L, t1)) + sum(x == y for x, y in zip(R, t2)); tot += 10; ok += c
    print(f"{pre}{k} {t['Team1']} vs {t['Team2']}  畫格 {len(fs)}  正確 {c}/10")
    for side, me, tr in (("左", L, t1), ("右", R, t2)):
        bad = [(i + 1, x, y) for i, (x, y) in enumerate(zip(me, tr)) if x != y]
        if bad: print("   ", side, "錯（第幾手, 辨識, 正解）:", bad)
print(f"合計 {ok}/{tot}")
