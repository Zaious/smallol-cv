# Outpost 上每分鐘跑一次（systemd timer，見 tools/outpost/）：管線的程序「卡住」時自己重啟它。
# outpost_run.py 只在程序結束時重開；卡住的（還活著、但不再做事）它看不到——2026-10-24 第 1 場，
# feed 記錄程式從 17:24 起問一次被拒一次，什麼都沒寫，直到手動重啟。
# 檢查（都只結束那一個程序，outpost_run 10 秒後重開；同一個程序 10 分鐘內最多動一次）：
#   服務：state.json 超過 150 秒沒更新 → 結束 live_service（主迴圈每 5 秒寫一次）。
#         原本 60 秒：2026-10-24 17:13 瑞士輪第 2 天第 1 場 BP 一開始，選角辨識一口氣讀 20 分鐘的畫面、主迴圈慢了 65 秒，
#         被當成卡住重啟（快取讀回，BP 沒有空白）。真的卡住（第 1 天那種）是好幾分鐘起跳，150 秒仍抓得到。
#   feed：比賽中（state 為 in_game、不是 paused）而本局 feed 檔超過 5 分鐘沒長 → 結束 live_feed_log。
#   轉播：等待或比賽中，而轉播畫面（snap/）超過 3 分鐘沒有新檔 → 結束 live_watch。
# 每次動作寫一行到 data/live_worlds2026/watchdog.log。
# 用法：python tools/watchdog.py [--dry]
import glob, json, os, signal, subprocess, sys, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.environ.get("WATCHDOG_DIR") or os.path.join(ROOT, "data", "live_worlds2026")   # WATCHDOG_DIR: for tests
LOG = os.path.join(D, "watchdog.log")
MARK = os.path.join(D, "svc", "watchdog.json")         # 上次動過哪個程序、什麼時候
DRY = "--dry" in sys.argv
COOL = 600
now = time.time()


def say(m):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {m}"
    print(line)
    if not DRY:
        with open(LOG, "a", encoding="utf-8") as f: f.write(line + "\n")


def age(p):
    try: return now - os.path.getmtime(p)
    except OSError: return None


def newest(pattern):
    ps = glob.glob(pattern)
    return max(ps, key=os.path.getmtime) if ps else None


def pids(script):
    """本服務（outpost_run 的子程序）中執行該腳本的程序。"""
    out = subprocess.run(["pgrep", "-f", f"tools/{script}"], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]


def restart(name, script, why):
    try: marks = json.load(open(MARK, encoding="utf-8"))
    except Exception: marks = {}
    if now - marks.get(name, 0) < COOL:
        say(f"{name}：{why}，但 {COOL // 60} 分鐘內動過，先不動"); return
    ps = pids(script)
    if not ps: say(f"{name}：{why}，但找不到程序"); return
    say(f"{name}：{why} → 結束 {ps}{'（試跑，不結束）' if DRY else ''}")
    if DRY: return
    for p in ps:
        try: os.kill(p, signal.SIGTERM)
        except ProcessLookupError: pass
    marks[name] = now
    os.makedirs(os.path.dirname(MARK), exist_ok=True)
    json.dump(marks, open(MARK, "w", encoding="utf-8"))


def main():
    st_path = os.path.join(D, "state.json")
    a = age(st_path)
    if a is not None and a > 150: restart("service", "live_service.py", f"state.json {a:.0f} 秒沒更新")
    try: st = json.load(open(st_path, encoding="utf-8"))
    except Exception: st = {}
    status = st.get("status")
    if status == "in_game" and not st.get("paused") and st.get("game"):
        fa = age(os.path.join(D, f"feed_{st['game']}.jsonl"))
        if fa is not None and fa > 300: restart("feed", "live_feed_log.mjs", f"比賽中本局 feed {fa:.0f} 秒沒長")
    if status in ("waiting", "in_game"):
        sa = age(newest(os.path.join(D, "snap", "*")) or "")
        if sa is not None and sa > 180: restart("watch", "live_watch.py", f"{status} 中轉播畫面 {sa:.0f} 秒沒有新檔")


if __name__ == "__main__":
    main()
