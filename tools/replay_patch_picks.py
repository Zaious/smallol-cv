# 重播資料加上 BP 中的即時選角（v0.9 之前錄的 statelog 沒有）：BP 期間每 3 秒插一筆，picks／hovering 用 draft_picks 重新辨識；
# 預示者歸屬依 Leaguepedia 正解修正（錄的時候是舊版辨識，判錯）。只給 tools/replay_service.py --log 用，不改原始 statelog。
# 用法：python tools/replay_patch_picks.py <from ISO> <to ISO> <輸出 jsonl> [預示者正解 B|R]
import sys, os, json, copy
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import live_service as L, draft_picks as DP
t0, t1, out = L.ts(sys.argv[1]), L.ts(sys.argv[2]), sys.argv[3]
herald_team = sys.argv[4] if len(sys.argv) > 4 else None
R = DP.Reader()
for w, fp in L.recent_off_frames_t(t0 - 1200, t1):
    im = cv2.imread(fp)
    if im is not None: L._PICK_CARDS[fp] = R.cards(im) if R.overlay(im) >= 0.6 else None
rows = [json.loads(l) for l in open(os.path.join(L.D, "statelog.jsonl"), encoding="utf-8")]
rows = [(L.ts(r["updated"]), r) for r in rows if t0 <= L.ts(r["updated"]) <= t1]
res = []; k = 0; t = rows[0][0]
while t <= t1:
    while k + 1 < len(rows) and rows[k + 1][0] <= t: k += 1
    r = copy.deepcopy(rows[k][1]); r["updated"] = L.iso(t)
    if r.get("status") == "waiting" and r.get("draft"):
        lp = L.draft_picks_live(t - 1200, t)
        if lp:
            for s in "BR":
                r["draft"]["current"][s].update(picks=lp[s]["picks"], hovering=lp[s]["hovering"], picksSource="broadcast")
    elif r.get("draft") and r.get("game"):                  # 比賽中：錄的時候有 bug（API 狀態落後＋空結果快取），本局 picks 是 null；用 feed 補上
        pk = L.game_picks(r["game"])
        for s in "BR":
            if pk: r["draft"]["current"][s]["picks"] = pk[s]["picks"]
            r["draft"]["current"][s]["picksSource"] = "feed"
    h = r.get("herald") or (r.get("broadcast") or {}).get("herald")
    if herald_team and h and h.get("team"): h["team"] = herald_team
    res.append(r); t += 3 if r.get("status") == "waiting" else 10
with open(out, "w", encoding="utf-8") as f:
    for r in res: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("寫出", len(res), "筆", out)
