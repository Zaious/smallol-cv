# Stream CV 服務輸出合約（v0，2026-10-16）

桌面工具（DesktopLOL）讀這份資料。服務由 `tools/live_service.py` 產生，每 5 秒更新一次。

- HTTP：`GET http://127.0.0.1:8787/state.json`（日後上 VPS 改成對外網址；欄位不變）
- 檔案：`data/live_worlds2026/state.json`（目前狀態）、`data/live_worlds2026/events.jsonl`（新事件逐行附加）
- 範例：`docs/samples/state_finished_game.json`（Worlds 2026 Play-In，MVK vs FUR 第 3 局結束時的真實輸出）

## 慣例

- 隊伍一律用 `B`（藍方，小地圖左下）與 `R`（紅方，小地圖右上），不是戰隊名。戰隊名與 logo 由桌面工具從官方 API 取得。
- 遊戲時間：`gameTime` / `spawnAt` / `until` 等字串為 `M:SS`；同名的 `sec` 為秒數，方便排序與倒數。
- `status`：`idle`（無進行中的小局）、`waiting`、`in_game`、`finished`。`idle` 時只有 `status` 與 `updated`。
- 資料來源標示：龍、巴龍、水晶、擊殺、金錢來自官方 feed（準確）；「哪一座塔」來自畫面辨識（CV）；計時欄位是依規則表推算。

## 欄位

| 欄位 | 型別 | 來源 | 說明 |
| --- | --- | --- | --- |
| `game` | string | feed | 官方小局 ID |
| `updated` | ISO 時間 | 服務 | 本次更新時間 |
| `gameClock` | `M:SS` | feed＋計分列時鐘 | 目前遊戲時間 |
| `clockSource` | string | 服務 | 時間換算依據（計分列時鐘或 feed 時間戳） |
| `videoLagSec` / `measuredLagSec` | number | 服務 | 直播畫面落後 feed 的秒數（設定值／實測值） |
| `dragons.B` / `dragons.R` | string[] | feed | 依序拿到的龍屬性：`infernal` `ocean` `mountain` `cloud` `hextech` `chemtech` `elder` |
| `riftElement` | string \| null | feed | 地圖屬性（第三條龍起固定）；第三條龍被拿之前為 null |
| `soul` | `{team, element}` \| null | feed | 龍魂 |
| `elderKills` | `{B, R}` | feed | 遠古龍次數 |
| `barons` / `inhibitors` / `kills` / `gold` | `{B, R}` | feed | 累計（`inhibitors` 為該隊**打掉**的水晶數） |
| `towersDestroyedBy` | `{B, R}` | feed | 該隊**打掉**的塔數（含重生後再打掉的主堡塔） |
| `towersLost.B` / `towersLost.R` | `{site, gameTime, sec}[]` | CV | 該隊**失去**的塔是哪幾座；`site` 見下 |
| `towersLost.nexusTurretsDown` | `{teamLost, site, respawnAt}[]` | CV＋規則 | 已倒的主堡塔與重生時間（3 分鐘） |
| `towersLost.nexusRespawnsSeen` | 陣列 | CV | 畫面確認的主堡塔重生 |
| `timers.nextDragon` | `{kind, element, elementNote, spawnAt, sec}` | 規則 | `kind`=`elemental`/`elder`；`element` 不確定時為 null，原因在 `elementNote` |
| `timers.nextBaron` | `{spawnAt, sec}` | 規則 | |
| `timers.activeBuffs` | `{buff, team, until, untilSec}[]` | 規則 | `buff`=`baron`（180 秒）/`elder`（150 秒） |
| `timers.inhibitorsDown` | `{teamLost, respawnAt}[]` | 規則 | 水晶 5 分鐘重生 |
| `timers.grubsWindow` / `heraldWindow` | string | 規則 | 三蟲 8:00–14:45、預示者 15:00–19:45（被誰拿：尚未支援） |
| `events` | 陣列 | feed | `{type: dragon/baron/inhibitor/tower, team, element?, sec, gameTime}`，`team` 為**取得者** |

`site` 值：`top_outer` `top_inner` `top_inhib_tower` `mid_outer` `mid_inner` `mid_inhib_tower` `bot_outer` `bot_inner` `bot_inhib_tower` `nexus_t1` `nexus_t2`。

## 已知限制（v0）

- 塔的命名平均比畫面晚約 7 秒（需累積 8 秒的消失證據）；被英雄頭像遮住時會更晚。比賽結束時的最後幾座可能是由 feed 數量推算補上。
- 三蟲、預示者由誰取得、紅藍 buff 尚未支援（評估中）。
- 欄位可能在 v1 增加，但 v0 既有欄位的意義不變。
