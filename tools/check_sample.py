# 樣本檢查閘：docs/samples/ 的 state 樣本在 commit 前必須通過（exit 0）。
# 起因：2026-10-16 樣本兩度產壞（一次空檔、一次缺 towersLost），桌面工具照著畫就會錯。
# 用法：python tools/check_sample.py <state.json> [...]
import json, sys
REQ_FINISHED = ["status", "game", "gameClock", "timers", "dragons", "barons", "inhibitors", "towersDestroyedBy", "kills", "gold",
                "events", "towersLost", "series", "draft", "players"]
bad = 0
for p in sys.argv[1:]:
    errs = []
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception as e: print(f"FAIL {p}: 不是合法 JSON（{e!r}）"); bad += 1; continue
    if d.get("status") in ("in_game", "finished"):
        errs += [f"缺 {k}" for k in REQ_FINISHED if not d.get(k)]
        tl = d.get("towersLost") or {}
        if isinstance(tl, dict):
            named = len(tl.get("B") or []) + len(tl.get("R") or [])
            feed = sum((d.get("towersDestroyedBy") or {}).values())
            if feed and not named: errs.append(f"feed 有 {feed} 座塔倒了，但 towersLost 一座都沒有")
        if d.get("towersError"): errs.append(f"towersError: {d['towersError']}")
        pl = d.get("players") or {}
        if pl and (len(pl.get("B") or []) != 5 or len(pl.get("R") or []) != 5): errs.append("players 不是每隊 5 人")
        dr = d.get("draft") or {}
        if dr.get("bansSupported") and not any((dr.get("current") or {}).get(s, {}).get("bans", [None])[0] for s in "BR"):
            errs.append("bansSupported 為 true，但本局兩隊禁用都是空的（樣本應帶禁用）")
    elif d.get("status") == "waiting":
        errs += [f"缺 {k}" for k in ("series", "draft") if not d.get(k)]
    else:
        errs.append(f"status 不是樣本該有的值：{d.get('status')}")
    if errs: print(f"FAIL {p}:"); [print("  -", e) for e in errs]; bad += 1
    else: print(f"OK   {p}")
sys.exit(1 if bad else 0)
