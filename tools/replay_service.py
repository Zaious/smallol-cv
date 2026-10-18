# 模擬比賽：把服務錄下的 statelog.jsonl（桌面工具每一刻實際會看到的 state.json）照時間重放，給桌面工具調手感用。
# /state.json 依重放時鐘回傳當下那一筆（updated 改成現在，免得被當成過期）；其他路徑（schedule、history、teams）轉給正式服務。
# 用法：python tools/replay_service.py [--from 2026-10-17T17:49] [--to 2026-10-17T21:30] [--speed 1] [--skip 0] [--port 8788] [--loop]
#   --list：列出錄到的時段與每局的開始時間
#   桌面工具：設定 →「資料來源」改成 http://127.0.0.1:8788/state.json；看完改回 http://127.0.0.1:8787/state.json
import sys, os, json, time, argparse, datetime as dt, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
D = os.path.join(os.path.dirname(__file__), "..", "data", "live_worlds2026")
LIVE = "http://127.0.0.1:8787"
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="t0", default="2026-10-17T17:49"); ap.add_argument("--to", dest="t1", default="2026-10-17T21:30")
ap.add_argument("--speed", type=float, default=1.0); ap.add_argument("--skip", type=float, default=0, help="從開頭跳過幾分鐘（錄影時間）")
ap.add_argument("--port", type=int, default=8788); ap.add_argument("--loop", action="store_true"); ap.add_argument("--list", action="store_true")
ap.add_argument("--log", default=os.path.join(D, "statelog.jsonl"), help="改播 tools/replay_patch_picks.py 補過的紀錄")
a = ap.parse_args()

rows = []
for l in open(a.log, encoding="utf-8"):
    try: r = json.loads(l)
    except ValueError: continue
    rows.append((ts(r["updated"]), r))
if a.list:
    prev = None
    for t, r in rows:
        k = (r["status"], r.get("game"))
        if k != prev: print(iso(t), r["status"], r.get("game") or "", (r.get("series") or {}).get("game") or ""); prev = k
    sys.exit()
T0, T1 = ts(a.t0 + ("" if a.t0.endswith("Z") else "Z")), ts(a.t1 + ("" if a.t1.endswith("Z") else "Z"))
rows = [x for x in rows if T0 <= x[0] <= T1]
if not rows: sys.exit("這段時間沒有紀錄；先用 --list 看有哪些時段")
START = time.time()

def current():
    span = rows[-1][0] - rows[0][0]
    el = (time.time() - START) * a.speed + a.skip * 60
    if a.loop and span > 0: el %= span
    t = rows[0][0] + el; cur = rows[0][1]
    for rt, r in rows:
        if rt > t: break
        cur = r
    out = dict(cur); out["updated"] = iso(time.time()); out["replay"] = {"recordedAt": cur["updated"], "speed": a.speed}
    return out

class H(BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path.split("?")[0] == "/state.json":
            return self.send(200, json.dumps(current(), ensure_ascii=False).encode("utf-8"))
        try:
            with urllib.request.urlopen(LIVE + self.path, timeout=10) as r: self.send(r.status, r.read(), r.headers.get("Content-Type", "application/json"))
        except urllib.error.HTTPError as e: self.send(e.code, e.read())
        except Exception as e: self.send(502, json.dumps({"error": f"正式服務沒有回應：{e}"}).encode("utf-8"))

print(f"重放 {iso(rows[0][0])} → {iso(rows[-1][0])}，{len(rows)} 筆，速度 ×{a.speed}，跳過 {a.skip} 分鐘；http://127.0.0.1:{a.port}/state.json", flush=True)
ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
