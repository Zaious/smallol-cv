# Leaguepedia（lol.fandom.com）Cargo 查詢，含限流退避。結果存 data/lp/<name>.json。
# 用法（模組）：from lp_fetch import cargo, fields
#   fields("Players") → 該表欄位；cargo(name, tables=..., fields=..., where=..., ...) → 存檔並回傳列
# Leaguepedia 對同一 IP 限流很嚴：每次請求間隔至少 6 秒，被限流時退避 2、4、6… 分鐘，最多 8 次。
import json, os, time, urllib.parse, urllib.request
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "lp"); os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "DesktopLOL-probe/0.1 (personal research)"}
_last = [0.0]

def _call(params):
    for i in range(1, 9):
        wait = float(os.environ.get("LP_GAP", "6")) - (time.time() - _last[0])   # 請求間隔（秒），限流嚴重時以 LP_GAP 加大
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        url = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        if (d.get("error") or {}).get("code") == "ratelimited":
            print(f"限流，第 {i} 次，等 {120 * i} 秒", flush=True); time.sleep(120 * i); continue
        return d
    raise RuntimeError("Leaguepedia 限流 8 次仍失敗")

def fields(table):
    d = _call({"action": "cargofields", "table": table})
    if "error" in d: raise RuntimeError(d["error"])
    f = d["cargofields"]; json.dump(f, open(os.path.join(OUT, f"fields_{table}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return f

def cargo(name, **q):
    """分頁取完（每頁 500）。"""
    rows, off = [], 0
    while True:
        d = _call({"action": "cargoquery", "limit": 500, "offset": off, **q})
        if "error" in d: raise RuntimeError(d["error"])
        page = [r["title"] for r in d.get("cargoquery", [])]; rows += page
        if len(page) < 500: break
        off += 500
    json.dump(rows, open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rows

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for t in ("Players", "TournamentRosters", "TournamentPlayers", "TournamentResults", "Tournaments"):
        try: f = fields(t); print(t, "欄位", list(f.keys()), flush=True)
        except Exception as e: print(t, "失敗", e, flush=True)
    rows = cargo("worlds2026_overview", tables="ScoreboardGames", fields="OverviewPage,Tournament", where="DateTime_UTC >= '2026-10-15'", group_by="OverviewPage")
    print("世界賽頁面", rows, flush=True)
