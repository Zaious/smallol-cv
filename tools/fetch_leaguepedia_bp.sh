#!/usr/bin/env bash
# 取 Leaguepedia 2025 Worlds 決賽 KT vs T1 的計分表（BP 紀錄）。被限流時退避重試。
# 輸出：data/worlds2025_final_scoreboard.json（本機資料，不提交）
set -u
OUT=data/worlds2025_final_scoreboard.json
for i in $(seq 1 12); do
  curl -s -G "https://lol.fandom.com/api.php" \
    --data-urlencode "action=cargoquery" \
    --data-urlencode "tables=ScoreboardGames" \
    --data-urlencode "fields=GameId,Team1,Team2,Winner,Team1Bans,Team2Bans,Team1Picks,Team2Picks,N_GameInMatch,MatchId,DateTime_UTC" \
    --data-urlencode "where=DateTime_UTC >= '2025-11-08' AND DateTime_UTC < '2025-11-10' AND (Team1 LIKE '%KT%' OR Team2 LIKE '%KT%')" \
    --data-urlencode "limit=10" --data-urlencode "format=json" \
    -H "User-Agent: DesktopLOL-probe/0.1 (personal research; contact: zaious.design@gmail.com)" > "$OUT.tmp"
  if ! grep -q '"error"' "$OUT.tmp"; then mv "$OUT.tmp" "$OUT"; echo "OK attempt $i"; exit 0; fi
  echo "ratelimited attempt $i"; sleep $((120 * i))
done
echo "FAILED after 8 attempts"; exit 1
