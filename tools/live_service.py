# 即時服務 v0：讀 live_feed_log.mjs 的 feed 記錄與 live_classify.py 的逐秒判讀，每 5 秒更新一次對局狀態。
# 輸出：<out_dir>/state.json（目前狀態）、<out_dir>/events.jsonl（新事件逐行附加）、HTTP http://127.0.0.1:<port>/state.json
# 塔「哪一座」：以 trigger_sim_clf4.py --live 重跑累積資料（命名是因果的，重跑等同即時）；feed 結束時把資料截在結束點並做補滿。
# 龍（屬性、龍魂、遠古）、巴龍、水晶、擊殺、金錢：直接取自官方 feed。計時類（重生、buff 持續）尚未實作：規則需先對 16.20 版查證。
# 用法：python tools/live_service.py [--dir data/live_worlds2026] [--port 8787] [--once <gameId>]
import csv, glob, json, os, subprocess, sys, threading, time, datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np

arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
D = arg("--dir", "data/live_worlds2026"); PORT = int(arg("--port", "8787")); ONCE = arg("--once", None)
LAG, G0 = 31.0, 1000
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
gclock = lambda sec: f"{int(sec)//60}:{int(sec)%60:02d}"
STATE = {"status": "starting"}; LOCK = threading.Lock(); _ARCHIVED = set()
sys.path.insert(0, HERE)
from hud_clock import read_clock, read_clock_safe
import cv2
# 物件規則（版本 26.x；來源：官方 /dev 2026 Season One Gameplay Preview 與 LoL Wiki，2026-10-16 查閱；尚未在比賽畫面上逐項驗證）
RULES = {
    "dragonFirstSpawn": 5 * 60, "dragonRespawn": 5 * 60,          # 元素龍：5:00 首次；擊殺後 5 分鐘重生
    "elderAfterSoul": 6 * 60, "elderRespawn": 6 * 60, "elderBuff": 150,   # 某隊第 4 條元素龍後 6 分鐘出遠古；遠古 buff 150 秒
    "baronFirstSpawn": 20 * 60, "baronRespawn": 6 * 60, "baronBuff": 180,  # 巴龍 20:00；重生 6 分鐘；Hand of Baron 180 秒（存活隊員）
    "grubsSpawn": 8 * 60, "grubsDespawn": 14 * 60 + 45,             # 三蟲 8:00 一次，14:45 消失（不重生）
    "heraldSpawn": 15 * 60, "heraldDespawn": 19 * 60 + 45,          # 預示者 15:00 一次，19:45 消失
    "inhibitorRespawn": 5 * 60, "nexusTurretRespawn": 3 * 60,       # 水晶 5 分鐘重生；主堡塔 3 分鐘以 40% 血量重生
}

_HUD_CACHE = {}
def hud_clock_reads(st0, t_end):
    """讀本局的計分列時鐘：回傳 [(畫面牆鐘 w, 遊戲時鐘 − w)]，依 w 排序。畫面牆鐘以格數 n 錨定；讀值有快取。"""
    out = []
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        run = os.path.basename(p)[9:-4]
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        off = np.array([ts(r["wall_utc"]) - int(r["n"]) for r in rows]); anchor = float(np.median(off[-600:]))
        for hp in sorted(glob.glob(f"{D}/snap/hud_{run}_*.png")):
            n = int(hp[-11:-4]); w = n + anchor
            if not (st0 - 30 <= w <= t_end + 90): continue
            if hp not in _HUD_CACHE: _HUD_CACHE[hp] = read_clock_safe(cv2.imread(hp), x0=920 - 500)
            c = _HUD_CACHE[hp]
            if c is not None: out.append((w, c - w))
    return sorted(out)

# ── 系列賽與 BP（esports-api 需要 x-api-key：只讀環境變數 LOL_API_KEY，不寫進任何檔案）──
import urllib.request
KEY = os.environ.get("LOL_API_KEY")
_API_CACHE = {}
def _get(url, key=False, ttl=30):
    now = time.time(); c = _API_CACHE.get(url)
    if c and now - c[0] < ttl: return c[1]
    req = urllib.request.Request(url, headers={"x-api-key": KEY} if key else {})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8")) if r.status == 200 else None
    _API_CACHE[url] = (now, d); return d

def live_matches():
    if not KEY: return []
    d = _get("https://esports-api.lolesports.com/persisted/gw/getLive?hl=en-US", key=True)
    return [e["match"]["id"] for e in (d or {}).get("data", {}).get("schedule", {}).get("events", []) or [] if e.get("match")]

def match_details(mid):
    d = _get(f"https://esports-api.lolesports.com/persisted/gw/getEventDetails?hl=en-US&id={mid}", key=True)
    return d["data"]["event"]["match"]

SCACHE = os.path.join(D, "series_cache.json")
def _scache():
    try: return json.load(open(SCACHE, encoding="utf-8"))
    except Exception: return {"games": {}, "matchOf": {}}

def game_picks(gid):
    """已開局小局的選角（feed gameMetadata，免金鑰）：依位置順序（上、野、中、下、輔），不是 BP 順序。"""
    d = _get(f"https://feed.lolesports.com/livestats/v1/window/{gid}", ttl=3600)
    if not d: return None
    m = d["gameMetadata"]; out = {}
    for side, k in (("B", "blueTeamMetadata"), ("R", "redTeamMetadata")):
        ps = sorted(m[k]["participantMetadata"], key=lambda p: p["participantId"])
        out[side] = {"teamId": m[k]["esportsTeamId"], "picks": [p["championId"] for p in ps], "roles": [p["role"] for p in ps]}
    return out

def players_snapshot(gid, ref_ts):
    """選手數據（feed，免金鑰）：window 的 participants（等級、KDA、CS、金錢、血量）＋ details 的 items（Data Dragon 裝備 id）。
    取 ref_ts（本服務已收到的最新 feed 時間戳）所在 10 秒窗口的最後一幀。participantId 1–5 藍方、6–10 紅方（8 局皆如此）。"""
    t = dt.datetime.fromtimestamp(int(ref_ts // 10 * 10), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    w = _get(f"https://feed.lolesports.com/livestats/v1/window/{gid}?startingTime={t}", ttl=5)
    d = _get(f"https://feed.lolesports.com/livestats/v1/details/{gid}?startingTime={t}", ttl=5)
    if not w or not w.get("frames"): return None
    meta = {p["participantId"]: (side, p) for side, k in (("B", "blueTeamMetadata"), ("R", "redTeamMetadata")) for p in w["gameMetadata"][k]["participantMetadata"]}
    wf = w["frames"][-1]; items = {}
    if d and d.get("frames"): items = {p["participantId"]: p["items"] for p in d["frames"][-1]["participants"]}
    out = {"B": [], "R": [], "asOf": wf["rfc460Timestamp"]}
    for team in ("blueTeam", "redTeam"):
        for p in wf[team]["participants"]:
            side, m = meta[p["participantId"]]
            out[side].append({"role": m["role"], "name": m["summonerName"].strip(), "champion": m["championId"], "level": p["level"],   # feed 有時名字帶尾端空白（"C9 Loki "）
                              "kills": p["kills"], "deaths": p["deaths"], "assists": p["assists"], "cs": p["creepScore"], "gold": p["totalGold"],
                              "hp": p["currentHealth"], "maxHp": p["maxHealth"], "items": items.get(p["participantId"])})
    return out

def series_and_draft(gid):
    """回傳 (series, draft, live_game_state)。gid=None 時找進行中的系列賽的下一局（BP 中）。"""
    if not KEY: return None, None, None
    cache = _scache(); mid = cache["matchOf"].get(gid) if gid else None
    if not mid and gid:                                        # feed 記錄器的 log 有 game → match 對應（服務中途重啟時用）
        import re
        try:
            for l in open(os.path.join(D, "feed.log"), encoding="utf-8"):
                m_ = re.search(rf"game {gid} .*match (\d+)", l)
                if m_: mid = m_.group(1)
        except FileNotFoundError: pass
    if not mid:
        for m_id in live_matches():
            md = match_details(m_id)
            if gid is None or any(g["id"] == gid for g in md["games"]): mid = m_id; break
    if not mid: return None, None, None
    md = match_details(mid); code = {t["id"]: t["code"] for t in md["teams"]}; wins = {t["id"]: (t.get("result") or {}).get("gameWins", 0) for t in md["teams"]}
    games = sorted(md["games"], key=lambda g: g["number"])
    if gid: cur = next(g for g in games if g["id"] == gid)
    else:
        cur = next((g for g in games if g["state"] == "inProgress"), None) or next((g for g in games if g["state"] == "unstarted"), None)
        if not cur: return None, None, None
    side = {("B" if t["side"] == "blue" else "R"): t["id"] for t in cur["teams"]}
    sides_source = "api"
    if cur["state"] != "completed" and feed_start(cur["id"]) is None:
        # 開打前 API 的藍紅方不可靠（Day 2：7 局中 5 局在 BP 中顛倒）；改看 BP 畫面中央的隊伍 logo（Day 1+2：1295/1295 張判對）
        try:
            bs = broadcast_sides(md, time.time())
            if bs: side = bs; sides_source = "broadcast"
            else: sides_source = "api_unconfirmed"
        except Exception as e:
            print(iso(time.time()), "BP 藍紅方判斷例外", repr(e), flush=True); sides_source = "api_unconfirmed"
    # 勝場：本局開始前的值。第一次看到本局（尚未結束）時記下 gameWins；之後一律用記下的值
    gc = cache["games"].get(cur["id"])
    if gc is None and cur["state"] != "completed":
        gc = {"match": mid, "winsAtStart": wins}; cache["games"][cur["id"]] = gc
    for g in games: cache["matchOf"][g["id"]] = mid
    json.dump(cache, open(SCACHE, "w", encoding="utf-8"))
    ws = gc["winsAtStart"] if gc else None
    series = {"bestOf": md["strategy"]["count"], "game": cur["number"], "matchId": mid, "sidesSource": sides_source,
              "teams": {s_: {"code": code.get(tid), "wins": (ws or {}).get(tid)} for s_, tid in side.items()}}
    if not ws: series["winsNote"] = "服務未在本局開始前看到系列賽，無法確定開局前勝場"
    def side_draft(gid_, sd, bans=None):
        pk = game_picks(gid_) if gid_ else None
        out = {}
        for s_, tid in sd.items():
            p = next((v for v in (pk or {}).values() if v["teamId"] == tid), None)
            out[s_] = {"team": code.get(tid), "bans": (bans or {}).get(s_) or [None] * 5, "picks": p["picks"] if p else [None] * 5}
        return out
    def game_bans(g):
        """該局的禁用（畫面辨識）：已開局者取開局前 20 分鐘的 BP 畫面做最終判定；BP 中者只回穩定出現的格子。"""
        try:
            st0 = feed_start(g["id"])
            if st0 is not None: return draft_bans(st0 + LAG - 1200, st0 + LAG, final=True)
            if g["state"] != "completed": return draft_bans(time.time() - 1200, time.time(), final=False)
        except Exception as e:
            print(iso(time.time()), "禁用辨識例外", repr(e), flush=True)
        return None
    current = {"game": cur["number"], **side_draft(cur["id"] if cur["state"] != "unstarted" else None, side, game_bans(cur)), "turn": None}
    earlier = []
    for g in games:
        if g["number"] < cur["number"] and g["state"] == "completed":
            sd = {("B" if t["side"] == "blue" else "R"): t["id"] for t in g["teams"]}
            earlier.append({"game": g["number"], **side_draft(g["id"], sd, game_bans(g))})
    draft = {"current": current, "earlier": earlier,
             "picksOrder": "role", "bansSupported": True, "bansOrder": "ban", "turnSupported": False}
    return series, draft, cur["state"]

def broadcast_sides(md, t_now):
    """BP 畫面中央的隊伍 logo（左＝藍方）判斷藍紅方：最近 120 秒的 BP 畫格多數決，至少 3 票。回傳 {"B": teamId, "R": teamId} 或 None。"""
    import draft_sides as DS, bans26 as BN
    from collections import Counter
    logos = {t["code"]: DS.fetch_logo(t["code"], t["image"]) for t in md["teams"]}
    id_of = {t["code"]: t["id"] for t in md["teams"]}
    votes = Counter()
    for fp in recent_off_frames(t_now - 120, t_now):
        im = cv2.imread(fp)
        if im is None or not BN.visible(im): continue
        r = DS.sides(im, logos)
        if r: votes[(r[0], r[1])] += 1
    if not votes or votes.most_common(1)[0][1] < 3: return None
    (bc, rc), _ = votes.most_common(1)[0]
    return {"B": id_of[bc], "R": id_of[rc]}

def recent_off_frames(t_from, t_to):
    """擷取存下的非比賽畫面（off_<RUN>_<n>.jpg）中，畫面時間落在 [t_from, t_to] 的檔案路徑（依時間排序）。"""
    out = []
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        run = os.path.basename(p)[9:-4]
        offs = glob.glob(f"{D}/snap/off_{run}_*.jpg")
        if not offs: continue
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows[-600:]]))
        out += [(int(fp[-11:-4]) + anchor, fp) for fp in offs if t_from <= int(fp[-11:-4]) + anchor <= t_to]
    return [fp for _, fp in sorted(out)]

def feed_start(gid):
    """本服務記錄到的該局 feed 第一個 in_game 時間戳（秒）；沒有記錄時回 None。"""
    p = f"{D}/feed_{gid}.jsonl"
    if not os.path.exists(p): return None
    for l in open(p, encoding="utf-8"):
        x = json.loads(l)
        if x["state"] == "in_game": return ts(x["ts"])
    return None

_BAN_CACHE = {}
def draft_bans(t_from, t_to, final):
    """從擷取存下的非比賽畫面（off_<RUN>_<n>.jpg，每 3 秒）辨識禁用。畫面牆鐘以各擷取段的格數 n 錨定。
    final=True：BP 列最後 3 張可見畫格加總，10 格一對一指派（Day 1 共 8 局 80/80）。
    final=False（BP 進行中）：某格在最近 3 張可見畫格的第一名相同且分數 >= 0.45 才回報，否則 null（避免把閃爍中的待選畫面報成禁用；此模式尚未驗證）。
    回傳 {"B": [禁用 1–5], "R": [禁用 1–5]}（依禁用順序；左側隊伍＝藍方）或 None。"""
    import bans26 as BN
    frames = []
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        run = os.path.basename(p)[9:-4]
        offs = sorted(glob.glob(f"{D}/snap/off_{run}_*.jpg"))
        if not offs: continue
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows]))
        for fp in offs:
            w = int(fp[-11:-4]) + anchor
            if t_from <= w <= t_to: frames.append((w, fp))
    vis = []
    for w, fp in sorted(frames):
        if fp not in _BAN_CACHE:
            im = cv2.imread(fp); _BAN_CACHE[fp] = BN.slot_scores_live(im) if im is not None and BN.visible(im) else None
        if _BAN_CACHE[fp] is not None: vis.append(_BAN_CACHE[fp])
    if not vis: return None
    if final:
        from scipy.optimize import linear_sum_assignment
        _, c = linear_sum_assignment(-sum(vis[-3:])); res = [BN.NAMES[i] for i in c]
    else:
        res = []
        for j in range(10):
            tops = [int(S[j].argmax()) for S in vis[-3:]]
            ok = len(vis) >= 3 and len(set(tops)) == 1 and all(S[j].max() >= 0.45 for S in vis[-3:])
            res.append(BN.NAMES[tops[-1]] if ok else None)
        dup = {n for n in res if n and res.count(n) > 1}
        res = [None if n in dup else n for n in res]
    return {"B": res[:5], "R": res[5:][::-1]}


_OBJ_CACHE = {}
_ANN_CACHE = {}; _HERALD_FOUND = {}
def broadcast_objectives(st0, t_end, lag):
    """轉播畫面上的物件資訊（tools/objective_box.py）：
    左上角計時框（obj_<RUN>_*.png，每 5 秒）→ 下一條龍屬性、上方野怪坑的下一隻（grubs/herald/baron）；
    計分列兩端（hud_<RUN>_*.png，每 5 秒）→ 兩隊三蟲數。
    畫面時間 w 換成遊戲時間：w − st0 − lag（未處理暫停）。回傳 dict 或 None。"""
    import objective_box as OB
    from collections import Counter
    reads = []
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        run = os.path.basename(p)[9:-4]
        objs = glob.glob(f"{D}/snap/obj_{run}_*.png")
        if not objs: continue
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows])); lay = {int(r["n"]): r["layout"] for r in rows}
        for fp in sorted(objs):
            n = int(fp[-11:-4]); w = n + anchor
            if not (st0 + lag <= w <= t_end + lag + 30) or lay.get(n) != "1": continue
            if fp not in _OBJ_CACHE:
                ob = OB.read(cv2.imread(fp)); hp = f"{D}/snap/hud_{run}_{n:07d}.png"
                gr = OB.read_grubs(cv2.imread(hp), x_off=-500) if os.path.exists(hp) else {"B": None, "R": None}
                _OBJ_CACHE[fp] = (ob["dragon"], ob["pit"], gr)
            reads.append((w - st0 - lag, *_OBJ_CACHE[fp]))
    if not reads: return None
    def mode_last(vals, k=3):
        v = [x for x in vals if x is not None][-k:]
        return Counter(v).most_common(1)[0][0] if v else None
    out = {"nextDragonElement": mode_last([r[1] for r in reads]),
           "voidgrubs": {s: mode_last([r[3][s] for r in reads]) for s in "BR"}, "pitNext": mode_last([r[2] for r in reads])}
    # 預示者：計時框上方那格由 herald 換成 baron 的時間 ≈ 預示者被打掉（19:45 前）或消失（19:45 後）
    seq = [(t, p) for t, _, p, _ in reads if p]
    seen_h = [t for t, p in seq if p == "herald"]
    after = [t for t, p in seq if p == "baron" and seen_h and t > seen_h[-1]]
    # 預示者歸屬：畫面上方公告「Blue/Red team has defeated the Rift Herald!」（ann_<RUN>_*.png，每秒）。
    # tools/herald_banner.py（軟文字遮罩）：Day 1+2 共 12 局留一局，門檻 0.75 時每局第一則 12/12、過門檻 100 張中藍紅方判錯 0；
    # 過門檻的「其他公告」只有「X team has summoned the Rift Herald」，隊伍與擊殺方相同。1080p 直播畫面僅以 1 局驗證（0.80–0.82）。
    herald_team = None
    if st0 in _HERALD_FOUND: herald_team, herald_at = _HERALD_FOUND[st0]
    else:
        try:
            import herald_banner as HBN
            TB = dict(np.load(os.path.join(ROOT, "assets", "herald_banner_templates.npz")))
            for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
                run = os.path.basename(p)[9:-4]; anns = glob.glob(f"{D}/snap/ann_{run}_*.png")
                if not anns: continue
                rows = list(csv.DictReader(open(p, encoding="utf-8")))
                anchor = float(np.median([ts(r["wall_utc"]) - int(r["n"]) for r in rows]))
                for fp in sorted(fp for fp in anns if 14 * 60 <= int(fp[-11:-4]) + anchor - st0 - lag <= 20 * 60 + 30):
                    if fp not in _ANN_CACHE:                      # 每張只算一次：文字遮罩太淡就記 None
                        m = HBN.mask(cv2.imread(fp))
                        _ANN_CACHE[fp] = None if m.mean() < 0.04 else max(((HBN.ncc_shift(m, t), k) for k, t in TB.items()))
                    hit = _ANN_CACHE[fp]
                    if hit and hit[0] >= 0.75:
                        herald_team = hit[1]; herald_at = int(int(fp[-11:-4]) + anchor - st0 - lag)
                        _HERALD_FOUND[st0] = (herald_team, herald_at); break
                if herald_team: break
        except Exception as e:
            print(iso(time.time()), "預示者公告辨識例外", repr(e), flush=True)
    if herald_team:
        out["herald"] = {"status": "taken", "at": gclock(herald_at), "sec": herald_at, "team": herald_team, "teamSource": "announcement"}
        return out
    if not seen_h: out["herald"] = {"status": "upcoming"}
    elif not after: out["herald"] = {"status": "alive_or_upcoming"}
    else:
        tk = int((seen_h[-1] + after[0]) / 2)
        out["herald"] = {"status": "taken" if tk < RULES["heraldDespawn"] - 5 else "taken_or_despawned", "at": gclock(tk), "sec": tk, "team": None,
                         "note": "時間為計時框換圖的前後兩次讀值中點（每 5 秒一張）；歸屬尚未支援"}
    return out

def load_feed(gid):
    return [json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl", encoding="utf-8")]

def current_game():
    """最近有更新、且仍在進行或剛結束（10 分鐘內）的小局。"""
    best = None
    for p in glob.glob(f"{D}/feed_*.jsonl"):
        m = os.path.getmtime(p)
        if best is None or m > best[0]: best = (m, p)
    if not best or time.time() - best[0] > 600: return None
    return os.path.basename(best[1])[5:-6]

def cv_rows(st0, t_end, lag=LAG):
    """把所有 clf_live_*.csv 中落在本局的逐秒判讀，轉成 trigger_sim 的時間軸（畫面時間以格數 n 錨定）。"""
    out = {}
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        off = np.array([ts(r["wall_utc"]) - int(r["n"]) for r in rows])
        for i, r in enumerate(rows):
            if "R_top_outer_A" not in r: continue                # 缺塔欄位的列（例如只有版面欄位）不用，避免整個塔命名失效
            w = int(r["n"]) + float(np.median(off[max(0, i - 300):i + 300])) - lag
            if not (st0 - 60 <= w <= t_end): continue
            out[int(round(w - st0)) + G0] = r
    return out

def tower_naming(gid, feed, finished, lag=LAG):
    ig = [x for x in feed if x["state"] == "in_game"]
    st0 = ts(ig[0]["ts"]); end = ts(feed[-1]["ts"])
    rows = cv_rows(st0, end + 10 if finished else time.time(), lag)
    if len(rows) < 30: return None, "畫面資料不足"
    sites = [k[:-2] for k in next(iter(rows.values())) if k.endswith("_A")]
    tmp = os.path.join(D, "svc"); os.makedirs(tmp, exist_ok=True)
    with open(f"{tmp}/clf.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["t"] + [f"{s}_{c}" for s in sites for c in "ADO"])
        for t in sorted(rows): w.writerow([t] + [rows[t][f"{s}_{c}"] for s in sites for c in "ADO"])
    with open(f"{tmp}/events.txt", "w") as f:
        prev = None
        for x in feed:
            cur = {"B_towers": x["B"]["t"], "R_towers": x["R"]["t"], "B_inhib": x["B"]["i"], "R_inhib": x["R"]["i"]}
            if prev:
                for k in cur:
                    if cur[k] > prev[k]: f.write(f'{x["ts"]} {k} {prev[k]}->{cur[k]}\n')
            prev = cur
    cmd = [sys.executable, os.path.join(HERE, "trigger_sim_clf4.py"), f"{tmp}/clf.csv", f"{tmp}/events.txt", str(G0), ig[0]["ts"], str(lag), "--thr", "0.7", "--live", "--json", f"{tmp}/named.json"]
    if finished: cmd.append("--complete")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode != 0: return None, (r.stderr or r.stdout or f"trigger_sim 結束碼 {r.returncode}")[-300:]
    named = json.load(open(f"{tmp}/named.json", encoding="utf-8"))
    out = {tm: sorted(({"site": s[2:], "gameTime": gclock(v["onset"]), "sec": v["onset"]} for s, v in named[tm].items()), key=lambda x: x["sec"]) for tm in "RB"}
    # 主堡塔：被摧毀 3 分鐘後重生（26.1 起 40% 血量）；倒數以命名的消失時間 + 規則推算，重生由畫面確認後從已摧毀清單移除
    out["nexusTurretsDown"] = [{"teamLost": tm, "site": x["site"], "respawnAt": gclock(x["sec"] + RULES["nexusTurretRespawn"])} for tm in "RB" for x in out[tm] if x["site"].startswith("nexus")]
    out["nexusRespawnsSeen"] = [{**r, "destroyedAt": gclock(r["destroyed"]), "respawnSeenAt": gclock(r["respawnSeen"])} for r in named.get("respawns", [])]
    return out, None

def objectives(feed, clock_of):
    """clock_of(feed 時間戳秒) -> 遊戲時鐘秒。"""
    ig = [x for x in feed if x["state"] == "in_game"]; st0 = ts(ig[0]["ts"]); last = feed[-1]
    ev = []; prev = None
    for x in feed:
        if prev:
            for side in "BR":
                for i in range(len(prev[side]["d"]), len(x[side]["d"])):
                    ev.append({"type": "dragon", "team": side, "element": x[side]["d"][i], "sec": round(clock_of(ts(x["ts"])))})
                for k, name in (("b", "baron"), ("i", "inhibitor"), ("t", "tower")):
                    for _ in range(x[side][k] - prev[side][k]): ev.append({"type": name, "team": side, "sec": round(clock_of(ts(x["ts"])))})
        prev = x
    for e in ev: e["gameTime"] = gclock(e["sec"])
    drag = {s: [d for d in last[s]["d"] if d != "elder"] for s in "BR"}
    # 前兩條龍屬性不同，第三條起固定為地圖屬性（8 局 feed 皆符合）；地圖屬性在 feed 中要到第三條龍被拿下才看得到
    order = [e["element"] for e in ev if e["type"] == "dragon" and e["element"] != "elder"]
    rift = order[2] if len(order) >= 3 else None
    soul = next(({"team": s, "element": rift} for s in "BR" if len(drag[s]) >= 4), None)
    now = clock_of(ts(last["ts"]))
    dk = [e for e in ev if e["type"] == "dragon"]; elem = [e for e in dk if e["element"] != "elder"]
    soul_ev = None; cnt = {"B": 0, "R": 0}
    for e in elem:
        cnt[e["team"]] += 1
        if cnt[e["team"]] == 4 and soul_ev is None: soul_ev = e
    if soul_ev:
        elders = [e for e in dk if e["element"] == "elder"]
        nxt = (elders[-1]["sec"] + RULES["elderRespawn"]) if elders else soul_ev["sec"] + RULES["elderAfterSoul"]
        next_dragon = {"kind": "elder", "spawnAt": gclock(nxt), "sec": nxt}
    else:
        nxt = (dk[-1]["sec"] + RULES["dragonRespawn"]) if dk else RULES["dragonFirstSpawn"]
        el = rift if len(elem) >= 2 and rift else None
        next_dragon = {"kind": "elemental", "element": el, "elementNote": None if el else ("地圖屬性已定但 feed 尚未揭露（要等第三條龍被拿或讀計分列）" if len(elem) == 2 else "隨機"), "spawnAt": gclock(nxt), "sec": nxt}
    bk = [e for e in ev if e["type"] == "baron"]
    bn = (bk[-1]["sec"] + RULES["baronRespawn"]) if bk else RULES["baronFirstSpawn"]
    buffs = []
    for e in bk:
        if e["sec"] + RULES["baronBuff"] > now: buffs.append({"buff": "baron", "team": e["team"], "until": gclock(e["sec"] + RULES["baronBuff"]), "untilSec": e["sec"] + RULES["baronBuff"]})
    for e in dk:
        if e["element"] == "elder" and e["sec"] + RULES["elderBuff"] > now: buffs.append({"buff": "elder", "team": e["team"], "until": gclock(e["sec"] + RULES["elderBuff"]), "untilSec": e["sec"] + RULES["elderBuff"]})
    inh = [{"teamLost": "R" if e["team"] == "B" else "B", "respawnAt": gclock(e["sec"] + RULES["inhibitorRespawn"])} for e in ev if e["type"] == "inhibitor" and e["sec"] + RULES["inhibitorRespawn"] > now]
    timers = {"nextDragon": next_dragon, "nextBaron": {"spawnAt": gclock(bn), "sec": bn}, "activeBuffs": buffs, "inhibitorsDown": inh,
              "grubsWindow": f'{gclock(RULES["grubsSpawn"])}–{gclock(RULES["grubsDespawn"])}', "heraldWindow": f'{gclock(RULES["heraldSpawn"])}–{gclock(RULES["heraldDespawn"])}',
              "note": "計時依規則表推算；下一條龍屬性、三蟲數、預示者狀態另由轉播畫面讀取（見 voidgrubs、herald、nextDragon.elementSource）"}
    return {
        "gameClock": gclock(now), "timers": timers,
        "dragons": {s: last[s]["d"] for s in "BR"},
        "riftElement": rift, "soul": soul,
        "elderKills": {s: last[s]["d"].count("elder") for s in "BR"},
        "barons": {s: last[s]["b"] for s in "BR"}, "inhibitors": {s: last[s]["i"] for s in "BR"},
        "towersDestroyedBy": {s: last[s]["t"] for s in "BR"}, "kills": {s: last[s]["k"] for s in "BR"}, "gold": {s: last[s]["g"] for s in "BR"},
        "events": ev,
    }

def update(gid=None):
    gid = gid or current_game()
    if not gid:
        # 沒有進行中的小局：若有進行中的系列賽（BP 中、局間），回 waiting 並附系列賽與 BP
        try: series, draft, _ = series_and_draft(None)
        except Exception as e: series, draft = None, None
        if series: return {"status": "waiting", "updated": iso(time.time()), "series": series, "draft": draft}
        return {"status": "idle", "updated": iso(time.time())}
    feed = load_feed(gid)
    if not any(x["state"] == "in_game" for x in feed):
        st = {"status": "waiting", "game": gid, "updated": iso(time.time())}
        try:
            series, draft, _ = series_and_draft(gid)
            if series: st["series"], st["draft"] = series, draft
        except Exception as e: st["seriesError"] = repr(e)[:200]
        return st
    finished = feed[-1]["state"] == "finished"
    st = {"status": "finished" if finished else "in_game", "game": gid, "updated": iso(time.time()), "videoLagSec": LAG}
    try:
        series, draft, _ = series_and_draft(gid)
        if series: st["series"], st["draft"] = series, draft
    except Exception as e:
        st["seriesError"] = repr(e)[:200]
    try:
        pl = players_snapshot(gid, ts(feed[-1]["ts"]))
        if pl: st["players"] = pl
    except Exception as e:
        st["playersError"] = repr(e)[:200]
    ig = [x for x in feed if x["state"] == "in_game"]; st0 = ts(ig[0]["ts"]); end = ts(feed[-1]["ts"])
    reads = hud_clock_reads(st0, end if finished else time.time())
    if len(reads) >= 5:
        offs = np.array([o for _, o in reads]); ws = np.array([w for w, _ in reads])
        # 直播落後 feed 的秒數：開局附近的讀值推回時鐘 0:00 的畫面時間，減去 feed 開局時間戳（以中位數抗誤讀）
        L = float(np.median([(-o) - st0 for o in offs]))       # 全局讀值中位數（只用不含 0、9 的讀值；Day 2 前 12 張的估法被誤讀拖到 −490 秒）
        def clock_of(t):
            v = t + L                                          # feed 事件在畫面上出現的時間
            i = np.argsort(np.abs(ws - v))[:5]                 # 取最接近的 5 個讀值的偏移中位數（抗誤讀，跟得上暫停）
            return v + float(np.median(offs[i]))
        st["clockSource"] = f"計分列時鐘（{len(reads)} 張）"; st["measuredLagSec"] = round(L, 1)
    else:
        clock_of = lambda t: t - st0
        st["clockSource"] = "feed 時間戳（未讀到計分列時鐘；與畫面時鐘可能差數十秒）"
    st.update(objectives(feed, clock_of))
    try:
        bo = broadcast_objectives(st0, end if finished else time.time(), st.get("measuredLagSec") or LAG)
        if bo:
            nd = st["timers"]["nextDragon"]
            if bo["nextDragonElement"]:
                if bo["nextDragonElement"] == "elder": nd["kind"] = "elder"
                else: nd["element"] = bo["nextDragonElement"]; nd["elementNote"] = None
                nd["elementSource"] = "broadcast"
            else: nd["elementSource"] = "rules"
            st["voidgrubs"] = bo["voidgrubs"]; st["herald"] = bo["herald"]; st["pitNext"] = bo["pitNext"]
    except Exception as e:
        st["broadcastError"] = repr(e)[:200]
    towers, err = tower_naming(gid, feed, finished, st.get("measuredLagSec") or LAG)   # 直播落後秒數依來源不同（YouTube 約 31、Twitch 約 46），有實測就用實測
    st["towersLost"] = towers                                  # 鍵為失去塔的隊伍（R/B），值為已命名的站點與影片顯示消失的遊戲時間
    if err: st["towersError"] = err
    return st

def log_new_events(old, new):
    if not new.get("game"): return
    seen = set()
    if old.get("game") == new["game"]:
        seen = {json.dumps(e, sort_keys=True) for e in old.get("events", [])}
        seen |= {f'tw|{tm}|{x["site"]}' for tm in "RB" for x in (old.get("towersLost") or {}).get(tm, [])}
    with open(f"{D}/events.jsonl", "a", encoding="utf-8") as f:
        for e in new.get("events", []):
            if json.dumps(e, sort_keys=True) not in seen: f.write(json.dumps({"game": new["game"], "at": new["updated"], **e}, ensure_ascii=False) + "\n")
        for tm in "RB":
            for x in (new.get("towersLost") or {}).get(tm, []):
                if f'tw|{tm}|{x["site"]}' not in seen: f.write(json.dumps({"game": new["game"], "at": new["updated"], "type": "tower_named", "teamLost": tm, **x}, ensure_ascii=False) + "\n")

WORLDS_LEAGUE = "98767975604431411"
_SCHED = {"at": 0, "data": None}
def schedule():
    """Worlds 2026 賽程（官方 getSchedule，5 分鐘快取）。比分放在 result 欄位，桌面工具可整欄隱藏（不爆雷）。"""
    if _SCHED["data"] and time.time() - _SCHED["at"] < 300: return _SCHED["data"]
    if not KEY: return {"error": "服務沒有 LOL_API_KEY，無法取得賽程"}
    evs, url, seen = [], f"https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=en-US&leagueId={WORLDS_LEAGUE}", set()
    for _ in range(4):                                         # 目前頁＋往後最多 3 頁（淘汰賽可能在下一頁）
        d = _get(url, key=True, ttl=300)["data"]["schedule"]
        for e in d["events"]:
            if e["startTime"] >= "2026-01-01" and e.get("match") and e["match"]["id"] not in seen: seen.add(e["match"]["id"]); evs.append(e)
        nxt = (d.get("pages") or {}).get("newer")
        if not nxt: break
        url = f"https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=en-US&leagueId={WORLDS_LEAGUE}&pageToken={nxt}"
    # 官方 getStandings 的 flags.isSpoiler：該場的對戰組合本身會洩露先前比賽結果（lolesports 官網用來防雷）
    spoiler = {}
    try:
        T = _get(f"https://esports-api.lolesports.com/persisted/gw/getTournamentsForLeague?hl=en-US&leagueId={WORLDS_LEAGUE}", key=True, ttl=3600)
        tid = next(t["id"] for t in T["data"]["leagues"][0]["tournaments"] if t["startDate"] >= "2026-01-01")
        S = _get(f"https://esports-api.lolesports.com/persisted/gw/getStandings?hl=en-US&tournamentId={tid}", key=True, ttl=300)
        for stg in S["data"]["standings"][0]["stages"]:
            for sec in stg["sections"]:
                for mm in sec.get("matches") or []: spoiler[mm["id"]] = "isSpoiler" in (mm.get("flags") or [])
    except Exception as ex:
        print(iso(time.time()), "賽程防雷標記例外", repr(ex), flush=True)
    out = []
    for e in sorted(evs, key=lambda e: e["startTime"]):
        m = e["match"]; teams = [{"code": t["code"], "name": t["name"], "image": t.get("image")} for t in m["teams"]]
        wins = [(t.get("result") or {}).get("gameWins") for t in m["teams"]]
        res = None
        if e["state"] in ("inProgress", "completed"):
            res = {"wins": wins, "winner": next((t["code"] for t in m["teams"] if (t.get("result") or {}).get("outcome") == "win"), None)}
        out.append({"matchId": m["id"], "start": e["startTime"], "state": e["state"], "stage": e.get("blockName"),
                    "bestOf": (m.get("strategy") or {}).get("count"), "teams": teams, "result": res,
                    "teamsSpoiler": spoiler.get(m["id"])})
    data = {"updated": iso(time.time()), "league": "Worlds 2026", "matches": out,
            "note": "result 為比分與勝方（不爆雷時整欄隱藏）；teamsSpoiler 為 true 時對戰組合本身會洩露先前結果（官方 isSpoiler 標記），不爆雷時隊伍也要藏；隊伍代碼 TBD 表示尚未確定"}
    _SCHED.update(at=time.time(), data=data); return data

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/schedule.json":
            try: body = json.dumps(schedule(), ensure_ascii=False).encode("utf-8")
            except Exception as e: body = json.dumps({"error": repr(e)[:200]}, ensure_ascii=False).encode("utf-8")
        elif path in ("/", "/state.json"):
            with LOCK: body = json.dumps(STATE, ensure_ascii=False).encode("utf-8")
        elif path == "/teams.json":
            fp = os.path.join(ROOT, "data", "archive", "teamsheet.json")      # tools/build_teamsheet.py 產生
            if not os.path.exists(fp): self.send_response(404); self.end_headers(); return
            body = open(fp, "rb").read()
        elif path.startswith("/history/"):
            # 歷史資料（tools/archive.py 產生）：/history/teams.json、/history/players.json、/history/games.json、/history/game/<gameId>.json
            A = os.path.join(ROOT, "data", "archive"); rel = path[len("/history/"):]
            if rel in ("teams.json", "players.json"): fp = os.path.join(A, rel)
            elif rel == "games.json":
                idx = []
                for p in glob.glob(os.path.join(A, "games", "*.json")):
                    r = json.load(open(p, encoding="utf-8"))
                    idx.append({k: r.get(k) for k in ("gameId", "matchId", "stage", "game", "bestOf", "start", "duration", "teams", "winner")})
                body = json.dumps({"games": sorted(idx, key=lambda x: x["start"])}, ensure_ascii=False).encode("utf-8"); fp = None
            elif rel.startswith("game/") and rel[5:-5].isdigit() and rel.endswith(".json"): fp = os.path.join(A, "games", rel[5:])
            else: fp = ""
            if fp is not None:
                if not fp or not os.path.exists(fp): self.send_response(404); self.end_headers(); return
                body = open(fp, "rb").read()
        else: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if ONCE:
        print(json.dumps(update(ONCE), ensure_ascii=False, indent=1)); sys.exit()
    threading.Thread(target=lambda: ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever(), daemon=True).start()
    while True:
        try:
            new = update()
            with LOCK: old = dict(STATE); STATE.clear(); STATE.update(new)
            log_new_events(old, new)
            # 一局結束（狀態第一次變成 finished）約 2 分鐘後，在背景重建歷史資料庫（tools/archive.py）
            if new.get("status") == "finished" and new.get("game") and new["game"] not in _ARCHIVED:
                _ARCHIVED.add(new["game"])
                threading.Timer(120, lambda: subprocess.Popen([sys.executable, os.path.join(HERE, "archive.py")], cwd=ROOT,
                                stdout=open(os.path.join(D, "archive.log"), "a"), stderr=subprocess.STDOUT)).start()
            # 狀態紀錄：內容有變（不計 updated）才附加一行，供事後重看「桌面工具每一刻會看到什麼」
            strip = lambda x: {k: v for k, v in x.items() if k != "updated"}
            if strip(new) != strip(old):
                with open(f"{D}/statelog.jsonl", "a", encoding="utf-8") as f: f.write(json.dumps(new, ensure_ascii=False) + "\n")
            if new.get("status") == "waiting":                 # 真實 waiting 樣本（BP 中／局間）：每局各存一份，給桌面工具對合約
                os.makedirs(f"{D}/samples", exist_ok=True)
                sp = f'{D}/samples/waiting_{new.get("series", {}).get("matchId", "x")}_g{new.get("series", {}).get("game", 0)}.json'
                if not os.path.exists(sp): json.dump(new, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            json.dump(new, open(f"{D}/state.json.tmp", "w", encoding="utf-8"), ensure_ascii=False); os.replace(f"{D}/state.json.tmp", f"{D}/state.json")
        except Exception as e:
            with LOCK: STATE["error"] = repr(e)
            print(iso(time.time()), "例外", repr(e), flush=True)
        time.sleep(5)
