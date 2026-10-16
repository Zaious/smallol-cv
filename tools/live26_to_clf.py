# 2026 即時逐秒判讀（clf_live_<RUN>.csv）→ trigger_sim 用的逐秒 CSV ＋ feed 事件檔。時間軸同 snap26_to_clf（t = 牆鐘 − LAG − feed 開局時間戳 + G0）。
# 用法：python tools/live26_to_clf.py <clf_live_RUN.csv> <gameId>
import csv, json, sys, datetime as dt
LAG, G0 = 31.0, 1000
src, gid = sys.argv[1], sys.argv[2]; D = "data/live_worlds2026"
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
r = [json.loads(l) for l in open(f"{D}/feed_{gid}.jsonl")]; ig = [x for x in r if x["state"] == "in_game"]
st0 = ts(ig[0]["ts"]); end = ts(r[-1]["ts"])
with open(f"data/feed_events_w26_{gid}.txt", "w") as f:
    prev = None
    for x in r:
        cur = {"B_towers": x["B"]["t"], "R_towers": x["R"]["t"], "B_inhib": x["B"]["i"], "R_inhib": x["R"]["i"]}
        if prev:
            for k in cur:
                if cur[k] > prev[k]: f.write(f'{x["ts"]} {k} {prev[k]}->{cur[k]}\n')
        prev = cur
rows = list(csv.DictReader(open(src, encoding="utf-8")))
sites = [k[:-2] for k in rows[0] if k.endswith("_A")]
# 直播以 HLS 分段送達，數秒畫面會同時到，牆鐘不等於畫面時間；畫面時間用格數 n（1 fps），以「牆鐘 − n」的滾動中位數錨定
import numpy as np
off = np.array([ts(row["wall_utc"]) - int(row["n"]) for row in rows])
anchor = [float(np.median(off[max(0, i - 300):i + 300])) for i in range(len(rows))]
out = {}
for i, row in enumerate(rows):
    w = int(row["n"]) + anchor[i]
    if not (st0 - 60 <= w - LAG <= end + 60): continue
    t = int(round(w - LAG - st0)) + G0
    rec = {"t": t}
    for s in sites: rec[f"{s}_A"], rec[f"{s}_D"], rec[f"{s}_O"] = row[f"{s}_A"], row[f"{s}_D"], row[f"{s}_O"]
    out[t] = rec
cols = ["t"] + [f"{s}_{c}" for s in sites for c in "ADO"]
with open(f"data/clf_w26_{gid}.csv", "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(out[t] for t in sorted(out))
print(gid, "start", ig[0]["ts"], "rows", len(out), "visible", sum(1 for row in rows if row["layout"] == "1" and st0 - 60 <= ts(row["wall_utc"]) - LAG <= end + 60))
