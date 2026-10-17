# 歷史資料庫（給桌面工具「沒比賽時」用）：把已結束的 Worlds 2026 小局整理成 JSON。
#   data/archive/games/<gameId>.json：單局回顧（藍紅方、勝方、禁用、選角與選手數據、最終數字、龍、三蟲、預示者、哪幾座塔、每分鐘經濟差）
#   data/archive/teams.json：各隊 BP 歷史；data/archive/players.json：各選手角色池與勝率
# 來源與優先序（每個欄位都記來源）：
#   賽程、系列賽、藍紅方：官方 esports-api（getSchedule、getEventDetails；開打後的藍紅方）
#   選角、選手數據、裝備、擊殺、金錢、塔數、水晶、巴龍、龍、經濟差：官方 feed（本機記錄的 feed_<gameId>.jsonl，沒有就線上抓）
#   禁用：本服務的畫面辨識（statelog）＞ Leaguepedia；勝方、三蟲、預示者：Leaguepedia（data/bans26/leaguepedia_games.json）
#   哪幾座塔倒了：本服務的塔命名（data/trig4_w26_<gameId>.json，只有我們有錄影的局）
# 用法：LOL_API_KEY=... python tools/archive.py
import sys, os, json, glob, importlib.util, datetime as dt
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.argv = [sys.argv[0]]; sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("svc", os.path.join(HERE, "live_service.py")); svc = importlib.util.module_from_spec(spec); spec.loader.exec_module(svc)
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.join(ROOT, "data", "live_worlds2026"); OUT = os.path.join(ROOT, "data", "archive"); os.makedirs(f"{OUT}/games", exist_ok=True)
ts = svc.ts; gclock = svc.gclock
champ_names = json.load(open(os.path.join(ROOT, "hero-icons", "16.20.1_champion.json"), encoding="utf-8"))["data"]
name2id = {v["name"]: k for k, v in champ_names.items()}
LPN = {"Karmine Corp": "KC", "Cloud9": "C9", "MVK Esports": "MVK", "FURIA": "FUR"}   # Leaguepedia 隊名 → 官方代碼（之後隊伍增加要補）

def lp_games():
    p = os.path.join(ROOT, "data", "bans26", "leaguepedia_games.json")
    try: return [r["title"] for r in json.load(open(p, encoding="utf-8")).get("cargoquery", [])]
    except Exception: return []
LP = lp_games()

def lp_find(blue, red, start):
    """以藍紅方代碼與開打時間（±40 分鐘）找 Leaguepedia 的該局；Leaguepedia 的 Team1 為藍方。"""
    for t in LP:
        if LPN.get(t["Team1"]) == blue and LPN.get(t["Team2"]) == red:
            if abs(ts(t["DateTime UTC"].replace(" ", "T") + "Z") - start) < 2400: return t
    return None

def feed_rows(gid):
    p = f"{D}/feed_{gid}.jsonl"
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else None

def cv_bans(gid):
    """本服務在該局進行中輸出的最終禁用（statelog 的最後一筆 in_game/finished）。"""
    last = None
    p = f"{D}/statelog.jsonl"
    if not os.path.exists(p): return None
    for l in open(p, encoding="utf-8"):
        d = json.loads(l)
        if d.get("game") == gid and d.get("draft") and d["status"] in ("in_game", "finished"): last = d["draft"]["current"]
    if last and any(last[s]["bans"][0] for s in "BR"): return {s: last[s]["bans"] for s in "BR"}, "cv"
    p2 = os.path.join(ROOT, "data", "bans26", "d1_cv_bans.json")         # Day 1：服務當時還沒有禁用辨識，改用錄影版 BP 畫面的辨識（80/80）
    if os.path.exists(p2):
        v = json.load(open(p2, encoding="utf-8")).get(gid)
        if v: return v, "cv_vod"
    return None

def build_game(m, g, sched_entry):
    gid = g["id"]; rows = feed_rows(gid)
    if not rows: return None
    ig = [x for x in rows if x["state"] == "in_game"]
    if not ig: return None
    st0, end = ts(ig[0]["ts"]), ts(rows[-1]["ts"]); last = rows[-1]
    md = svc.match_details(m["matchId"]); code = {t["id"]: t["code"] for t in md["teams"]}
    sides = {("B" if t["side"] == "blue" else "R"): code[t["id"]] for t in g["teams"]}
    rec = {"gameId": gid, "matchId": m["matchId"], "stage": m["stage"], "game": g["number"], "bestOf": m["bestOf"],
           "start": svc.iso(st0), "durationSec": int(end - st0), "duration": gclock(end - st0), "teams": sides, "sources": {}}
    lp = lp_find(sides["B"], sides["R"], st0)
    # 勝方
    if lp and lp.get("Winner") in ("1", "2"): rec["winner"] = "B" if lp["Winner"] == "1" else "R"; rec["sources"]["winner"] = "leaguepedia"
    else:
        # 備援：本服務的塔命名中，主堡塔被打掉的一方為輸家（Leaguepedia 限流時用；以系列賽比分交叉驗證）
        rec["winner"] = None; rec["sources"]["winner"] = "unknown"
        tp0 = os.path.join(ROOT, "data", f"trig4_w26_{gid}.json")
        if os.path.exists(tp0):
            t0 = json.load(open(tp0, encoding="utf-8"))
            lost_nexus = [s for s in "BR" if any("_nexus_" in k for k in t0[s])]
            if len(lost_nexus) == 1: rec["winner"] = "R" if lost_nexus[0] == "B" else "B"; rec["sources"]["winner"] = "cv_nexus"
    # 選角與選手數據（feed 最後一幀）
    pl = svc.players_snapshot(gid, ts(last["ts"]))
    rec["players"] = pl; rec["sources"]["players"] = "feed"
    # 禁用
    b = cv_bans(gid)
    if b: rec["bans"], rec["sources"]["bans"] = b
    elif lp: rec["bans"] = {"B": [name2id.get(x.strip(), x.strip()) for x in lp["Team1Bans"].split(",")], "R": [name2id.get(x.strip(), x.strip()) for x in lp["Team2Bans"].split(",")]}; rec["sources"]["bans"] = "leaguepedia"
    else: rec["bans"] = None
    # 最終數字（feed；towers／inhibitors 為該隊打掉的數量）
    rec["final"] = {s: {"kills": last[s]["k"], "gold": last[s]["g"], "towers": last[s]["t"], "inhibitors": last[s]["i"], "barons": last[s]["b"], "dragons": last[s]["d"]} for s in "BR"}
    rec["sources"]["final"] = "feed"
    # 三蟲、預示者（Leaguepedia）
    if lp:
        rec["voidgrubs"] = {"B": int(lp["Team1VoidGrubs"] or 0), "R": int(lp["Team2VoidGrubs"] or 0)}
        rec["heralds"] = {"B": int(lp["Team1RiftHeralds"] or 0), "R": int(lp["Team2RiftHeralds"] or 0)}
        rec["sources"]["voidgrubs"] = rec["sources"]["heralds"] = "leaguepedia"
    # 哪幾座塔倒了（本服務的塔命名；只有錄影的局）
    tp = os.path.join(ROOT, "data", f"trig4_w26_{gid}.json")
    if os.path.exists(tp):
        t4 = json.load(open(tp, encoding="utf-8"))
        rec["towersLost"] = {s: sorted(({"site": k[2:], "gameTime": gclock(v["onset"]), "sec": v["onset"]} for k, v in t4[s].items()), key=lambda x: x["sec"]) for s in "BR"}
        rec["sources"]["towersLost"] = "cv"
    # 每分鐘經濟差（藍 − 紅）
    gd = []; nxt = 0
    for x in ig:
        t = ts(x["ts"]) - st0
        if t >= nxt: gd.append([int(t // 60), x["B"]["g"] - x["R"]["g"]]); nxt += 60
    rec["goldDiffPerMin"] = gd
    return rec

def main():
    sched = svc.schedule()
    games = []
    for m in sched["matches"]:
        if m["state"] not in ("completed", "inProgress"): continue
        md = svc.match_details(m["matchId"])
        for g in sorted(md["games"], key=lambda g: g["number"]):
            if g["state"] != "completed": continue
            r = build_game(m, g, m)
            if r:
                json.dump(r, open(f"{OUT}/games/{r['gameId']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1); games.append(r)
                print(r["gameId"], r["stage"], f"G{r['game']}", r["teams"]["B"], "vs", r["teams"]["R"], "勝", r["winner"], "| 來源", r["sources"])
            else: print(g["id"], "沒有 feed 記錄，略過")
    # 各隊 BP 歷史
    teams = defaultdict(list)
    for r in games:
        for s, o in (("B", "R"), ("R", "B")):
            teams[r["teams"][s]].append({"gameId": r["gameId"], "start": r["start"], "stage": r["stage"], "game": r["game"], "side": s,
                                         "opponent": r["teams"][o], "win": None if r["winner"] is None else r["winner"] == s,
                                         "bans": (r["bans"] or {}).get(s), "picks": [{"role": p["role"], "player": p["name"], "champion": p["champion"]} for p in (r["players"] or {}).get(s, [])]})
    json.dump({"updated": svc.iso(dt.datetime.now().timestamp()), "teams": teams}, open(f"{OUT}/teams.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 各選手角色池
    players = {}
    for r in games:
        for s in "BR":
            for p in (r["players"] or {}).get(s, []):
                e = players.setdefault(p["name"], {"team": r["teams"][s], "role": p["role"], "games": [], "pool": {}})
                win = None if r["winner"] is None else r["winner"] == s
                e["games"].append({"gameId": r["gameId"], "champion": p["champion"], "win": win, "k": p["kills"], "d": p["deaths"], "a": p["assists"]})
                c = e["pool"].setdefault(p["champion"], {"games": 0, "wins": 0, "k": 0, "d": 0, "a": 0})
                c["games"] += 1; c["wins"] += bool(win); c["k"] += p["kills"]; c["d"] += p["deaths"]; c["a"] += p["assists"]
    json.dump({"updated": svc.iso(dt.datetime.now().timestamp()), "scope": "Worlds 2026（本服務有記錄的小局）", "players": players}, open(f"{OUT}/players.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成：{len(games)} 局、{len(teams)} 隊、{len(players)} 位選手")
    try:                                                     # 順便更新隊伍資料檔的本屆上場局數（只讀本地檔，不打 Leaguepedia）
        import build_teamsheet; build_teamsheet.main()
    except Exception as e: print("隊伍資料檔更新失敗", repr(e))

if __name__ == "__main__": main()
