#!/bin/bash
# 重啟資料服務的一個程序，先過部署閘門（BP 中、開賽前 10 分鐘不准）。outpost_run 會在 10 秒後把它重開。
#   tools/safe_restart.sh service|feed|watch
# 要硬來（例如服務已經壞了）：FORCE=1 tools/safe_restart.sh service
set -e
cd "$(dirname "$0")/.."
case "$1" in
  service) pat="tools/live_service.py" ;;
  feed)    pat="tools/live_feed_log.mjs" ;;
  watch)   pat="tools/live_watch.py" ;;
  *) echo "用法：$0 service|feed|watch" >&2; exit 1 ;;
esac
if [ "${FORCE:-}" != "1" ]; then venv/bin/python tools/deploy_gate.py; fi
main=$(systemctl show smallol -p MainPID --value)
pid=$(ps -o pid=,args= --ppid "$main" | awk -v p="$pat" 'index($0, p) {print $1}')
[ -n "$pid" ] || { echo "找不到 $1 的程序" >&2; exit 1; }
kill "$pid"
echo "已結束 $1（$pid），約 10 秒後由 outpost_run 重開"
