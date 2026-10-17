# feed 補抓：live_feed_log 只從「開始追蹤時的 now−45 秒」往後記，若晚開始追蹤就漏掉開局片段（Day 2 第 3、5 局）。
# 本工具以二分搜尋找出該局第一個有幀的 10 秒窗口，把開局到現有記錄第一幀之間的幀補進 feed_<gameId>.jsonl（依時間排序重寫）。
# 用法：python tools/feed_backfill.py <dir> <gameId> [...]
import json, os, sys, time, urllib.request, urllib.error, datetime as dt
D = sys.argv[1]
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def window(gid, t):
    try:
        r = urllib.request.urlopen(f"https://feed.lolesports.com/livestats/v1/window/{gid}?startingTime={iso(t)}", timeout=15)
        if r.status != 200: return []
        return json.loads(r.read() or b"{}").get("frames", [])
    except urllib.error.HTTPError: return []

def row(gid, f, wall):
    b, r = f["blueTeam"], f["redTeam"]
    return {"wall": wall, "game": gid, "ts": f["rfc460Timestamp"], "state": f["gameState"], "backfill": True,
            "B": {"t": b["towers"], "i": b["inhibitors"], "b": b["barons"], "d": b["dragons"], "k": b["totalKills"], "g": b["totalGold"]},
            "R": {"t": r["towers"], "i": r["inhibitors"], "b": r["barons"], "d": r["dragons"], "k": r["totalKills"], "g": r["totalGold"]}}

for gid in sys.argv[2:]:
    p = f"{D}/feed_{gid}.jsonl"
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    first = min(ts(x["ts"]) for x in rows)
    lo, hi = (first - 3600) // 10 * 10, first // 10 * 10           # lo：無幀；hi：有幀
    if window(gid, lo): print(gid, "一小時前就有幀，略過"); continue
    while hi - lo > 10:
        mid = (lo + hi) // 2 // 10 * 10
        if window(gid, mid): hi = mid
        else: lo = mid
    add = []; t = hi; wall = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    while t < first:
        for f in window(gid, t):
            if ts(f["rfc460Timestamp"]) < first: add.append(row(gid, f, wall))
        t += 10; time.sleep(0.2)
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]  # 重讀：補抓期間記錄器可能又附加了新幀
    seen = set(); merged = []
    for x in sorted(add + rows, key=lambda x: x["ts"]):
        if x["ts"] in seen: continue
        seen.add(x["ts"]); merged.append(x)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        for x in merged: f.write(json.dumps(x) + "\n")
    os.replace(p + ".tmp", p)
    ig = [x for x in merged if x["state"] == "in_game"]
    print(gid, f"補 {len(add)} 幀；第一個 in_game 由 {iso(first)} 提前到 {ig[0]['ts'][:19]}Z（金錢 {ig[0]['B']['g']}/{ig[0]['R']['g']}）")
