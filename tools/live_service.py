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
STATE = {"status": "starting"}; LOCK = threading.Lock()
sys.path.insert(0, HERE)
from hud_clock import read_clock
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
            if hp not in _HUD_CACHE: _HUD_CACHE[hp] = read_clock(cv2.imread(hp), x0=920 - 500)
            c = _HUD_CACHE[hp]
            if c is not None: out.append((w, c - w))
    return sorted(out)

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

def cv_rows(st0, t_end):
    """把所有 clf_live_*.csv 中落在本局的逐秒判讀，轉成 trigger_sim 的時間軸（畫面時間以格數 n 錨定）。"""
    out = {}
    for p in sorted(glob.glob(f"{D}/clf_live_*.csv")):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows: continue
        off = np.array([ts(r["wall_utc"]) - int(r["n"]) for r in rows])
        for i, r in enumerate(rows):
            w = int(r["n"]) + float(np.median(off[max(0, i - 300):i + 300])) - LAG
            if not (st0 - 60 <= w <= t_end): continue
            out[int(round(w - st0)) + G0] = r
    return out

def tower_naming(gid, feed, finished):
    ig = [x for x in feed if x["state"] == "in_game"]
    st0 = ts(ig[0]["ts"]); end = ts(feed[-1]["ts"])
    rows = cv_rows(st0, end + 10 if finished else time.time())
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
    cmd = [sys.executable, os.path.join(HERE, "trigger_sim_clf4.py"), f"{tmp}/clf.csv", f"{tmp}/events.txt", str(G0), ig[0]["ts"], str(LAG), "--thr", "0.7", "--live", "--json", f"{tmp}/named.json"]
    if finished: cmd.append("--complete")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode != 0: return None, r.stderr[-300:]
    named = json.load(open(f"{tmp}/named.json", encoding="utf-8"))
    return {tm: sorted(({"site": s[2:], "gameTime": gclock(v["onset"]), "sec": v["onset"]} for s, v in named[tm].items()), key=lambda x: x["sec"]) for tm in "RB"}, None

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
              "note": "計時依規則表推算；三蟲與預示者是否被擊殺、由誰擊殺，feed 不提供，尚未從畫面讀取"}
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
    if not gid: return {"status": "idle", "updated": iso(time.time())}
    feed = load_feed(gid)
    if not any(x["state"] == "in_game" for x in feed): return {"status": "waiting", "game": gid, "updated": iso(time.time())}
    finished = feed[-1]["state"] == "finished"
    st = {"status": "finished" if finished else "in_game", "game": gid, "updated": iso(time.time()), "videoLagSec": LAG}
    ig = [x for x in feed if x["state"] == "in_game"]; st0 = ts(ig[0]["ts"]); end = ts(feed[-1]["ts"])
    reads = hud_clock_reads(st0, end if finished else time.time())
    if len(reads) >= 5:
        offs = np.array([o for _, o in reads]); ws = np.array([w for w, _ in reads])
        # 直播落後 feed 的秒數：開局附近的讀值推回時鐘 0:00 的畫面時間，減去 feed 開局時間戳（以中位數抗誤讀）
        L = float(np.median([(-o) - st0 for o in offs[:12]]))
        def clock_of(t):
            v = t + L                                          # feed 事件在畫面上出現的時間
            i = np.argsort(np.abs(ws - v))[:5]                 # 取最接近的 5 個讀值的偏移中位數（抗誤讀，跟得上暫停）
            return v + float(np.median(offs[i]))
        st["clockSource"] = f"計分列時鐘（{len(reads)} 張）"; st["measuredLagSec"] = round(L, 1)
    else:
        clock_of = lambda t: t - st0
        st["clockSource"] = "feed 時間戳（未讀到計分列時鐘；與畫面時鐘可能差數十秒）"
    st.update(objectives(feed, clock_of))
    towers, err = tower_naming(gid, feed, finished)
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

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/state.json"): self.send_response(404); self.end_headers(); return
        with LOCK: body = json.dumps(STATE, ensure_ascii=False).encode("utf-8")
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
            json.dump(new, open(f"{D}/state.json.tmp", "w", encoding="utf-8"), ensure_ascii=False); os.replace(f"{D}/state.json.tmp", f"{D}/state.json")
        except Exception as e:
            with LOCK: STATE["error"] = repr(e)
            print(iso(time.time()), "例外", repr(e), flush=True)
        time.sleep(5)
