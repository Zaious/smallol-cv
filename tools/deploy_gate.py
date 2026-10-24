# 部署閘門：BP 進行中、或下一場 10 分鐘內開始時，不准重啟服務（結束碼 2）。
# 起因：2026-10-24 18:14 第 2 場 BP 中重啟資料服務，BP 要重讀 20 分鐘的畫面，空白了約 5 分鐘。
# 比賽中（in_game）可以：選角改由官方 feed 提供，重啟只空約 1 分鐘。
# 用法：python tools/deploy_gate.py   （0=可以；2=現在不行，原因印在 stderr）
#       tools/safe_restart.sh 會先過這關
import calendar, json, os, sys, time, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(ROOT, "data", "live_worlds2026")
PORT = int(os.environ.get("PORT", "8081"))


def no(why):
    print(f"✗ 部署閘門：{why}", file=sys.stderr); sys.exit(2)


try: st = json.load(open(os.path.join(D, "state.json"), encoding="utf-8"))
except Exception: st = {}
cur = (st.get("draft") or {}).get("current") or {}
in_bp = st.get("status") == "waiting" and any(
    x for s in "BR" for k in ("bans", "picks", "hovering") for x in ((cur.get(s) or {}).get(k) or []))
if in_bp: no("BP 進行中（已有禁選），等開打後再部署")

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/schedule.json", timeout=10) as r: sched = json.load(r)
    soon = [m for m in sched.get("matches", []) if m.get("state") == "unstarted"
            and 0 <= calendar.timegm(time.strptime(m["start"][:19], "%Y-%m-%dT%H:%M:%S")) - time.time() <= 600]
    if soon: no(f"下一場 {soon[0]['start']} 10 分鐘內開始")
except SystemExit: raise
except Exception as e: print(f"! 部署閘門：賽程讀不到（{e!r}），只依目前狀態判斷", file=sys.stderr)
print(f"✓ 部署閘門：可以（目前 {st.get('status')}）")
