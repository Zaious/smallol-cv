# 事後補禁用：歷史檔裡沒有禁用、但伺服器還留著該局 BP 畫面（snap/off_*）的局，用最終判定（10 格一對一指派）重讀一次，
# 寫到 data/archive/cv_bans_backfill.json，由 tools/archive.py 讀。起因：2026-10-18 伺服器缺 scipy，那天的局開打後禁用全部失敗。
# 用法：python tools/bans_backfill.py   （直播延遲取環境變數 VIDEO_LAG，與服務相同）
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.argv = [sys.argv[0]]; sys.path.insert(0, HERE)
import live_service as svc
OUT = os.path.join(ROOT, "data", "archive"); P = os.path.join(OUT, "cv_bans_backfill.json")
svc.D = os.path.join(ROOT, "data", "live_worlds2026")
done = json.load(open(P, encoding="utf-8")) if os.path.exists(P) else {}
for f in sorted(glob.glob(os.path.join(OUT, "games", "*.json"))):
    r = json.load(open(f, encoding="utf-8")); gid = r["gameId"]
    if r.get("bans") or gid in done: continue
    st0 = svc.feed_start(gid)
    if st0 is None: print(gid, "沒有 feed 記錄"); continue
    b = svc.draft_bans(st0 + svc.LAG - 1200, st0 + svc.LAG, final=True)
    print(gid, r["teams"], "->", b)
    if b and all(b[s] and all(b[s]) for s in "BR"): done[gid] = b
json.dump(done, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("寫入", len(done), "局")
